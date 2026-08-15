"""The offline suite is hermetic — these tests keep it that way.

Everything here tests ``conftest.py`` itself, which is unusual and earns its
place: the promise is a *negative* one ("no test ever hits the network"), and a
negative promise nobody checks decays into a comment. It was a comment until
now — the docstring claimed hermeticity while nothing enforced it, so a new
provider call, a lazily-imported model download, or a fixture that forgot its
fake would have gone unnoticed (this package degrades a failed fetch to ``None``
or to a smaller result set on purpose, so reaching the network is *silent*).

The point is therefore not the happy path. It is that the guard is armed: if
someone loosens the address check, drops the teardown assertion, or removes the
autouse fixture, something here goes red.
"""

import socket

import pytest

from conftest import (
    OutboundNetworkAttempt,
    _is_local_address,
    fail_on_outbound_attempts,
)


def test_the_network_guard_is_armed(_no_outbound_network):
    """A real outbound connection attempt is refused *and* recorded.

    Requesting the guard fixture by name is deliberate: the test must consume
    the recording it just provoked, or the guard's teardown assertion would
    (correctly) fail this test for the attempt it made on purpose.
    """
    with pytest.raises(OutboundNetworkAttempt) as excinfo:
        socket.create_connection(("api.openverse.org", 443), timeout=1)

    assert "api.openverse.org" in str(excinfo.value), (
        "the failure must name the host, or a future network-touching test is "
        "mysterious rather than diagnosable"
    )
    assert _no_outbound_network == ["DNS lookup api.openverse.org"]
    _no_outbound_network.clear()  # consumed: this attempt was the assertion


def test_the_network_guard_refuses_a_literal_ip_too(_no_outbound_network):
    """Blocking DNS is not enough — a literal IP skips resolution entirely."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(OutboundNetworkAttempt):
            sock.connect(("93.184.216.34", 443))
    finally:
        sock.close()

    assert _no_outbound_network == ["connect ('93.184.216.34', 443)"]
    _no_outbound_network.clear()


def test_the_teardown_backstop_reports_a_swallowed_attempt():
    """Refusing the connection is not enough — the attempt must be *reported*.

    ``_imageio.fetch_image`` returns ``None`` for any exception and the source
    layer translates transport failures into an ``IllustrationError``, so a
    refusal alone can be absorbed into a still-passing test. The record
    asserted at teardown is what actually holds the line.
    """
    with pytest.raises(pytest.fail.Exception, match="outbound network I/O"):
        fail_on_outbound_attempts(["connect ('93.184.216.34', 443)"])

    fail_on_outbound_attempts([])  # nothing recorded => no complaint


@pytest.mark.parametrize(
    "address",
    [
        ("127.0.0.1", 8000),
        ("::1", 8000),
        ("localhost", 8000),
        ("0.0.0.0", 8000),
        "/tmp/some.sock",
    ],
)
def test_local_addresses_stay_allowed(address):
    """The guard must not break loopback or non-IP sockets."""
    assert _is_local_address(address)


@pytest.mark.parametrize(
    "address",
    [
        ("api.openverse.org", 443),
        ("commons.wikimedia.org", 443),
        ("93.184.216.34", 443),
        ("10.0.0.5", 443),
    ],
)
def test_remote_addresses_are_refused(address):
    assert not _is_local_address(address)


def test_a_provider_search_without_a_fake_session_is_caught(_no_outbound_network):
    """The case this exists for: a real `search()` with nothing stubbed.

    ``illustration.search`` is one call away from the internet, so this is what
    an accidentally-networked test looks like. It must fail loudly rather than
    return a plausible-looking result set fetched for real.
    """
    from illustration import facade

    with pytest.raises(BaseException) as excinfo:
        facade.search("a stormy harbour at dusk", n=1, source="openverse", cache=False)

    assert "api.openverse.org" in str(excinfo.value)
    assert _no_outbound_network == ["DNS lookup api.openverse.org"]
    _no_outbound_network.clear()
