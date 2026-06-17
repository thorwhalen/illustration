# Kickoff Prompt — `illustration`: a façade + agentic layer for image *retrieval*

You are a senior Python architect building a new package, **`illustration`**, in Thor Whalen's ecosystem. Project root is `/Users/thorwhalen/Dropbox/py/proj/t/illustration/`. You have broad autonomy: plan thoroughly, make and record design decisions, do your own research when needed — but bias hard toward shipping a working vertical slice early (see *Definition of Done — Milestone 1*). Don't block on questions you can answer yourself by reading the research, studying the ecosystem packages, or reading provider docs. When a fork is genuinely consequential (e.g., the public shape of the escape-hatch API), pick a sensible default, record the decision and its rationale, and proceed.

## What this project is

`illustration` finds **existing** images to illustrate narrated video. It is **not** image *generation* — the companion narration→TTS→Ken-Burns pipeline already exists, and generating fresh images per beat is expensive. Instead, given narration text (a line, a beat, or a whole script), `illustration` *retrieves* fitting images from stock/open-media corpora. The technical domain is **cross-modal text-to-image retrieval** (semantic image search), enhanced with an **agentic / RAG-style curation loop**.

The system has two layers, and you build them in this order:

1. **The pure-search provider façade** — one unified interface over many heterogeneous image-search backends (Pexels, Openverse, Pixabay, Unsplash, Wikimedia Commons, etc.). This is the foundation and the first thing that must work.
2. **The agentic curation layer** — on top of pure search: it expands/varies queries, runs searches, inspects results (metadata *and* the actual pixels), decides whether to search more or finalize, and curates a final selection. This layer leans on AI services (text→text, image→text, embeddings), all accessed through the ecosystem's `aix` façade.

Terminology note to avoid confusion: in this doc a **provider** (or **backend**) is a pure search source; an **agent** is part of the agentic curation layer. (Thor sometimes calls providers "search agents" informally — they are not agents in the LLM sense.)

## What we already know (start here, don't re-derive)

A prior research pass established the current (2026) landscape — treat as given:

- **Google Custom Search JSON API is closed to new customers** and is being discontinued (EOL Jan 1, 2027). **Bing Search APIs were fully retired in August 2025** (all sub-APIs, including Image Search). Do **not** spend time trying to use either as a provider. The realistic "open-web breadth" fallback is a paid scraping API (SerpApi / DataForSEO / Oxylabs), pay-as-you-go-ish — treat as an optional, later, paid provider.
- The purpose-built free APIs are the right foundation:
  - **Pexels** — free, ~200 req/hr & 20k/month, no attribution required, photos *and* video. Easiest all-purpose start.
  - **Openverse** — free API; ~800M+ CC/public-domain works aggregated from Flickr, Smithsonian, NASA, museums, etc.; rich machine-generated tags and one-click attribution. Best breadth + metadata.
  - **Pixabay** — free commercial use; license explicitly permits downloading, **caching, and self-hosting** the files (and AI/ML use).
  - **Unsplash** — highest-quality photos, free commercial use, but stricter API guidelines around hotlinking/attribution/download-tracking.
  - **Wikimedia Commons** — no key, deep file-level metadata, per-asset license must be checked.
- **Licensing/cacheability is first-class, not an afterthought.** "Free for commercial use" generally means no model/property releases, no indemnification, and you assume legal risk; several licenses prohibit compiling their content into a competing search index. Crucially, because the Ken-Burns step downloads and locally processes the bytes, the **hotlink-vs-cache distinction matters per provider** (Pixabay permits caching; Unsplash's guidelines are stricter). Carry license, attribution, source URL, author, and a `cacheable` flag through to the result schema from day one.
- **Recommended retrieval pattern:** none of the free providers expose embeddings, so use provider **lexical/tag search (with LLM query expansion) as a cheap recall stage**, then re-embed and **rerank locally with a CLIP-family model (OpenCLIP / SigLIP)** as the precision stage. This keeps the semantic layer provider-independent. (Lexical-only is fine for Milestone 1; add the CLIP rerank in Milestone 2.)

## Required reading & process setup (Phase 0)

Before writing feature code:

1. **Read all three research reports** in `misc/docs/research/` and take structured notes into the repo (e.g., `docs/notes/` or a design doc). Distill the decisions they imply; cite them in your design doc rather than re-deriving.
2. **Read and follow the `github-memory` skill** for how to use GitHub in this project (repo setup, issues, PRs, commit/decision memory). Use it as the system of record for the plan, decisions, and progress throughout.
3. **Apply Thor's coding skills**: `python-coding-standards` (modularity, docstrings + doctests, informative errors, `check_requirements`, Mapping/MutableMapping store patterns, progressive disclosure) and `python-package-architecture` (project file layout, `pyproject.toml`, `argh` CLI dispatch, the dispatch-to-interface pattern). Match the ecosystem's idioms.
4. **Study the ecosystem façade packages** before designing the façade — `aix` (most important), `falaw`, and `denote` all solve "one clean interface over heterogeneous backends, with an escape hatch." Adopt their established idiom rather than inventing a new pattern. Locate them via the installed environment (`pip show <pkg>`) and/or GitHub. For the agentic layer, study **`ir`** for agentic design patterns.
5. **Survey the providers' actual APIs** (read their docs; light web fetching is fine). Produce the comparison tables described below.
6. **Write a short design doc** capturing: the provider comparison, the canonical-parameter mapping, the chosen escape-hatch design (with rejected alternatives and why), the result schema, and the milestone plan. Commit it. Then start building.

You may run your own deep research to fill gaps (specific provider params, CLIP-vs-SigLIP tradeoffs, agentic RAG loop patterns), but keep it scoped — shipping Milestone 1 takes priority over exhaustiveness.

## Layer 1 design problem — the provider façade

This is the heart of the early work. Do it carefully.

### Compare the backends, then design the common interface

Build a **provider × parameter matrix**: for each candidate provider (start with Pexels, Openverse, Pixabay, Unsplash, Wikimedia Commons; keep SerpApi/Flickr/Europeana/Smithsonian/NASA as later candidates), record auth method, the search endpoint, every search parameter it accepts, and its response schema.

From that, design the façade:

- **First positional argument is the query string.** Everything else is keyword.
- Identify the **intersection** of parameters supported across providers and choose **canonical names** for them. Likely candidates (verify against real docs, you decide the final set and names): number of results (`n` / `n_results` / `limit` — pick one), pagination (`page`), `orientation`, `size`, `color`, `safe` (safe-search), `lang`/`locale`, content type (photo / illustration / vector / video). Deliver a **canonical→native parameter mapping table** (canonical name → each provider's native parameter name, with notes on unsupported ones and how you degrade gracefully).
- **Normalize the output** into a single result schema (Pydantic v2; it's the SSOT). At minimum: `provider`, `id`, `url`, `thumbnail_url`, `width`, `height`, `tags`, `description`, `license`, `attribution`, `source_page_url`, `author`, and `cacheable: bool`. This schema is shared with the agentic layer downstream, so design it as the stable contract.

### The escape hatch (the part Thor specifically wants you to think about)

A pure façade exposes only the common interface — but we still want to reach a particular provider's special powers when needed. That's a deliberate, controlled violation of façade purity. Design the cleanest possible escape hatch. Evaluate at least these options against how `aix`/`falaw`/`denote` handle the same tension, and pick one (or a principled combination):

1. A typed common interface plus a `provider_params: dict` / `**provider_kwargs` passthrough merged into the native call.
2. A namespaced `extra` dict keyed by provider name (so a single call can carry per-provider overrides).
3. Per-provider Pydantic config objects; the façade accepts the canonical args and an optional provider-specific config.
4. A two-tier API: the unified façade for the common case, plus direct access to the underlying provider client/`raw_search` for full power (`facade.providers["pexels"]` …).
5. Curried/partial providers (preconfigured backends) à la the ecosystem's preset pattern.

State the rule for *when* a parameter is promoted from "provider-specific escape hatch" to "canonical façade argument" (e.g., once ≥N providers support it), so the interface evolves predictably rather than by accretion.

### Other façade requirements

- **Plugin/registry pattern**: each provider is a small plugin implementing a `search` Protocol; a registry maps name→provider; the façade dispatches. Open-closed — adding a provider must not touch the façade.
- **Caching** mirroring `falaw`: a SHA-256 key over `(provider, normalized_query, normalized_params)` → results, stored behind an injectable `MutableMapping` (`dol`). Default to a local store; make it swappable via dependency injection.
- **Config/secrets**: API keys from env/config, never hardcoded; fail with an informative error (`check_requirements`-style) when a provider's key is missing.
- **Respect each provider's TOS**: rate limits, and the hotlink-vs-cache rule reflected in the `cacheable` flag.
- **CLI** via `argh` per the package-architecture skill, so `illustration search "..."` works from the shell.

## Layer 2 — agentic curation (after Layer 1 is solid)

On top of pure search, build an agent loop: *expand/vary the query → search across providers → inspect candidates (metadata + the image itself) → score/rerank → decide to search more or finalize → curate the selection*. Take design cues from **`ir`**.

- **All AI services go through `aix`** — text→text (query expansion, critique, relevance judging), image→text (describe/caption a candidate), and embeddings (CLIP-style rerank). If `aix` lacks a needed capability (image→text is the likely gap; possibly embeddings), **add it to `aix`** following `aix`'s own conventions, and manage that contribution via the `github-memory` workflow.
- Add **cheap classical-CV pre-filters** before any VLM call (aspect ratio, brightness, blur via Laplacian variance, dominant color, face count) to avoid spending model calls on obviously unfit candidates.
- Make the loop **composable and inspectable**: prefer a declarative pipeline (meshed/`nw`-style), persist each stage's intermediate output so a run is auditable, and make the final selection editable/overridable by a human.
- **Sequence-level selection** (later): pick one image per beat while balancing relevance, cross-shot visual coherence, near-duplicate avoidance, and quality — MMR, `apricot-select` (submodular), `imagededup` (perceptual-hash), `pyiqa` (NR-IQA). Don't let this block earlier milestones.

## Definition of Done — Milestone 1 (reach this early)

A genuinely working vertical slice using **one free provider** (recommend **Openverse** for breadth/metadata, or **Pexels** for the simplest key flow):

- `illustration.search("a stormy harbour at dusk", n=10)` returns a list of normalized result objects (the shared schema), with license/attribution/`cacheable` populated.
- SHA-256-keyed caching works (second identical call hits the cache).
- Works from the CLI (`argh`).
- Has doctests/tests and informative errors for missing keys.
- The provider registry + façade are structured so a second provider is a drop-in addition.
- Design doc, decision log, and repo memory are committed via the `github-memory` workflow.

## Milestone roadmap (refine in your design doc)

- **M0 — Orient & set up**: read research + ecosystem packages, provider survey, design doc, package skeleton, GitHub setup.
- **M1 — One free provider end-to-end** (Definition of Done above).
- **M2 — Multi-provider façade**: add 2–3 providers, finalize the escape hatch, add local CLIP/SigLIP rerank on top of provider recall.
- **M3 — Agentic curation**: the loop via `aix` (+ `ir` patterns); add image→text to `aix` if missing.
- **M4 — Sequence selection & integration**: diversity/dedup/quality selection; an integration hook for the narration→Ken-Burns pipeline.

## Operating principles

Functional/declarative over imperative; composition over inheritance; facades, SSOT, dependency injection, open-closed, plugin architecture (don't be dogmatic). Pydantic v2 as schema source of truth. Progressive disclosure: trivial cases trivial, full power available. Commit often and keep the GitHub decision log current so the plan and rationale are always recoverable. Be autonomous: decide, record, proceed.
