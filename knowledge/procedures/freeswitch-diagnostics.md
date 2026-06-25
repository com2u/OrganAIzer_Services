---
id: freeswitch-diagnostics
type: procedure
owner: voice-freeswitch-guardian
status: active
last_reviewed: 2026-06-24
sources:
  - backend/voice/freeswitch/verify_freeswitch.sh
  - backend/voice/freeswitch/README.md
  - backend/voice/freeswitch/inbound_ai_dialplan.xml
---

# FreeSWITCH runtime diagnostics

## When to use

To get a read-only snapshot of the FreeSWITCH / COMtrexx / backend runtime when
diagnosing inbound-call or ESL-socket problems. Nothing is modified.

## Prerequisites

- Run on the host where FreeSWITCH runs (WSL).
- Tools used by the script when present: `ss` (or `netstat`), `fs_cli`, `grep`,
  `diff`. Missing tools are noted and skipped.

## Steps

1. Run the diagnostic from the repo root:
   ```bash
   bash backend/voice/freeswitch/verify_freeswitch.sh
   ```

The script checks, in order:
1. Backend listening on the **ESL outbound** port `8085` (`ss`/`netstat`).
2. `comtrexx` gateway registration (`fs_cli -x 'sofia status gateway comtrexx'`).
3. Active channels and status (`fs_cli -x 'show channels'`, `fs_cli -x 'status'`).
4. External SIP profile bind/RTP IPs (`fs_cli -x 'sofia status profile external'`).
5. Deployed inbound dialplan existence and socket target
   (`/etc/freeswitch/dialplan/public/00_inbound_ai.xml`; expected target
   `127.0.0.1:8085`).
6. Drift between the repo template (`inbound_ai_dialplan.xml`) and the deployed file.
7. Recent FreeSWITCH log lines (`OPTIONS`, `INVITE`, `NO_ROUTE`, `socket`,
   `ai_inbound`) from `/var/log/freeswitch/freeswitch.log`.

## Validation

- Each section prints `✔` (ok), `⚠` (warn), or `✘` (fail) per the script.

## Expected outcomes

- Port `8085` bound; gateway `REGED`; deployed dialplan present and pointing to
  `127.0.0.1:8085`; no drift vs the repo template.

## Common failure modes

- **Nothing listening on `8085`** — backend not running (section 1).
- **Gateway not `REGED`** — see `comtrexx-registration-troubleshooting` (section 2).
- **Deployed dialplan missing / wrong socket target** — inbound calls are not routed
  to the backend (section 5).
- **Drift detected** — deployed XML differs from the repo template (section 6).
- **OPTIONS but no INVITE** — SIP up, but COMtrexx not forwarding to `003010`
  (section 7 / summary).

## Recovery

- If the deployed dialplan is missing, the script prints the exact deploy step:
  copy `inbound_ai_dialplan.xml` to
  `/etc/freeswitch/dialplan/public/00_inbound_ai.xml`, then
  `fs_cli -x 'reloadxml'` (also documented in `backend/voice/freeswitch/README.md`).

## Notes

- The script is read-only and never aborts on a single failed check.
- Authoritative ESL/COMtrexx addresses live in `config.py`, the FreeSWITCH XML, and
  `backend/voice/freeswitch/README.md` — diagnose against those, do not restate them.
