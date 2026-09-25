# illustration-search

Text-to-image retrieval over open-media corpora, **in the browser**. The TypeScript twin of the Python [`illustration`](https://github.com/thorwhalen/illustration) package: one `search()` over Openverse, Wikimedia Commons, Pexels and Pixabay, every hit normalised into one schema with licence and attribution first-class.

```bash
npm install illustration-search
```

```ts
import { search } from 'illustration-search';

// Openverse and Wikimedia need no key.
const hits = await search('stormy harbour at dusk', { n: 5 });

// Pexels and Pixabay take the caller's own key. The facade never reads storage.
const stock = await search('harbour', {
  source: ['pexels', 'pixabay'],
  credentials: { pexels: PEXELS_KEY, pixabay: PIXABAY_KEY },
  orientation: 'landscape',
  licenseAllow: true, // keep only commercial-safe licences
});

for (const h of hits) console.log(h.url, h.license, h.attribution, h.cacheable);
```

All four providers answer browser requests directly (CORS `*`, verified 2026-09-25). The transport is one option, `fetch`, so a server relay is a `fetch` that rewrites the URL.

## What a hit carries

An `ImageResult`, generated from the Python schema: `provider`, `id`, `url`, `thumbnail_url`, `width`, `height`, `title`, `description`, `tags`, the seven **rights fields** (`license`, `license_url`, `attribution`, `source_page_url`, `author`, `author_url`, `cacheable`, exported as `RIGHTS_FIELDS`), `avg_color`, `query`, `score`, and `raw` (the untranslated provider payload).

Aggregators disclaim licence accuracy, so the gate is yours: `licenseAllow: true` (the default commercial-safe set) or a list of codes. Both sides are normalised through the same alias table as Python (`normalizeLicense`), and unknown is never allowed.

## What this package deliberately does not do

- **Store bytes.** URLs from providers are ephemeral or hotlink-restricted (Pixabay). Ingest a chosen picture into your own store, with its rights record; `cacheable` says whether you may.
- **Rerank, dedupe, curate.** That is `illustration`'s Layer 2 (SigLIP, DINOv2, a VLM judge) and stays on the Python side.
- **Video, yet.** `search(q, { media: 'video' })` is accepted and raises until video sources land ([illustration#33](https://github.com/thorwhalen/illustration/issues/33)).

## How it stays in step with Python

`schema/` at the repo root is written by `illustration export-schema`: the JSON Schema, the source registry, the licence tables and **parity fixtures** (what Python makes of each provider's canned payload, and of each filter combination). `npm run codegen` generates `src/generated/` from it, and `npm test` replays every fixture through the hand-ported provider code. A change on either side that forgets the other fails CI.

Adding a provider: register it on the Python side, run `illustration export-schema`, write its hooks under `src/providers/`, and `registerSource` it.
