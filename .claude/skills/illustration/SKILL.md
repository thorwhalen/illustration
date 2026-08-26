---
name: illustration
description: Use when you need to FIND AN EXISTING image — stock, Creative-Commons, or public-domain — to illustrate a narration beat, storyboard panel, script line, scene description, or slide. Retrieval, NOT generation. Triggers on "find a photo/image for this beat", "illustrate this narration", "get b-roll stills for a voiceover", "search stock images", "find a public-domain / CC image of X", "pick one image per beat for a storyboard", "openverse / wikimedia commons / pexels / pixabay search", and any use of illustration.search / rerank / curate / curate_sequence / license_allowlist / to_walkthru_document. Use INSTEAD of generating an image whenever a real photograph or existing artwork is wanted, and BEFORE hand-rolling an HTTP client against a stock-photo API. ALSO read it before shipping any retrieved image into a video, page, or deck — it carries the licence and attribution obligations that come with third-party media.
---

# illustration — find existing images for narration beats

`illustration` retrieves images that already exist; it never generates one.
Give it text, get back normalized, **licence-carrying** hits.

```bash
pip install illustration                      # base: no API key needed
pip install 'illustration[rerank]'            # + SigLIP-2 cross-modal rerank
pip install 'illustration[curate]'            # + the agentic per-beat loop (aix + ir)
pip install 'illustration[video,persist]'     # + burns/walkthru render, lacing persist
```

Everything public is imported from the top level:
`from illustration import search, rerank, curate, curate_sequence, license_allowlist, ImageResult, using_credentials`.

## Licence & attribution — read this before you ship anything

You are handling **third-party media under varying licences**. Dropping the
credit is a real legal problem, not a style nit. The package gives you
everything you need on every hit; using it is your job.

Every `ImageResult` carries: `license`, `license_url`, `attribution` (a
ready-to-render sentence), `source_page_url`, `author`, `author_url`, and
`cacheable`. That set is `illustration.RIGHTS_FIELDS` — use it when you need to
copy the rights record onto your own model, and keep the field names, so nobody
downstream needs a rename table. `persist_sequence` stores all seven on the
lacing annotation, so a selection read back later can still be attributed.

**The obligations, per source:**

| source | licence | you must |
|---|---|---|
| **openverse** | per-result CC / public-domain (`by`, `by-sa`, `cc0`, `by-nc`, `by-nd`, …) | render `attribution` for the whole BY family; check for `nc`/`nd` before commercial or edited use; `by-sa` imposes share-alike on derivatives |
| **wikimedia** | per-file, varies (`cc-by-sa-4.0`, `pd`, …) | render `attribution` (author + licence + "via Wikimedia Commons"); send a descriptive User-Agent (the package does); verify per file |
| **pexels** | single Pexels License, commercial OK | credit the photographer ("Photo by X on Pexels") **and** link prominently back to Pexels |
| **pixabay** | single Pixabay Content License, commercial OK | show where the image came from; **no permanent hotlinking** — download to your own server first |

Non-negotiables:

1. **Carry `attribution` and `source_page_url` through your whole pipeline.**
   If your beat/panel data model has no field for them, add one before you add
   this retrieval step. Attribution that is dropped at step 1 cannot be
   recovered at step 9.
2. **`cacheable` is per-result** (all four built-ins currently set it `True`).
   Honour it before persisting bytes anywhere.
3. **The licence gate is OPT-IN and OFF by default.** `search()` returns
   whatever the provider returned, `by-nc-nd` included. If commercial use
   matters, gate explicitly — and read the gotcha below about how matching
   actually works.
4. **Aggregators disclaim licence accuracy.** For anything commercially
   sensitive, treat `license` as a hint and verify on `source_page_url`.

```python
from illustration import search, license_allowlist

hits = search("a stormy harbour at dusk", n=20)
safe = license_allowlist(hits, allow={"cc0", "pdm"})  # public-domain only
# or inline, same gate:
safe = search("a stormy harbour at dusk", n=20, license_allow={"cc0", "pdm"})
```

## `search(query, *, n=10, source=None, ...)` — the front door

First argument is the query; **everything else is keyword-only**. Returns
`list[ImageResult]`.

```python
import illustration

hits = illustration.search("a stormy harbour at dusk", n=10)
hit = hits[0]
hit.url  # full-resolution image URL
hit.thumbnail_url  # smaller/faster variant
hit.license  # e.g. 'by-sa'
hit.attribution  # ready-to-render credit sentence
hit.cacheable  # may you download/cache the bytes?
hit.raw  # the untranslated provider payload — nothing is lost
```

Key arguments:

- `n=10` — results **per source**. With several sources the per-source lists are
  concatenated (up to `n × len(sources)`), not merged or deduplicated.
- `source=None` → the default set, which is **`("openverse",)` only** — not all
  four. Pass `source="pexels"` or `source=["openverse", "wikimedia"]` to widen.
- Canonical filters, translated per provider and dropped where unsupported:
  `orientation` (`landscape`/`portrait`/`square`), `size`
  (`large`/`medium`/`small`), `safe=True`, `license_type`
  (`commercial`/`all-cc`/`modification`/`all`), `color`, `content_type`
  (`photo`/`illustration`/`vector`).
- `license_allow=False` — the gate (see above). `True` = the default
  commercial-safe set, or pass your own iterable of licence codes.
- `rerank=False` — `True` runs SigLIP-2 over the assembled results.
- `cache=True` — SHA-256 content-addressed JSON files under
  `~/.cache/illustration/`; `refresh=True` forces a re-fetch;
  `cache=False` bypasses. To inject your own `dol`-style store, wrap it:
  `cache=SearchCache(my_mutable_mapping)` (`from illustration import
  SearchCache`) — a bare mapping is *not* accepted and raises.
- `api_key=...` and flat native params (anything `search()` doesn't name — e.g.
  Pixabay's native `image_type="photo"`) are **single-source only**: they raise
  on a multi-source fan-out. Use
  `provider_params={"pixabay": {"image_type": "photo"}}` and
  `using_credentials(...)` instead.

## Sources

| source | key needed | corpus |
|---|---|---|
| `openverse` *(default)* | no | 800M+ CC / public-domain, aggregated from 50+ sources |
| `wikimedia` | no | 140M+ free media; historical / editorial / fine-art, deep metadata |
| `pexels` | `PEXELS_API_KEY` | curated high-quality stock photos |
| `pixabay` | `PIXABAY_API_KEY` | free commercial-use; licence permits self-hosting |

Inspect them at runtime: `illustration.list_sources()`,
`illustration.get_source("openverse").info.to_dict()`, or from the shell
`illustration sources` / `illustration info openverse`.

Keys resolve in this order: explicit `api_key=` → `using_credentials(...)` →
the environment variable → a `config2py` config entry. A missing key raises
`MissingCredentialError`, which names the variable, the ways to set it, and
where to get a key — and never logs the value.

```python
with illustration.using_credentials(pexels="...", pixabay="..."):
    illustration.search("harbour", source=["pexels", "pixabay"])
```

## `rerank(query, results, *, scorer=None, descending=True)` — precision

Provider search is cheap **recall** over tags/lexical text. For **precision**,
rerank with true text↔image similarity (SigLIP-2, local, no API cost). Use the
recall→rerank pattern:

```python
beat = "a stormy harbour at dusk"
hits = illustration.search(beat, n=50)  # recall
top = illustration.rerank(beat, hits)[:10]  # precision
top = illustration.search(beat, n=50, rerank=True)[:10]  # the same, in one call
```

Returns **copies** with `.score` populated, sorted descending. Needs
`[rerank]` (raises `RerankDependencyError` naming the extra if missing); image
embeddings are content-addressed and cached, so overlapping candidates are cheap.
Any `(query, results) -> scores` callable can be passed as `scorer=`.

## `curate(beat, ...)` — one vetted image for one beat

Goes past ranking: retrieve → grade → conditionally re-query, with a
classical-CV pre-filter gating the expensive vision-LM, and hard caps enforced
in code. **This one spends money** (LLM + VLM calls via `aix`).

```python
from illustration import curate, Budget

result = curate(
    "a stormy harbour at dusk, fishermen hauling nets",
    sources=["openverse", "pexels"],
    budget=Budget(max_iter=3, max_judge_calls=8, accept_threshold=0.62),
)
result.best.result.url  # the chosen image
result.best.rubric.overall  # its VLM rubric score, when judged
result.accepted, result.reason, result.grade
for step in result.trace:  # per-iteration run-log
    print(step.iteration, step.grade, step.action, step.best_score)
result.spend  # {'iterations', 'search_calls', 'caption_calls', 'judge_calls', 'est_cost'}
```

`Budget` defaults: `max_iter=3`, `max_search_calls=8`, `max_caption_calls=12`,
`max_judge_calls=8`, `accept_threshold=0.62`. Set `max_cost` + `cost_estimator`
for a money ceiling on top of the call caps. Every paid step is an injectable
seam — `search_fn`, `expander`, `refiner`, `scorer`, `describe`, `grader`,
`checks`, `fetch` — so you can stub any of them and run the loop offline.

## `curate_sequence(beats, ...)` — one image per beat, across a storyboard

`curate` picks for one beat in isolation, which will happily give you the same
picture twice. `curate_sequence` optimizes the **sequence**: relevance +
cross-shot coherence − redundancy, with a perceptual-hash near-duplicate hard
constraint.

```python
from illustration import curate_sequence

result = curate_sequence(
    [
        "a stormy harbour at dawn",
        "fishermen hauling nets",
        "the catch unloaded at the quay",
    ]
)
for bs in result.selection.selections:
    print(bs.beat_index, bs.chosen.url, bs.coherence, bs.forced_duplicate)
result.selection.chosen  # [ImageResult | None, ...] in beat order
```

- A beat with no candidates yields `chosen=None` — always handle it.
- `forced_duplicate=True` means every candidate near-duplicated an earlier beat
  and the constraint was relaxed; surface it rather than ignoring it.
- Despite the name, the default path **spends no LLM money**: pools come from
  `search` + the local SigLIP rerank, and coherence/near-duplicate suppression
  degrade to off (silently) when `[rerank]` / Pillow+NumPy aren't installed.
- For the full per-beat CRAG loop — which *does* spend — unwrap the loop's
  `Candidate` envelopes, since the pool must be `ImageResult`s:
  `curate_sequence(beats, per_beat=lambda b: [c.result for c in curate(b).candidates])`.
- Tuning passes through to `select_sequence`: `alpha=0.30` (coherence weight),
  `beta=0.50` (redundancy penalty), `phash_threshold=6`, plus `relevance`,
  `embed`, `hasher`, `shortlist` seams.

## Handing the selection onward (opt-in hooks)

```python
from illustration import (
    render_sequence_video,
    to_walkthru_document,
    persist_sequence,
    record_override,
    resolve_selection,
)

# Ken-Burns film from the chosen stills + a pre-built narration track ([video]).
render_sequence_video(result, saveas="film.mp4", narration_audio="narration.mp3")

# Or pure data: a walkthru DemoDocument a walkthru/reelee consumer renders its way.
doc = to_walkthru_document(result, narration=["dawn…", "nets…", "quay…"])

# Persist the decisions as lacing standoff annotations ([persist]).
store = persist_sequence(result)
record_override(store, 1, my_preferred_image, reason="better composition")
resolve_selection(store, 1)  # the director's choice now supersedes the machine's
```

`render_sequence_video` needs `burns` **and `ffmpeg` on PATH**; the `render`
argument accepts a stub so you can test without either. `persist_sequence`
returns a fresh in-memory `lacing` store when you don't pass one; overrides are
append-only, never destructive.

The stored body keeps the rights record, so attribution survives the round trip:

```python
selected = resolve_selection(store, 1)["selected"]
selected["attribution"], selected["license"], selected["source_page_url"]
```

A body written before v0.0.6 has those keys absent/`None` — `cacheable is None`
means *not recorded*, which is not the same as "not cacheable".

## CLI

```bash
illustration search "a stormy harbour at dusk" --n 10
illustration search "rusty bicycle" --source openverse --size large --json
illustration curate "a stormy harbour at dusk" --source openverse --max-iter 3
illustration curate-sequence "dawn harbour" "hauling nets" "the quay"
illustration sources
illustration info openverse
```

## Gotchas

- **`license_allow=True` normalises before comparing, so all four providers'
  own spellings work.** The default set is
  `{cc0, pdm, by, by-sa, pexels-license, pixabay-license}` and both sides go
  through `normalize_license` first, so Wikimedia's `cc-by-sa-4.0` /
  `CC BY-SA 4.0` and Pixabay's `Pixabay License` all match. (Before v0.0.6 the
  match was exact and those two sources silently gated to `[]` — if you are
  reading older notes saying to pass an explicit `allow=`, that is stale.)
  What normalisation does **not** do is soften a restriction: `by-nc`,
  `by-nd`, `cc-by-nc-nd-4.0` are dropped, and an unrecognised code
  (`PD-US-expired`, bespoke museum terms) is dropped too — unknown is not
  allowed. If you need one of those, name it yourself in `allow={...}`.
- **`n` is per source, and multi-source results are concatenated, not fused.**
  Rerank (or `curate`) if you want one merged ranking.
- **The default source set is Openverse alone.** Widening to keyed providers is
  an explicit `source=` plus a key.
- **`search()` results are cached by default** — an identical repeat call never
  hits the network. Pass `refresh=True` when you actually want fresh results.
  Empty result sets are deliberately not cached, so a zero-hit query re-fetches.
- **Not every provider supports every filter.** Wikimedia supports *none* of the
  canonical filters; unsupported ones are dropped silently rather than erroring.
- **`.score` is `None` until something reranks.** Don't sort on it blindly.
- **`curate` spends money** (LLM/VLM via `aix`) and needs the `[curate]` extra
  plus provider and model API keys. `search`, `rerank` and the default
  `curate_sequence` spend nothing beyond the provider quota — `curate_sequence`
  only costs money if you inject a `per_beat` that calls `curate`.
- **This package does not generate images.** If nothing suitable exists in the
  corpora, say so — reach for the ecosystem's generation path instead of
  stretching a bad retrieval.
