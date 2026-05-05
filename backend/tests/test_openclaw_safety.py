"""
OpenClaw safety tests.

Covers:
  - docker-compose OpenClaw service has no exposed ports
  - Volume is bounded to ./infra/openclaw/openclaw-data only
  - No Docker socket mount, no repo root mount
  - Security settings: read_only, cap_drop ALL, no-new-privileges:true
  - openclaw.json denies risky tool groups (browser, filesystem, runtime, cron)
  - OpenClawClient instantiates and issues correct HTTP calls (mocked aiohttp)
  - API router exposes exactly /cleanup and /summarize

No real OpenClaw calls. No Docker commands. No network.
aiohttp is mocked for all client HTTP tests.
openclaw.json is checked with raw string reads — it is JSON5, not strict JSON.
"""

import asyncio
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

yaml = pytest.importorskip("yaml")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.openclaw_client import OpenClawClient

# ── File paths (derived from __file__ so they work regardless of cwd) ─────────
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DOCKER_COMPOSE_PATH = os.path.join(_REPO_ROOT, "docker-compose.yml")
_OPENCLAW_JSON_PATH = os.path.join(
    _REPO_ROOT, "infra", "openclaw", "openclaw-data", "openclaw.json"
)

# Parse docker-compose.yml once at module load (valid YAML)
with open(_DOCKER_COMPOSE_PATH) as _f:
    _COMPOSE = yaml.safe_load(_f)

_OPENCLAW_SVC = _COMPOSE["services"]["openclaw"]

# Read openclaw.json as raw text — JSON5 format (unquoted keys, // comments)
# json.load() would raise JSONDecodeError; raw string checks are used instead
with open(_OPENCLAW_JSON_PATH) as _f:
    _CONFIG_TEXT = _f.read()


# ── Async helper ──────────────────────────────────────────────────────────────
def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── aiohttp mock factory ──────────────────────────────────────────────────────
def _mock_aiohttp(status: int = 200, json_body: dict = None, text_body: str = "error"):
    """
    Build nested async context manager mocks for:
        async with aiohttp.ClientSession(timeout=...) as session:
            async with session.post(url, ...) as response:
    """
    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.json = AsyncMock(return_value=json_body or {})
    mock_response.text = AsyncMock(return_value=text_body)

    mock_post_cm = MagicMock()
    mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_post_cm)

    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=None)

    return mock_session_cm, mock_session, mock_response


# =============================================================================
# docker-compose OpenClaw service — infrastructure safety
# =============================================================================

class TestDockerComposeOpenClawSafety:
    """Verify openclaw service in docker-compose.yml meets all security requirements."""

    def test_openclaw_has_no_exposed_ports(self):
        ports = _OPENCLAW_SVC.get("ports")
        assert not ports, (
            f"openclaw service must have no exposed ports, found: {ports!r}"
        )

    def test_openclaw_volume_is_bounded_data_directory(self):
        volumes = _OPENCLAW_SVC.get("volumes", [])
        assert "./infra/openclaw/openclaw-data:/home/node/.openclaw" in volumes, (
            f"Expected bounded mount not found. Volumes: {volumes!r}"
        )

    def test_openclaw_volume_count_is_one(self):
        volumes = _OPENCLAW_SVC.get("volumes", [])
        assert len(volumes) == 1, (
            f"openclaw must have exactly one volume mount, found {len(volumes)}: {volumes!r}"
        )

    def test_openclaw_does_not_mount_docker_socket(self):
        for vol in _OPENCLAW_SVC.get("volumes", []):
            assert "/var/run/docker.sock" not in str(vol), (
                f"Docker socket must not be mounted: {vol!r}"
            )

    def test_openclaw_does_not_mount_repo_root(self):
        for vol in _OPENCLAW_SVC.get("volumes", []):
            host_side = str(vol).split(":")[0]
            assert host_side not in (".", "./", "/", "../", "../.."), (
                f"Repo root or broad path mount detected: {vol!r}"
            )

    def test_openclaw_read_only_true(self):
        assert _OPENCLAW_SVC.get("read_only") is True, (
            "openclaw service must have read_only: true"
        )

    def test_openclaw_cap_drop_includes_all(self):
        cap_drop = _OPENCLAW_SVC.get("cap_drop", [])
        assert "ALL" in cap_drop, (
            f"cap_drop must include ALL, got: {cap_drop!r}"
        )

    def test_openclaw_security_opt_includes_no_new_privileges(self):
        security_opt = _OPENCLAW_SVC.get("security_opt", [])
        assert "no-new-privileges:true" in security_opt, (
            f"security_opt must include no-new-privileges:true, got: {security_opt!r}"
        )


# =============================================================================
# openclaw.json — tool configuration safety (raw string, JSON5 format)
# =============================================================================

class TestOpenClawConfigSafety:
    """
    openclaw.json uses JSON5 — unquoted keys and // comments make json.load fail.
    All assertions check the raw file text directly.
    """

    def test_config_file_exists(self):
        assert os.path.isfile(_OPENCLAW_JSON_PATH), (
            f"openclaw.json not found at {_OPENCLAW_JSON_PATH}"
        )

    def test_tools_profile_is_minimal(self):
        assert '"minimal"' in _CONFIG_TEXT, (
            "tools.profile must be set to 'minimal'"
        )

    def test_browser_tool_denied(self):
        assert '"browser"' in _CONFIG_TEXT, (
            "browser tool group must appear in the deny list"
        )

    def test_filesystem_tool_denied(self):
        assert '"filesystem"' in _CONFIG_TEXT, (
            "filesystem tool group must appear in the deny list"
        )

    def test_runtime_tool_denied(self):
        assert '"runtime"' in _CONFIG_TEXT, (
            "runtime tool group must appear in the deny list"
        )

    def test_cron_tool_denied(self):
        assert '"cron"' in _CONFIG_TEXT, (
            "cron tool group must appear in the deny list"
        )

    def test_gateway_auth_mode_is_token(self):
        assert '"token"' in _CONFIG_TEXT, (
            "gateway auth.mode must be 'token'"
        )


# =============================================================================
# OpenClawClient construction — no network
# =============================================================================

class TestOpenClawClientConstruction:

    def test_client_instantiates_without_network(self):
        client = OpenClawClient("http://localhost:18789", "fake-token")
        assert client is not None

    def test_base_url_trailing_slash_stripped(self):
        client = OpenClawClient("http://localhost:18789/", "t")
        assert client.base_url == "http://localhost:18789"

    def test_client_stores_token(self):
        client = OpenClawClient("http://localhost:18789", "my-secret-token")
        assert client.token == "my-secret-token"


# =============================================================================
# OpenClawClient HTTP calls — aiohttp mocked, no network
# =============================================================================

class TestOpenClawClientHTTP:

    def setup_method(self):
        self.client = OpenClawClient("http://localhost:18789", "fake-token")

    def test_cleanup_request_posts_to_chat_completions(self):
        session_cm, mock_session, _ = _mock_aiohttp(
            json_body={"choices": [{"message": {"content": "ok"}}]}
        )
        with patch("services.openclaw_client.aiohttp.ClientSession", return_value=session_cm):
            _run(self.client.cleanup_request("normalize this"))

        call_url = mock_session.post.call_args.args[0]
        assert "/v1/chat/completions" in call_url

    def test_cleanup_request_sends_bearer_header(self):
        session_cm, mock_session, _ = _mock_aiohttp(
            json_body={"choices": [{"message": {"content": "ok"}}]}
        )
        with patch("services.openclaw_client.aiohttp.ClientSession", return_value=session_cm):
            _run(self.client.cleanup_request("normalize this"))

        headers = mock_session.post.call_args.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer fake-token"

    def test_cleanup_request_returns_cleaned_text(self):
        session_cm, _, _ = _mock_aiohttp(
            json_body={"choices": [{"message": {"content": "cleaned result"}}]}
        )
        with patch("services.openclaw_client.aiohttp.ClientSession", return_value=session_cm):
            result = _run(self.client.cleanup_request("raw input"))

        assert result == {"cleaned_text": "cleaned result"}

    def test_summarize_text_posts_to_chat_completions(self):
        session_cm, mock_session, _ = _mock_aiohttp(
            json_body={"choices": [{"message": {"content": "summary"}}]}
        )
        with patch("services.openclaw_client.aiohttp.ClientSession", return_value=session_cm):
            _run(self.client.summarize_text("long text here"))

        call_url = mock_session.post.call_args.args[0]
        assert "/v1/chat/completions" in call_url

    def test_summarize_text_returns_summary(self):
        session_cm, _, _ = _mock_aiohttp(
            json_body={"choices": [{"message": {"content": "short summary"}}]}
        )
        with patch("services.openclaw_client.aiohttp.ClientSession", return_value=session_cm):
            result = _run(self.client.summarize_text("long text"))

        assert result == {"summary": "short summary"}

    def test_cleanup_request_raises_on_non_200(self):
        session_cm, _, _ = _mock_aiohttp(status=500, text_body="Internal Server Error")
        with patch("services.openclaw_client.aiohttp.ClientSession", return_value=session_cm):
            with pytest.raises(Exception, match="OpenClaw cleanup failed"):
                _run(self.client.cleanup_request("hello"))

    def test_summarize_raises_on_non_200(self):
        session_cm, _, _ = _mock_aiohttp(status=503, text_body="Unavailable")
        with patch("services.openclaw_client.aiohttp.ClientSession", return_value=session_cm):
            with pytest.raises(Exception, match="OpenClaw summarization failed"):
                _run(self.client.summarize_text("hello"))


# =============================================================================
# OpenClaw API router — structure only, no server needed
# =============================================================================

class TestOpenClawAPIRouter:

    def test_router_is_importable(self):
        from api.openclaw import router
        assert router is not None

    def test_router_has_exactly_two_routes(self):
        from api.openclaw import router
        assert len(router.routes) == 2, (
            f"Expected 2 routes, found {len(router.routes)}: "
            f"{[r.path for r in router.routes]!r}"
        )

    def test_cleanup_route_exists(self):
        from api.openclaw import router
        paths_and_methods = {
            (r.path, m)
            for r in router.routes
            for m in r.methods
        }
        assert ("/cleanup", "POST") in paths_and_methods, (
            f"POST /cleanup not found. Routes: {paths_and_methods!r}"
        )

    def test_summarize_route_exists(self):
        from api.openclaw import router
        paths_and_methods = {
            (r.path, m)
            for r in router.routes
            for m in r.methods
        }
        assert ("/summarize", "POST") in paths_and_methods, (
            f"POST /summarize not found. Routes: {paths_and_methods!r}"
        )
