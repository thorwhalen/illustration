// The façade and the search template against a fake fetch: no test ever hits the network.

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { MissingCredentialError, ProviderError, RateLimitError } from './errors';
import { RIGHTS_FIELDS, licenseAllowlist, search } from './index';
import { getSource } from './registry';
import { requestHeaders, requestUrl } from './source';

const FIXTURES = resolve(__dirname, '../../schema/fixtures');
const payload = (name: string) =>
  JSON.parse(readFileSync(resolve(FIXTURES, `${name}.payload.json`), 'utf8')) as Record<string, unknown>;

/** A fetch that answers every request with `body` and records what it was asked. */
function fakeFetch(body: unknown, status = 200) {
  const calls: { url: URL; headers: Headers }[] = [];
  const fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: new URL(String(input)), headers: new Headers(init?.headers) });
    return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
  }) as typeof globalThis.fetch;
  return { fetch, calls };
}

describe('search', () => {
  it('defaults to openverse, no key, and returns full ImageResults', async () => {
    const { fetch, calls } = fakeFetch(payload('openverse'));
    const hits = await search('stormy harbour', { fetch });
    expect(hits).toHaveLength(2);
    expect(hits[0]!.provider).toBe('openverse');
    for (const field of RIGHTS_FIELDS) expect(hits[0]).toHaveProperty(field);
    expect(calls[0]!.url.origin + calls[0]!.url.pathname).toBe('https://api.openverse.org/v1/images/');
    expect(calls[0]!.url.searchParams.get('q')).toBe('stormy harbour');
    expect(calls[0]!.url.searchParams.get('mature')).toBe('false'); // safe=true by default
  });

  it('slices to n and stops paging on a short page', async () => {
    const { fetch, calls } = fakeFetch(payload('openverse'));
    const hits = await search('harbour', { n: 1, fetch });
    expect(hits).toHaveLength(1);
    expect(calls).toHaveLength(1);
  });

  it('fans out to several sources in order and concatenates', async () => {
    const bodies: Record<string, unknown> = {
      'api.openverse.org': payload('openverse'),
      'commons.wikimedia.org': payload('wikimedia'),
    };
    const fetch = (async (input: RequestInfo | URL) =>
      new Response(JSON.stringify(bodies[new URL(String(input)).hostname]))) as typeof globalThis.fetch;
    const hits = await search('harbour', { source: ['openverse', 'wikimedia'], fetch });
    expect(hits.map((h) => h.provider)).toEqual(['openverse', 'openverse', 'wikimedia']);
  });

  it('refuses a keyed provider without a key, naming where to get one', async () => {
    await expect(search('x', { source: 'pexels', fetch: fakeFetch({}).fetch })).rejects.toThrow(MissingCredentialError);
    await expect(search('x', { source: 'pexels', fetch: fakeFetch({}).fetch })).rejects.toThrow(/pexels\.com\/api/);
  });

  it('sends the key the way each provider wants it, and never in the message', async () => {
    const pexels = fakeFetch(payload('pexels'));
    await search('x', { source: 'pexels', credentials: { pexels: 'SECRET-P' }, fetch: pexels.fetch });
    expect(pexels.calls[0]!.headers.get('authorization')).toBe('SECRET-P');
    expect(pexels.calls[0]!.url.searchParams.has('key')).toBe(false);

    const pixabay = fakeFetch(payload('pixabay'));
    await search('x', { source: 'pixabay', credentials: { pixabay: 'SECRET-X' }, fetch: pixabay.fetch });
    expect(pixabay.calls[0]!.url.searchParams.get('key')).toBe('SECRET-X');
    expect(pixabay.calls[0]!.headers.has('authorization')).toBe(false);
  });

  it('applies the licence gate over the assembled results', async () => {
    const { fetch } = fakeFetch(payload('openverse'));
    const gated = await search('harbour', { fetch, licenseAllow: ['cc0'] });
    expect(gated.map((h) => h.license)).toEqual(['cc0']);
    const all = await search('harbour', { fetch, licenseAllow: true });
    expect(all).toHaveLength(2); // by-sa and cc0 are both on the default allowlist
  });

  it('translates HTTP failures into typed provider errors', async () => {
    await expect(search('x', { fetch: fakeFetch({}, 429).fetch })).rejects.toThrow(RateLimitError);
    await expect(search('x', { fetch: fakeFetch({}, 500).fetch })).rejects.toThrow(ProviderError);
  });

  it('reserves media: "video" without pretending to serve it', async () => {
    await expect(search('x', { media: 'video', fetch: fakeFetch({}).fetch })).rejects.toThrow(/video/);
  });
});

describe('request building', () => {
  it('removes null-valued params (how Wikimedia drops `generator` for exact titles)', () => {
    const source = getSource('wikimedia');
    const url = requestUrl(source, { ...source.record.fixed_params, ...source.queryParams('File:A.jpg', 1, 10) }, null);
    expect(url.searchParams.has('generator')).toBe(false);
    expect(url.searchParams.get('titles')).toBe('File:A.jpg');
  });

  it('sends Api-User-Agent rather than a header browsers forbid', () => {
    const headers = requestHeaders(getSource('wikimedia'), null, 'my-app/1.0 (me@example.org)');
    expect(headers.get('api-user-agent')).toBe('my-app/1.0 (me@example.org)');
    expect(headers.has('user-agent')).toBe(false);
  });
});

describe('licenseAllowlist', () => {
  it('normalises both sides and treats unknown as not allowed', () => {
    const rows = [{ license: 'CC BY-SA 4.0' }, { license: 'Pixabay License' }, { license: 'cc-by-nd-4.0' }, { license: null }];
    expect(licenseAllowlist(rows).map((r) => r.license)).toEqual(['CC BY-SA 4.0', 'Pixabay License']);
  });
});

describe('review-driven parity edges', () => {
  it('falls through an EMPTY string url like Python `or`, and skips an item with no id', async () => {
    const body = {
      photos: [
        { id: 1, src: { original: '', large2x: 'https://x/l2x.jpg', tiny: '' , medium: 'https://x/m.jpg' }, photographer: 'A' },
        { src: { original: 'https://x/o.jpg' } }, // no id → skipped, never id "undefined"
      ],
    };
    const hits = await search('x', { source: 'pexels', credentials: { pexels: 'k' }, fetch: fakeFetch(body).fetch });
    expect(hits.map((h) => [h.id, h.url, h.thumbnail_url])).toEqual([['1', 'https://x/l2x.jpg', 'https://x/m.jpg']]);
  });

  it('an empty allowlist is no gate (Python truthiness)', async () => {
    const { fetch } = fakeFetch(payload('openverse'));
    expect(await search('x', { fetch, licenseAllow: [] })).toHaveLength(2);
    expect(await search('x', { fetch, licenseAllow: new Set() })).toHaveLength(2);
  });

  it("auth: 'transport' skips the key check and attaches nothing, so a relay can add it", async () => {
    const { fetch, calls } = fakeFetch(payload('pexels'));
    const hits = await search('x', { source: 'pexels', auth: 'transport', fetch });
    expect(hits).toHaveLength(1);
    expect(calls[0]!.headers.has('authorization')).toBe(false);
  });

  it('translates a non-JSON or non-object body into a ProviderError', async () => {
    const text = (async () => new Response('not json', { status: 200 })) as typeof globalThis.fetch;
    await expect(search('x', { fetch: text })).rejects.toThrow(/not valid JSON/);
    const array = (async () => new Response('[]', { status: 200 })) as typeof globalThis.fetch;
    await expect(search('x', { fetch: array })).rejects.toThrow(/unexpected response type/);
  });

  it('decodes the HTML entities MediaWiki puts in Artist, like html.unescape', async () => {
    const body = JSON.parse(JSON.stringify(payload('wikimedia'))) as { query: { pages: Record<string, unknown>[] } };
    const page = body.query.pages[0] as { imageinfo: { extmetadata: Record<string, { value: string }> }[] };
    page.imageinfo[0]!.extmetadata.Artist = { value: 'Andr&eacute; Kert&eacute;sz &ndash; &copy; &amp; co &#150; x &amp' };
    const [hit] = await search('x', { source: 'wikimedia', fetch: fakeFetch(body).fetch });
    expect(hit!.author).toBe('André Kertész – © & co – x &');
  });

  it('keeps Wikimedia category members in API order (formatversion 2 list)', async () => {
    const mk = (pageid: number) => ({
      pageid,
      title: `File:${pageid}.jpg`,
      imageinfo: [{ mime: 'image/jpeg', url: `https://u/${pageid}.jpg`, extmetadata: {} }],
    });
    const body = { query: { pages: [mk(200), mk(100), mk(150)] } };
    const hits = await search('Category:X', { source: 'wikimedia', fetch: fakeFetch(body).fetch });
    expect(hits.map((h) => h.id)).toEqual(['200', '100', '150']);
  });

  it('never reaches the network by default (the vitest guard)', async () => {
    await expect(search('x')).rejects.toThrow(/offline test/);
  });
});
