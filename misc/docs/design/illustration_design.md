# `illustration` — Design Document

*Status: living document · First written for Milestone 1 (the provider façade).*

`illustration` finds **existing** images to illustrate narrated video. It is a
**cross-modal text-to-image retrieval** system (semantic image search over
stock / open-media corpora), *not* an image generator. Two layers, built in
order:

1. **The pure-search provider façade** (Layer 1) — one unified interface over
   many heterogeneous image-search backends (Openverse, Pexels, Pixabay,
   Unsplash, Wikimedia Commons, …). *This is Milestone 1.*
2. **The agentic curation layer** (Layer 2) — query expansion, multi-provider
   search, classical-CV + VLM inspection, rerank, a bounded corrective loop,
   and sequence-level selection. Built on the `aix` AI façade and `ir`
   retrieval patterns. *Milestones 3–4.*

> **Terminology.** A **provider** / **source** is a pure search backend (Pexels,
> Openverse, …). An **agent** belongs to Layer 2. Thor sometimes calls providers
> "search agents" informally — they are *not* agents in the LLM sense.

This document records the decisions, their rationale, and the rejected
alternatives. It is the durable design record; the running dev journal is
[issue #1](https://github.com/thorwhalen/illustration/issues/1).

---

## 0. Inputs to this design

Three research reports (in `misc/docs/research/`) established the 2026 landscape;
they are treated as given and cited here rather than re-derived:

- **R1** — *Cross-Modal Text-to-Image Retrieval Over an Existing Image Corpus*
  (retrieval architecture: two-stage hybrid recall→rerank, SigLIP-2,
  `meshed`/`dol`/SHA-256-cache/Pydantic, provenance).
- **R2** — *Agentic Multimodal Retrieval for Screenplay-to-Animation Pipelines*
  (bounded CRAG loop with hard budget caps, classical-CV pre-filters gating VLM
  calls, standoff annotations, license discipline).
- **R3** — *Image Source API Audit for Commercial-Adjacent Video Production*
  (the provider audit: Pexels primary, Pixabay cacheable companion, Openverse
  breadth, per-file license-allowlist gate).

Four ecosystem façade packages were studied so `illustration` adopts an
established idiom rather than inventing one:

- **`falaw`** — façade over fal.ai: a SHA-256 content-addressed cache, a
  pure-data Plan/Execute split with cost-honesty before execution, a three-ring
  escape hatch (`extra` dict → `model_id` override → raw `call_fal`), and a
  `contextvars` BYO-key idiom.
- **`denote`** — façade over heterogeneous audio backends: the **canonical
  escape-hatch design** — a four-rung ladder (`backend=` selector → per-backend
  `param_map` kwarg translation → named service handle → raw adapter + `.raw`
  on every result).
- **`aix`** — multi-provider AI façade: the gold-standard credentials layer
  (`resolve_api_key` + `MissingCredentialError` + `@requires_credentials`
  decorator), a layered-config SSOT, and the open-closed `Source(ABC)` +
  `MutableMapping` registry. *Has text embeddings but **no** image→text or
  image-embeddings — Layer 2 must add these.*
- **`ir`** — agentic retrieval substrate: `Retriever` contract, `fuse_hits`
  (cross-source RRF fan-in — raw scores never cross a source boundary),
  `SearchHit.source`, `select`/abstention, and the string-or-callable + lazy-LLM
  seam idiom. *Layer 2 consumes `ir` directly.*

---

## 1. Provider × parameter matrix (Milestone-1 candidates)

Verified against the live APIs, June 2026. Full audit of all candidate
providers (Pixabay, Unsplash, Wikimedia, Smithsonian, NASA, Brave, …) is in R3.

| | **Openverse** *(M1 primary)* | **Pexels** *(M1 drop-in #2)* |
|---|---|---|
| Auth | **None** (anonymous tier) | API key in `Authorization` header, **no `Bearer` prefix** |
| Endpoint | `GET https://api.openverse.org/v1/images/` | `GET https://api.pexels.com/v1/search` |
| Query param | `q` (≤200 chars) | `query` (required) |
| Count / page | `page_size` (anon max **20**), `page` | `per_page` (max **80**), `page` |
| Orientation | `aspect_ratio` ∈ `square,tall,wide` | `orientation` ∈ `landscape,portrait,square` |
| Size | `size` ∈ `large,medium,small` | `size` ∈ `large,medium,small` |
| Color | — | `color` (named or `#hex`) |
| Safe-search | `mature` (bool; default false) | — (corpus is curated) |
| License filter | `license`, `license_type` (`commercial`/`all-cc`/…) | — (single Pexels License) |
| Content type | `category` ∈ `photograph,illustration,digitized_artwork` | — (photos only) |
| Locale | — | `locale` (30+ codes) |
| Rate limit | 20/min, 200/day (anon) | 200/hr, 20k/mo |
| Image URL | `results[].url` | `photos[].src.original` |
| Thumbnail | `results[].thumbnail` (proxy) | `photos[].src.tiny` / `.medium` |
| Source page | `results[].foreign_landing_url` | `photos[].url` |
| Author | `results[].creator` | `photos[].photographer` |
| Tags | `results[].tags[].name` *(objects)* | — (none) |
| Per-result license | `license` + `license_version` + `license_url` + `attribution` | — (constant) |
| Cacheable | **Yes** (CC/PD; preserve attribution) | Yes (Pexels License; credit + backlink) |

**Why Openverse is the M1 primary:** it needs **no API key**, so
`illustration.search("…")` works out of the box with zero setup — the strongest
possible "ready to use" default. Pexels is the second provider precisely
*because* it requires a key: it proves the registry is a true drop-in **and**
exercises the credentials / `check_requirements` path.

---

## 2. Canonical parameters & the canonical→native mapping

**First positional argument is the query string. Everything else is keyword.**

A parameter is **canonical** (a first-class façade argument) once **≥2
providers** support a semantically-equivalent param. Until then it lives in the
escape hatch (§4). Two deliberate exceptions are promoted regardless of provider
count because R2/R3 make them first-class concerns: **`safe`** (safety) and
**`license_type`** (licensing/commercial-use). Each source declares a
`param_map` (à la `denote`) translating canonical → native, with
`on_unsupported='ignore'` so an unsupported param degrades gracefully (and is
recorded in the result's `degraded` notes, never silently dropped at debug
level).

| Canonical | Type / values | → Openverse | → Pexels | Notes |
|---|---|---|---|---|
| *(positional)* `query` | `str` | `q` | `query` | required |
| `n` | `int` (default 10) | `page_size` (+ paginate) | `per_page` (+ paginate) | total wanted; façade paginates internally past per-page caps |
| `orientation` | `landscape\|portrait\|square` | `aspect_ratio` (`landscape→wide`, `portrait→tall`, `square`) | `orientation` (direct) | vocab differs → `coerce` in `param_map` |
| `size` | `large\|medium\|small` | `size` (direct) | `size` (direct) | identical vocab |
| `safe` | `bool` (default `True`) | `mature = not safe` | — (ignored; safe) | **first-class exception** |
| `license_type` | `commercial\|all-cc\|modification\|all\|None` | `license_type` | — (ignored; single license) | **first-class exception** |
| `color` | `str` (named/hex) | — | `color` | **1 provider → escape hatch** (promotion example) |
| `locale` | `str` | — | `locale` | 1 provider → escape hatch |
| `content_type` | `photo\|illustration\|vector` | `category` | — | 1 provider → escape hatch (promote when Pixabay lands) |

`color`, `locale`, `content_type` are shown to illustrate the promotion rule:
they are reachable today via `provider_params` and become canonical the moment a
second provider supports them (Pixabay adds `image_type` and `colors`).

---

## 3. The result schema (Pydantic v2 — the SSOT)

`ImageResult` is the stable contract shared with Layer 2 downstream (and,
through the federation's *Pydantic v2 → JSON Schema → Zod* rule, with any TS
frontend). Pydantic v2 is chosen over the ecosystem's usual frozen-dataclass
because the kickoff mandates it and it is the federation schema rule — even
though `falaw`/`aix`/`denote`/`ir` use dataclasses internally.

```python
class ImageResult(BaseModel):
    provider: str            # source name, e.g. "openverse"
    id: str                  # provider-native id
    url: str                 # full-resolution image URL
    thumbnail_url: str | None
    width: int | None
    height: int | None
    title: str | None        # short title
    description: str | None  # alt text / longer description
    tags: list[str]          # normalized to [] when absent
    license: str             # license code or name (e.g. "by-sa", "Pexels License")
    license_url: str | None
    attribution: str | None  # ready-to-render attribution sentence
    source_page_url: str | None
    author: str | None
    author_url: str | None
    cacheable: bool          # may bytes be downloaded/cached to our server?
    avg_color: str | None    # dominant-color hint where available (Pexels avg_color)
    # provenance / escape hatch
    query: str | None        # the canonical query that produced this hit
    score: float | None      # reserved for Layer-2 rerank; None at Layer 1
    raw: dict                # untranslated provider payload (denote's .raw convention)
```

`license`, `attribution`, `source_page_url`, `author`, and `cacheable` are
populated **from day one** (DoD + R3's "licensing is first-class"). `raw`
preserves every provider field so nothing is lost (escape-hatch rung 4). A
thin `to_search_hit()` adapter maps `ImageResult → ir.SearchHit` (with
`.source = provider`, `.pointer = url`) so Layer 2 can `ir.fuse_hits` across
providers.

A `license_allowlist(results, allow={...})` helper implements R3's mandatory
license-verification gate (default allow = CC0, PD, CC-BY, CC-BY-SA flagged;
reject NC/ND/unknown). It is available but not forced on `search()`.

---

## 4. The escape hatch (chosen design)

**Decision: adopt `denote`'s four-rung ladder, adapted for retrieval.** A pure
façade exposes only the common interface; reaching a provider's special powers
is a deliberate, controlled violation of purity, and `denote`'s situation
(heterogeneous backends behind one façade, wanting raw power) is structurally
identical to `illustration`'s. The four rungs, cleanest → rawest:

1. **`source=` selector.** `search(q, source="pexels")` (or a list/`None` for
   the registered default set). Picks which backend(s) without changing the
   normalized return type.
2. **Canonical kwargs + per-source `param_map` translation.** The §2 canonical
   args translate to native names per source via `make_param_translator(
   param_map, on_unsupported="ignore")`. A `param_map` entry of `None` means
   "this source doesn't support it" (degrade gracefully + record).
3. **Namespaced `provider_params: dict[str, dict]` passthrough**, plus a flat
   `**provider_kwargs` for the single-source case. The namespaced form is the
   refinement the `aix` study explicitly flagged: a flat `**kwargs` cannot say
   "this param is for Pexels, that one for Openverse" when fanning one call out
   to multiple sources. So:
   `search(q, source=["openverse","pexels"], provider_params={"pexels": {"color": "blue"}})`.
   Merged last into the native call (falaw's `extra`-dict idiom, namespaced).
4. **Named source handle + raw access.** `illustration.sources["pexels"]`
   returns the live source object; `source.raw_search(**native_params)` hits
   the backend with zero translation, and every `ImageResult.raw` carries the
   untranslated payload.

**Promotion rule (how the interface evolves predictably):** a `provider_params`
key is promoted to a canonical §2 argument once **≥2 registered providers**
support a semantically-equivalent param; at promotion it gets a `param_map`
entry per provider (`None` for those that don't support it). Safety and
licensing are promoted regardless of count.

### Rejected alternatives (and why)

- **Flat `**provider_kwargs` only (the `aix` idiom).** Clean for a single
  backend, but cannot disambiguate per-provider on multi-source fan-out — the
  exact gap the `aix` study called out. *Kept as the single-source convenience
  (rung 3a), rejected as the only mechanism.*
- **A single un-namespaced `extra: dict` (the `falaw` idiom).** Same
  multi-provider ambiguity. *Adopted in namespaced form (rung 3).*
- **Per-provider Pydantic config objects.** Heavy ceremony; every new provider
  param needs a schema edit; poor progressive disclosure for the common case.
  *Rejected — the `param_map` dict + `provider_params` covers it with far less
  ceremony.*
- **Curried/preset providers only (à la fal's `pick_model`).** Useful as an
  *additional* convenience (`safe`/`broad`/`fast` source presets), but not an
  escape hatch — it doesn't expose native params. *Adopted as a complementary
  preset layer, not the hatch.*

---

## 5. Caching (SHA-256 content-addressed, injectable `dol` store)

`falaw`, `aix`, and `ir` converge on the same recipe; `illustration` copies it:

```python
key = hashlib.sha256(
    json.dumps(
        {"source": source_id, "query": q, "params": normalized_params,
         "schema": SEARCH_CACHE_SCHEMA},      # version token, bumped on schema change
        sort_keys=True, default=str,
    ).encode()
).hexdigest()
```

- **Normalization** is `sort_keys=True` + `default=str` (dict-order invariant,
  per falaw's tested invariant) over the **canonical** params *after* translation
  defaults are applied, so logically identical queries collapse to one key.
- The **store is an injectable `MutableMapping`** (`dol`), defaulting to
  `JsonFiles` under the cache dir (`ILLUSTRATION_CACHE_DIR` →
  `XDG_CACHE_HOME/illustration` → `~/.cache/illustration/search`). Swap to S3 /
  Redis / Mongo without touching call sites.
- The façade wraps the cache like falaw's `cached_call_fal`: peek → return on
  hit → else fetch + store. `search(..., refresh=True)` bypasses the read.
- The schema-version token in the key makes invalidation **structural** (a new
  key) rather than manual deletion when the result schema changes.

Per-source results are cached **per source**, so a multi-source query reuses any
single source's prior cache entry. (The DoD's "second identical call hits the
cache" is satisfied for the single-source case directly.)

---

## 6. Config & secrets (`check_requirements`-style, with BYO-key seam)

Adopt `aix`'s credentials design (which already implements the global
`check_requirements` rule) plus `falaw`'s `contextvars` BYO idiom:

- **`PROVIDER_ENV_VARS`** (`{"pexels": "PEXELS_API_KEY", …}`) and
  **`PROVIDER_CONSOLE_URLS`** (where to get a key) — plain, appendable dicts.
- **`resolve_api_key(provider, *, api_key=None)`** precedence: explicit arg >
  per-request context (`using_credentials`) > env var > `config2py` store.
  Never prompts in a non-interactive context.
- **`MissingCredentialError`** names *which* key, *how* to set it (export /
  config), and *where* to get one (console URL). Key values are never logged.
- **`@requires_credentials(provider)`** decorator separates error-raising from
  business logic (the user's "separate concerns via decorators" principle).
  Sources that need no key (Openverse) are simply not decorated.
- **`using_credentials(pexels="…")`** context manager binds per-request keys via
  a `ContextVar` without threading a credential arg through every call — the
  seam reelee-web's BYO-keys / future internal-keys model will use.

---

## 7. Architecture & layout

Open-closed plugin/registry, exactly as `aix.ai_models` / `ir.registry` do it:
each provider is a small `RetrievalSource` implementing a `search` protocol,
registered by name into a module-level `MutableMapping`; the façade dispatches.
Adding a provider touches **only** a new file under `sources/` + one
registration — never the façade.

```
illustration/
  __init__.py      # curated __all__: search, ImageResult, sources, register_source,
                   #   using_credentials, license_allowlist, RetrievalSource, …
  schema.py        # ImageResult (Pydantic v2 SSOT), to_search_hit, license_allowlist
  base.py          # RetrievalSource Protocol/ABC, SourceInfo
  translation.py   # make_param_translator(param_map, on_unsupported=…)  (denote-style)
  registry.py      # _SOURCES dict, register_source/get_source/list_sources,
                   #   SourcesView (Mapping, dict+attr access), default-source policy
  credentials.py   # PROVIDER_ENV_VARS/URLS, resolve_api_key, MissingCredentialError,
                   #   requires_credentials, using_credentials (ContextVar)
  caching.py       # search_cache_key, SearchCache over an injectable dol MutableMapping
  config.py        # XDG dirs + DFLT_* constants (DFLT_N, DFLT_SOURCES, allowlist)
  facade.py        # search(query, *, n, source, orientation, size, safe, license_type,
                   #   provider_params, cache, refresh, **provider_kwargs)
  sources/
    __init__.py
    openverse.py   # OpenverseSource — no key
    pexels.py      # PexelsSource — needs key (@requires_credentials)
  cli.py           # thin argh wrappers (ir idiom)
  __main__.py      # argh dispatch; [project.scripts] illustration = …
```

Layer 2 (later) adds `expand.py` (query formulation via `aix`), `inspect.py`
(classical-CV pre-filters + VLM caption/judge via `aix`), `rerank.py`
(CLIP/SigLIP, optional), `curate.py` (the bounded CRAG loop + `ir.fuse_hits` /
`ir.select`), and `sequence.py` (MMR / submodular / pHash selection). All
AI calls go through `aix`; image→text and image-embeddings will be **added to
`aix`** (the studied gap) following `aix`'s conventions.

---

## 8. Milestone plan

- **M0 — Orient & set up.** ✅ Read R1–R3, study façade packages, verify provider
  APIs, write this doc, set up the repo + issue #1.
- **M1 — One provider end-to-end** (this milestone). Openverse end-to-end
  (no key → works out of the box) + Pexels as the drop-in proof: `ImageResult`
  schema, `RetrievalSource` + registry, SHA-256 `dol` cache, `search()` façade,
  `argh` CLI, credentials/`check_requirements`, doctests + offline tests.
- **M2 — Multi-provider façade.** Add Pixabay + Wikimedia (+ Unsplash with its
  hotlink/competing-index constraints honored); finalize the escape hatch under
  real fan-out; add the license-allowlist gate to the default path; add local
  CLIP/SigLIP rerank (R1) on top of provider recall.
- **M3 — Agentic curation.** The bounded CRAG loop (R2) via `aix` + `ir`
  patterns; classical-CV pre-filters; add image→text to `aix`; hard budget caps.
- **M4 — Sequence selection & integration.** MMR / submodular / pHash / NR-IQA
  selection (license-safe libs only); an integration hook for the
  narration→TTS→Ken-Burns pipeline.

---

## References

- `misc/docs/research/illustration_01 … reelee.md` (R1 — retrieval architecture)
- `misc/docs/research/illustration_02 … Pipelines.md` (R2 — agentic loop)
- `misc/docs/research/illustration_03 … (2026).md` (R3 — provider audit)
- Ecosystem study (issue #1): `falaw` (cache + Plan + escape hatch), `denote`
  (escape-hatch ladder + `param_map`), `aix` (credentials + registry +
  embeddings gap), `ir` (`Retriever` / `fuse_hits` / `select`).
