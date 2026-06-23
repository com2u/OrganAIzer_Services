# FreeSWITCH / COMtrexx — Architecture & Diagnostics

## Runtime topology

```
COMtrexx PBX (172.20.0.244)
  │  SIP/TLS :5061 (registration)
  │  SIP/TLS :5061 (inbound INVITE)
  │  SRTP ←→ RTP
  ▼
FreeSWITCH (WSL — same host as backend)
  │  ESL inbound  127.0.0.1:8021  (Python → FS for originate / status)
  │  ESL outbound 127.0.0.1:8085  (FS → Python, one TCP conn per call)
  ▼
Python backend (WSL — backend/main.py)
  │  faster-whisper STT
  │  edge-tts TTS
  │  OpenRouter LLM
  ▼
Caller (PSTN / SIP phone)
```

**Both FreeSWITCH and the Python backend run inside WSL on the same host.**
Because they share the same WSL instance, all ESL communication uses `127.0.0.1`.
The WSL2 gateway IP (`172.21.224.1`) is only relevant when one process runs on
Windows and the other in WSL — that is NOT the current topology.

### Key addresses

| Parameter | Value | Where set |
|---|---|---|
| COMtrexx IP | `172.20.0.244` | `comtrexx_gateway.xml`, `inbound_ai_dialplan.xml`, `config.py` default |
| SIP username / extension | `003010` | `comtrexx_gateway.xml` |
| COMtrexx internal user | `29 / Renato AI` | COMtrexx admin UI |
| FS → COMtrexx (SIP/TLS) | `172.20.0.244:5061` | `comtrexx_gateway.xml` |
| Python listens for ESL outbound | `0.0.0.0:8085` | `main.py` / `FREESWITCH_ESL_OUTBOUND_PORT` |
| FS connects to Python | `127.0.0.1:8085` | `inbound_ai_dialplan.xml` socket action |
| Python → FS ESL inbound | `127.0.0.1:8021` | `FREESWITCH_ESL_HOST` / `FREESWITCH_ESL_PORT` |
| ESL password | `ClueCon` (default) | `FREESWITCH_ESL_PASSWORD` |
| Escalation park orbits | `778`, `779` | `AI_WAITING_ROOM_PRIMARY/SECONDARY` |

---

## Inbound vs outbound call flow

### Outbound (Python-initiated)

1. Python calls `originate_call()` in `voice/outbound.py`.
2. `send_api_command()` sends `originate {vars}sofia/gateway/comtrexx/<number> &socket(127.0.0.1:8085 async full)` to FS over ESL inbound (port 8021).
3. FS dials the number via the `comtrexx` gateway (SIP/TLS → COMtrexx → PSTN).
4. When the remote answers, FS connects back to Python on port 8085 (ESL outbound socket).
5. `handle_esl_call()` picks it up, matches the UUID via `pop_outbound_context()`, and runs the outbound AI conversation loop.

**Trigger:** Python. No dialplan involved for the initial leg.

### Inbound (COMtrexx-initiated)

1. An external call arrives at COMtrexx.
2. COMtrexx sends a SIP **INVITE** to FreeSWITCH (extension 003010 is registered via `comtrexx_gateway.xml`).
3. FS matches the INVITE against the dialplan context `public` → `00_inbound_ai.xml`.
4. The dialplan executes `socket 127.0.0.1:8085 async full` — FS connects to Python.
5. Python performs the ESL handshake, then runs the inbound AI conversation loop.

**Trigger:** COMtrexx sends an INVITE. This requires:
- The gateway is REGED (`sofia status gateway comtrexx` → `REGED`).
- COMtrexx has a routing rule that forwards calls to extension 003010.
- `00_inbound_ai.xml` is deployed and `reloadxml` has been run after any change.

### Why OPTIONS is not an inbound call

SIP OPTIONS is a keep-alive / capability probe sent by COMtrexx to check whether
FreeSWITCH is reachable. It does **not** carry audio and does **not** trigger the
dialplan. Seeing OPTIONS in the FS log means the SIP connection is alive but it
does **not** mean inbound calls will work. Only an INVITE starts a call session.

If you see OPTIONS but no INVITE for a call you expected to ring, the problem is
upstream of FreeSWITCH: COMtrexx is not routing the call to extension 003010.

---

## Escalation / waiting room

When the AI escalates, it parks the caller in the COMtrexx waiting room using a
SIP **REFER (deflect)** to `sip:778@<COMtrexx IP>` (primary orbit), falling back
to `779` (secondary). REFER is used because a direct bridge INVITE to a park
orbit is rejected by COMtrexx with cause 88 `INCOMPATIBLE_DESTINATION` — only the
REFER from the internal `003010` leg is accepted.

After the deflect:

- The caller hears COMtrexx's **native waiting music**.
- A technician must **pick up the call manually** from the orbit.
- COMtrexx park orbit 778 does **not** return the call to the AI on timeout.

**There is no automatic voicemail fallback after parking.** The voicemail helpers
in `esl_call_handler.py` are retained in the repository but are not wired to the
escalation path. Voicemail after deflect would require **both**:

1. COMtrexx configured to forward the timed-out orbit back to extension `003010`, and
2. orbit-return detection in the backend (not implemented).

Until both exist, escalation = deflect to the manned waiting room only.

---

## Configuration files in this directory

| File | Deploy to | Apply with |
|---|---|---|
| `comtrexx_gateway.xml` | `/etc/freeswitch/sip_profiles/external/comtrexx_gateway.xml` | `fs_cli -x "sofia profile external restart"` |
| `inbound_ai_dialplan.xml` | `/etc/freeswitch/dialplan/public/00_inbound_ai.xml` | `fs_cli -x "reloadxml"` |
| `default_transfer_dialplan.xml` | `/etc/freeswitch/dialplan/default/10_comtrexx_transfer.xml` | `fs_cli -x "reloadxml"` |

**These files are templates.** Replace `YOUR_SIP_PASSWORD_HERE` in
`comtrexx_gateway.xml` with the real SIP password for extension 003010 before
deploying. Do not commit the password to source control.

---

## Diagnostics

Run `verify_freeswitch.sh` (in this directory) to get a read-only snapshot of the
current runtime state without modifying anything:

```bash
bash backend/voice/freeswitch/verify_freeswitch.sh
```

The script checks: backend port binding, gateway registration status, active
channels, SIP profile IPs, dialplan socket target, file drift between repo
templates and deployed files, and recent FS log lines for call events.
