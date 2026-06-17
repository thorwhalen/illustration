"""Tests for the CLI wrappers (offline, via a registered fake source)."""

import json

from illustration import cli
from illustration.base import RetrievalSource
from illustration.registry import register_source, unregister_source
from illustration.schema import ImageResult


class _CliSource(RetrievalSource):
    name = "clisrc"

    def _items(self, response):  # pragma: no cover
        return []

    def _normalize(self, item, *, query):  # pragma: no cover
        ...

    def search(self, query, *, n=10, api_key=None, native_params=None, **canonical):
        return [
            ImageResult(provider="clisrc", id=str(i), url=f"u{i}", title=f"Title {i}",
                        license="cc0", query=query)
            for i in range(n)
        ]


def test_cli_sources_lists_builtins():
    out = cli.sources()
    assert "openverse" in out and "pexels" in out


def test_cli_info_returns_json():
    out = cli.info("openverse")
    data = json.loads(out)
    assert data["name"] == "openverse" and data["requires_key"] is False


def test_cli_search_text(monkeypatch, tmp_path):
    monkeypatch.setenv("ILLUSTRATION_CACHE_DIR", str(tmp_path))
    register_source(_CliSource())
    try:
        out = cli.search("harbour", n=2, source="clisrc")
    finally:
        unregister_source("clisrc")
    assert "[clisrc]" in out
    assert "Title 0" in out and "cc0" in out


def test_cli_search_json(monkeypatch, tmp_path):
    monkeypatch.setenv("ILLUSTRATION_CACHE_DIR", str(tmp_path))
    register_source(_CliSource())
    try:
        out = cli.search("harbour", n=1, source="clisrc", json=True)
    finally:
        unregister_source("clisrc")
    data = json.loads(out)
    assert data[0]["provider"] == "clisrc"
