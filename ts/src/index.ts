/**
 * illustration-search — text-to-image retrieval over open-media corpora, in the browser.
 *
 * The TypeScript twin of the Python `illustration` package. The result schema,
 * rights fields, licence tables and provider registry are generated from the
 * Python side (`schema/` at the repo root); the provider code is ported by hand
 * and pinned to it by fixtures.
 *
 * ```ts
 * import { search } from 'illustration-search';
 * const hits = await search('stormy harbour at dusk', { n: 5 });           // Openverse, no key
 * const stock = await search('harbour', { source: ['pexels', 'pixabay'],  // the caller's own keys
 *                                         credentials: { pexels, pixabay } });
 * ```
 *
 * Every hit carries `license`, `license_url`, `attribution`, `source_page_url`,
 * `author`, `author_url` and `cacheable` (`RIGHTS_FIELDS`). Whether a hit may be
 * used, and whom to credit, is answered from those; the facade never stores bytes.
 */

export { search, type SearchOptions, type MediaType } from './search';
export { searchSource, defineSource, makeResult, sourceRecord, perPageFor } from './source';
export type { RetrievalSource, SourceHooks, SearchSourceOptions, Json } from './source';
export { registerSource, getSource, listSources, defaultSources } from './registry';
export { normalizeLicense, licenseAllowlist, DEFAULT_LICENSE_ALLOWLIST } from './licensing';
export { makeParamTranslator } from './translation';
export type { ParamMap, ParamSpec, ParamTranslator, Translation } from './translation';
export {
  IllustrationError,
  UnknownSourceError,
  MissingCredentialError,
  ProviderError,
  RateLimitError,
} from './errors';
export { imageResultSchema, type ImageResult, type ImageResultInput } from './generated/image-result';
export { SOURCE_RECORDS } from './generated/sources';
export { CONSTANTS } from './generated/constants';
export type { SourceRecord, SourceInfo, AuthRecord, ParamRecord } from './source-record';
export { openverse } from './providers/openverse';
export { wikimedia } from './providers/wikimedia';
export { pexels } from './providers/pexels';
export { pixabay } from './providers/pixabay';

import { CONSTANTS } from './generated/constants';

/** The seven fields that answer "may we ship this, and whom must we credit?". */
export const RIGHTS_FIELDS = CONSTANTS.rights_fields;
export type RightsField = (typeof RIGHTS_FIELDS)[number];
