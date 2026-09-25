/**
 * Licence normalisation and the allowlist gate, mirroring `illustration.licensing`
 * and `illustration.schema.license_allowlist`.
 *
 * The alias table is generated data, not re-typed here. The transform is the
 * same three steps in the same order as Python, because the order is what makes
 * `cc-0` reachable (the version strip would otherwise eat its `-0`), and the
 * invariant is the same: **a restriction token is never dropped**. The Python
 * side's `license_normalization_cases` are replayed in `parity.test.ts`.
 */

import { CONSTANTS } from './generated/constants';
import type { ImageResult } from './generated/image-result';

const ALIASES: Readonly<Record<string, string>> = CONSTANTS.license_aliases;

/** The default commercial-safe allowlist (`DFLT_LICENSE_ALLOWLIST` on the Python side). */
export const DEFAULT_LICENSE_ALLOWLIST: readonly string[] = CONSTANTS.default_license_allowlist;

// A trailing version, e.g. the "-4.0" of "cc-by-sa-4.0"; the leading separator is
// required so a code that merely ends in a digit (`cc0`) is left alone.
const VERSION_SUFFIX = /[-_ ]v?\d+(?:\.\d+)*$/;
const CC_PREFIX = /^cc[-_ ]/;
const SEPARATORS = /[\s_]+/g;

/** Fold a provider's licence spelling onto one canonical, comparable code.
 *  `null` for null/blank: an absent licence is never a code. */
export function normalizeLicense(value: string | null | undefined): string | null {
  if (!value || !value.trim()) return null;
  let code = value.trim().toLowerCase().replace(SEPARATORS, '-');
  if (Object.hasOwn(ALIASES, code)) return ALIASES[code]!;
  code = code.replace(VERSION_SUFFIX, '');
  if (Object.hasOwn(ALIASES, code)) return ALIASES[code]!;
  code = code.replace(CC_PREFIX, '');
  return (Object.hasOwn(ALIASES, code) ? ALIASES[code]! : code) || null;
}

/** Keep only results whose licence is on the allowlist; unknown is not allowed.
 *  Both sides are normalised, so provider dialects match without enumeration. */
export function licenseAllowlist<T extends Pick<ImageResult, 'license'>>(
  results: Iterable<T>,
  opts: { allow?: Iterable<string> | null } = {},
): T[] {
  const allowed = new Set<string>();
  for (const code of opts.allow ?? DEFAULT_LICENSE_ALLOWLIST) {
    const normalized = normalizeLicense(code);
    if (normalized !== null) allowed.add(normalized);
  }
  const kept: T[] = [];
  for (const result of results) {
    const code = normalizeLicense(result.license);
    if (code !== null && allowed.has(code)) kept.push(result);
  }
  return kept;
}
