"""Tests for the ImageResult schema and helpers."""

import pytest

from illustration.schema import ImageResult, check_attributions, license_allowlist


def test_defaults():
    r = ImageResult(provider="p", id="1", url="u")
    assert r.tags == []
    assert r.raw == {}
    assert r.cacheable is False
    assert r.score is None


def test_roundtrip_dump_validate():
    r = ImageResult(provider="p", id="1", url="u", license="cc0", tags=["a"], raw={"x": 1})
    again = ImageResult.model_validate(r.model_dump())
    assert again == r


def test_license_allowlist_default():
    a = ImageResult(provider="p", id="1", url="u", license="cc0")
    b = ImageResult(provider="p", id="2", url="u", license="by-nc")
    c = ImageResult(provider="p", id="3", url="u", license=None)
    kept = license_allowlist([a, b, c])
    assert [r.id for r in kept] == ["1"]


def test_license_allowlist_custom_and_case_insensitive():
    a = ImageResult(provider="p", id="1", url="u", license="BY-NC")
    kept = license_allowlist([a], allow={"by-nc"})
    assert [r.id for r in kept] == ["1"]


# --- check_attributions (illustration#22) ------------------------------------


def test_check_attributions_flags_licence_less_credit():
    bare_name = ImageResult(provider="wikimedia", id="1", url="u", license="by-sa",
                             attribution="EliziR")
    proper = ImageResult(provider="wikimedia", id="2", url="u", license="by-sa",
                          attribution="Alice / CC BY-SA 4.0, via Wikimedia Commons")
    no_attribution = ImageResult(provider="wikimedia", id="3", url="u", license="by-sa",
                                  attribution=None)
    assert [r.id for r in check_attributions([bare_name, proper, no_attribution])] == [
        "1", "3",
    ]


def test_check_attributions_does_not_flag_unlicensed_results():
    # Nothing to name a licence *for* -- license_allowlist already handles
    # "no license", so check_attributions stays silent rather than duplicating it.
    r = ImageResult(provider="p", id="1", url="u", license=None, attribution=None)
    assert check_attributions([r]) == []


def test_check_attributions_is_read_only():
    # A regression audit helper must never mutate what it inspects.
    r = ImageResult(provider="p", id="1", url="u", license="by-sa", attribution="Bob")
    before = r.model_copy()
    check_attributions([r])
    assert r == before


def test_to_search_hit_bridges_to_ir():
    ir = pytest.importorskip("ir")
    r = ImageResult(provider="openverse", id="abc", url="https://x/i.jpg",
                    description="a harbour", score=0.5)
    hit = r.to_search_hit()
    assert isinstance(hit, ir.SearchHit)
    assert hit.source == "openverse"
    assert hit.artifact_id == "abc"  # provider-native id; source carries provenance
    assert hit.score == 0.5
    assert hit.metadata["url"] == "https://x/i.jpg"  # full result rides in metadata
    # the disclosure pointer must resolve to the image URL (ir scans POINTER_KEYS)
    assert hit.pointer == "https://x/i.jpg"


# --- check_attributions: the credit must name *this* licence ------------------
@pytest.mark.parametrize(
    "license,attribution",
    [
        ("by-sa", "© Jane Doe"),  # a rights notice, not a licence
        ("by-sa", "Copyright Jane Doe"),
        ("by", "Jane Doe / CC0, via Wikimedia Commons"),  # a different licence
        ("by-sa", "Jane Doe / Public domain"),
        ("cc-by-sa-4.0", "Photo: CC Sabathia"),  # "CC" as a name, no code
        ("by-nc", "Jane / CC BY 4.0"),  # drops the NC restriction
    ],
)
def test_check_attributions_flags_credit_naming_the_wrong_or_no_licence(
    license, attribution
):
    r = ImageResult(provider="p", id="1", url="u", license=license,
                    attribution=attribution)
    assert check_attributions([r]) == [r]


@pytest.mark.parametrize(
    "license,attribution",
    [
        ("by-sa", "Alice / CC BY-SA 4.0, via Wikimedia Commons"),
        ("cc-by-sa-4.0", "Jane, CC-BY-SA-4.0"),
        ("by-sa", "Jane Doe, Creative Commons Attribution-ShareAlike 4.0"),
        ("by-nc-nd", "Jane / CC BY-NC-ND 3.0"),
        ("CC BY-SA 3.0 DE", "Jane / CC BY-SA 3.0 DE"),  # jurisdiction port
        ("by-sa", "Jane / CC BY - SA"),
        ("CC0 1.0", "Joost Evers / Anefo / CC0, via Wikimedia Commons"),
        ("Pixabay License", "Jane on Pixabay (Pixabay License)"),
    ],
)
def test_check_attributions_passes_credit_naming_its_licence(license, attribution):
    r = ImageResult(provider="p", id="1", url="u", license=license,
                    attribution=attribution)
    assert check_attributions([r]) == []


def test_check_attributions_accepts_the_licence_url_in_the_credit():
    url = "https://creativecommons.org/licenses/by-sa/4.0/"
    r = ImageResult(provider="p", id="1", url="u", license="by-sa",
                    license_url=url, attribution=f"Jane Doe ({url})")
    assert check_attributions([r]) == []
