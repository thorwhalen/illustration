"""The package exception hierarchy.

Errors are informative by design: a :class:`MissingCredentialError` names *which*
key is missing, *how* to provide it, and *where* to obtain it — and never logs
the key value itself.

>>> raise MissingCredentialError("pexels", env_var="PEXELS_API_KEY",
...     console_url="https://www.pexels.com/api/new/")   # doctest: +IGNORE_EXCEPTION_DETAIL
Traceback (most recent call last):
illustration.errors.MissingCredentialError: ...
"""

from __future__ import annotations

__all__ = [
    "IllustrationError",
    "UnknownSourceError",
    "MissingCredentialError",
    "ProviderError",
    "RateLimitError",
    "RerankDependencyError",
    "CurateDependencyError",
]


class IllustrationError(Exception):
    """Base class for every error raised by :mod:`illustration`."""


class UnknownSourceError(IllustrationError, KeyError):
    """A source name was requested that is not in the registry."""

    def __init__(self, name: str, known: "list[str] | None" = None):
        self.name = name
        self.known = list(known or [])
        msg = f"Unknown source {name!r}."
        if self.known:
            msg += f" Registered sources: {', '.join(sorted(self.known))}."
        super().__init__(msg)


class MissingCredentialError(IllustrationError):
    """A source needs an API key that could not be resolved.

    The message tells the user exactly what to do; key values are never logged.
    """

    def __init__(
        self,
        provider: str,
        *,
        env_var: "str | None" = None,
        console_url: "str | None" = None,
    ):
        self.provider = provider
        self.env_var = env_var
        self.console_url = console_url
        lines = [f"No API key found for source {provider!r}."]
        if env_var:
            lines.append(
                f"Set it via the {env_var} environment variable, a config2py "
                f"config entry keyed {env_var!r}, or pass api_key=... / "
                f"illustration.using_credentials({provider}='...')."
            )
        if console_url:
            lines.append(f"Get a key at: {console_url}")
        super().__init__(" ".join(lines))


class RerankDependencyError(IllustrationError, ImportError):
    """The optional local-rerank dependencies are not installed.

    The message names the missing packages and the extra that provides them.
    """

    def __init__(self, missing: "list[str] | None" = None):
        self.missing = list(missing or [])
        names = (
            ", ".join(self.missing) if self.missing else "transformers, torch, pillow"
        )
        super().__init__(
            f"Local rerank needs the optional dependencies ({names}). "
            "Install them with: pip install 'illustration[rerank]'."
        )


class CurateDependencyError(IllustrationError, ImportError):
    """An optional Layer-2 (agentic curation) dependency is not installed.

    The message names the missing packages and the extra that provides them,
    so the failure is actionable (e.g. ``pip install 'illustration[curate]'``).
    """

    def __init__(
        self,
        missing: "list[str] | None" = None,
        *,
        extra: str = "curate",
        purpose: str = "agentic curation",
    ):
        self.missing = list(missing or [])
        self.extra = extra
        names = ", ".join(self.missing) if self.missing else "aix, ir"
        super().__init__(
            f"Layer-2 {purpose} needs the optional dependencies ({names}). "
            f"Install them with: pip install 'illustration[{extra}]'."
        )


class ProviderError(IllustrationError):
    """A provider's HTTP API returned an error or an unusable response."""

    def __init__(self, provider: str, message: str, *, status: "int | None" = None):
        self.provider = provider
        self.status = status
        prefix = f"[{provider}]"
        if status is not None:
            prefix += f" HTTP {status}"
        super().__init__(f"{prefix} {message}")


class RateLimitError(ProviderError):
    """A provider returned HTTP 429 (rate limit exceeded)."""
