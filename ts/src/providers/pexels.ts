/**
 * Pexels (key required, raw value in `Authorization`): curated stock photos under the Pexels License.
 * Twin of `illustration/providers/pexels.py`; pinned by `schema/fixtures/pexels.expected.json`.
 */

import { type Json, defineSource, makeResult } from '../source';

const PEXELS_LICENSE = 'Pexels License';
const PEXELS_LICENSE_URL = 'https://www.pexels.com/license/';

export const pexels = defineSource('pexels', {
  paramMap: {
    orientation: { name: 'orientation', choices: ['landscape', 'portrait', 'square'] },
    size: { name: 'size', choices: ['large', 'medium', 'small'] },
    // `safe` is a no-op (curated corpus); `license_type` has no equivalent (single licence).
    safe: null,
    license_type: null,
    color: 'color', // a named or #hex colour
    content_type: null, // photos only
  },
  items(response) {
    return (response.photos as Json[] | undefined) ?? [];
  },
  normalize(item, query) {
    const src = (item.src as Json | undefined) ?? {};
    const photographer = (item.photographer as string | null | undefined) ?? null;
    const url = (src.original ?? src.large2x ?? src.large) as string | undefined;
    if (!url) throw new Error('item has no image url');
    return makeResult({
      provider: 'pexels',
      id: String(item.id),
      url,
      thumbnail_url: ((src.tiny ?? src.medium) as string | undefined) ?? null,
      width: (item.width as number | null | undefined) ?? null,
      height: (item.height as number | null | undefined) ?? null,
      title: null,
      description: (item.alt as string | undefined) || null,
      tags: [], // Pexels returns no tags
      license: PEXELS_LICENSE,
      license_url: PEXELS_LICENSE_URL,
      attribution: photographer ? `Photo by ${photographer} on Pexels` : 'Photo from Pexels',
      source_page_url: (item.url as string | null | undefined) ?? null, // the Pexels web page
      author: photographer,
      author_url: (item.photographer_url as string | null | undefined) ?? null,
      cacheable: true, // Pexels License permits caching for display
      avg_color: (item.avg_color as string | null | undefined) ?? null,
      query,
      raw: { ...item },
    });
  },
});
