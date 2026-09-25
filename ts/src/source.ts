/**
 * A source = its declared record (generated) + its coded hooks (a provider module),
 * and the one search template every source runs through — the TS twin of
 * `illustration.base.RetrievalSource`.
 *
 * `searchSource` is the template method: it enforces the credential check,
 * canonical→native translation, pagination capped by `max_pages`, and per-item
 * normalisation that *skips* a malformed item rather than failing the search.
 * Provider modules supply hooks; they never re-implement the template.
 *
 * Transport is one argument, `fetch` (default `globalThis.fetch`). A server relay
 * is a `fetch` that rewrites the URL; nothing else changes.
 */

import { MissingCredentialError, ProviderError, RateLimitError } from './errors';
import { CONSTANTS } from './generated/constants';
import { type ImageResult, imageResultSchema } from './generated/image-result';
import { SOURCE_RECORDS } from './generated/sources';
import type { SourceRecord } from './source-record';
import { type ParamMap, type ParamTranslator, makeParamTranslator } from './translation';

export type Json = Record<string, unknown>;

/** The coded half of a source. */
export interface SourceHooks {
  /** Canonical→native spec; `coerce` functions live here because they cannot be data. */
  readonly paramMap: ParamMap;
  /** Extract the raw result items from a decoded response. */
  items(response: Json): Iterable<Json>;
  /** Map one raw item to an `ImageResult`. Throw to have the item skipped. */
  normalize(item: Json, query: string): ImageResult;
  /** Every param that depends on the query (the query itself and paging).
   *  Override when the request *shape* changes with the query (Wikimedia). */
  queryParams?(query: string, page: number, perPage: number): Record<string, unknown>;
  /** Native pagination params for a 1-based page. Override for offset models. */
  pageParams?(page: number, perPage: number): Record<string, unknown>;
}

export interface RetrievalSource extends SourceHooks {
  readonly name: string;
  readonly record: SourceRecord;
  readonly translate: ParamTranslator;
  queryParams(query: string, page: number, perPage: number): Record<string, unknown>;
  pageParams(page: number, perPage: number): Record<string, unknown>;
}

/** The generated record for `name`, or throw: a provider module cannot exist
 *  without its Python twin having been exported. */
export function sourceRecord(name: string): SourceRecord {
  const record = SOURCE_RECORDS.find((r) => r.name === name);
  if (!record) {
    throw new Error(
      `No exported record for source ${JSON.stringify(name)}: register it on the Python side and run \`illustration export-schema\`.`,
    );
  }
  return record;
}

/** Bind a provider module's hooks to its generated record. */
export function defineSource(name: string, hooks: SourceHooks): RetrievalSource {
  const record = sourceRecord(name);
  const pageParams =
    hooks.pageParams?.bind(hooks) ??
    ((page: number, perPage: number) => ({
      [record.page_param]: page,
      [record.per_page_param]: perPage,
    }));
  const queryParams =
    hooks.queryParams?.bind(hooks) ??
    ((query: string, page: number, perPage: number) => ({
      [record.query_param]: query,
      ...pageParams(page, perPage),
    }));
  return {
    ...hooks,
    name,
    record,
    translate: makeParamTranslator(hooks.paramMap),
    pageParams,
    queryParams,
  };
}

/** Fill schema defaults and validate: what the Python side's `ImageResult(...)`
 *  constructor does. Undefined fields take their defaults (`null`, `[]`, `{}`). */
export function makeResult(fields: Partial<ImageResult> & Pick<ImageResult, 'provider' | 'id' | 'url'>): ImageResult {
  const defined: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(fields)) if (v !== undefined) defined[k] = v;
  return imageResultSchema.parse(defined);
}

export interface SearchSourceOptions {
  /** Results wanted (default `CONSTANTS.defaults.n`). */
  readonly n?: number;
  /** The caller's key for a keyed provider. */
  readonly apiKey?: string | null;
  /** Provider-native params merged last, overriding translated ones (the escape hatch). */
  readonly nativeParams?: Readonly<Record<string, unknown>> | null;
  /** Canonical filters (`orientation`, `size`, `safe`, …), translated per source. */
  readonly canonical?: Readonly<Record<string, unknown>>;
  /** The transport seam. A relay is a `fetch` that rewrites the URL. */
  readonly fetch?: typeof globalThis.fetch;
  readonly signal?: AbortSignal;
  /** Sent as `Api-User-Agent` (a browser cannot set `User-Agent`; Wikimedia honours this one). */
  readonly userAgent?: string;
}

/** The per-page clamp: at least `min_per_page`, at most `max_per_page`, ideally `n`. */
export function perPageFor(record: SourceRecord, n: number): number {
  return Math.max(record.min_per_page, Math.min(n, record.max_per_page));
}

/** Search one source and return up to `n` normalised results. */
export async function searchSource(
  source: RetrievalSource,
  query: string,
  opts: SearchSourceOptions = {},
): Promise<ImageResult[]> {
  if (!query) throw new Error('query must be a non-empty string');
  const n = opts.n ?? CONSTANTS.defaults.n;
  const { record } = source;
  const apiKey = opts.apiKey ?? null;
  if (record.info.requires_key && !apiKey) {
    throw new MissingCredentialError(source.name, {
      envVar: record.env_var,
      consoleUrl: record.console_url,
    });
  }
  const { native } = source.translate(opts.canonical ?? {});
  Object.assign(native, opts.nativeParams ?? {});

  const results: ImageResult[] = [];
  const perPage = perPageFor(record, n);
  let page = 1;
  while (results.length < n && page <= CONSTANTS.defaults.max_pages) {
    const params = {
      ...record.fixed_params,
      ...native,
      ...source.queryParams(query, page, perPage),
    };
    const response = await get(source, params, { ...opts, apiKey });
    const items = Array.from(source.items(response));
    if (items.length === 0) break;
    for (const item of items) {
      const normalized = safeNormalize(source, item, query);
      if (normalized !== null) {
        results.push(normalized);
        if (results.length >= n) break;
      }
    }
    if (items.length < perPage) break; // last page
    page += 1;
  }
  return results.slice(0, n);
}

function safeNormalize(source: RetrievalSource, item: Json, query: string): ImageResult | null {
  try {
    return source.normalize(item, query);
  } catch {
    return null; // one bad item must not sink the whole search
  }
}

/** Build the request URL: fixed + translated + query params, then the auth
 *  query param, with `null`/`undefined` values *removed* (a provider suppresses
 *  one of its own fixed params that way, as Wikimedia drops `generator`). */
export function requestUrl(
  source: RetrievalSource,
  params: Readonly<Record<string, unknown>>,
  apiKey: string | null,
): URL {
  const url = new URL(source.record.endpoint);
  const merged: Record<string, unknown> = { ...params };
  const { auth } = source.record;
  if (auth.kind === 'query' && apiKey && auth.name) {
    merged[auth.name] = (auth.format ?? '{key}').replace('{key}', apiKey);
  }
  for (const [key, value] of Object.entries(merged)) {
    if (value === null || value === undefined) continue;
    url.searchParams.set(key, String(value));
  }
  return url;
}

export function requestHeaders(source: RetrievalSource, apiKey: string | null, userAgent?: string): Headers {
  const headers = new Headers({ Accept: 'application/json' });
  if (userAgent) headers.set('Api-User-Agent', userAgent);
  const { auth } = source.record;
  if (auth.kind === 'header' && apiKey && auth.name) {
    headers.set(auth.name, (auth.format ?? '{key}').replace('{key}', apiKey));
  }
  return headers;
}

async function get(
  source: RetrievalSource,
  params: Readonly<Record<string, unknown>>,
  opts: SearchSourceOptions & { apiKey: string | null },
): Promise<Json> {
  const doFetch = opts.fetch ?? globalThis.fetch;
  let response: Response;
  try {
    response = await doFetch(requestUrl(source, params, opts.apiKey), {
      method: 'GET',
      headers: requestHeaders(source, opts.apiKey, opts.userAgent),
      signal: opts.signal,
    });
  } catch (e) {
    throw new ProviderError(source.name, `request failed: ${(e as Error).message ?? e}`);
  }
  const { status } = response;
  if (status === 429) throw new RateLimitError(source.name, 'rate limit exceeded', 429);
  if (status === 401 || status === 403) {
    throw new ProviderError(source.name, 'authentication failed (check API key)', status);
  }
  if (status >= 400) throw new ProviderError(source.name, await shortBody(response), status);
  return (await response.json()) as Json;
}

async function shortBody(response: Response): Promise<string> {
  try {
    const text = (await response.text()).trim();
    return text.length > 200 ? `${text.slice(0, 200)}…` : text || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}
