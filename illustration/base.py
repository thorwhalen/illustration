"""The provider plugin contract: :class:`RetrievalSource`.

Each image-search provider is a small subclass implementing a few hooks; the
base class supplies the uniform behaviour (canonical→native translation,
pagination to satisfy ``n``, HTTP with a descriptive User-Agent, credential
checking, per-item normalization that never lets one bad item fail the search).
Adding a provider touches only a new subclass + one registration — never the
façade (open-closed).

A subclass declares class attributes (``name``, ``endpoint``, ``query_param``,
``page_param``, ``per_page_param``, ``max_per_page``, ``param_map``, ``info``)
and implements three hooks: :meth:`_items`, :meth:`_normalize`, and
(if the provider needs a key) :meth:`_auth_headers`.

See ``illustration/providers/openverse.py`` for the canonical example.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from illustration.config import HTTP_TIMEOUT, MAX_PAGES, user_agent
from illustration.credentials import check_requirements, resolve_api_key
from illustration.errors import ProviderError, RateLimitError
from illustration.schema import ImageResult
from illustration.translation import make_param_translator

__all__ = ["RetrievalSource", "SourceInfo"]


@dataclass(frozen=True)
class SourceInfo:
    """Static, human-facing metadata about a source (for discovery + the gate)."""

    name: str
    description: str = ""
    requires_key: bool = False
    homepage: str | None = None
    default_cacheable: bool = True
    license_note: str = ""
    rate_limit: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        from dataclasses import asdict

        return asdict(self)


class RetrievalSource(ABC):
    """Abstract base for a pure image-search provider.

    Subclasses set the class attributes below and implement :meth:`_items` and
    :meth:`_normalize` (and :meth:`_auth_headers` if the provider needs a key).
    :meth:`search` and :meth:`raw_search` are **template methods — do not
    override them**: they enforce credential checks, canonical→native
    translation, pagination (capped by ``MAX_PAGES``), and per-item normalization
    that skips rather than fails on a malformed item. Override a hook, not the
    template, so a provider can never silently lose those guarantees.
    """

    #: Registry key, e.g. ``"openverse"``. Required.
    name: str = ""
    #: Search endpoint URL. Required.
    endpoint: str = ""
    #: Native name of the free-text query parameter.
    query_param: str = "q"
    #: Native name of the page-number parameter.
    page_param: str = "page"
    #: Native name of the results-per-page parameter.
    per_page_param: str = "page_size"
    #: Hard cap on results per page this provider allows.
    max_per_page: int = 20
    #: Constant native params sent on every request (e.g. an API mode/format).
    fixed_params: Mapping[str, Any] = MappingProxyType({})
    #: Canonical→native parameter spec (see :mod:`illustration.translation`).
    #: Immutable empty default so subclasses never share one mutable dict.
    param_map: Mapping[str, Any] = MappingProxyType({})
    #: Static metadata (a per-instance one is synthesized in __init__ if unset).
    info: SourceInfo = SourceInfo(name="")

    def __init__(self, *, session: Any = None):
        # `session` lets callers/tests inject a requests.Session (or a stub).
        self._session = session
        if not self.info.name:  # never leave a nameless shared SourceInfo sentinel
            self.info = SourceInfo(name=self.name)
        self._translate = make_param_translator(
            self.param_map, on_unsupported="ignore", source_name=self.name
        )

    # -- public API ----------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        n: int = 10,
        api_key: "str | None" = None,
        native_params: "Mapping[str, Any] | None" = None,
        **canonical: Any,
    ) -> list[ImageResult]:
        """Search ``query`` and return up to ``n`` normalized :class:`ImageResult`.

        ``canonical`` are façade-canonical filters (see the façade ``search`` and
        the design doc §2); each is translated to the provider's native param via
        ``param_map``, degrading gracefully where unsupported. ``native_params``
        are raw provider-native params (the escape hatch) merged last, overriding
        translated ones.
        """
        if not query:
            raise ValueError("query must be a non-empty string")
        check_requirements(self.name, api_key=api_key)
        key = resolve_api_key(self.name, api_key=api_key)

        native, _dropped = self._translate(canonical)
        if native_params:
            native.update(native_params)

        results: list[ImageResult] = []
        per_page = max(1, min(n, self.max_per_page))
        page = 1
        while len(results) < n and page <= MAX_PAGES:
            params = {**self.fixed_params, **native}
            params[self.query_param] = query
            params.update(self._page_params(page=page, per_page=per_page))
            response = self._get(params, api_key=key)
            items = self._items(response)
            if not items:
                break
            for item in items:
                normalized = self._safe_normalize(item, query=query)
                if normalized is not None:
                    results.append(normalized)
                    if len(results) >= n:
                        break
            if len(items) < per_page:
                break  # last page
            page += 1
        return results[:n]

    def raw_search(self, *, api_key: "str | None" = None, **native_params: Any) -> dict:
        """Hit the endpoint with zero translation — the deepest escape hatch.

        ``native_params`` are passed through verbatim as the provider's own
        query parameters; the raw decoded JSON response is returned.
        """
        check_requirements(self.name, api_key=api_key)
        key = resolve_api_key(self.name, api_key=api_key)
        # include fixed_params as a base so raw_search to APIs with mandatory
        # constant params (e.g. action=query) still works; caller params win.
        return self._get({**self.fixed_params, **native_params}, api_key=key)

    # -- hooks for subclasses ------------------------------------------------

    @abstractmethod
    def _items(self, response: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
        """Extract the list of raw result items from a decoded response."""

    @abstractmethod
    def _normalize(self, item: Mapping[str, Any], *, query: str) -> ImageResult:
        """Map one raw provider item to an :class:`ImageResult`."""

    def _page_params(self, *, page: int, per_page: int) -> dict:
        """Native pagination params for a 1-based ``page``. Override for offset
        models (e.g. Wikimedia's ``gsroffset``). Default is page-number based."""
        return {self.page_param: page, self.per_page_param: per_page}

    def _auth_headers(self, api_key: "str | None") -> dict:
        """HTTP auth headers for this provider (default: none)."""
        return {}

    def _auth_params(self, api_key: "str | None") -> dict:
        """Native query params carrying auth (default: none).

        For providers that take the key as a query param (e.g. Pixabay's
        ``key=``) rather than a header.
        """
        return {}

    # -- internals -----------------------------------------------------------

    def _safe_normalize(self, item: Mapping[str, Any], *, query: str) -> "ImageResult | None":
        """Normalize one item, skipping (not failing) on a malformed item."""
        try:
            return self._normalize(item, query=query)
        except Exception:  # one bad item must not sink the whole search
            return None

    def _get(self, params: Mapping[str, Any], *, api_key: "str | None" = None) -> dict:
        """Perform the HTTP GET and return decoded JSON, translating errors."""
        import requests  # lazy: keep `import illustration` light

        session = self._session or requests
        headers = {"User-Agent": user_agent(), "Accept": "application/json"}
        headers.update(self._auth_headers(api_key))
        request_params = {**dict(params), **self._auth_params(api_key)}
        try:
            resp = session.get(
                self.endpoint, params=request_params, headers=headers, timeout=HTTP_TIMEOUT
            )
        except Exception as e:  # network/transport failure
            raise ProviderError(self.name, f"request failed: {e}") from e
        status = getattr(resp, "status_code", None)
        if status == 429:
            raise RateLimitError(self.name, "rate limit exceeded", status=429)
        if status in (401, 403):
            raise ProviderError(
                self.name, "authentication failed (check API key)", status=status
            )
        if status is not None and status >= 400:
            raise ProviderError(self.name, _short_body(resp), status=status)
        try:
            decoded = resp.json()
        except Exception as e:
            raise ProviderError(self.name, f"response was not valid JSON: {e}") from e
        if not isinstance(decoded, dict):
            # a valid-JSON-but-non-object body (array / null / scalar) would crash
            # _items downstream with a bare AttributeError; surface it informatively
            raise ProviderError(
                self.name,
                f"unexpected response type {type(decoded).__name__} (expected a JSON object)",
                status=status,
            )
        return decoded


def _short_body(resp: Any, limit: int = 200) -> str:
    text = getattr(resp, "text", "") or ""
    text = text.strip().replace("\n", " ")
    return text[:limit] if text else "request failed"
