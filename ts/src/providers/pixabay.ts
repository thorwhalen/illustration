/**
 * Pixabay (key required, as the `key=` query param): free commercial-use images whose licence
 * permits caching and self-hosting. Twin of `illustration/providers/pixabay.py`; pinned by
 * `schema/fixtures/pixabay.expected.json`.
 */

import { type Json, defineSource, makeResult, required } from '../source';

const PIXABAY_LICENSE = 'Pixabay License';
const PIXABAY_LICENSE_URL = 'https://pixabay.com/service/license-summary/';
// canonical orientation → Pixabay's vocabulary (no 'square' → 'all')
const ORIENTATION: Readonly<Record<string, string>> = {
  landscape: 'horizontal',
  portrait: 'vertical',
  square: 'all',
};
// canonical size → Pixabay min_width (no size tier; approximate with a width floor)
const SIZE_MIN_WIDTH: Readonly<Record<string, number>> = { large: 1920, medium: 1280, small: 640 };

export const pixabay = defineSource('pixabay', {
  paramMap: {
    orientation: {
      name: 'orientation',
      choices: ['landscape', 'portrait', 'square'],
      coerce: (o) => ORIENTATION[String(o)],
    },
    size: {
      name: 'min_width',
      choices: ['large', 'medium', 'small'],
      coerce: (s) => SIZE_MIN_WIDTH[String(s)],
    },
    safe: { name: 'safesearch', coerce: (safe) => (safe ? 'true' : 'false') },
    license_type: null, // single Pixabay License
    color: 'colors',
    content_type: { name: 'image_type', choices: ['photo', 'illustration', 'vector'] },
  },
  items(response) {
    return (response.hits as Json[] | undefined) ?? [];
  },
  normalize(item, query) {
    const user = (item.user as string | null | undefined) ?? null;
    const tags = String(item.tags ?? '')
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);
    // `||`, not `??`: Python's `a or b` falls through an EMPTY string too.
    const url = ((item.largeImageURL || item.webformatURL || item.imageURL) as string | undefined) || null;
    if (!url) throw new Error('item has no image url');
    return makeResult({
      provider: 'pixabay',
      id: String(required(item, 'id')),
      url,
      thumbnail_url: (item.previewURL as string | null | undefined) ?? null,
      width: (item.imageWidth as number | null | undefined) ?? null,
      height: (item.imageHeight as number | null | undefined) ?? null,
      title: null,
      description: null,
      tags,
      license: PIXABAY_LICENSE,
      license_url: PIXABAY_LICENSE_URL,
      attribution: user ? `Image by ${user} on Pixabay` : 'Image from Pixabay',
      source_page_url: (item.pageURL as string | null | undefined) ?? null,
      author: user,
      author_url: null,
      cacheable: true, // licence permits caching / self-hosting
      avg_color: null,
      query,
      raw: { ...item },
    });
  },
});
