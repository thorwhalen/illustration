# illustration.licensing

Licence-code normalisation — one vocabulary for four provider vocabularies.

Every provider spells the same licence differently: Openverse emits `by-sa`,
Wikimedia Commons emits `cc-by-sa-4.0` (and `CC BY-SA 4.0` as the short
name), Pixabay emits `Pixabay License`. [`normalize_license()`](#illustration.licensing.normalize_license) folds those
spellings onto one canonical code so the licence gate
([`illustration.schema.license_allowlist()`](illustration.schema.md#illustration.schema.license_allowlist)) can compare like with like,
instead of silently returning `[]` for two of the four built-in sources.

\*\*The safety invariant, and it is the whole reason this module is small and
boring: normalisation may never drop a restriction token.\*\* `nc`
(non-commercial) and `nd` (no-derivatives) are exactly what an allowlist
exists to exclude, so the transform only ever removes things that carry no
permission meaning — a `cc`/`cc-` prefix and a trailing version number —
and every other spelling must be listed, by hand, in [`LICENSE_ALIASES`](#illustration.licensing.LICENSE_ALIASES).
A code that is not recognised stays as-is and therefore fails the allowlist:
**unknown is not allowed**, in both directions.

```pycon
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
```

[`display_license()`](#illustration.licensing.display_license) is the inverse-flavoured sibling, for *showing* a
licence rather than comparing it — see its own docstring for why it works on
the recorded spelling rather than the normalised code.

### Module Attributes

| [`LICENSE_ALIASES`](#illustration.licensing.LICENSE_ALIASES)    | Whole-code spellings that no mechanical rule can fold, mapped by hand.   |
|---------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`RESTRICTION_TOKENS`](#illustration.licensing.RESTRICTION_TOKENS) | Tokens that *restrict* use.                                              |

### Functions

| [`normalize_license`](#illustration.licensing.normalize_license)(value)      | Fold a provider's licence spelling onto one canonical, comparable code.   |
|--------------------------------------------------------------------------------|---------------------------------------------------------------------------|
| [`display_license`](#illustration.licensing.display_license)(value)        | The conventional human spelling of a licence, for on-screen credit.       |
| [`mentions_license`](#illustration.licensing.mentions_license)(attribution) | Whether `attribution` appears to name a licence or rights status.         |

### illustration.licensing.LICENSE_ALIASES *= {'cc-0': 'cc0', 'cc-pdm': 'pdm', 'cc-publicdomain': 'pdm', 'cc-zero': 'cc0', 'pd': 'pdm', 'pdm-owner': 'pdm', 'public-domain': 'pdm', 'public-domain-mark': 'pdm', 'publicdomain': 'pdm', 'zero': 'cc0'}*

Whole-code spellings that no mechanical rule can fold, mapped by hand. Kept
deliberately short: every entry is a judgement that two strings name the same
permissions, and a wrong entry silently widens the gate. Every key must stay
*reachable* — `"cc-0"` was dead for a release because the version strip ran
first and turned it into `"cc"`, so a CC0 image spelled that way was dropped
by the default gate; `test_every_alias_key_is_reachable` now pins that.

### illustration.licensing.RESTRICTION_TOKENS *= frozenset({'nc', 'nd', 'sampling'})*

Tokens that *restrict* use. Present only so the guard test can assert that
normalisation never removes one; nothing in the transform consults it.

### illustration.licensing.display_license(value)

The conventional human spelling of a licence, for on-screen credit.

Unlike [`normalize_license()`](#illustration.licensing.normalize_license) (a canonical code for *comparison*, with
the version stripped by design), this is for *display* — a credit line, a
video description, an attribution card — and works on the **recorded**
spelling rather than the normalised one, because the version is
information a normalised code deliberately drops and a credit arguably
should keep: `cc-by-sa-4.0` and a hypothetical `cc-by-sa-3.0` compare
equal under [`normalize_license()`](#illustration.licensing.normalize_license) but are not the same licence to name
on screen.

Recognised Creative Commons / public-domain codes (the same vocabulary
[`normalize_license()`](#illustration.licensing.normalize_license) produces) get the conventional spelling —
`"by-sa"` → `"CC BY-SA"`, `"cc0"` → `"CC0"`, `"pdm"` →
`"Public Domain Mark"` — with the recorded version appended if the input
carried one. This is presentation only: an input that does not resolve to
a known permission code is title-cased and returned as-is, never
reinterpreted — it must still fail [`normalize_license()`](#illustration.licensing.normalize_license)’s consumers
(e.g. [`illustration.schema.license_allowlist()`](illustration.schema.md#illustration.schema.license_allowlist)) exactly as before.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

```pycon
>>> display_license("cc-by-sa-4.0")
'CC BY-SA 4.0'
>>> display_license("CC BY-SA 4.0")
'CC BY-SA 4.0'
>>> display_license("by-sa")           # no version in the recorded spelling
'CC BY-SA'
>>> display_license("cc0"), display_license("CC0 1.0")
('CC0', 'CC0 1.0')
>>> display_license("pd"), display_license("public domain")
('Public Domain Mark', 'Public Domain Mark')
>>> display_license("cc-by-nc-nd-4.0")  # restrictions survive, same as normalize_license
'CC BY-NC-ND 4.0'
>>> display_license("Pixabay License")  # not a CC/PD code -- shown, not invented
'Pixabay License'
>>> display_license(None) is None
True
```

### illustration.licensing.mentions_license(attribution)

Whether `attribution` appears to name a licence or rights status.

A soft, presentation-side audit signal for
[`illustration.schema.check_attributions()`](illustration.schema.md#illustration.schema.check_attributions) — CC BY / CC BY-SA require
the licence to be identified in the credit, and some providers’ raw
attribution text (notably Wikimedia Commons’ `extmetadata.Attribution`,
illustration#22) is sometimes just the author’s name with no licence
mentioned at all, even when the file’s `license`/`license_url` fields
are populated and correct. This never changes what a licence *is* — it
only flags text that does not visibly say what it is, for a caller to
review or fall back on `author`/`license`/`license_url` themselves.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

```pycon
>>> mentions_license("Alice / CC BY-SA 4.0, via Wikimedia Commons")
True
>>> mentions_license("Public domain, via Wikimedia Commons")
True
>>> mentions_license("EliziR")            # illustration#22: bare author name
False
>>> mentions_license("Use freely, credit ACME")  # custom wording, no licence named
False
>>> mentions_license(None)
False
```

### illustration.licensing.normalize_license(value)

Fold a provider’s licence spelling onto one canonical, comparable code.

Lower-cases, unifies separators to `-`, strips a trailing version and a
leading `cc-`, then applies [`LICENSE_ALIASES`](#illustration.licensing.LICENSE_ALIASES). Returns `None` for
`None`/blank — an absent licence is never a code.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

```pycon
>>> normalize_license("by-sa"), normalize_license("cc0"), normalize_license("CC0 1.0")
('by-sa', 'cc0', 'cc0')
>>> normalize_license("Pexels License"), normalize_license("  BY  ")
('pexels-license', 'by')
>>> normalize_license("public domain"), normalize_license("cc-by-3.0")
('pdm', 'by')
>>> normalize_license("cc-0")  # the version strip would otherwise eat "-0"
'cc0'
>>> normalize_license("")  is None
True
```
