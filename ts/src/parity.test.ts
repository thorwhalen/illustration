// Parity with the Python side, replayed from schema/ (what `illustration export-schema` wrote).
//
// Everything a provider *codes* — coerce functions, item extraction, normalisation, query
// routing — is ported by hand in src/providers/. These tests are what stop the port from
// drifting: Python computed every expectation below from the same canned payload and the
// same request cases, and the TS side must produce it byte for byte.

import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { CONSTANTS } from './generated/constants';
import { normalizeLicense } from './licensing';
import { getSource, listSources } from './registry';
import { perPageFor } from './source';

const FIXTURES = resolve(__dirname, '../../schema/fixtures');

interface Fixture {
  query: string;
  expected: Record<string, unknown>[];
  requests: { canonical: Record<string, unknown>; native: Record<string, unknown>; dropped: string[] }[];
  query_params: { query: string; page: number; per_page: number; params: Record<string, unknown> }[];
  per_page: { n: number; per_page: number }[];
}

function load(name: string): { payload: Record<string, unknown>; fixture: Fixture } {
  return {
    payload: JSON.parse(readFileSync(resolve(FIXTURES, `${name}.payload.json`), 'utf8')),
    fixture: JSON.parse(readFileSync(resolve(FIXTURES, `${name}.expected.json`), 'utf8')),
  };
}

const exported = readdirSync(FIXTURES)
  .filter((f) => f.endsWith('.expected.json'))
  .map((f) => f.replace(/\.expected\.json$/, ''));

describe('every exported source is registered here, and vice versa', () => {
  it('registry ⇔ fixtures', () => {
    expect(listSources().sort()).toEqual(exported.sort());
  });
});

describe.each(exported)('%s', (name) => {
  const { payload, fixture } = load(name);
  const source = getSource(name);

  it('normalises the canned payload exactly as Python does', () => {
    const results = [];
    for (const item of source.items(payload)) {
      try {
        results.push(source.normalize(item, fixture.query));
      } catch {
        // skipped, as `_safe_normalize` skips
      }
    }
    expect(results).toEqual(fixture.expected);
  });

  it.each(fixture.requests)('translates canonical filters %#', (c) => {
    const { native, dropped } = source.translate(c.canonical);
    expect(native).toEqual(c.native);
    expect(dropped.sort()).toEqual([...c.dropped].sort());
  });

  it.each(fixture.query_params)('builds query params for %s', (c) => {
    expect(source.queryParams(c.query, c.page, c.per_page)).toEqual(c.params);
  });

  it.each(fixture.per_page)('clamps n=$n to per_page=$per_page', (c) => {
    expect(perPageFor(source.record, c.n)).toBe(c.per_page);
  });
});

describe('licence normalisation', () => {
  it.each(CONSTANTS.license_normalization_cases)('folds %o', (c) => {
    expect(normalizeLicense(c.input)).toBe(c.output);
  });

  it('never drops a restriction token', () => {
    for (const token of CONSTANTS.restriction_tokens) {
      expect(normalizeLicense(`cc-by-${token}-4.0`)).toContain(token);
    }
  });
});
