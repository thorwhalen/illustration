/**
 * The declared half of a source, as exported by `illustration export-schema`.
 *
 * Everything a Python `RetrievalSource` subclass *declares* (endpoint, parameter
 * names, paging caps, fixed params, auth style, canonical→native parameter names,
 * `SourceInfo`) arrives here as data (`src/generated/sources.ts`). What it *codes*
 * (`coerce` functions, `_items`, `_normalize`, a `_query_params` override) is
 * ported by hand in `src/providers/` and pinned by the parity fixtures.
 */

export interface SourceInfo {
  readonly name: string;
  readonly description: string;
  readonly requires_key: boolean;
  readonly homepage: string | null;
  readonly default_cacheable: boolean;
  readonly license_note: string;
  readonly rate_limit: string;
  readonly tags: readonly string[];
}

/** How the key travels: a header (`Authorization: <key>`), a query param (`key=`), or not at all. */
export interface AuthRecord {
  readonly kind: 'none' | 'header' | 'query';
  readonly name: string | null;
  /** Template with `{key}` where the raw key goes. */
  readonly format: string | null;
}

/** A canonical parameter's native name and guard; `coerce: true` means the Python
 *  side transforms the value and the provider module must do the same. */
export interface ParamRecord {
  readonly name: string | null;
  readonly choices: readonly string[] | null;
  readonly coerce: boolean;
}

export interface SourceRecord {
  readonly name: string;
  readonly endpoint: string;
  readonly query_param: string;
  readonly page_param: string;
  readonly per_page_param: string;
  readonly max_per_page: number;
  readonly min_per_page: number;
  readonly fixed_params: Readonly<Record<string, unknown>>;
  readonly auth: AuthRecord;
  /** Keyed by canonical parameter name; `null` = explicitly unsupported (degrades). */
  readonly params: Readonly<Record<string, ParamRecord | null>>;
  readonly info: SourceInfo;
  readonly env_var: string | null;
  readonly console_url: string | null;
}
