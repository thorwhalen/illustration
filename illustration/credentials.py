"""API-key resolution (the ``aix`` credentials idiom + ``falaw`` BYO-key seam).

A source that needs a key (e.g. Pexels) resolves it with this precedence:

1. an explicit ``api_key=`` argument,
2. a per-request binding via :func:`using_credentials` (a ``ContextVar`` — the
   "bring-your-own-key" seam a web backend uses without threading a credential
   argument through every call),
3. the provider's environment variable (see :data:`PROVIDER_ENV_VARS`),
4. a ``config2py`` config store keyed by the env-var name.

Missing keys raise an informative :class:`~illustration.errors.MissingCredentialError`
(naming *which* key, *how* to set it, *where* to get one) — values are never logged.

>>> with using_credentials(pexels="secret-123"):
...     resolve_api_key("pexels")
'secret-123'
>>> resolve_api_key("openverse") is None      # no key needed; none configured
True
"""

from __future__ import annotations

import contextlib
import contextvars
import os
from typing import Callable

from illustration.errors import MissingCredentialError

__all__ = [
    "PROVIDER_ENV_VARS",
    "PROVIDER_CONSOLE_URLS",
    "resolve_api_key",
    "check_requirements",
    "requires_credentials",
    "using_credentials",
    "current_credentials",
]

#: Provider name -> the environment variable that holds its API key.
#: Appendable: add a row when a new keyed provider is registered.
PROVIDER_ENV_VARS: dict[str, str] = {
    "pexels": "PEXELS_API_KEY",
    "pixabay": "PIXABAY_API_KEY",
}

#: Provider name -> where a user obtains a key (shown in the missing-key error).
PROVIDER_CONSOLE_URLS: dict[str, str] = {
    "pexels": "https://www.pexels.com/api/new/",
    "pixabay": "https://pixabay.com/api/docs/",
}

# Per-request key bindings (BYO keys), e.g. {"pexels": "..."}; never mutated in
# place — `using_credentials` swaps the whole mapping and resets on exit.
_KEYS_VAR: "contextvars.ContextVar[dict | None]" = contextvars.ContextVar(
    "illustration_provider_keys", default=None
)


def current_credentials() -> dict:
    """The provider keys currently bound by :func:`using_credentials` (a copy)."""
    return dict(_KEYS_VAR.get() or {})


@contextlib.contextmanager
def using_credentials(**provider_keys: str):
    """Bind per-request provider API keys for the duration of the ``with`` block.

    Falsy values are ignored (so an optional request header passes straight
    through). Bindings nest: an inner block overlays the outer.

    >>> with using_credentials(pexels="k1"):
    ...     with using_credentials(pexels="k2"):
    ...         inner = resolve_api_key("pexels")
    ...     outer = resolve_api_key("pexels")
    >>> inner, outer
    ('k2', 'k1')
    """
    merged = current_credentials()
    merged.update({k: v for k, v in provider_keys.items() if v})
    token = _KEYS_VAR.set(merged)
    try:
        yield
    finally:
        _KEYS_VAR.reset(token)


def resolve_api_key(provider: str, *, api_key: "str | None" = None) -> "str | None":
    """Resolve the API key for ``provider`` by precedence, or ``None`` if absent.

    Does not raise — callers that *require* a key use :func:`check_requirements`.
    Reads are non-interactive (never prompts).
    """
    if api_key:
        return api_key
    bound = current_credentials().get(provider)
    if bound:
        return bound
    env_var = PROVIDER_ENV_VARS.get(provider)
    if env_var:
        from_env = os.environ.get(env_var)
        if from_env:
            return from_env
        from_store = _config_store_get(env_var)
        if from_store:
            return from_store
    return None


def check_requirements(provider: str, *, api_key: "str | None" = None) -> "str | None":
    """Return the key for ``provider``, raising if a *required* key is missing.

    A provider with no entry in :data:`PROVIDER_ENV_VARS` needs no key and
    returns ``None``. Otherwise a missing key raises
    :class:`~illustration.errors.MissingCredentialError`.
    """
    key = resolve_api_key(provider, api_key=api_key)
    if key:
        return key
    if provider not in PROVIDER_ENV_VARS:
        return None  # keyless provider (e.g. openverse)
    raise MissingCredentialError(
        provider,
        env_var=PROVIDER_ENV_VARS.get(provider),
        console_url=PROVIDER_CONSOLE_URLS.get(provider),
    )


def requires_credentials(provider: str) -> Callable:
    """Decorator separating credential-checking from a function's business logic.

    Runs :func:`check_requirements` for ``provider`` before the wrapped function
    body, so the function never inlines key handling. (The built-in sources call
    :func:`check_requirements` directly; this decorator is the functional-style
    equivalent for Layer-2 helpers.)

    >>> @requires_credentials("pexels")
    ... def fetch(): return "ok"
    >>> with using_credentials(pexels="k"):
    ...     fetch()
    'ok'
    """

    def decorator(func: Callable) -> Callable:
        import functools

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            check_requirements(provider, api_key=kwargs.get("api_key"))
            return func(*args, **kwargs)

        return wrapper

    return decorator


def _config_store_get(key: str) -> "str | None":
    """Read ``key`` from the config2py config store, non-interactively.

    Uses ``config2py.configs`` (a ``TextFiles`` Mapping over the user's config
    dir) rather than ``get_config`` — the latter's default source chain includes
    an interactive prompt, which must never fire inside a library call.
    """
    try:
        from config2py import configs  # local, zero-dep ecosystem package

        return configs.get(key) or None
    except Exception:  # pragma: no cover - config2py optional/edge envs
        return None
