#!/usr/bin/env bash
# verify_freeswitch.sh — read-only diagnostic for FreeSWITCH / COMtrexx / backend
#
# Run from the repo root:
#   bash backend/voice/freeswitch/verify_freeswitch.sh
#
# Nothing is modified.  No secrets are required.  Missing tools/files are noted
# and the script continues rather than aborting.

set -euo pipefail

# ── colour helpers ─────────────────────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'
CYN='\033[0;36m'; BLD='\033[1m'; RST='\033[0m'

hdr()  { echo; echo -e "${BLD}${CYN}══ $* ══${RST}"; }
ok()   { echo -e "  ${GRN}✔${RST}  $*"; }
warn() { echo -e "  ${YEL}⚠${RST}  $*"; }
fail() { echo -e "  ${RED}✘${RST}  $*"; }
cmd()  { echo -e "  ${CYN}▶${RST}  $*"; }

run() {
    # run <description> <command…>
    # Prints the command, runs it, captures output. Never aborts on error.
    local desc="$1"; shift
    cmd "$*"
    local out
    if out=$("$@" 2>&1); then
        echo "$out"
    else
        warn "command returned non-zero (exit $?)"
        echo "$out"
    fi
}

require() {
    # require <tool> — warn if not on PATH
    if ! command -v "$1" &>/dev/null; then
        warn "'$1' not found on PATH — skipping related checks"
        return 1
    fi
    return 0
}

# ── repo anchor ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
REPO_INBOUND_XML="$SCRIPT_DIR/inbound_ai_dialplan.xml"
DEPLOYED_INBOUND_XML="/etc/freeswitch/dialplan/public/00_inbound_ai.xml"
FS_LOG="/var/log/freeswitch/freeswitch.log"

echo
echo -e "${BLD}FreeSWITCH / COMtrexx / Backend — Runtime Diagnostic${RST}"
echo -e "  Repo root : $REPO_ROOT"
echo -e "  Run at    : $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

# ══════════════════════════════════════════════════════════════════════════════
hdr "1. Backend listening on port 8085 (ESL outbound socket)"
# ══════════════════════════════════════════════════════════════════════════════

if require ss; then
    cmd "ss -tlnp | grep ':8085'"
    result=$(ss -tlnp 2>/dev/null | grep ':8085' || true)
    if [[ -n "$result" ]]; then
        ok "Port 8085 is bound"
        echo "$result"
    else
        fail "Nothing is listening on port 8085 — backend may not be running"
    fi
elif require netstat; then
    cmd "netstat -tlnp | grep ':8085'"
    result=$(netstat -tlnp 2>/dev/null | grep ':8085' || true)
    if [[ -n "$result" ]]; then
        ok "Port 8085 is bound"
        echo "$result"
    else
        fail "Nothing is listening on port 8085"
    fi
else
    fail "Neither 'ss' nor 'netstat' found — cannot check port binding"
fi

# ══════════════════════════════════════════════════════════════════════════════
hdr "2. FreeSWITCH gateway 'comtrexx' registration status"
# ══════════════════════════════════════════════════════════════════════════════

if require fs_cli; then
    cmd "fs_cli -x 'sofia status gateway comtrexx'"
    gw_out=$(fs_cli -x 'sofia status gateway comtrexx' 2>&1 || true)
    echo "$gw_out"
    if echo "$gw_out" | grep -q 'REGED'; then
        ok "Gateway comtrexx: REGED (registered)"
    elif echo "$gw_out" | grep -q 'NOREG\|DOWN\|FAIL\|TRYING'; then
        fail "Gateway comtrexx is NOT registered — inbound calls will not arrive"
    else
        warn "Could not parse gateway state from output above"
    fi
else
    fail "'fs_cli' not found — FreeSWITCH may not be installed or not on PATH"
fi

# ══════════════════════════════════════════════════════════════════════════════
hdr "3. Active channels (CallsIN / CallsOUT)"
# ══════════════════════════════════════════════════════════════════════════════

if require fs_cli; then
    cmd "fs_cli -x 'show channels'"
    fs_cli -x 'show channels' 2>&1 || warn "Command returned non-zero"

    echo
    cmd "fs_cli -x 'status'"
    status_out=$(fs_cli -x 'status' 2>&1 || true)
    echo "$status_out"
    # Extract session counters line
    sessions=$(echo "$status_out" | grep -i 'session\|call' | head -5 || true)
    if [[ -n "$sessions" ]]; then
        ok "Session stats shown above"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
hdr "4. External SIP profile — SIP bind address and RTP IPs"
# ══════════════════════════════════════════════════════════════════════════════

if require fs_cli; then
    cmd "fs_cli -x 'sofia status profile external'"
    profile_out=$(fs_cli -x 'sofia status profile external' 2>&1 || true)
    echo "$profile_out"

    sip_ip=$(echo "$profile_out" | grep -i 'rtp-ip\|sip-ip\|bind\|local' | head -8 || true)
    if [[ -n "$sip_ip" ]]; then
        ok "SIP/RTP IP lines shown above"
    else
        warn "Could not extract SIP/RTP IP lines from profile output"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
hdr "5. Deployed inbound dialplan — existence and socket target"
# ══════════════════════════════════════════════════════════════════════════════

cmd "test -f $DEPLOYED_INBOUND_XML"
if [[ -f "$DEPLOYED_INBOUND_XML" ]]; then
    ok "File exists: $DEPLOYED_INBOUND_XML"

    cmd "grep -n 'socket' $DEPLOYED_INBOUND_XML"
    socket_line=$(grep -n 'socket' "$DEPLOYED_INBOUND_XML" 2>/dev/null || true)
    if [[ -n "$socket_line" ]]; then
        echo "$socket_line"
        # Extract the host:port from   data="HOST:PORT async full"
        socket_target=$(echo "$socket_line" | grep -oP '(?<=data=")[^"]+' | head -1 || true)
        if [[ -n "$socket_target" ]]; then
            host_port="${socket_target%% *}"   # strip " async full"
            ok "Dialplan socket target: $host_port"
            # Expected endpoint is configurable (see render_inbound_dialplan.sh):
            #   AI_ESL_OUTBOUND_HOST -> FREESWITCH_ESL_OUTBOUND_HOST -> 127.0.0.1
            #   AI_ESL_OUTBOUND_PORT -> FREESWITCH_ESL_OUTBOUND_PORT -> 8085
            exp_host="${AI_ESL_OUTBOUND_HOST:-${FREESWITCH_ESL_OUTBOUND_HOST:-127.0.0.1}}"
            exp_port="${AI_ESL_OUTBOUND_PORT:-${FREESWITCH_ESL_OUTBOUND_PORT:-8085}}"
            if [[ "$host_port" == "${exp_host}:${exp_port}" ]]; then
                ok "Target matches configured endpoint ${exp_host}:${exp_port}"
            else
                warn "Target $host_port differs from configured AI_ESL_OUTBOUND endpoint ${exp_host}:${exp_port}"
                warn "If this is intentional (e.g. Windows portproxy uses a host IP), ignore."
                warn "Otherwise re-render: bash backend/voice/freeswitch/render_inbound_dialplan.sh --reload"
            fi
            if [[ "$host_port" == *'{{'* ]]; then
                fail "Deployed dialplan still contains an unrendered placeholder — run render_inbound_dialplan.sh"
            fi
        fi
    else
        warn "No 'socket' action found in $DEPLOYED_INBOUND_XML"
    fi
else
    fail "Not found: $DEPLOYED_INBOUND_XML"
    warn "Inbound calls will not be routed to the backend until this file is rendered"
    warn "Render + deploy with (do NOT cp the template — it has placeholders):"
    warn "  bash $SCRIPT_DIR/render_inbound_dialplan.sh --reload"
fi

# ══════════════════════════════════════════════════════════════════════════════
hdr "6. Drift check — rendered repo template vs deployed inbound dialplan"
# ══════════════════════════════════════════════════════════════════════════════

# The repo template carries {{AI_ESL_OUTBOUND_*}} placeholders, so it never
# matches the deployed file byte-for-byte. Render it with the same endpoint the
# deployment uses, then compare — this still catches genuine drift (extra rules,
# stale logic) without flagging the expected placeholder substitution.
cmd "test -f $REPO_INBOUND_XML"
if [[ ! -f "$REPO_INBOUND_XML" ]]; then
    fail "Repo template not found: $REPO_INBOUND_XML"
elif [[ ! -f "$DEPLOYED_INBOUND_XML" ]]; then
    warn "Deployed file does not exist — cannot compare (see section 5)"
else
    rendered_tmp="$(mktemp)"
    if bash "$SCRIPT_DIR/render_inbound_dialplan.sh" "$rendered_tmp" >/dev/null 2>&1; then
        cmd "diff <(render template) $DEPLOYED_INBOUND_XML"
        diff_out=$(diff "$rendered_tmp" "$DEPLOYED_INBOUND_XML" 2>&1 || true)
        if [[ -z "$diff_out" ]]; then
            ok "Rendered template matches deployed file — no drift detected"
        else
            warn "Deployed file differs from rendered template:"
            echo "$diff_out"
            warn "Re-render if needed: bash $SCRIPT_DIR/render_inbound_dialplan.sh --reload"
        fi
    else
        warn "Could not render template for comparison (see render_inbound_dialplan.sh)"
    fi
    rm -f "$rendered_tmp"
fi

# ══════════════════════════════════════════════════════════════════════════════
hdr "7. Recent FreeSWITCH log — OPTIONS, INVITE, NO_ROUTE, socket, ai_inbound"
# ══════════════════════════════════════════════════════════════════════════════

cmd "test -f $FS_LOG"
if [[ ! -f "$FS_LOG" ]]; then
    warn "Log file not found: $FS_LOG"
    warn "Trying alternate location: /var/log/freeswitch/*.log"
    alt_log=$(ls /var/log/freeswitch/*.log 2>/dev/null | head -1 || true)
    if [[ -n "$alt_log" ]]; then
        ok "Using: $alt_log"
        FS_LOG="$alt_log"
    else
        fail "No FreeSWITCH log found — is FreeSWITCH installed?"
        FS_LOG=""
    fi
fi

if [[ -n "$FS_LOG" && -f "$FS_LOG" ]]; then
    cmd "grep -i 'OPTIONS\|INVITE\|NO_ROUTE\|socket\|ai_inbound' $FS_LOG | tail -20"
    log_hits=$(grep -i 'OPTIONS\|INVITE\|NO_ROUTE\|socket\|ai_inbound' "$FS_LOG" 2>/dev/null | tail -20 || true)
    if [[ -n "$log_hits" ]]; then
        echo "$log_hits"
    else
        warn "No matching log lines found — FS may be idle or log was rotated"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
hdr "Summary"
# ══════════════════════════════════════════════════════════════════════════════

echo
echo -e "  ${BLD}Key things to check if inbound calls are not arriving:${RST}"
echo    "    1. Gateway must be REGED   (section 2)"
echo    "    2. Port 8085 must be bound (section 1)"
echo    "    3. Deployed dialplan must exist and point to the configured AI_ESL_OUTBOUND endpoint (section 5)"
echo    "    4. COMtrexx must be routing calls to extension 003010"
echo    "       — OPTIONS in the log means SIP is up; INVITE means a call was sent"
echo    "       — No INVITE = COMtrexx is not forwarding to 003010"
echo
