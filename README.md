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

1. **The provider façade** (this release) — one unified `search()` over many
   heterogeneous image-search backends (Openverse, Pexels, …), normalizing every
   result into one schema with license/attribution/cacheability first-class.
2. **An agentic curation layer** (forthcoming) — query expansion, multi-provider
   search, classical-CV + vision-LM inspection, reranking, and sequence-level
   selection, built on the `aix` AI façade and `ir` retrieval substrate.

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
| **pexels** | `PEXELS_API_KEY` | curated high-quality stock photos |

Pick a source (or several), and filter:

```python
illustration.search("harbour", source="openverse", orientation="landscape", size="large")
illustration.search("harbour", source=["openverse", "pexels"], n=5)   # per-source
```

Canonical filters (`orientation`, `size`, `safe`, `license_type`) translate to
each provider's native parameters and degrade gracefully where a provider
doesn't support one.

### Keys

Pexels needs a key (Openverse does not). Provide it however suits you:

```python
import os; os.environ["PEXELS_API_KEY"] = "..."      # env var
# or per-request (the bring-your-own-key seam, e.g. a web backend):
with illustration.using_credentials(pexels="..."):
    illustration.search("harbour", source="pexels")
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
license, license URL, attribution, and a `cacheable` flag. Aggregators disclaim
license accuracy, so gate on a known-good set when it matters:

```python
from illustration import license_allowlist
safe = license_allowlist(hits)                          # CC0/PD/BY/BY-SA default
safe = license_allowlist(hits, allow={"cc0", "pdm"})    # public-domain only
```

## License

MIT
