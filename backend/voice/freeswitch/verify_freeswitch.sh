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
            if [[ "$host_port" == "127.0.0.1:8085" ]]; then
                ok "Target is 127.0.0.1:8085 — correct for WSL-local topology"
            else
                warn "Target is $host_port — expected 127.0.0.1:8085 for WSL-local setup"
                warn "If backend and FreeSWITCH are on the same WSL instance, update to 127.0.0.1:8085"
            fi
        fi
    else
        warn "No 'socket' action found in $DEPLOYED_INBOUND_XML"
    fi
else
    fail "Not found: $DEPLOYED_INBOUND_XML"
    warn "Inbound calls will not be routed to the backend until this file is deployed"
    warn "Deploy with:"
    warn "  cp $REPO_INBOUND_XML $DEPLOYED_INBOUND_XML"
    warn "  fs_cli -x 'reloadxml'"
fi

# ══════════════════════════════════════════════════════════════════════════════
hdr "6. Drift check — repo template vs deployed inbound dialplan"
# ══════════════════════════════════════════════════════════════════════════════

cmd "test -f $REPO_INBOUND_XML"
if [[ ! -f "$REPO_INBOUND_XML" ]]; then
    fail "Repo template not found: $REPO_INBOUND_XML"
elif [[ ! -f "$DEPLOYED_INBOUND_XML" ]]; then
    warn "Deployed file does not exist — cannot compare (see section 5)"
else
    cmd "diff $REPO_INBOUND_XML $DEPLOYED_INBOUND_XML"
    diff_out=$(diff "$REPO_INBOUND_XML" "$DEPLOYED_INBOUND_XML" 2>&1 || true)
    if [[ -z "$diff_out" ]]; then
        ok "Files are identical — no drift detected"
    else
        warn "Deployed file differs from repo template:"
        echo "$diff_out"
    fi
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
echo    "    3. Deployed dialplan must exist and point to 127.0.0.1:8085 (section 5)"
echo    "    4. COMtrexx must be routing calls to extension 003010"
echo    "       — OPTIONS in the log means SIP is up; INVITE means a call was sent"
echo    "       — No INVITE = COMtrexx is not forwarding to 003010"
echo
