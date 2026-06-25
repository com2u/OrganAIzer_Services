---
id: comtrexx-registration-troubleshooting
type: procedure
owner: comtrexx-integration-guardian
status: active
last_reviewed: 2026-06-24
sources:
  - backend/voice/freeswitch/verify_freeswitch.sh
  - backend/voice/freeswitch/README.md
  - backend/voice/freeswitch/comtrexx_gateway.xml
  - backend/voice/config.py
---

# COMtrexx gateway registration troubleshooting

## When to use

Inbound calls are not reaching the AI, or you need to confirm the FreeSWITCH
`comtrexx` gateway is registered with the COMtrexx PBX.

## Prerequisites

- Access to the host where FreeSWITCH runs (WSL), with `fs_cli` on PATH.
- Repository checked out (for `verify_freeswitch.sh` and the XML templates).
- No secrets required — the diagnostic is read-only.

## Steps

1. Run the read-only diagnostic from the repo root:
   ```bash
   bash backend/voice/freeswitch/verify_freeswitch.sh
   ```
2. Check the gateway registration state directly:
   ```bash
   fs_cli -x 'sofia status gateway comtrexx'
   ```
3. If the gateway is not registered after a config change, restart the external
   SIP profile (per `backend/voice/freeswitch/README.md`):
   ```bash
   fs_cli -x 'sofia profile external restart'
   ```

## Validation

- Section 2 of `verify_freeswitch.sh` reports the gateway state.
- `sofia status gateway comtrexx` output contains `REGED`.

## Expected outcomes

- **Healthy:** gateway state is `REGED` (registered). COMtrexx address is
  `172.20.0.244`, SIP/TLS `5061`, extension `003010` (authoritative values live in
  `comtrexx_gateway.xml` / `config.py` — see those files, do not hardcode elsewhere).

## Common failure modes

- **`NOREG` / `DOWN` / `FAIL` / `TRYING`** — gateway not registered; inbound calls
  will not arrive (flagged by `verify_freeswitch.sh` section 2).
- **`fs_cli` not found** — FreeSWITCH not installed or not on PATH.
- **OPTIONS in the log but no INVITE** — SIP is up but COMtrexx is not routing calls
  to extension `003010` (per `verify_freeswitch.sh` summary). This is an
  upstream/COMtrexx-side routing issue, not a FreeSWITCH registration issue.

## Recovery

- After editing `comtrexx_gateway.xml`, deploy it to the path documented in
  `backend/voice/freeswitch/README.md` and apply with
  `fs_cli -x 'sofia profile external restart'`, then re-run `verify_freeswitch.sh`.
- The repo XML is a **template** containing `YOUR_SIP_PASSWORD_HERE`; the real SIP
  password must be present in the deployed copy (never committed).

## Notes

- **Needs Human Confirmation:** COMtrexx-side admin steps (credentials, the routing
  rule that forwards calls to `003010`) are configured in the COMtrexx admin UI and
  are not described in the repository.
