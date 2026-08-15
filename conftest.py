"""Pytest fixtures and offline HTTP fakes (no test ever hits the network).

Two halves. ``FakeSession`` / ``FakeResponse`` plus a canned payload fixture per
provider are how a test *gets* a provider response without leaving the machine.
:func:`_no_outbound_network` is what makes the parenthesis above true rather
than aspirational: it is autouse, so a test that starts reaching out fails on
the spot, naming the host it tried to reach.

A test that genuinely must talk to the real world marks itself
``@pytest.mark.live`` (the opt-in SigLIP inference test is the only one).
"""

import ipaddress
import os
import socket
import sys

import pytest

# Make the in-repo package importable without an editable install (and prefer
# the local source when one is installed).
sys.path.insert(0, os.path.dirname(__file__))


# --- the offline network guard ----------------------------------------------


class OutboundNetworkAttempt(BaseException):
    """An offline test tried to talk to a non-local host.

    Derived from :class:`BaseException`, not :class:`Exception`, on purpose:
    this package is deliberately fail-soft about transport errors —
    ``_imageio.fetch_image`` returns ``None`` for *any* exception and
    ``RetrievalSource`` translates request failures into an
    ``IllustrationError`` — so anything catchable would be caught and the
    attempt would vanish silently.
    """


#: Hostnames that mean "this machine" without going through DNS.
LOCAL_HOSTNAMES = frozenset(
    {"", "localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}
)


def _is_local_address(address):
    """True when ``address`` is loopback, unspecified, or not an IP endpoint.

    Non-tuple addresses (``AF_UNIX`` paths, ``AF_NETLINK`` ints) are local by
    construction. A bare hostname that is not a known loopback alias counts as
    outbound: resolving it is itself a network round-trip.
    """
    if not isinstance(address, (tuple, list)) or not address:
        return True
    host = address[0]
    if host is None:
        return True
    host = str(host)
    if host in LOCAL_HOSTNAMES:
        return True
    try:
        ip = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False  # an unresolved name -> looking it up is already outbound
    return ip.is_loopback or ip.is_unspecified


def install_network_guard(monkeypatch):
    """Refuse and record every non-local socket use; return the record.

    Split out of the fixture so both halves of the guard are reachable from a
    test — see ``tests/test_offline_guard.py``.
    """
    attempts = []
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def refuse(what, target):
        attempts.append(f"{what} {target}")
        raise OutboundNetworkAttempt(
            f"Offline test attempted {what} to {target!r}. The suite is "
            "hermetic: inject a fake transport (the `make_session` fixture) or "
            "stub the seam that fetches, and mark the test `live` only if it "
            "really must reach the real world."
        )

    def connect(self, address, *args, **kwargs):
        if not _is_local_address(address):
            refuse("connect", str(address))
        return real_connect(self, address, *args, **kwargs)

    def connect_ex(self, address, *args, **kwargs):
        if not _is_local_address(address):
            refuse("connect", str(address))
        return real_connect_ex(self, address, *args, **kwargs)

    def getaddrinfo(host, port, *args, **kwargs):
        if not _is_local_address((host, port)):
            refuse("DNS lookup", str(host))
        return real_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    return attempts


def fail_on_outbound_attempts(attempts):
    """Fail the test if the guard recorded anything. The swallow-proof half.

    Refusing the connection is not the same as reporting it: the fail-soft
    paths above turn a refused fetch into ``None`` or a degraded result and the
    test would stay green. Asserting the *record* at teardown is what makes the
    attempt impossible to hide.
    """
    if attempts:
        pytest.fail(
            "Offline test performed outbound network I/O: "
            + "; ".join(sorted(set(attempts)))
        )


@pytest.fixture(autouse=True)
def _no_outbound_network(request, monkeypatch):
    """Fail the test if it tries to reach a non-local host.

    Declared before every other fixture in this module so it is set up first
    and torn down last — it therefore covers fixture setup as well as the test
    body. Tests marked ``live`` opt out.
    """
    if request.node.get_closest_marker("live") is not None:
        yield []
        return
    attempts = install_network_guard(monkeypatch)
    yield attempts
    fail_on_outbound_attempts(attempts)


# --- offline HTTP fakes ------------------------------------------------------


def _page_index(params):
    """Derive the 1-based page from request params (page-number OR offset model).

    Faithful to both pagination styles a source may use: an explicit ``page``,
    or an offset pair (``gsroffset``/``gsrlimit`` for Wikimedia, ``offset``/
    ``limit`` generally). Without this, an offset-paginating provider would always
    re-fetch page 1.
    """
    if "page" in params:
        return params["page"]
    for off, lim in (("gsroffset", "gsrlimit"), ("offset", "limit")):
        if off in params:
            per = params.get(lim) or 1
            return params[off] // per + 1
    return 1


class FakeResponse:
    """A stand-in for ``requests.Response`` good enough for the source layer."""

    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    """Injectable ``session`` for a :class:`RetrievalSource`.

    ``pages`` maps a 1-based page number to the JSON payload returned for that
    page; ``response`` (if given) is returned for every call regardless of page.
    Records each call in ``.calls`` for assertions.
    """

    def __init__(
        self, pages=None, *, response=None, status_code=200, text="", raises=None
    ):
        self.pages = pages or {}
        self.response = response
        self.status_code = status_code
        self.text = text
        self.raises = (
            raises  # an exception instance to raise from .get() (transport error)
        )
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        params = dict(params or {})
        self.calls.append(
            {"url": url, "params": params, "headers": dict(headers or {})}
        )
        if self.raises is not None:
            raise self.raises
        payload = (
            self.response
            if self.response is not None
            else self.pages.get(_page_index(params), {"results": [], "photos": []})
        )
        return FakeResponse(payload, status_code=self.status_code, text=self.text)


@pytest.fixture
def make_session():
    """Factory: ``make_session({1: payload})`` or ``make_session(response=...)``."""

    def _make(pages=None, *, response=None, status_code=200, text="", raises=None):
        return FakeSession(
            pages, response=response, status_code=status_code, text=text, raises=raises
        )

    return _make


@pytest.fixture
def openverse_payload():
    """A canned 2-result Openverse page (page 1 of 2)."""
    return {
        "result_count": 3,
        "page_count": 2,
        "page": 1,
        "page_size": 2,
        "results": [
            {
                "id": "uuid-1",
                "title": "Stormy Harbour",
                "url": "https://img.example/full1.jpg",
                "thumbnail": "https://api.openverse.org/v1/images/uuid-1/thumb/",
                "width": 1024,
                "height": 768,
                "creator": "Jane Doe",
                "creator_url": "https://flickr.example/jane",
                "tags": [
                    {"name": "harbour"},
                    {"name": "storm"},
                    {"accuracy": 0.9},  # no name -> must be filtered out
                ],
                "license": "by-sa",
                "license_version": "2.0",
                "license_url": "https://creativecommons.org/licenses/by-sa/2.0/",
                "attribution": '"Stormy Harbour" by Jane Doe is licensed under CC BY-SA 2.0.',
                "foreign_landing_url": "https://flickr.example/photos/jane/1",
                "provider": "flickr",
                "source": "flickr",
                "category": "photograph",
                "filetype": None,
            },
            {
                "id": "uuid-2",
                "title": "Dusk Pier",
                "url": "https://img.example/full2.jpg",
                "thumbnail": "https://api.openverse.org/v1/images/uuid-2/thumb/",
                "width": 800,
                "height": 600,
                "creator": None,
                "tags": [],
                "license": "cc0",
                "license_version": "1.0",
                "license_url": None,  # cc0 -> null
                "attribution": "Marked as public domain.",
                "foreign_landing_url": "https://wikimedia.example/2",
                "provider": "wikimedia",
                "source": "wikimedia",
            },
        ],
    }


@pytest.fixture
def pexels_payload():
    """A canned 1-result Pexels response."""
    return {
        "page": 1,
        "per_page": 2,
        "total_results": 1,
        "photos": [
            {
                "id": 123,
                "width": 4000,
                "height": 3000,
                "url": "https://www.pexels.com/photo/123/",
                "photographer": "John Smith",
                "photographer_url": "https://www.pexels.com/@john",
                "photographer_id": 7,
                "avg_color": "#5A6B7C",
                "alt": "A stormy harbour at dusk",
                "liked": False,
                "src": {
                    "original": "https://images.pexels.example/123/orig.jpg",
                    "large2x": "https://images.pexels.example/123/l2x.jpg",
                    "large": "https://images.pexels.example/123/l.jpg",
                    "medium": "https://images.pexels.example/123/m.jpg",
                    "small": "https://images.pexels.example/123/s.jpg",
                    "portrait": "https://images.pexels.example/123/p.jpg",
                    "landscape": "https://images.pexels.example/123/ls.jpg",
                    "tiny": "https://images.pexels.example/123/tiny.jpg",
                },
            }
        ],
    }


@pytest.fixture
def pixabay_payload():
    """A canned 1-result Pixabay response."""
    return {
        "total": 100,
        "totalHits": 100,
        "hits": [
            {
                "id": 555,
                "pageURL": "https://pixabay.com/photos/harbour-555/",
                "type": "photo",
                "tags": "harbour, boats, dusk",
                "previewURL": "https://cdn.pixabay.example/555_150.jpg",
                "webformatURL": "https://cdn.pixabay.example/555_640.jpg",
                "largeImageURL": "https://cdn.pixabay.example/555_1280.jpg",
                "imageWidth": 4000,
                "imageHeight": 3000,
                "user": "janedoe",
                "user_id": 42,
            }
        ],
    }


@pytest.fixture
def wikimedia_payload():
    """A canned MediaWiki response: one image + one non-image (audio) to drop."""
    return {
        "batchcomplete": "",
        "query": {
            "pages": {
                "12345": {
                    "pageid": 12345,
                    "ns": 6,
                    "title": "File:Stormy Harbour.jpg",
                    "index": 1,
                    "imageinfo": [
                        {
                            "user": "Alice",
                            "size": 123456,
                            "width": 1024,
                            "height": 768,
                            "thumburl": "https://upload.wikimedia.example/thumb/330px-Stormy_Harbour.jpg",
                            "url": "https://upload.wikimedia.example/Stormy_Harbour.jpg",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Stormy_Harbour.jpg",
                            "mime": "image/jpeg",
                            "extmetadata": {
                                "License": {"value": "cc-by-sa-4.0"},
                                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                "LicenseUrl": {
                                    "value": "https://creativecommons.org/licenses/by-sa/4.0"
                                },
                                "Artist": {
                                    "value": '<a href="//commons.wikimedia.org/wiki/User:Alice">Alice</a>'
                                },
                                "ImageDescription": {
                                    "value": "A <b>stormy</b> harbour at dusk."
                                },
                                "Attribution": {"value": ""},
                            },
                        }
                    ],
                },
                "67890": {  # a non-image file that must be dropped by MIME
                    "pageid": 67890,
                    "ns": 6,
                    "title": "File:Foghorn.ogg",
                    "index": 2,
                    "imageinfo": [
                        {
                            "mime": "audio/ogg",
                            "url": "https://upload.wikimedia.example/Foghorn.ogg",
                            "width": 0,
                            "height": 0,
                            "extmetadata": {},
                        }
                    ],
                },
            }
        },
    }
