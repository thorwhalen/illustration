"""Tests for the local rerank precision stage.

The orchestration and missing-dependency paths are tested OFFLINE with no torch.
Cache tests need numpy (importorskip). A real SigLIP inference test runs only
when the [rerank] extra is installed AND ILLUSTRATION_LIVE_RERANK=1 (it downloads
a model and hits the network), mirroring the live-API test convention.
"""

import os

import pytest

from illustration import facade
from illustration.base import RetrievalSource
from illustration.errors import RerankDependencyError
from illustration.reranking import (
    SiglipScorer,
    _embedding_key,
    check_rerank_requirements,
    make_siglip_scorer,
    rerank,
)
from illustration.registry import register_source, unregister_source
from illustration.schema import ImageResult


def _results(n):
    return [ImageResult(provider="p", id=str(i), url=f"u{i}", thumbnail_url=f"t{i}") for i in range(n)]


# --- orchestration (no torch) ----------------------------------------------


def test_rerank_sorts_and_sets_scores():
    ranked = rerank("q", _results(4), scorer=lambda q, rs: [0.2, 0.9, 0.1, 0.5])
    assert [r.id for r in ranked] == ["1", "3", "0", "2"]
    assert [r.score for r in ranked] == [0.9, 0.5, 0.2, 0.1]


def test_rerank_empty_returns_empty_without_scorer():
    # must not build a model for an empty candidate set
    assert rerank("q", []) == []


def test_rerank_descending_false():
    ranked = rerank("q", _results(3), scorer=lambda q, rs: [0.2, 0.9, 0.1], descending=False)
    assert [r.id for r in ranked] == ["2", "0", "1"]


def test_rerank_score_count_mismatch_raises():
    with pytest.raises(ValueError, match="scores for"):
        rerank("q", _results(3), scorer=lambda q, rs: [0.1, 0.2])


def test_rerank_does_not_mutate_inputs():
    original = _results(2)
    rerank("q", original, scorer=lambda q, rs: [0.1, 0.9])
    assert all(r.score is None for r in original)  # copies, not in-place


def test_search_rerank_with_callable_scorer():
    class _Stub(RetrievalSource):
        name = "rerankstub"

        def _items(self, response):  # pragma: no cover
            return []

        def _normalize(self, item, *, query):  # pragma: no cover
            ...

        def search(self, query, *, n=10, api_key=None, native_params=None, **canonical):
            return [ImageResult(provider="rerankstub", id=str(i), url=f"u{i}") for i in range(n)]

    register_source(_Stub())
    try:
        hits = facade.search("q", n=3, source="rerankstub", cache=False,
                             rerank=lambda q, rs: [0.1, 0.5, 0.3])
    finally:
        unregister_source("rerankstub")
    assert [r.id for r in hits] == ["1", "2", "0"]
    assert hits[0].score == 0.5


# --- missing-dependency path (no torch) ------------------------------------


def test_check_requirements_raises_when_missing(monkeypatch):
    monkeypatch.setattr("illustration.reranking._importable", lambda m: False)
    with pytest.raises(RerankDependencyError) as exc:
        check_rerank_requirements()
    assert "illustration[rerank]" in str(exc.value)


def test_make_siglip_scorer_raises_when_missing(monkeypatch):
    monkeypatch.setattr("illustration.reranking._importable", lambda m: False)
    with pytest.raises(RerankDependencyError):
        make_siglip_scorer()


def test_embedding_key_is_stable_and_distinct():
    k = _embedding_key("model-a", "http://x/i.jpg")
    assert k == _embedding_key("model-a", "http://x/i.jpg")
    assert k != _embedding_key("model-b", "http://x/i.jpg")  # model in the key
    assert k != _embedding_key("model-a", "http://x/j.jpg")  # url in the key


# --- cache behavior (needs numpy) ------------------------------------------


def test_siglip_scorer_uses_embedding_cache():
    np = pytest.importorskip("numpy")
    calls = {"n": 0}

    class _StubScorer(SiglipScorer):
        def _embed_image_url(self, url, model, processor):  # bypass the real model
            calls["n"] += 1
            return np.array([1.0, 0.0, 0.0], dtype="float32")

    store = {}
    scorer = _StubScorer(model="m", cache=store)
    r = ImageResult(provider="p", id="1", url="http://x/i.jpg", thumbnail_url="http://x/t.jpg")
    v1 = scorer._image_embedding(r, model=None, processor=None)  # miss -> embeds + stores
    v2 = scorer._image_embedding(r, model=None, processor=None)  # hit -> from store
    assert calls["n"] == 1  # embedded once
    assert np.allclose(v1, v2)
    assert len(store) == 1


def test_image_field_fallback_and_none():
    np = pytest.importorskip("numpy")
    seen = []

    class _StubScorer(SiglipScorer):
        def _embed_image_url(self, url, model, processor):
            seen.append(url)
            return np.array([1.0, 0.0], dtype="float32")

    scorer = _StubScorer(model="m", cache={})
    # thumbnail present -> thumbnail used
    scorer._image_embedding(
        ImageResult(provider="p", id="1", url="full1", thumbnail_url="thumb1"),
        model=None, processor=None,
    )
    # thumbnail None -> falls back to .url
    scorer._image_embedding(
        ImageResult(provider="p", id="2", url="full2", thumbnail_url=None),
        model=None, processor=None,
    )
    assert seen == ["thumb1", "full2"]
    # neither url present -> None embedding (=> -1.0 score downstream), no fetch
    none_url = ImageResult.model_construct(provider="p", id="3", url=None, thumbnail_url=None)
    assert scorer._image_embedding(none_url, model=None, processor=None) is None


def test_invalid_image_field_rejected_at_construction():
    with pytest.raises(ValueError, match="image_field"):
        SiglipScorer(model="m", cache={}, image_field="not_a_field")


def test_l2_normalize_zero_and_unit():
    np = pytest.importorskip("numpy")
    from illustration.reranking import _l2_normalize

    assert np.allclose(_l2_normalize(np.zeros(3)), np.zeros(3))  # zero-norm guard, no NaN
    out = _l2_normalize(np.array([3.0, 4.0]))  # 3-4-5 triangle
    assert np.allclose(out, [0.6, 0.8]) and abs(float(np.linalg.norm(out)) - 1.0) < 1e-6


def test_fetch_image_happy_and_failure(monkeypatch):
    np = pytest.importorskip("numpy")  # noqa: F841
    Image = pytest.importorskip("PIL.Image")
    import io

    from illustration import reranking

    # a tiny real PNG as response bytes
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (10, 20, 30)).save(buf, format="PNG")
    png = buf.getvalue()

    class _Resp:
        content = png

        def raise_for_status(self):
            pass

    monkeypatch.setattr("requests.get", lambda url, **kw: _Resp())
    img = reranking._fetch_image("http://x/i.png")
    assert img is not None and img.size == (4, 4) and img.mode == "RGB"

    def _boom(url, **kw):
        raise ConnectionError("down")

    monkeypatch.setattr("requests.get", _boom)
    assert reranking._fetch_image("http://x/i.png") is None  # failure -> None, not raise


# --- real SigLIP inference (opt-in; downloads a model + hits the network) ---

_LIVE = os.environ.get("ILLUSTRATION_LIVE_RERANK") == "1"


@pytest.mark.skipif(not _LIVE, reason="set ILLUSTRATION_LIVE_RERANK=1 to run (downloads a model)")
def test_live_siglip_rerank():
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    pytest.importorskip("PIL")
    hits = facade.search("a small wooden sailboat on calm water", n=4, cache=False,
                         source="openverse")
    if not hits:
        pytest.skip("no recall results to rerank")
    ranked = rerank("a small wooden sailboat on calm water", hits)
    assert all(r.score is not None for r in ranked)
    assert all(ranked[i].score >= ranked[i + 1].score for i in range(len(ranked) - 1))
