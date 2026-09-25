"""The committed ``schema/`` directory is a fresh export, and every source has a fixture.

``ts/`` (the npm package ``illustration-search``) is generated from and tested
against ``schema/``. If the Pydantic model, a provider's declared vocabulary, the
licence tables or a canned payload change without ``illustration export-schema``
being re-run, the TypeScript side keeps building against the old contract and
nothing on that side can notice. So the drift guard lives here, on the side that
changed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from illustration.registry import list_sources
from illustration.schema import RIGHTS_FIELDS
from illustration.schema_export import export_schema

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schema"


def _fresh_export(tmp_path: Path) -> Path:
    out = tmp_path / "schema"
    fixtures = out / "fixtures"
    fixtures.mkdir(parents=True)
    for payload in (SCHEMA_DIR / "fixtures").glob("*.payload.json"):
        (fixtures / payload.name).write_bytes(payload.read_bytes())
    export_schema(out)
    return out


def _generated_files(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*.json"))
        if not p.name.endswith(".payload.json")
    }


def test_committed_schema_is_up_to_date(tmp_path):
    fresh = _generated_files(_fresh_export(tmp_path))
    committed = _generated_files(SCHEMA_DIR)
    stale = sorted(
        name for name in fresh | committed if fresh.get(name) != committed.get(name)
    )
    assert not stale, (
        f"schema/ is stale for {stale}; run `illustration export-schema` and commit."
    )


def test_export_is_deterministic(tmp_path):
    first = _generated_files(_fresh_export(tmp_path / "a"))
    second = _generated_files(_fresh_export(tmp_path / "b"))
    assert first == second


@pytest.mark.parametrize("name", list_sources())
def test_every_registered_source_has_a_payload_and_an_expected_fixture(name):
    """A provider without a canned payload has no parity test on the TS side."""
    assert (SCHEMA_DIR / "fixtures" / f"{name}.payload.json").exists()
    expected = json.loads(
        (SCHEMA_DIR / "fixtures" / f"{name}.expected.json").read_text()
    )
    assert expected["expected"], f"{name}: the canned payload normalises to nothing"
    for result in expected["expected"]:
        # the rights record must reach the TS side under the same names
        assert set(RIGHTS_FIELDS) <= set(result)


def test_sources_json_lists_every_registered_source():
    names = {s["name"] for s in json.loads((SCHEMA_DIR / "sources.json").read_text())}
    assert names == set(list_sources())
