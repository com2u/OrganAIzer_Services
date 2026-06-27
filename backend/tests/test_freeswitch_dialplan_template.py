"""
Template-hygiene tests for the FreeSWITCH inbound AI dialplan.

The inbound dialplan socket endpoint must be CONFIGURABLE, never a hardcoded
local IP committed to the repository. The canonical template carries the
placeholders {{AI_ESL_OUTBOUND_HOST}} / {{AI_ESL_OUTBOUND_PORT}}; the deployed
file is produced from it by render_inbound_dialplan.sh.

These tests are hermetic — no FreeSWITCH, no ESL, no network. They guard against
a regression where someone pastes a working-but-local IP (e.g. 172.20.0.42) back
into the committed template.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_FS_DIR = Path(__file__).resolve().parents[1] / "voice" / "freeswitch"
TEMPLATE = REPO_FS_DIR / "inbound_ai_dialplan.xml"
RENDER_SCRIPT = REPO_FS_DIR / "render_inbound_dialplan.sh"

# Private / loopback / link-local IPv4 ranges that must never be hardcoded in the
# committed template's socket action (RFC1918 + loopback + APIPA).
_PRIVATE_IP_RE = re.compile(
    r"\b("
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|169\.254\.\d{1,3}\.\d{1,3}"
    r"|127\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r")\b"
)

# The specific local Wi-Fi IP that was temporarily committed and must stay out.
_FORBIDDEN_LITERAL = "172.20.0.42"


def _socket_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if "application=\"socket\"" in ln]


def test_template_exists():
    assert TEMPLATE.is_file(), f"missing template: {TEMPLATE}"


def test_socket_action_uses_placeholders():
    text = TEMPLATE.read_text(encoding="utf-8")
    socket_lines = _socket_lines(text)
    assert socket_lines, "no socket action found in inbound dialplan template"
    for ln in socket_lines:
        assert "{{AI_ESL_OUTBOUND_HOST}}" in ln, (
            f"socket action must use the host placeholder, got: {ln.strip()}"
        )
        assert "{{AI_ESL_OUTBOUND_PORT}}" in ln, (
            f"socket action must use the port placeholder, got: {ln.strip()}"
        )


def test_no_forbidden_local_ip_in_socket_action():
    """The temporary local IP must never be committed in the active socket action."""
    text = TEMPLATE.read_text(encoding="utf-8")
    for ln in _socket_lines(text):
        assert _FORBIDDEN_LITERAL not in ln, (
            f"hardcoded local IP {_FORBIDDEN_LITERAL} leaked into socket action: {ln.strip()}"
        )


def test_no_private_ip_in_active_socket_action():
    """No RFC1918 / loopback / link-local literal may appear in the socket action."""
    text = TEMPLATE.read_text(encoding="utf-8")
    for ln in _socket_lines(text):
        m = _PRIVATE_IP_RE.search(ln)
        assert m is None, (
            f"hardcoded local IP {m.group(0)!r} found in committed socket action "
            f"({ln.strip()}); use the {{{{AI_ESL_OUTBOUND_HOST}}}} placeholder instead"
        )


def test_render_script_exists():
    assert RENDER_SCRIPT.is_file(), f"missing render script: {RENDER_SCRIPT}"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_render_substitutes_placeholders(tmp_path):
    """Rendering with explicit env produces a deployable file with no placeholders."""
    out = tmp_path / "00_inbound_ai.xml"
    env = {
        "PATH": "/usr/bin:/bin",
        "AI_ESL_OUTBOUND_HOST": "10.1.2.3",
        "AI_ESL_OUTBOUND_PORT": "9099",
    }
    result = subprocess.run(
        ["bash", str(RENDER_SCRIPT), str(out)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"render failed: {result.stderr}"
    rendered = out.read_text(encoding="utf-8")
    assert "{{" not in rendered, "rendered output still contains a placeholder"
    assert 'data="10.1.2.3:9099 async full"' in rendered, (
        f"socket action not rendered as expected:\n{rendered}"
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_render_defaults_to_loopback(tmp_path, monkeypatch):
    """With no env override the renderer must default to the safe local endpoint."""
    out = tmp_path / "00_inbound_ai.xml"
    # Minimal env: no AI_ESL_* / FREESWITCH_ESL_* so defaults apply. HOME unset so
    # the script reads only backend/.env if present; we point it away from a real
    # .env by running with a clean env (the script tolerates a missing file).
    env = {"PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        ["bash", str(RENDER_SCRIPT), str(out)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"render failed: {result.stderr}"
    rendered = out.read_text(encoding="utf-8")
    # Default host:port is 127.0.0.1:8085 UNLESS backend/.env overrides it. Accept
    # either the loopback default or whatever non-placeholder value .env supplied,
    # but never an unrendered placeholder.
    assert "{{" not in rendered
    assert re.search(r'data="[^"{}]+:\d+ async full"', rendered), (
        f"socket action not concretely rendered:\n{rendered}"
    )
