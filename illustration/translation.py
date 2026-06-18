"""Canonical → native parameter translation (the ``denote`` ``param_map`` idiom).

Each source declares a ``param_map`` mapping a *canonical* façade parameter name
to how that source expresses it natively. :func:`make_param_translator` turns a
``param_map`` into a callable that rewrites a dict of canonical kwargs into the
provider's native kwargs, degrading gracefully on parameters the source does not
support.

A ``param_map`` value may be:

- a ``str`` — straight rename to that native parameter name;
- a ``dict`` — ``{"name": <native>, "coerce": <fn>, "choices": <set>}`` where
  ``coerce`` transforms the value (e.g. vocabulary mapping) and ``choices``
  validates it;
- ``None`` — the parameter is *explicitly unsupported* by this source (degrade);
- *(a canonical key absent from the map is also treated as unsupported)*.

>>> pmap = {
...     "orientation": {"name": "aspect_ratio",
...                     "coerce": lambda o: {"landscape": "wide"}.get(o, o)},
...     "size": "size",
...     "license_type": None,
... }
>>> translate = make_param_translator(pmap)
>>> native, dropped = translate({"orientation": "landscape", "size": "large",
...                              "license_type": "commercial"})
>>> native
{'aspect_ratio': 'wide', 'size': 'large'}
>>> dropped
['license_type']
"""

from __future__ import annotations

import warnings
from typing import Any, Callable, Mapping, Tuple

__all__ = ["make_param_translator", "ParamTranslator"]

#: A translator maps canonical kwargs -> (native kwargs, dropped canonical names).
ParamTranslator = Callable[[Mapping[str, Any]], Tuple[dict, list]]

_ON_UNSUPPORTED = ("ignore", "warn", "raise")


def make_param_translator(
    param_map: Mapping[str, Any],
    *,
    on_unsupported: str = "ignore",
    source_name: str = "",
) -> ParamTranslator:
    """Build a translator from a ``param_map`` (see module docstring).

    ``on_unsupported`` governs what happens when a canonical param has no native
    equivalent: ``'ignore'`` (drop silently, the graceful default), ``'warn'``
    (drop + :func:`warnings.warn`), or ``'raise'`` (raise ``ValueError``).
    Parameters whose value is ``None`` are skipped entirely (an unset filter).
    """
    if on_unsupported not in _ON_UNSUPPORTED:
        raise ValueError(
            f"on_unsupported must be one of {_ON_UNSUPPORTED}, got {on_unsupported!r}"
        )

    def translate(canonical: Mapping[str, Any]) -> Tuple[dict, list]:
        native: dict = {}
        dropped: list = []
        for key, value in canonical.items():
            if value is None:
                continue  # an unset filter is not a "dropped" param
            spec = param_map.get(key, _UNSUPPORTED)
            if spec is None or spec is _UNSUPPORTED:
                _handle_unsupported(key, on_unsupported, source_name, dropped)
                continue
            native_name, coerced = _apply_spec(
                key, value, spec, on_unsupported, source_name
            )
            if native_name is None:  # choices validation failed under 'ignore'/'warn'
                dropped.append(key)
                continue
            native[native_name] = coerced
        return native, dropped

    return translate


# --- internals --------------------------------------------------------------


class _Unsupported:
    __slots__ = ()

    def __repr__(self):  # pragma: no cover - debug aid
        return "<UNSUPPORTED>"


_UNSUPPORTED = _Unsupported()


def _handle_unsupported(key: str, policy: str, source_name: str, dropped: list) -> None:
    dropped.append(key)
    if policy == "raise":
        where = f" by source {source_name!r}" if source_name else ""
        raise ValueError(f"Parameter {key!r} is not supported{where}.")
    if policy == "warn":
        where = f" by {source_name}" if source_name else ""
        warnings.warn(f"Dropping unsupported parameter {key!r}{where}.", stacklevel=3)


def _apply_spec(
    key: str, value: Any, spec: Any, policy: str, source_name: str
) -> Tuple[Any, Any]:
    """Return (native_name, coerced_value); native_name is None to signal drop."""
    if isinstance(spec, str):
        return spec, value
    if callable(spec) and not isinstance(spec, Mapping):
        return key, spec(value)
    if isinstance(spec, Mapping):
        native_name = spec.get("name", key)
        choices = spec.get("choices")
        if choices is not None and value not in choices:
            if policy == "raise":
                raise ValueError(
                    f"Parameter {key!r}={value!r} not in allowed choices {sorted(choices)}."
                )
            if policy == "warn":
                warnings.warn(
                    f"Dropping {key!r}={value!r}: not in {sorted(choices)}.",
                    stacklevel=4,
                )
            return None, None
        coerce = spec.get("coerce")
        return native_name, (coerce(value) if coerce else value)
    raise TypeError(f"Invalid param_map spec for {key!r}: {spec!r}")
