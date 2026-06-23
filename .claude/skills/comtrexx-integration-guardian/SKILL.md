---
name: comtrexx-integration-guardian
description: Owns the COMtrexx PBX integration boundary — the FreeSWITCH↔COMtrexx gateway, extension 003010, waiting-room orbits 778/779, and the canonical SIP REFER (deflect) escalation mechanism. Activate when editing escalation transfer logic, the comtrexx gateway/dialplan XML, COMtrexx-facing config, or anything touching how calls reach or leave COMtrexx. Enforces deflect-not-bridge for orbits, manual orbit pickup, and the no-automatic-voicemail reality.
---

# COMtrexx Integration Guardian

Owns the contract between the backend/FreeSWITCH and the **COMtrexx PBX**. This is
where calls enter (inbound to extension `003010`) and where escalations are parked
(orbits `778`/`779`). COMtrexx authorizes calls by their origin and direction, so
the *mechanism* (REFER vs bridge) is not interchangeable — choosing wrong breaks
escalation with `INCOMPATIBLE_DESTINATION`. This guardian exists because that
exact regression already happened (commit `e6ce4d7`).

## Purpose

- Keep escalation using the mechanism COMtrexx accepts (SIP REFER / deflect).
- Keep the FreeSWITCH↔COMtrexx topology (gateway, `003010`, orbits) coherent
  across code, XML, and docs.
- State plainly what is automatic and what is manual, so nobody re-adds a phantom
  voicemail/return fallback that the PBX does not actually provide.

## When to activate

- Editing escalation transfer in `backend/voice/esl_call_handler.py`
  (`_conversation_loop` deflect loop) or `backend/voice/escalation.py`
  (`transfer_to_extension`).
- Editing `backend/voice/freeswitch/*.xml` (`comtrexx_gateway.xml`,
  `inbound_ai_dialplan.xml`, `default_transfer_dialplan.xml`) or
  `verify_freeswitch.sh`.
- Editing COMtrexx-facing config in `backend/voice/config.py`
  (`COMTREXX_IP`, `COMTREXX_EXTENSION`, `AI_WAITING_ROOM_PRIMARY/SECONDARY`).
- Editing `backend/voice/esl_client.py` `execute()` where `deflect` is dispatched.

## Topology / key addresses (MUST stay coherent)

```
COMtrexx 172.20.0.244 ──SIP/TLS:5061──▶ FreeSWITCH (WSL), gateway name "comtrexx"
COMtrexx ──INVITE to ext 003010──▶ FreeSWITCH public dialplan ──socket──▶ Python AI
AI escalates ──deflect sip:778@COMtrexx──▶ COMtrexx parks caller in orbit 778 (then 779)
```

- **Extension `003010`** — the AI's SIP user, registered via `comtrexx_gateway.xml`.
  COMtrexx routes inbound calls to `003010`; FreeSWITCH hands them to Python over
  the ESL outbound socket. (Default `COMTREXX_EXTENSION` is `003010`.)
- **Waiting rooms `778` / `779`** — COMtrexx park orbits, set via
  `AI_WAITING_ROOM_PRIMARY` / `AI_WAITING_ROOM_SECONDARY`. The orbits provide
  COMtrexx's native waiting music.
- The gateway must be `REGED` (`sofia status gateway comtrexx`). SIP **OPTIONS**
  keep-alives are not calls — only an **INVITE** starts a session.

## COMtrexx integration invariants (MUST hold)

1. **Deflect is the canonical escalation mechanism.** Escalation parks the caller
   with a SIP REFER: `handler.execute("deflect", f"sip:{ext}@{config.COMTREXX_IP}")`,
   primary `778` then secondary `779`. The REFER originates from the internal
   `003010` leg, so COMtrexx accepts a re-route to its own park orbit.
2. **NEVER replace deflect with a bridge for 778/779.** A direct
   `bridge sofia/gateway/comtrexx/778` arrives at COMtrexx as a **trunk-side
   INVITE** to a park orbit, which COMtrexx rejects with **cause 88
   `INCOMPATIBLE_DESTINATION`**. This is not tunable — it is COMtrexx's
   authorization model. (This is exactly the `e6ce4d7` regression; see
   `voice-freeswitch-guardian` #5.) `default_transfer_dialplan.xml` also bridges
   `77[89]` via the gateway and is the **wrong** mechanism for orbits — do not
   treat it as the deflect path.
3. **Manual pickup from the orbit.** After deflect the caller hears COMtrexx
   waiting music and a **technician must pick up the call manually** from the
   orbit. The escalation email is the handoff trigger (see
   `escalation-email-privacy-guardian`).
4. **No automatic voicemail fallback.** COMtrexx park orbit `778` does **not**
   return the call to the AI on timeout. There is therefore **no automatic
   voicemail after deflect**. Enabling it would require BOTH (a) COMtrexx
   configured to forward the timed-out orbit back to extension `003010`, AND
   (b) backend orbit-return detection — which is **not implemented**. The retained
   voicemail helpers in `esl_call_handler.py` must stay unwired until both exist.
5. **ESL/COMtrexx addresses coherent in three places.** `config.py`, the
   FreeSWITCH XML, and `freeswitch/README.md` must agree on IPs, ports, the
   gateway name, `003010`, and the orbits. Change all three together.
6. **Templates only in the repo.** The XML are templates with
   `YOUR_SIP_PASSWORD_HERE`. Never commit a real SIP password; never assume repo
   XML equals the deployed `/etc/freeswitch/...` files.

## Live validation checklist (run on the host where FreeSWITCH runs)

This cannot be validated in CI (no real PBX) — it is a manual, out-of-band check:

- [ ] `bash backend/voice/freeswitch/verify_freeswitch.sh` — read-only snapshot.
- [ ] `fs_cli -x "sofia status gateway comtrexx"` shows `REGED`.
- [ ] Place a real inbound call; confirm an **INVITE** (not just OPTIONS) reaches
      `003010` and the AI answers.
- [ ] Trigger escalation; confirm the FS log shows `deflect`/REFER to
      `sip:778@…`, **not** `bridge sofia/gateway/comtrexx/778`, and **no**
      `INCOMPATIBLE_DESTINATION` / cause 88.
- [ ] Confirm the caller hears COMtrexx orbit music and a technician can pick up
      manually from `778` (then `779`).
- [ ] Confirm the escalation email arrived with the correct orbit + Call-ID.
- [ ] If any XML changed: `reloadxml` (dialplan) or `sofia profile external
      restart` (gateway), and re-run `verify_freeswitch.sh`.

## Test limitations in CI

- Backend tests are **hermetic** — no real COMtrexx, FreeSWITCH, or SIP. The
  deflect-not-bridge guarantee is pinned by **source/mechanism assertions and
  mocks** (`TestEscalationUsesDeflect` in `test_phone_safety.py`), not a live call.
- CI proves the *mechanism* (deflect used, bridge-to-orbit absent, helpers
  removed); it does **not** prove COMtrexx accepts the call. Live PBX behavior
  stays a separate manual validation (above) — keep it out of CI (see
  `pipeline-guardian`).

```bash
# Mechanism gate (WSL debian12, .venv-wsl):
cd backend
../.venv-wsl/bin/python -m pytest tests/test_phone_safety.py tests/test_voice_bugs_regression.py -q
```

## Documentation updates required

- `backend/voice/freeswitch/README.md` for any gateway/`003010`/orbit/dialplan or
  mechanism change.
- `VOICE_MODE.md` for escalation behavior changes.
- `backend/voice/config.py` docstrings (+ `.env.example`) for COMtrexx-facing vars.

## Forbidden behavior

- Do NOT escalate to `778`/`779` via `bridge sofia/gateway/comtrexx/...` — REFER
  (deflect) only.
- Do NOT claim/implement automatic orbit-return or automatic voicemail after
  deflect unless COMtrexx forward + orbit-return detection both exist.
- Do NOT wire the retained voicemail helpers into the escalation path here.
- Do NOT change one ESL/COMtrexx address location without the other two.
- Do NOT commit real SIP passwords or treat repo XML as the deployed XML.
- Do NOT add a live COMtrexx/FreeSWITCH dependency to the automated test suite.
