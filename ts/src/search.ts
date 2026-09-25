/**
 * The front door: `search(query, options)`, the TS twin of `illustration.search`.
 *
 * Layer 1 only. Rerank, dedupe and curation (illustration's Layer 2) are model
 * and numpy territory and stay on the Python side; caching is the application's
 * (a browser has no content-addressed store, the server relay's side does).
 *
 * `media` is accepted now so the signature has room for video (illustration#33);
 * `"video"` raises until video sources are registered on the Python side and
 * exported.
 */

import { IllustrationError } from './errors';
import { CONSTANTS } from './generated/constants';
import type { ImageResult } from './generated/image-result';
import { licenseAllowlist } from './licensing';
import { defaultSources, getSource } from './registry';
import { searchSource } from './source';

export type MediaType = 'image' | 'video';

export interface SearchOptions {
  /** Results wanted **per source** (default `CONSTANTS.defaults.n`). */
  readonly n?: number;
  /** A source name, a list of names, or omitted for the default set. */
  readonly source?: string | readonly string[];
  readonly orientation?: 'landscape' | 'portrait' | 'square' | (string & {});
  readonly size?: 'large' | 'medium' | 'small' | (string & {});
  /** Exclude mature content where the provider supports it (default `true`). */
  readonly safe?: boolean;
  /** `commercial` | `all-cc` | `modification` | `all` (providers with licence filtering). */
  readonly licenseType?: string;
  /** A named colour or `#hex` (Pexels, Pixabay). */
  readonly color?: string;
  /** `photo` | `illustration` | `vector` (providers map or skip what they lack). */
  readonly contentType?: 'photo' | 'illustration' | 'vector' | (string & {});
  /** The licence gate: `false` (default) = none; `true` = the default commercial-safe
   *  allowlist; an iterable of codes = keep only those. Aggregators disclaim licence
   *  accuracy, so gate when commercial use matters. */
  readonly licenseAllow?: boolean | Iterable<string>;
  /** Per-source native params, e.g. `{ pexels: { color: 'blue' } }` (the escape hatch). */
  readonly providerParams?: Readonly<Record<string, Readonly<Record<string, unknown>>>>;
  /** The caller's keys by provider name. The facade never reads storage. */
  readonly credentials?: Readonly<Record<string, string | null | undefined>>;
  /** `"image"` (default). `"video"` is reserved for illustration#33. */
  readonly media?: MediaType;
  /** The transport seam (default `globalThis.fetch`). */
  readonly fetch?: typeof globalThis.fetch;
  readonly signal?: AbortSignal;
  /** Sent as `Api-User-Agent`; Wikimedia etiquette asks for a descriptive one. */
  readonly userAgent?: string;
}

/** Search for up to `n` images per source. Per-source lists are concatenated in
 *  source order (up to `n × sources`); the licence gate is applied over the whole. */
export async function search(query: string, opts: SearchOptions = {}): Promise<ImageResult[]> {
  if (!query || typeof query !== 'string') throw new Error('query must be a non-empty string');
  const n = opts.n ?? CONSTANTS.defaults.n;
  if (!(n > 0)) throw new Error(`n must be a positive integer, got ${n}`);
  const media = opts.media ?? 'image';
  if (media !== 'image') {
    throw new IllustrationError(
      `no ${media} sources are registered yet (illustration#33); only media: "image" is available`,
    );
  }
  const names = resolveSourceNames(opts.source);
  const canonical = {
    orientation: opts.orientation ?? null,
    size: opts.size ?? null,
    safe: opts.safe ?? true,
    license_type: opts.licenseType ?? null,
    color: opts.color ?? null,
    content_type: opts.contentType ?? null,
  };
  const perSource = await Promise.all(
    names.map((name) =>
      searchSource(getSource(name), query, {
        n,
        canonical,
        apiKey: opts.credentials?.[name] ?? null,
        nativeParams: opts.providerParams?.[name] ?? null,
        fetch: opts.fetch,
        signal: opts.signal,
        userAgent: opts.userAgent,
      }),
    ),
  );
  let results = perSource.flat();
  if (opts.licenseAllow) {
    results = licenseAllowlist(results, {
      allow: opts.licenseAllow === true ? null : opts.licenseAllow,
    });
  }
  return results;
}

function resolveSourceNames(source: SearchOptions['source']): string[] {
  if (source === undefined || source === null) return defaultSources();
  if (typeof source === 'string') return [source];
  const names = [...source];
  if (names.length === 0) throw new Error('source list is empty; pass at least one source name');
  return names;
}
