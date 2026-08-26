# illustration — agent & contributor guide

`illustration` is **cross-modal text-to-image retrieval**: given narration text
(a beat, a panel, a script line), it *finds an existing image* in stock /
open-media corpora. It is **not an image generator** and must not become one —
generation lives elsewhere in the ecosystem (`falaw` / fal.ai). Everything here
assumes the image already exists and someone else owns it.

## Start here

- **[`.claude/skills/illustration`](.claude/skills/illustration/SKILL.md)** — the
  consumer-facing skill: how to *use* the package to find images for beats, and
  the licence/attribution obligations that come with them. Read that first if
  you are a caller rather than a contributor.
- **[`README.md`](README.md)** — the human-facing tour (same material, longer).
- **[`misc/docs/design/illustration_design.md`](misc/docs/design/illustration_design.md)**
  — provider comparison, canonical parameter mapping, escape-hatch design,
  result schema, roadmap. The rationale for most of what follows.

## The mandate (do not drift from this)

**Retrieval, not generation.** The package's job ends at *choosing* images.
Anything downstream — rendering, pacing, timelines, TTS — belongs to the
ecosystem packages `illustration` hooks into, never inlined here.

Two consequences that have already shaped the code:

- `illustration.video` renders through **`burns` directly**, not through
  `walkthru`'s reelee render target — routing through reelee would create an
  `illustration → reelee → illustration` cycle. Keep it that way.
- `illustration.persistence` maps onto **`lacing`** rather than growing an
  annotation store of its own. If a general "selection track" facade proves
  worth sharing, it belongs upstream in `lacing`.

## Architecture — two layers

**Layer 1, the provider façade.** One `search()` over heterogeneous backends,
normalizing every hit into one schema with licence/attribution/cacheability
first-class.

**Layer 2, agentic curation.** Query expansion → multi-provider search → rank
fusion → classical-CV pre-filter → SigLIP rerank → VLM judge, inside a
budget-bounded corrective loop; plus sequence-level selection across a whole
storyboard.

| Module | Owns | Heavy deps |
|---|---|---|
| `schema` | `ImageResult` (Pydantic v2, the SSOT), `RIGHTS_FIELDS`, `license_allowlist`, `to_search_hit` | pure |
| `licensing` | `normalize_license` — one canonical code from four provider vocabularies | pure |
| `base` | `RetrievalSource` ABC + `SourceInfo`; paging, HTTP, error translation | `requests` (lazy) |
| `providers/` | `openverse`, `wikimedia`, `pexels`, `pixabay` adapters | — |
| `registry` | `register_source` / `get_source` / `sources` (the open-closed seam) | pure |
| `facade` | `search()` — the front door | pure |
| `translation` | `make_param_translator`: canonical filters → native params | pure |
| `caching` | `SearchCache`, SHA-256 content-addressed, over an injectable `dol` store | `dol` |
| `credentials` | key precedence + `using_credentials` BYO-key `ContextVar` | `config2py` |
| `config` | XDG dirs, every default constant, `package_version` / `user_agent` | pure |
| `errors` | the `IllustrationError` tree | pure |
| `reranking` | SigLIP-2 cross-modal rerank + cached image embeddings | `[rerank]` |
| `expansion` | query expansion / refinement seams | `[curate]` |
| `inspection` | CV pre-filters, NSFW gate, VLM caption/judge rubric | `[curate]`/`[rerank]` |
| `curation` | `curate()` — the bounded CRAG loop, `Budget` | `[curate]` |
| `sequence` | `select_sequence` / `curate_sequence`, in-house MMR + DCT pHash | `numpy` |
| `persistence` | selections as `lacing` standoff annotations, OTIO export | `[persist]` |
| `video` | `render_sequence_video` (burns), `to_walkthru_document` | `[video]` |
| `cli` / `__main__` | thin `argh` wrappers; no business logic | `argh` |
| `_imageio` | the single image fetch/decode path (fail-soft) | `requests`/`Pillow` |

## The licence/attribution invariant

This package hands callers **third-party media under varying licences**. That is
its defining constraint, not a footnote.

- `ImageResult` carries `license`, `license_url`, `attribution`,
  `source_page_url`, `author`, `author_url`, `cacheable` — populated from day
  one, by every provider. **A new provider that cannot populate them does not
  ship.** Never add a normalizer that leaves `license`/`attribution` empty when
  the provider supplies them.
- Aggregators (Openverse, Wikimedia) disclaim licence accuracy, so the gate is
  the caller's: `license_allow=` on `search()`, or `license_allowlist(hits)`.
  It is **opt-in and off by default** — do not quietly make it default-on
  either; a silent filter is worse than an explicit one.
- `license_allowlist` normalises **both sides** through
  `licensing.normalize_license` before comparing, so the four provider dialects
  (`by-sa` from Openverse, `cc-by-sa-4.0` / `CC BY-SA 4.0` from Commons,
  `Pixabay License`, `Pexels License`) all reach the same canonical code. Before
  #13 the comparison was exact and Wikimedia + Pixabay silently gated to `[]`.
  **The normaliser's invariant is that it may never drop a restriction token**
  — it removes only a `cc-` prefix and a trailing version, and every other
  spelling is a hand-written entry in `LICENSE_ALIASES`. An unrecognised code
  survives unchanged and therefore fails the gate: unknown is not allowed.
  `tests/test_licensing.py` asserts both directions and is mutation-tested;
  widening the alias table is a decision, never a convenience.
- **The rights record survives persistence.** `RIGHTS_FIELDS` (in `schema`) is
  the SSOT for the seven fields that answer "may we ship this, and whom must we
  credit?", and `persistence._CandidateRef` declares every one of them under the
  *same names* so no consumer needs a rename table. They are optional with
  defaults, which is what makes the addition additive (no lacing migration);
  `cacheable` is `bool | None` so "not recorded" stays distinguishable from
  "recorded as False". Adding a field to `RIGHTS_FIELDS` without adding it to
  `_CandidateRef` turns `tests/test_persistence.py` red — pydantic would
  otherwise ignore the undeclared key and lose it silently.

## Adding a provider (open-closed)

Subclass `RetrievalSource`, declare `endpoint` / `query_param` /
`per_page_param` / `max_per_page` (and `min_per_page` if the API rejects a small
page — Pixabay's documented minimum is 3) / `param_map` / `info`, implement `_items` and
`_normalize`, then `register_source(MySource())`. The façade is untouched.
Auth goes in `_auth_headers` (header key) or `_auth_params` (query-param key);
non-standard pagination in `_page_params`; mandatory constants in
`fixed_params`. Add the provider's env var to `credentials.PROVIDER_ENV_VARS`
and its key-signup URL to `PROVIDER_CONSOLE_URLS`.

**Parameter promotion rule:** a filter becomes a canonical `search()` argument
only once **two or more** providers support it. Until then it stays in the
escape hatch (`provider_params=` / flat `**provider_kwargs`). `safe` and
`license_type` are the deliberate exceptions.

## Optional extras

`pip install illustration[<extra>]` — the base install is `pydantic`,
`requests`, `dol`, `config2py`, `argh` only.

| extra | pulls | for |
|---|---|---|
| `rerank` | transformers, torch, pillow, numpy | SigLIP-2 rerank + the NSFW gate |
| `curate` | aix, ir, pillow, numpy | the agentic loop (LLM/VLM via `aix`, fusion via `ir`) |
| `sequence` | apricot-select | optional submodular shortlisting seam |
| `video` | burns, walkthru | the render + `DemoDocument` hooks |
| `persist` | lacing | standoff-annotation persistence (`lacing[otio]` for OTIO) |
| `test` | ir, lacing, opentimelineio, burns, walkthru, numpy, pillow | what CI installs so the offline suite *runs* instead of skipping |

Every heavy dependency is imported **lazily, inside the function that needs it**
— `import illustration` must never pull torch, aix, lacing, burns or walkthru.
There are doctests and tests that depend on this; keep them green.

## Tests are offline, always

`python -m pytest -q` from the repo root (that is also how you get the current
test count — don't pin a number in a doc, it only drifts). `conftest.py`
provides `FakeSession` / `FakeResponse` plus a canned payload fixture per
provider; **no test ever hits the network and no test ever spends money.**

That first half is *enforced*, not merely promised: `conftest.py`'s autouse
`_no_outbound_network` refuses (and records) any non-local `connect` or DNS
lookup, and fails the test at teardown naming the host — because this package
degrades a failed fetch to `None` or to a shorter result list on purpose, so an
accidentally-networked test would otherwise stay green. Reach for the fakes, or
mark a deliberately-live test `@pytest.mark.live` (the opt-in SigLIP inference
test is the only one). `tests/test_offline_guard.py` keeps the guard armed.

Every paid step in Layer 2 is an injectable seam (`search_fn`, `expander`,
`refiner`, `scorer`, `describe`, `grader`, `checks`, `fetch`, `per_beat`,
`embed`, `hasher`, `relevance`, `shortlist`) precisely so the suite can run the
real control flow with stubs. When you add a paid call, add the seam with it.

`pytest` runs `--doctest-modules` over `illustration/` as well as `tests/`, so a
docstring example is a test — mark network/extra-dependent ones `# doctest: +SKIP`.

## Conventions

- Favour functional style; small focused helpers (`_underscore` for
  module-private, inner functions for single-use). `dataclasses` for plain data,
  Pydantic v2 for the wire/contract models.
- Arguments beyond the 3rd position are keyword-only; most public functions here
  are keyword-only from the 2nd.
- **No magic numbers outside `config.py`** (or a named module constant where the
  value is module-local, e.g. `DFLT_ALPHA`, `DFLT_PHASH_THRESHOLD`).
- Every module needs a top-level docstring (ruff enforces `D100`; auto-extracted
  for the published docs).
- Informative errors from the `IllustrationError` tree — a missing key names the
  key, how to set it, and where to get one, and never logs the value.
- `__version__` is read from installed distribution metadata via
  `config.package_version()`. **Never hardcode it** — `pyproject.toml` is the
  SSOT and the wads release job bumps it.

## CI

`.github/workflows/ci.yml` calls the `i2mint/wads` reusable workflow; all
configuration is `[tool.wads.ci.*]` in `pyproject.toml` (extras `dev,test`,
Python 3.10 + 3.12, Windows too, ruff on). **A push to the default branch
publishes to PyPI and bumps the version** — do not re-run a default-branch
workflow run casually.
