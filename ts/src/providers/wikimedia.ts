/**
 * Wikimedia Commons (no key): 140M+ free media files with deep per-file metadata.
 * Twin of `illustration/providers/wikimedia.py`; pinned by `schema/fixtures/wikimedia.expected.json`.
 *
 * Quirks carried over: `query.pages` (a list under formatversion 2) is sorted by search `index`;
 * pagination is offset-based (`gsroffset`); a `Category:…` query routes to the category-members
 * generator and a `File:…` query to an exact-title lookup (which *drops* `generator`, expressed
 * as a `null` value the request builder removes); the `Artist` field is HTML; non-images in the
 * File namespace are dropped by MIME during normalisation.
 */

import { decodeHTML } from 'entities';

import { type Json, defineSource, makeResult, required } from '../source';

const TAG_RE = /<[^>]+>/g;
const HREF_RE = /href=["']([^"']+)["']/i;
const CATEGORY_PREFIX = 'category:';
const FILE_PREFIX = 'file:';

function isFileTitle(query: string): boolean {
  return query.trim().toLowerCase().startsWith(FILE_PREFIX);
}

function isCategory(query: string): boolean {
  return query.trim().toLowerCase().startsWith(CATEGORY_PREFIX);
}

function categoryTitle(query: string): string {
  return `Category:${query.trim().slice(CATEGORY_PREFIX.length).trim()}`;
}

function fileTitle(query: string): string {
  return `File:${query.trim().slice(FILE_PREFIX.length).trim()}`;
}

function stripHtml(value: string | null | undefined): string | null {
  if (!value) return null;
  const text = decodeHTML(value.replace(TAG_RE, '')).trim();
  return text || null;
}

function firstHref(value: string | null | undefined): string | null {
  if (!value) return null;
  const m = HREF_RE.exec(value);
  if (!m) return null;
  const url = m[1]!;
  return url.startsWith('//') ? `https:${url}` : url;
}

function buildAttribution(author: string | null, licenseShort: string | null): string | null {
  if (author && licenseShort) return `${author} / ${licenseShort}, via Wikimedia Commons`;
  if (author) return `${author}, via Wikimedia Commons`;
  if (licenseShort) return `${licenseShort}, via Wikimedia Commons`;
  return null;
}

export const wikimedia = defineSource('wikimedia', {
  paramMap: {}, // Commons exposes no canonical search-time filters here
  pageParams(page, perPage) {
    return { gsrlimit: perPage, gsroffset: (page - 1) * perPage };
  },
  queryParams(query, page, perPage) {
    if (isFileTitle(query)) {
      return {
        generator: null, // removed by the request builder; this is a direct lookup
        titles: query
          .split('|')
          .filter((part) => part.trim())
          .map(fileTitle)
          .join('|'),
      };
    }
    if (!isCategory(query)) {
      return { gsrsearch: query, ...this.pageParams!(page, perPage) };
    }
    return {
      generator: 'categorymembers',
      gcmtitle: categoryTitle(query),
      gcmtype: 'file',
      gcmlimit: perPage,
    };
  },
  items(response) {
    const pages = ((response.query as Json | undefined)?.pages as Json[] | Record<string, Json> | undefined) ?? [];
    // A list under formatversion 2 (API order, which a pageid-keyed dict would lose at
    // JSON.parse); sort by search `index` for relevance, stable for category members.
    const items = Array.isArray(pages) ? pages : Object.values(pages);
    return items.sort(
      (a, b) => ((a.index as number | undefined) ?? 0) - ((b.index as number | undefined) ?? 0),
    );
  },
  normalize(item, query) {
    const info = ((item.imageinfo as Json[] | undefined) ?? [{}])[0] ?? {};
    if (!String(info.mime ?? '').startsWith('image/')) throw new Error('not an image file');
    const em = (info.extmetadata as Record<string, Json> | undefined) ?? {};
    const emValue = (key: string): string | null => {
      const v = em[key];
      return typeof v === 'object' && v !== null && typeof v.value === 'string' ? v.value : null;
    };
    const artistHtml = emValue('Artist');
    let title = (item.title as string | undefined) ?? '';
    if (title.startsWith('File:')) title = title.slice('File:'.length);
    const licenseShort = emValue('LicenseShortName');
    return makeResult({
      provider: 'wikimedia',
      id: String(required(item, 'pageid')),
      url: String(required(info, 'url')),
      thumbnail_url: (info.thumburl as string | null | undefined) ?? null,
      width: (info.width as number | null | undefined) ?? null,
      height: (info.height as number | null | undefined) ?? null,
      title: title || null,
      description: stripHtml(emValue('ImageDescription')),
      tags: [], // Commons categories are noisy/HTML; omitted at this layer
      license: emValue('License') || licenseShort,
      license_url: emValue('LicenseUrl'),
      attribution: stripHtml(emValue('Attribution')) || buildAttribution(stripHtml(artistHtml), licenseShort),
      source_page_url: (info.descriptionurl as string | null | undefined) ?? null,
      author: stripHtml(artistHtml),
      author_url: firstHref(artistHtml),
      cacheable: true, // free content; preserve attribution (gate per-file licence)
      avg_color: null,
      query,
      raw: { ...item },
    });
  },
});
