"""Tests for the source registry and the sources view."""

import pytest

from illustration.base import RetrievalSource
from illustration.errors import UnknownSourceError
from illustration.registry import (
    get_source,
    list_sources,
    register_source,
    sources,
    unregister_source,
)
from illustration.schema import ImageResult


class _Tiny(RetrievalSource):
    name = "tiny"

    def _items(self, response):
        return []

    def _normalize(self, item, *, query):  # pragma: no cover - unused
        return ImageResult(provider="tiny", id="x", url="u")


def test_builtins_registered():
    assert "openverse" in list_sources()
    assert "pexels" in list_sources()


def test_register_get_unregister():
    register_source(_Tiny())
    try:
        assert "tiny" in list_sources()
        assert get_source("tiny").name == "tiny"
    finally:
        unregister_source("tiny")
    assert "tiny" not in list_sources()


def test_unknown_source_raises():
    with pytest.raises(UnknownSourceError):
        get_source("does-not-exist")


def test_sources_view_dict_and_attr_access():
    assert sources["openverse"].name == "openverse"
    assert sources.openverse.name == "openverse"
    assert "openverse" in sources
    assert len(sources) >= 2


def test_sources_view_unknown_attr_raises_attribute_error():
    with pytest.raises(AttributeError):
        _ = sources.nonexistent


def test_register_without_name_errors():
    class _NoName(RetrievalSource):
        name = ""

        def _items(self, response):
            return []

        def _normalize(self, item, *, query):  # pragma: no cover
            ...

    with pytest.raises(ValueError):
        register_source(_NoName())
