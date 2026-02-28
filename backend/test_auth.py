"""
Unit tests for backend/auth.py

Covers:
- Missing API_KEYS env var → RuntimeError at import time
- Valid key in X-API-Key header → passes, returns key
- Invalid key in X-API-Key header → raises HTTP 401
"""

import importlib
import os
import sys
import types
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reload_auth(monkeypatch, api_keys_value: str | None):
    """
    (Re-)import backend.auth with a controlled API_KEYS env value.

    api_keys_value=None means the variable is absent from the environment.
    """
    # Patch the environment before importing
    if api_keys_value is None:
        monkeypatch.delenv("API_KEYS", raising=False)
    else:
        monkeypatch.setenv("API_KEYS", api_keys_value)

    # Remove cached module so the module-level code re-executes
    sys.modules.pop("auth", None)
    sys.modules.pop("backend.auth", None)

    # Import from the backend package directory
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location(
        "auth",
        pathlib.Path(__file__).parent / "auth.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _load_auth_module(monkeypatch, api_keys=None, api_key=None):
    """Helper: reload auth with controlled env vars."""
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    if api_keys is not None:
        monkeypatch.setenv("API_KEYS", api_keys)
    if api_key is not None:
        monkeypatch.setenv("API_KEY", api_key)
    sys.modules.pop("auth", None)
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location(
        "auth", pathlib.Path(__file__).parent / "auth.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMissingApiKeys:
    """Module startup raises RuntimeError when neither API_KEYS nor API_KEY is set."""

    def test_both_absent_raises(self, monkeypatch):
        with pytest.raises(RuntimeError):
            _load_auth_module(monkeypatch)

    def test_api_keys_empty_string_raises(self, monkeypatch):
        with pytest.raises(RuntimeError):
            _load_auth_module(monkeypatch, api_keys="")

    def test_api_keys_only_commas_raises(self, monkeypatch):
        with pytest.raises(RuntimeError):
            _load_auth_module(monkeypatch, api_keys=",,,")


class TestApiKeyFallback:
    """API_KEY (singular, legacy) is accepted as a fallback."""

    @pytest.mark.asyncio
    async def test_legacy_api_key_is_accepted(self, monkeypatch):
        """Existing .env files using API_KEY (singular) must still work."""
        mod = _load_auth_module(monkeypatch, api_key="legacy-key")
        result = await mod.get_api_key("legacy-key")
        assert result == "legacy-key"

    @pytest.mark.asyncio
    async def test_api_keys_takes_precedence_over_api_key(self, monkeypatch):
        """When both are set, API_KEYS wins and API_KEY is ignored."""
        mod = _load_auth_module(monkeypatch, api_keys="new-key", api_key="old-key")
        result = await mod.get_api_key("new-key")
        assert result == "new-key"
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            await mod.get_api_key("old-key")


class TestGetApiKey:
    """get_api_key dependency function behaviour."""

    @pytest.fixture()
    def auth(self, monkeypatch):
        """Load auth module with a known set of keys."""
        return _reload_auth(monkeypatch, "valid-key-1,valid-key-2")

    @pytest.mark.asyncio
    async def test_valid_key_is_accepted(self, auth):
        result = await auth.get_api_key("valid-key-1")
        assert result == "valid-key-1"

    @pytest.mark.asyncio
    async def test_second_valid_key_is_accepted(self, auth):
        result = await auth.get_api_key("valid-key-2")
        assert result == "valid-key-2"

    @pytest.mark.asyncio
    async def test_invalid_key_raises_401(self, auth):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await auth.get_api_key("not-a-real-key")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_key_raises_401(self, auth):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await auth.get_api_key("")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_key_with_surrounding_whitespace_is_trimmed(self, monkeypatch):
        """Keys defined with spaces around commas must still work."""
        auth = _reload_auth(monkeypatch, " spaced-key , another-key ")
        result = await auth.get_api_key("spaced-key")
        assert result == "spaced-key"
