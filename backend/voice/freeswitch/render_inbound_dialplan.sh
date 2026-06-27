#!/usr/bin/env bash
# render_inbound_dialplan.sh — render the inbound AI dialplan template into the
# deployed FreeSWITCH file, substituting the ESL outbound socket endpoint.
#
# The repo template (inbound_ai_dialplan.xml) is host-agnostic: it carries the
# placeholders {{AI_ESL_OUTBOUND_HOST}} and {{AI_ESL_OUTBOUND_PORT}}. This script
# resolves those from the environment (first match wins) and writes a concrete,
# deployable XML file. No host-specific IP is ever committed to the repository.
#
#   AI_ESL_OUTBOUND_HOST  ->  FREESWITCH_ESL_OUTBOUND_HOST  ->  127.0.0.1   (default)
#   AI_ESL_OUTBOUND_PORT  ->  FREESWITCH_ESL_OUTBOUND_PORT  ->  8085        (default)
#
# Values are read from backend/.env (if present) and may be overridden by real
# environment variables, e.g.:
#   AI_ESL_OUTBOUND_HOST=172.20.0.42 bash render_inbound_dialplan.sh --reload
#
# Usage:
#   bash backend/voice/freeswitch/render_inbound_dialplan.sh [OUTPUT_PATH] [--reload]
#
#   OUTPUT_PATH  Where to write the rendered XML.
#                Default: /etc/freeswitch/dialplan/public/00_inbound_ai.xml
#   --reload     After writing, run `fs_cli -x "reloadxml"` if fs_cli is on PATH.
#
# Render to a temp file for inspection without touching FreeSWITCH:
#   bash backend/voice/freeswitch/render_inbound_dialplan.sh /tmp/00_inbound_ai.xml

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TEMPLATE="$SCRIPT_DIR/inbound_ai_dialplan.xml"
DEFAULT_OUTPUT="/etc/freeswitch/dialplan/public/00_inbound_ai.xml"

OUTPUT=""
DO_RELOAD=0
for arg in "$@"; do
    case "$arg" in
        --reload) DO_RELOAD=1 ;;
        -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
        *) OUTPUT="$arg" ;;
    esac
done
OUTPUT="${OUTPUT:-$DEFAULT_OUTPUT}"

# ── Load backend/.env (real environment still wins) ──────────────────────────
ENV_FILE="$REPO_ROOT/backend/.env"
declare -A FILE_ENV=()
if [[ -f "$ENV_FILE" ]]; then
    while IFS= read -r line; do
        line="${line%$'\r'}"                       # strip CRLF
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ "$line" =~ ^[[:space:]]*$ ]] && continue
        [[ "$line" != *=* ]] && continue
        key="${line%%=*}"; val="${line#*=}"
        key="$(echo "$key" | tr -d '[:space:]')"
        val="${val%\"}"; val="${val#\"}"            # strip surrounding quotes
        val="${val%\'}"; val="${val#\'}"
        FILE_ENV["$key"]="$val"
    done < "$ENV_FILE"
fi

# resolve <VAR> from: real env -> backend/.env -> fallback chain
resolve() {
    local out=""
    for name in "$@"; do
        if [[ -n "${!name:-}" ]]; then out="${!name}"; break; fi
        if [[ -n "${FILE_ENV[$name]:-}" ]]; then out="${FILE_ENV[$name]}"; break; fi
    done
    printf '%s' "$out"
}

HOST="$(resolve AI_ESL_OUTBOUND_HOST FREESWITCH_ESL_OUTBOUND_HOST)"
PORT="$(resolve AI_ESL_OUTBOUND_PORT FREESWITCH_ESL_OUTBOUND_PORT)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8085}"

# ── Validate ─────────────────────────────────────────────────────────────────
if [[ ! -f "$TEMPLATE" ]]; then
    echo "ERROR: template not found: $TEMPLATE" >&2; exit 1
fi
if [[ -z "$HOST" ]]; then
    echo "ERROR: resolved ESL outbound host is empty" >&2; exit 1
fi
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "ERROR: resolved ESL outbound port is not numeric: '$PORT'" >&2; exit 1
fi

# ── Render ───────────────────────────────────────────────────────────────────
rendered="$(sed \
    -e "s|{{AI_ESL_OUTBOUND_HOST}}|$HOST|g" \
    -e "s|{{AI_ESL_OUTBOUND_PORT}}|$PORT|g" \
    "$TEMPLATE")"

if [[ "$rendered" == *'{{'* ]]; then
    echo "ERROR: unresolved placeholder(s) remain after render:" >&2
    echo "$rendered" | grep -n '{{' >&2 || true
    exit 1
fi

OUT_DIR="$(dirname "$OUTPUT")"
if [[ ! -d "$OUT_DIR" ]]; then
    echo "ERROR: output directory does not exist: $OUT_DIR" >&2
    echo "       (is FreeSWITCH installed on this host?)" >&2
    exit 1
fi

printf '%s\n' "$rendered" > "$OUTPUT"

echo "Rendered inbound AI dialplan:"
echo "  template : $TEMPLATE"
echo "  output   : $OUTPUT"
echo "  socket   : ${HOST}:${PORT} async full"
echo

# ── Reload ───────────────────────────────────────────────────────────────────
if [[ "$DO_RELOAD" -eq 1 ]]; then
    if command -v fs_cli &>/dev/null; then
        echo "Reloading FreeSWITCH XML..."
        fs_cli -x "reloadxml"
    else
        echo "WARNING: --reload requested but fs_cli not on PATH." >&2
        echo "         Run manually:  fs_cli -x \"reloadxml\"" >&2
    fi
else
    echo "Next step — apply in FreeSWITCH:"
    echo "  fs_cli -x \"reloadxml\""
fi
