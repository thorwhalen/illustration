/**
 * Openverse (anonymous tier, no key): 800M+ CC / public-domain images.
 * Twin of `illustration/providers/openverse.py`; pinned by `schema/fixtures/openverse.expected.json`.
 */

import { type Json, defineSource, makeResult } from '../source';

const ORIENTATION_TO_ASPECT: Readonly<Record<string, string>> = {
  landscape: 'wide',
  portrait: 'tall',
  square: 'square',
};

const CONTENT_TYPE_TO_CATEGORY: Readonly<Record<string, string>> = {
  photo: 'photograph',
  illustration: 'illustration',
};

export const openverse = defineSource('openverse', {
  paramMap: {
    orientation: {
      name: 'aspect_ratio',
      coerce: (o) => ORIENTATION_TO_ASPECT[String(o)] ?? o,
    },
    size: { name: 'size', choices: ['large', 'medium', 'small'] },
    safe: { name: 'mature', coerce: (safe) => !safe },
    license_type: 'license_type',
    // content_type: Openverse `category` has no 'vector' → only photo/illustration
    content_type: {
      name: 'category',
      choices: ['photo', 'illustration'],
      coerce: (ct) => CONTENT_TYPE_TO_CATEGORY[String(ct)],
    },
    color: null, // Openverse has no color filter (explicitly unsupported)
  },
  items(response) {
    return (response.results as Json[] | undefined) ?? [];
  },
  normalize(item, query) {
    const tags = ((item.tags as unknown[] | undefined) ?? [])
      .filter((t): t is Json => typeof t === 'object' && t !== null && !!(t as Json).name)
      .map((t) => String(t.name));
    if (item.url === undefined || item.url === null) throw new Error('item has no url');
    const title = (item.title as string | null | undefined) ?? null;
    return makeResult({
      provider: 'openverse',
      id: String(item.id),
      url: String(item.url),
      thumbnail_url: (item.thumbnail as string | null | undefined) ?? null,
      width: (item.width as number | null | undefined) ?? null,
      height: (item.height as number | null | undefined) ?? null,
      title,
      description: title, // Openverse exposes no separate description
      tags,
      license: (item.license as string | null | undefined) ?? null,
      license_url: (item.license_url as string | null | undefined) ?? null,
      attribution: (item.attribution as string | null | undefined) ?? null,
      source_page_url: (item.foreign_landing_url as string | null | undefined) ?? null,
      author: (item.creator as string | null | undefined) ?? null,
      author_url: (item.creator_url as string | null | undefined) ?? null,
      cacheable: true, // CC / public-domain media is cacheable (preserve attribution)
      avg_color: null,
      query,
      raw: { ...item },
    });
  },
});
