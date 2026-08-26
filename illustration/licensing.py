"""Licence-code normalisation — one vocabulary for four provider vocabularies.

Every provider spells the same licence differently: Openverse emits ``by-sa``,
Wikimedia Commons emits ``cc-by-sa-4.0`` (and ``CC BY-SA 4.0`` as the short
name), Pixabay emits ``Pixabay License``. :func:`normalize_license` folds those
spellings onto one canonical code so the licence gate
(:func:`illustration.schema.license_allowlist`) can compare like with like,
instead of silently returning ``[]`` for two of the four built-in sources.

**The safety invariant, and it is the whole reason this module is small and
boring: normalisation may never drop a restriction token.** ``nc``
(non-commercial) and ``nd`` (no-derivatives) are exactly what an allowlist
exists to exclude, so the transform only ever removes things that carry no
permission meaning — a ``cc``/``cc-`` prefix and a trailing version number —
and every other spelling must be listed, by hand, in :data:`LICENSE_ALIASES`.
A code that is not recognised stays as-is and therefore fails the allowlist:
**unknown is not allowed**, in both directions.

>>> normalize_license("cc-by-sa-4.0")
'by-sa'
>>> normalize_license("CC BY-SA 4.0")
'by-sa'
>>> normalize_license("Pixabay License")
'pixabay-license'
>>> normalize_license("cc-by-nc-nd-4.0")          # restrictions survive intact
'by-nc-nd'
>>> normalize_license(None) is None
True
"""

from __future__ import annotations

import re

__all__ = ["normalize_license", "LICENSE_ALIASES", "RESTRICTION_TOKENS"]

#: Whole-code spellings that no mechanical rule can fold, mapped by hand. Kept
#: deliberately short: every entry is a judgement that two strings name the same
#: permissions, and a wrong entry silently widens the gate.
LICENSE_ALIASES = {
    "cc-zero": "cc0",
    "cc-0": "cc0",
    "zero": "cc0",
    "publicdomain": "pdm",
    "public-domain": "pdm",
    "public-domain-mark": "pdm",
    "pd": "pdm",
    "pdm-owner": "pdm",
    "cc-pdm": "pdm",
    "cc-publicdomain": "pdm",
}

#: Tokens that *restrict* use. Present only so the guard test can assert that
#: normalisation never removes one; nothing in the transform consults it.
RESTRICTION_TOKENS = frozenset({"nc", "nd", "sampling"})

# A trailing version, e.g. the "-4.0" of "cc-by-sa-4.0". The leading separator is
# required so a code that merely *ends* in a digit (``cc0``) is left alone.
_VERSION_SUFFIX_RE = re.compile(r"[-_ ]v?\d+(?:\.\d+)*$")
# The Creative Commons prefix, which carries no permission meaning of its own.
_CC_PREFIX_RE = re.compile(r"^cc[-_ ]")
_SEPARATORS_RE = re.compile(r"[\s_]+")


def normalize_license(value: "str | None") -> "str | None":
    """Fold a provider's licence spelling onto one canonical, comparable code.

    Lower-cases, unifies separators to ``-``, strips a trailing version and a
    leading ``cc-``, then applies :data:`LICENSE_ALIASES`. Returns ``None`` for
    ``None``/blank — an absent licence is never a code.

    >>> normalize_license("by-sa"), normalize_license("cc0"), normalize_license("CC0 1.0")
    ('by-sa', 'cc0', 'cc0')
    >>> normalize_license("Pexels License"), normalize_license("  BY  ")
    ('pexels-license', 'by')
    >>> normalize_license("public domain"), normalize_license("cc-by-3.0")
    ('pdm', 'by')
    >>> normalize_license("")  is None
    True
    """
    if not value or not value.strip():
        return None
    code = _SEPARATORS_RE.sub("-", value.strip().lower())
    code = _VERSION_SUFFIX_RE.sub("", code)
    if code in LICENSE_ALIASES:  # alias before de-prefixing (e.g. "cc-pdm")
        return LICENSE_ALIASES[code]
    code = _CC_PREFIX_RE.sub("", code)
    return LICENSE_ALIASES.get(code, code) or None
