"""Export the Python SSOT as committed JSON for the TypeScript twin (``ts/``).

``illustration`` ships twice: as this Python package and as the npm package
``illustration-search`` (``ts/``), which runs the same ``search()`` in a browser.
The two must agree on the result schema, the rights record, the licence
vocabulary, every provider's request vocabulary, and what each provider's
payload normalises into. None of that is re-authored on the TypeScript side:
this module writes it out as JSON, the TS build generates its types from the
schema and reads the registries as data, and its parity tests replay the
fixtures below and assert the same output byte for byte.

What lands in ``<out_dir>``:

- ``image-result.schema.json`` — :class:`~illustration.schema.ImageResult` as
  JSON Schema (the codegen input for the Zod type).
- ``sources.json`` — one record per registered source: endpoint, parameter
  names, paging caps, fixed params, auth style, canonical→native parameter
  names, and its :class:`~illustration.base.SourceInfo`.
- ``constants.json`` — ``RIGHTS_FIELDS``, the licence alias table, the default
  allowlist, façade defaults, credential lookups, and licence-normalisation
  cases (input → canonical code) the TS port must reproduce.
- ``fixtures/<source>.expected.json`` — derived from the hand-authored
  ``fixtures/<source>.payload.json`` (shared with ``conftest.py``): the
  normalised results, canonical→native translations for a fixed set of filter
  combinations, query/paging params, and the per-page clamp.

``tests/test_schema_export.py`` pins the committed directory to a fresh export,
so a schema or provider change that forgets to run ``illustration export-schema``
fails CI here, before the TS side can drift.

>>> from illustration.schema_export import CANONICAL_REQUEST_CASES
>>> all(isinstance(case, dict) for case in CANONICAL_REQUEST_CASES)
True
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from illustration.base import RetrievalSource, per_page_for
from illustration.config import (
    DFLT_LICENSE_ALLOWLIST,
    DFLT_N,
    DFLT_SOURCES,
    HTTP_TIMEOUT,
    MAX_PAGES,
)
from illustration.credentials import PROVIDER_CONSOLE_URLS, PROVIDER_ENV_VARS
from illustration.facade import _CANONICAL_PARAMS
from illustration.licensing import (
    LICENSE_ALIASES,
    RESTRICTION_TOKENS,
    normalize_license,
)
from illustration.registry import get_source, list_sources
from illustration.schema import RIGHTS_FIELDS, ImageResult

__all__ = [
    "export_schema",
    "CANONICAL_REQUEST_CASES",
    "QUERY_CASES",
    "LICENSE_CASES",
    "FIXTURE_QUERY",
]

#: The query every fixture is normalised under (it lands in ``ImageResult.query``).
FIXTURE_QUERY = "stormy harbour"

#: Filter combinations every source translates in its fixture. Chosen to hit
#: every canonical parameter, every ``choices`` guard (a valid and an invalid
#: value), a boolean coercion in both states, and the empty case.
CANONICAL_REQUEST_CASES: tuple[Mapping[str, Any], ...] = (
    {},
    {
        "orientation": "landscape",
        "size": "large",
        "safe": True,
        "license_type": "commercial",
        "color": "blue",
        "content_type": "photo",
    },
    {"orientation": "portrait", "size": "medium", "content_type": "illustration"},
    {"orientation": "square", "size": "small", "content_type": "vector"},
    {"safe": False},
    {"orientation": "diagonal", "size": "huge", "content_type": "hologram"},
    {"license_type": "all-cc", "color": "#ff0000"},
)

#: ``(query, page, per_page)`` triples every source builds query params for.
#: The ``Category:`` and ``File:`` forms exercise Wikimedia's routing; the
#: others are plain paging.
QUERY_CASES: tuple[tuple[str, int, int], ...] = (
    ("stormy harbour", 1, 10),
    ("stormy harbour", 3, 5),
    ("Category:Ships at dusk", 1, 20),
    ("File:Stormy Harbour.jpg|File:Dusk Pier.jpg", 1, 10),
)

#: ``n`` values whose per-page clamp every source records.
PER_PAGE_CASES: tuple[int, ...] = (1, 3, 10, 50, 500)

#: Licence spellings the TS ``normalizeLicense`` must fold identically.
LICENSE_CASES: tuple[str | None, ...] = (
    None,
    "",
    "   ",
    "by-sa",
    "BY",
    "  BY  ",
    "cc0",
    "CC0 1.0",
    "cc-0",
    "cc-zero",
    "cc-by-sa-4.0",
    "CC BY-SA 4.0",
    "cc-by-nc-nd-2.0",
    "cc_by_3.0",
    "Pexels License",
    "Pixabay License",
    "public domain",
    "Public Domain Mark",
    "pdm",
    "cc-pdm",
    "sampling+",
    "by-nc",
    "CC-BY-SA-v2.5",
)


def export_schema(
    out_dir: "str | Path | None" = None,
    *,
    sources: "Iterable[str] | None" = None,
) -> list[Path]:
    """Write the JSON contract under ``out_dir``; return the paths written.

    ``out_dir`` defaults to the ``schema/`` directory of *this checkout* (the
    one holding the hand-authored ``fixtures/*.payload.json``). This is
    repository tooling: with no checkout — an installed wheel, or a directory
    with no payload fixtures — it refuses rather than scattering a partial
    ``schema/`` tree wherever the shell happens to be.

    ``sources`` defaults to every registered source. A source with no
    ``fixtures/<name>.payload.json`` gets no expected-fixture file (its
    registry record is still written), so a provider can be registered before
    its canned payload exists, but the TS parity suite will then have nothing
    to replay for it.
    """
    out = _resolve_out_dir(out_dir)
    fixtures_dir = out / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    names = list(sources) if sources is not None else list_sources()

    written = [
        _write(out / "image-result.schema.json", ImageResult.model_json_schema()),
        _write(out / "sources.json", [_source_record(get_source(n)) for n in names]),
        _write(out / "constants.json", _constants()),
    ]
    for name in names:
        payload_path = fixtures_dir / f"{name}.payload.json"
        if not payload_path.exists():
            continue
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        written.append(
            _write(
                fixtures_dir / f"{name}.expected.json",
                _fixture_record(get_source(name), payload),
            )
        )
    return written


def _resolve_out_dir(out_dir: "str | Path | None") -> Path:
    if out_dir is not None:
        return Path(out_dir)
    checkout = Path(__file__).resolve().parent.parent / "schema"
    if not any(checkout.glob("fixtures/*.payload.json")):
        raise FileNotFoundError(
            "export-schema is repository tooling: no schema/fixtures/*.payload.json "
            f"next to this package ({checkout}). Run it from a checkout of "
            "thorwhalen/illustration, or pass out_dir explicitly."
        )
    return checkout


# --- records ------------------------------------------------------------------


def _source_record(src: RetrievalSource) -> dict:
    """Everything about a source that is declared rather than coded."""
    return {
        "name": src.name,
        "endpoint": src.endpoint,
        "query_param": src.query_param,
        "page_param": src.page_param,
        "per_page_param": src.per_page_param,
        "max_per_page": src.max_per_page,
        "min_per_page": src.min_per_page,
        "fixed_params": dict(src.fixed_params),
        "auth": _auth_record(src),
        "params": {
            name: _param_record(src.param_map.get(name)) for name in _CANONICAL_PARAMS
        },
        "info": src.info.to_dict(),
        "env_var": PROVIDER_ENV_VARS.get(src.name),
        "console_url": PROVIDER_CONSOLE_URLS.get(src.name),
    }


def _auth_record(src: RetrievalSource) -> dict:
    """How the key travels, derived from the hooks rather than declared twice."""
    probe = "PROBE-KEY"
    headers = src._auth_headers(probe)
    params = src._auth_params(probe)
    if headers:
        (name, value), *_ = headers.items()
        return {"kind": "header", "name": name, "format": value.replace(probe, "{key}")}
    if params:
        (name, value), *_ = params.items()
        return {
            "kind": "query",
            "name": name,
            "format": str(value).replace(probe, "{key}"),
        }
    return {"kind": "none", "name": None, "format": None}


def _param_record(spec: Any) -> "dict | None":
    """A canonical parameter's native name and guard; ``None`` when unsupported.

    ``coerce`` is a function and cannot be exported; the fixture's request
    cases are what pin its behaviour on the other side.
    """
    if spec is None:
        return None
    if isinstance(spec, str):
        return {"name": spec, "choices": None, "coerce": False}
    if isinstance(spec, Mapping):
        choices = spec.get("choices")
        return {
            "name": spec.get("name"),
            "choices": sorted(choices) if choices is not None else None,
            "coerce": callable(spec.get("coerce")),
        }
    if callable(spec):
        return {"name": None, "choices": None, "coerce": True}
    raise TypeError(f"unexportable param_map spec: {spec!r}")


def _constants() -> dict:
    return {
        "rights_fields": list(RIGHTS_FIELDS),
        "canonical_params": list(_CANONICAL_PARAMS),
        "license_aliases": dict(LICENSE_ALIASES),
        "restriction_tokens": sorted(RESTRICTION_TOKENS),
        "default_license_allowlist": sorted(DFLT_LICENSE_ALLOWLIST),
        "defaults": {
            "n": DFLT_N,
            "sources": list(DFLT_SOURCES),
            "max_pages": MAX_PAGES,
            "http_timeout_s": HTTP_TIMEOUT,
        },
        "provider_env_vars": dict(PROVIDER_ENV_VARS),
        "provider_console_urls": dict(PROVIDER_CONSOLE_URLS),
        "license_normalization_cases": [
            {"input": value, "output": normalize_license(value)}
            for value in LICENSE_CASES
        ],
    }


def _fixture_record(src: RetrievalSource, payload: Mapping[str, Any]) -> dict:
    """What this package makes of a canned payload and of each request case."""
    expected = []
    for item in src._items(payload):
        result = src._safe_normalize(item, query=FIXTURE_QUERY)
        if result is not None:
            expected.append(result.model_dump(mode="json"))
    requests = []
    for case in CANONICAL_REQUEST_CASES:
        native, dropped = src._translate(case)
        requests.append({"canonical": dict(case), "native": native, "dropped": dropped})
    return {
        "query": FIXTURE_QUERY,
        "expected": expected,
        "requests": requests,
        "query_params": [
            {
                "query": query,
                "page": page,
                "per_page": per_page,
                "params": src._query_params(query, page=page, per_page=per_page),
            }
            for query, page, per_page in QUERY_CASES
        ],
        "per_page": [
            {"n": n, "per_page": per_page_for(src, n)} for n in PER_PAGE_CASES
        ],
    }


# --- io -------------------------------------------------------------------------


def _write(path: Path, obj: Any) -> Path:
    """Write ``obj`` as deterministic JSON (sorted keys, stable formatting)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
