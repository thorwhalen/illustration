"""Tests for credential resolution and the informative missing-key error."""

import pytest

from illustration.credentials import (
    check_requirements,
    requires_credentials,
    resolve_api_key,
    using_credentials,
)
from illustration.errors import MissingCredentialError


def test_explicit_key_wins(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "from-env")
    assert resolve_api_key("pexels", api_key="explicit") == "explicit"


def test_context_beats_env(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "from-env")
    with using_credentials(pexels="from-ctx"):
        assert resolve_api_key("pexels") == "from-ctx"


def test_env_used_when_no_context(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "from-env")
    assert resolve_api_key("pexels") == "from-env"


def test_using_credentials_nesting():
    with using_credentials(pexels="k1"):
        with using_credentials(pexels="k2"):
            assert resolve_api_key("pexels") == "k2"
        assert resolve_api_key("pexels") == "k1"


def test_falsy_keys_ignored(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.setattr("illustration.credentials._config_store_get", lambda key: None)
    with using_credentials(pexels=""):
        # empty string is ignored; falls through to env/store (None here)
        assert resolve_api_key("pexels", api_key=None) is None


def test_keyless_provider_needs_no_key():
    # openverse has no env-var entry -> check_requirements returns None, no raise
    assert check_requirements("openverse") is None


def test_missing_key_raises_informative(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.setattr("illustration.credentials._config_store_get", lambda key: None)
    with pytest.raises(MissingCredentialError) as exc:
        check_requirements("pexels")
    msg = str(exc.value)
    assert "PEXELS_API_KEY" in msg  # names the key
    assert "pexels.com/api" in msg  # tells where to get one
    assert "secret" not in msg.lower()  # never leaks a value


def test_requires_credentials_decorator(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.setattr("illustration.credentials._config_store_get", lambda key: None)

    @requires_credentials("pexels")
    def fetch():
        return "ok"

    with pytest.raises(MissingCredentialError):
        fetch()
    with using_credentials(pexels="k"):
        assert fetch() == "ok"
