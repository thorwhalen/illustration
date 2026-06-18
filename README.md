# illustration

Find **existing** images to illustrate narrated video — cross-modal
text-to-image retrieval (semantic image search) over stock / open-media corpora.
Not an image *generator*: given narration text, it *retrieves* fitting images.

```python
import illustration

# No API key needed — Openverse is the default source.
hits = illustration.search("a stormy harbour at dusk", n=10)

hit = hits[0]
hit.url            # full-resolution image URL
hit.license        # e.g. 'by-sa'  (license carried through from day one)
hit.attribution    # ready-to-render attribution sentence
hit.cacheable      # may you download/cache the bytes?
```

From the shell:

```bash
illustration search "a stormy harbour at dusk" --n 10
illustration search "rusty bicycle" --source openverse --size large --json
illustration sources
illustration info openverse
```

That's the whole common case. Everything below is optional depth.

---

## What it is

`illustration` has two layers:

1. **The provider façade** — one unified `search()` over many heterogeneous
   image-search backends (Openverse, Pexels, …), normalizing every result into
   one schema with license/attribution/cacheability first-class.
2. **An agentic curation layer** — query expansion, multi-provider search,
   classical-CV + vision-LM inspection, reranking, a bounded corrective loop that
   returns one vetted image per beat (`illustration.curate`), and **sequence-level
   selection** across a whole storyboard with cross-shot coherence + near-duplicate
   suppression (`illustration.curate_sequence`). Built on the `aix` AI façade and
   `ir` retrieval substrate; the narrated-video and persistence hooks reuse the
   `burns` / `walkthru` / `lacing` ecosystem packages rather than reinventing them.

The design — provider comparison, canonical parameter mapping, escape-hatch
design, result schema, and roadmap — is in
[`misc/docs/design/illustration_design.md`](misc/docs/design/illustration_design.md).

## Install

```bash
pip install illustration
```

Local-ecosystem dependencies (`dol`, `config2py`) are developed alongside this
package; in the dev environment they resolve to local source.

## The result schema

`search()` returns a list of `ImageResult` (Pydantic v2 — the single source of
truth shared with the agentic layer):

| field | meaning |
|---|---|
| `provider`, `id` | which source, and its native id |
| `url`, `thumbnail_url` | full-resolution image, and a thumbnail |
| `width`, `height` | pixel dimensions |
| `title`, `description`, `tags` | text metadata (normalized) |
| `license`, `license_url`, `attribution` | **licensing, populated from day one** |
| `source_page_url`, `author`, `author_url` | provenance |
| `cacheable` | may the bytes be downloaded/cached to your server? |
| `raw` | the untranslated provider payload (nothing is lost) |

## Sources (providers)

| source | key needed? | notes |
|---|---|---|
| **openverse** *(default)* | no | 800M+ CC / public-domain images; works out of the box |
| **wikimedia** | no | 140M+ free media; historical / editorial / fine-art; deep metadata |
| **pexels** | `PEXELS_API_KEY` | curated high-quality stock photos |
| **pixabay** | `PIXABAY_API_KEY` | free commercial-use; license permits caching / self-hosting |

Pick a source (or several), and filter:

```python
illustration.search("harbour", source="openverse", orientation="landscape", size="large")
illustration.search("harbour", source=["openverse", "wikimedia"], n=5)   # per-source, no key
```

Canonical filters (`orientation`, `size`, `safe`, `license_type`, `color`,
`content_type`) translate to each provider's native parameters and degrade
gracefully where a provider doesn't support one.

### Keys

Pexels and Pixabay need a key (Openverse and Wikimedia do not). Provide it
however suits you:

```python
import os; os.environ["PEXELS_API_KEY"] = "..."      # env var
# or per-request (the bring-your-own-key seam, e.g. a web backend):
with illustration.using_credentials(pexels="...", pixabay="..."):
    illustration.search("harbour", source=["pexels", "pixabay"])
```

A missing key raises an informative `MissingCredentialError` that names the key,
how to set it, and where to get one — and never logs the value.

## Caching

Results are SHA-256 content-addressed and cached behind an injectable `dol`
store (default: JSON files under `~/.cache/illustration/`), so an identical
second call is free:

```python
illustration.search("harbour")                 # hits the network
illustration.search("harbour")                 # served from cache
illustration.search("harbour", refresh=True)   # force a re-fetch
illustration.search("harbour", cache=my_store) # inject any MutableMapping
```

## Rerank (precision)

Provider tag/lexical search is a cheap, high-**recall** stage. For **precision**,
rerank the candidates by true cross-modal (text↔image) similarity with a local
SigLIP-2 model — the recall→rerank pattern:

```python
hits = illustration.search("a stormy harbour at dusk", n=50)   # recall
top  = illustration.rerank("a stormy harbour at dusk", hits)[:10]  # precision
# or the one-liner:
top  = illustration.search("a stormy harbour at dusk", n=50, rerank=True)[:10]
```

`rerank` populates each result's `.score` and sorts by it. The default SigLIP-2
encoder needs the optional extra (`pip install 'illustration[rerank]'`); a clear
error tells you if it's missing. The scorer is injectable — pass any
`(query, results) -> scores` callable to use a different model:

```python
illustration.rerank("harbour", hits, scorer=my_scorer)
```

Image embeddings are content-addressed and cached, so re-ranking overlapping
candidates is cheap.

## Curate (agentic, the bounded CRAG loop)

`search` + `rerank` give you ranked candidates; `curate` goes one step further
and returns *one vetted image* for a narration beat, self-correcting across a
hard-bounded number of rounds. The loop is corrective-RAG-shaped — retrieve →
grade → conditionally re-query — with a classical-CV pre-filter gating the
expensive vision-LM, caption-first / judge-on-ambiguity escalation, and a
`Budget` of caps **enforced in code**:

```python
from illustration import curate, Budget

result = curate(
    "a stormy harbour at dusk, fishermen hauling nets",
    sources=["openverse", "pexels"],
    budget=Budget(max_iter=3, max_judge_calls=8, accept_threshold=0.62),
)
result.best.result.url        # the chosen image
result.best.rubric.overall    # its VLM rubric score (when judged)
result.accepted, result.reason
for step in result.trace:     # per-iteration run-log (queries, grade, action, spend)
    print(step.iteration, step.grade, step.action)
```

```bash
illustration curate "a stormy harbour at dusk" --source openverse --max-iter 3
```

This needs the optional `[curate]` extra (`pip install 'illustration[curate]'` —
`aix` + `ir` + Pillow/NumPy) plus provider and LLM API keys; the NSFW safety gate
and SigLIP rerank additionally want `[rerank]` (so `illustration[rerank,curate]`
for the full pipeline). Every paid step is an **injectable seam** — pass your own
`search_fn`, `expander`/`refiner`, `scorer`, `describe`, `grader`, or `checks` to
swap a model, add a test double, or run the loop entirely offline.

The image→text capability the judge/caption uses lives in `aix`
(`aix.describe_image`, provider-neutral over LiteLLM), so any vision-capable
model (Claude, GPT-4o, Gemini, …) works by model id alone.

## Sequence (storyboard selection)

`curate` picks the best image for *one* beat; `curate_sequence` picks one image
per beat across a whole storyboard, optimizing **cross-shot coherence** and
**diversity** with a perceptual-hash **near-duplicate** hard constraint — so
consecutive shots cohere and no two beats land on the same picture:

```python
from illustration import curate_sequence

result = curate_sequence([
    "a stormy harbour at dawn",
    "fishermen hauling nets",
    "the catch unloaded at the quay",
])
for bs in result.selection.selections:
    print(bs.beat_index, bs.chosen.url, bs.coherence, bs.forced_duplicate)
```

```bash
illustration curate-sequence "dawn harbour" "hauling nets" "the quay"
```

The selection math is **in-house and dependency-light** (NumPy MMR + a DCT
perceptual hash; coherence reuses the SigLIP embeddings the reranker already
caches) — `select_sequence(per_beat_candidates, *, relevance, embed, hasher,
shortlist, alpha, beta, phash_threshold)` exposes every part as an injectable
seam. `apricot` (submodular shortlisting) and `imagededup` (CNN dedup) are
optional upgrades you plug into the `shortlist` / `hasher` seams.

## Persist & render (ecosystem hooks)

The narrated-video and persistence steps are owned by other ecosystem packages;
illustration provides thin, opt-in hooks rather than reinventing them.

```python
# Render the selected stills into a Ken-Burns film (burns + your narration audio):
from illustration import render_sequence_video
render_sequence_video(result, saveas="film.mp4", narration_audio="narration.mp3")

# Or hand a walkthru DemoDocument to a walkthru/reelee consumer to render its way:
from illustration import to_walkthru_document
doc = to_walkthru_document(result, narration=["dawn…", "nets…", "quay…"])

# Persist selections (and director overrides) as lacing standoff annotations:
from illustration import persist_sequence, record_override, resolve_selection
store = persist_sequence(result)
record_override(store, 1, my_preferred_image, reason="better composition")
resolve_selection(store, 1)   # the director's choice now supersedes the machine's
```

These need the opt-in extras: `illustration[video]` (`burns` + `walkthru`) and
`illustration[persist]` (`lacing`; add `lacing[otio]` for `export_otio`). The
render hook uses `burns` directly — the same renderer `walkthru` uses — so it
never pulls the app layer.

## The escape hatch

A pure façade exposes only the common interface — but you can always reach a
provider's special powers, via a four-rung ladder (cleanest → rawest):

```python
# 1. pick the source(s)
illustration.search("q", source="pexels")

# 2. canonical filters (translated per provider)
illustration.search("q", orientation="portrait", size="large")

# 3. native passthrough — flat for one source, namespaced for many
illustration.search("q", source="pexels", color="blue")
illustration.search("q", source=["openverse", "pexels"],
                    provider_params={"pexels": {"color": "blue"}})

# 4. the raw provider client
illustration.sources["openverse"].raw_search(q="q", page_size=2)   # raw JSON
hits[0].raw                                                        # raw item
```

A parameter is promoted from the escape hatch to a canonical façade argument
once **two or more** providers support it (so the interface evolves predictably).

## Adding a provider

Open-closed — subclass `RetrievalSource` and register it; the façade is
untouched:

```python
from illustration import RetrievalSource, ImageResult, register_source

class MySource(RetrievalSource):
    name = "mysource"
    endpoint = "https://api.example.com/search"
    query_param = "q"
    per_page_param = "limit"
    max_per_page = 50
    param_map = {"size": "size", "orientation": {"name": "orient"}}

    def _items(self, response):
        return response.get("results", [])

    def _normalize(self, item, *, query):
        return ImageResult(provider=self.name, id=str(item["id"]),
                           url=item["image_url"], query=query)

register_source(MySource())
```

## Licensing

Licensing is first-class for commercial-adjacent video. Each result carries its
license, license URL, attribution, and a `cacheable` flag. Aggregators
(Wikimedia, Openverse) disclaim license accuracy, so gate on a known-good set
when it matters — either inline on `search()` or with the standalone helper:

```python
# inline gate (R3): keep only commercial-safe licenses
illustration.search("harbour", source="wikimedia", license_allow=True)
illustration.search("harbour", license_allow={"cc0", "pdm"})   # public-domain only

# or filter an existing result list
from illustration import license_allowlist
safe = license_allowlist(hits)                          # CC0/PD/BY/BY-SA default
safe = license_allowlist(hits, allow={"cc0", "pdm"})    # public-domain only
```

## License

MIT
