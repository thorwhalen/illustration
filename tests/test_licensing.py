"""Tests for licence-code normalisation and the gate it feeds (offline, free).

Two halves, and the second is the one that matters. The first checks that the
four provider vocabularies fold onto one code. The second checks the safety
invariant in the other direction: normalisation must never turn a restricted
licence into an allowed one. A permissive bug here ships someone else's
non-commercial photograph into a commercial video.
"""

import pytest

from illustration.config import DFLT_LICENSE_ALLOWLIST
from illustration.licensing import (
    LICENSE_ALIASES,
    RESTRICTION_TOKENS,
    normalize_license,
)
from illustration.providers.openverse import OpenverseSource
from illustration.providers.pexels import PexelsSource
from illustration.providers.pixabay import PixabaySource
from illustration.providers.wikimedia import WikimediaSource
from illustration.schema import ImageResult, license_allowlist


# --- normalisation ----------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Openverse already speaks the canonical dialect
        ("by-sa", "by-sa"),
        ("cc0", "cc0"),
        ("pdm", "pdm"),
        # Wikimedia's `License` and its `LicenseShortName` fallback
        ("cc-by-sa-4.0", "by-sa"),
        ("CC BY-SA 4.0", "by-sa"),
        ("cc-by-3.0", "by"),
        ("CC0 1.0", "cc0"),
        ("public domain", "pdm"),
        ("PD", "pdm"),
        # single-licence providers
        ("Pixabay License", "pixabay-license"),
        ("Pexels License", "pexels-license"),
        # whitespace / case / separators
        ("  BY  ", "by"),
        ("CC_BY_SA_4.0", "by-sa"),
        # absent stays absent — an unlicensed hit is never a code
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_normalize_license(raw, expected):
    assert normalize_license(raw) == expected


def test_unknown_code_is_left_alone_not_guessed():
    # Unrecognised means "not allowed", which requires the code to survive
    # unchanged rather than being coerced toward something familiar.
    assert normalize_license("PD-US-expired") == "pd-us-expired"
    assert normalize_license("some-bespoke-museum-terms") == "some-bespoke-museum-terms"


# --- the safety invariant ---------------------------------------------------

RESTRICTED = [
    "by-nc",
    "by-nd",
    "by-nc-sa",
    "by-nc-nd",
    "cc-by-nc-4.0",
    "cc-by-nd-4.0",
    "CC BY-NC-SA 3.0",
    "cc-by-nc-nd-4.0",
    "sampling",
    "nc-sampling+",
]


@pytest.mark.parametrize("raw", RESTRICTED)
def test_normalisation_never_drops_a_restriction_token(raw):
    normalized = normalize_license(raw)
    present = {t for t in RESTRICTION_TOKENS if t in raw.lower().split("-")}
    assert present, f"fixture {raw!r} carries no restriction token to preserve"
    assert present <= set(normalized.split("-"))


@pytest.mark.parametrize("raw", RESTRICTED)
def test_restricted_licences_never_pass_the_default_gate(raw):
    r = ImageResult(provider="p", id="1", url="u", license=raw)
    assert license_allowlist([r]) == []


def test_no_alias_maps_a_restricted_code_onto_a_permissive_one():
    # The alias table is the one place a human judgement could widen the gate.
    for source, target in LICENSE_ALIASES.items():
        restricted = {t for t in RESTRICTION_TOKENS if t in source.split("-")}
        assert not restricted, f"alias {source!r} -> {target!r} launders a restriction"


# --- the gate, against what the providers actually emit ---------------------


def _hits(source, session, payload, **kw):
    return source(session=session({1: payload})).search("harbour", n=1, **kw)


def test_every_builtin_providers_own_vocabulary_passes_the_default_gate(
    make_session, openverse_payload, wikimedia_payload, pixabay_payload, pexels_payload
):
    """The #13 regression: two of four providers used to gate to []."""
    openverse = _hits(OpenverseSource, make_session, openverse_payload)
    wikimedia = _hits(WikimediaSource, make_session, wikimedia_payload)
    pixabay = _hits(PixabaySource, make_session, pixabay_payload, api_key="k")
    pexels = _hits(PexelsSource, make_session, pexels_payload, api_key="k")
    for name, hits in [
        ("openverse", openverse),
        ("wikimedia", wikimedia),
        ("pixabay", pixabay),
        ("pexels", pexels),
    ]:
        assert hits, f"{name} fixture produced no hits"
        assert license_allowlist(hits) == hits, (
            f"{name} emits {hits[0].license!r}, which the default allowlist drops"
        )


def test_default_allowlist_entries_are_written_in_canonical_form():
    # Entries are normalised on use, so a non-canonical spelling would still
    # work — but it would read as a second dialect in the SSOT.
    for entry in DFLT_LICENSE_ALLOWLIST:
        assert normalize_license(entry) == entry
