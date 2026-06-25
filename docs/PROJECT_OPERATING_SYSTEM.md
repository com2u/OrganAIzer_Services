# OrganAIzer — Project Operating System

> The operating model for how OrganAIzer Services is built, changed, validated,
> documented, and deployed. This describes how the project **should** work. Where
> something is not yet implemented, it is marked **(future)** so this document is
> never mistaken for a feature list.

---

## 1. Purpose

OrganAIzer Services is a safety-sensitive system: it places real phone calls,
handles PII, sends email on a caller's behalf, and runs a bounded automation
container (OpenClaw). Small, well-meant changes have repeatedly caused outsized
regressions (e.g. an escalation rewrite that broke the COMtrexx waiting room).

This document defines the **operating system around the code** — the roles,
modes, workflow, and disciplines — so that:

- every change has a predictable lifecycle (**investigate → scope → implement →
  validate → document → review → commit**);
- safety-critical behavior (voice, confirmation gating, OpenClaw, logging,
  consent) never silently regresses;
- AI agents and human contributors operate within scope and against a single
  source of truth, not from memory or guesswork.

It complements, and does not replace, the guardian skills in `.claude/skills/`.
The master skill (`organalzer-master-skill`) is the machine-readable router; this
document is the human-readable operating model behind it.

---

## 2. Current problem

The repository has structural gaps that make ad-hoc changes risky:

- **No CI yet.** `.github/workflows/` is absent — nothing automatically runs the
  safety tests. The safety gate is currently a *manual* discipline. **(future: CI)**
- **In-memory state.** Executive-Agent sessions and idempotency stores live in a
  process-level dict; they are lost on restart and not multi-instance safe.
- **Out-of-repo runtime config.** FreeSWITCH/COMtrexx config is deployed under
  `/etc/freeswitch/...`; repo XML are templates and can drift from production.
- **Live telephony cannot be tested in CI.** COMtrexx/SIP validation is manual.
- **Scope creep risk.** An AI agent given a narrow task can fan out into unrelated
  files, refactors, or "improvements" that introduce regressions.
- **Source-of-truth drift.** Ports, IPs, env vars, and COMtrexx parameters appear
  in multiple places (config, compose, XML, docs) and can disagree.

The operating model below exists to contain these problems until they are
structurally fixed.

---

## 3. Operating principles

1. **One source of truth.** Every operational fact has exactly one authoritative
   location (see §11 and the table below). All other mentions are derived and must
   be kept in sync, never edited independently.
2. **Scope before edit.** A task is defined by its scope. Do not change files
   outside that scope. Broad, unrelated changes are a defect, not initiative.
3. **Safety behavior is sacred.** Confirmation gating, number masking, German-only
   dialing, consent-gated recordings, OpenClaw bounds, and log redaction are
   invariants — never weakened without an explicit, tested decision.
4. **Investigate before implementing.** Read the code and the relevant guardian
   skill first; do not act from memory or assumptions.
5. **Docs are part of the contract.** A change is not done until the docs that
   describe the changed behavior match it.
6. **Tests pin behavior.** A fixed bug or new safety behavior lands with a
   hermetic test that fails before and passes after.
7. **Manual where it must be.** Live COMtrexx/SIP behavior is validated by hand on
   the FreeSWITCH host — deliberately outside automated tests.
8. **Learn from regressions.** Past failures become permanent guardrails (skills +
   regression tests), not tribal knowledge.

### Single-source-of-truth map

| Operational fact | Authoritative source | Derived / kept-in-sync |
|---|---|---|
| Container topology & **published ports** | `docker-compose.yml` | `deploy.sh`, nginx, deployment docs |
| **Env vars** (names, defaults) | `backend/voice/config.py` + `backend/.env.example` | docs that list env vars |
| **COMtrexx/IPs/orbits** (`172.20.0.244`, `003010`, `778`/`779`) | `backend/voice/config.py` + `backend/voice/freeswitch/README.md` | FreeSWITCH XML templates, voice docs |
| **Docker image contract** | `backend/Dockerfile` + `backend/.dockerignore` | `docker-guardian` skill |
| **CI gate** | `.github/workflows/` **(future)** + `pipeline-guardian` | this doc |
| **Safety test set** | `backend/tests/` | guardian skills referencing it |

---

## 4. AI agent roles

These are **responsibilities in the operating model**, mostly fulfilled today by
guardian skills (`.claude/skills/`) invoked by a human-directed Claude/Codex
session. Fully autonomous multi-agent orchestration is **(future)**; until then,
each role is a hat worn deliberately, one at a time, within an agreed scope.

| Role | Responsibility | Backed by |
|---|---|---|
| **Project manager / orchestrator** | Defines scope, routes to the right guardian, enforces the lifecycle, says "no" to scope creep. | `organalzer-master-skill` |
| **Team leads (domain owners)** | Own a subsystem's invariants and review changes in it. | the guardian skills (voice, backend, frontend, docker, security, data, AI/prompt, COMtrexx, escalation-email) |
| **Implementation agent** | Makes the smallest correct change inside scope. | human-directed Claude/Codex in *implementation mode* |
| **Code reviewer** | Checks correctness, scope, and invariant adherence on the diff. | `/code-review`, `security-review` |
| **Testing agent** | Ensures the hermetic safety tests exist and pass (WSL runner). | `pipeline-guardian`, `regression-protection` |
| **Documentation agent** | Keeps docs in lockstep with behavior. | `documentation-sync` |
| **Deployment agent** | Validates build/topology; never deploys silently. | `docker-guardian`, deploy scripts |

**Rule:** an agent acts in exactly one role at a time and stays inside the task
scope. An agent must not silently expand into another role's domain (e.g. an
implementation pass that "also" refactors tests, rewrites docs broadly, or
changes Docker/CI) without that being part of the stated task.

---

## 5. Development modes

Pick a mode explicitly; do not blend them.

- **Try mode / investigation mode** — read-only. Trace code, run searches, run the
  app or read-only diagnostics (e.g. `verify_freeswitch.sh`). Produce findings and
  a plan. **No edits.** Default starting mode for any non-trivial task.
- **Safe mode** — minimal, reversible changes only; no changes to safety-critical
  paths (voice, confirmation gating, OpenClaw, logging, consent) without an
  accompanying test and guardian review. Used when uncertainty is high.
- **Implementation mode** — make the scoped change, smallest diff that is correct,
  matching surrounding code style.
- **Review mode** — examine the diff for correctness, scope adherence, and
  invariant violations; reject scope creep.
- **Documentation mode** — update only the docs that describe the changed behavior.

A typical change flows: *investigation → (safe/implementation) → review →
documentation*. Each mode has a clear exit (a plan, a diff, a passing test, a
review, updated docs).

---

## 6. Required workflow for every change

1. **Activate the master skill** and route to the matching guardian(s).
2. **Investigate** (read code + guardian + relevant docs). For multi-module or
   safety changes, run `change-impact-analysis` first.
3. **Confirm scope.** List the files you will touch. Anything beyond that is out
   of scope.
4. **Branch** if on `main` (feature branch).
5. **Implement** the smallest correct change.
6. **Validate** — run the safety test subset in WSL (§7). Live COMtrexx behavior:
   manual checklist (§7) on the FreeSWITCH host.
7. **Document** — `documentation-sync`: update every doc describing the behavior.
8. **Regression-protect** — add/extend a hermetic test (fails before, passes after).
9. **Review** the diff against the invariants and the original scope.
10. **Commit** per §9. Deploy only when explicitly asked, per §10.

---

## 7. Testing and validation layers

Layered, from fastest/most-automated to manual:

1. **Sanity / syntax** — the change imports and compiles; targeted unit checks.
2. **Hermetic safety subset (the gate).** No real network, FreeSWITCH, COMtrexx,
   SIP, Docker, or OAuth — all mocked. Run in **WSL debian12 with `.venv-wsl`**,
   never Windows Python:
   ```bash
   cd backend
   ../.venv-wsl/bin/python -m pytest tests/test_phone_safety.py \
     tests/test_openclaw_safety.py tests/test_executive_agent_safety.py \
     tests/test_logging_redaction.py tests/test_voice_bugs_regression.py -q
   ```
3. **Full backend suite** — `pytest tests/ -q` (WSL).
4. **Frontend** — `npm ci && npm run lint && npm run build`.
5. **Docker build check** — `docker compose build backend` (the backend image
   exists; full `docker compose build` fails until `frontend/Dockerfile` exists
   **(future)**).
6. **CI** — **(future)** a workflow that runs layers 2–5 on push/PR as a required,
   non-skippable gate. Must never depend on a live PBX.
7. **Manual COMtrexx / SIP validation (out of band).** Live telephony cannot run in
   CI. On the FreeSWITCH host: gateway `REGED`, inbound **INVITE** (not just
   OPTIONS) reaching `003010`, escalation using **deflect/REFER** (not bridge) to
   `778`/`779`, native orbit music, manual technician pickup, and no
   `INCOMPATIBLE_DESTINATION`. See `comtrexx-integration-guardian`.

---

## 8. Documentation rules

- **Docs are part of every change.** Behavior, endpoint, env var, protocol,
  topology, or security changes update the matching doc(s) in the same change.
- **One source of truth** (§3 table) — edit the authoritative location, then
  reconcile derived mentions; never let two docs disagree.
- **Mark the future.** Anything not yet implemented is labelled **(future)** so the
  docs never overstate the system.
- **Follow-up documents.** When a change is deliberately staged (e.g. Phase 2
  orbit-return voicemail), record the deferred work as an explicit follow-up note
  with its preconditions, not as an implied promise.
- **Keep docs current.** Stale docs are treated as defects. The
  `documentation-sync` skill maps change types to the exact files to update
  (`README.md`, `ARCHITECTURE.md`, `API_OVERVIEW.md`, `VOICE_MODE.md`,
  `backend/voice/freeswitch/README.md`, `SECURITY.md`, `DEPLOYMENT*.md`).
- **Cleaning/removing files safely.** Before deleting or overwriting a file:
  confirm what it actually is, that nothing references it, and that it is not an
  out-of-repo deployment template. If a file contradicts how it was described, stop
  and surface that rather than deleting. Never remove tests or docs to make a change
  "pass."

---

## 9. Commit rules (commit discipline)

- **Imperative subject**, scoped to one logical change.
- **No `Co-Authored-By` trailers** (repo convention).
- **Never commit secrets** — `.env`, `credentials.json`, token files, real SIP
  passwords stay out of git; repo FreeSWITCH XML keep placeholder values.
- **Commit only when asked.** If on `main`, branch first.
- **A commit should leave the tree green** — safety subset passing and docs updated
  for the behavior it changes.
- **Stage related changes together** (code + its test + its doc), not as scattered
  follow-ups.

---

## 10. Deployment rules (deployment discipline)

- **Deploy only on explicit request** — deployment is outward-facing and not
  implied by "make the change."
- **Build before deploy.** `docker compose build` must succeed; today only the
  backend image builds — the **frontend Dockerfile is missing (future)** and
  `deploy.sh` will fail until it exists.
- **Keep topology coherent.** Published ports (`backend 5263:8000`,
  `frontend 5264:80`, `openclaw` no ports) must agree across `docker-compose.yml`,
  `deploy.sh`, nginx, and docs.
- **Secrets at runtime only** — via `.env` + `env_file`, never baked into image
  layers (`.dockerignore` enforces this).
- **OpenClaw stays bounded** — no exposed ports, `read_only`, `cap_drop: ALL`,
  `no-new-privileges`, single data volume, tool deny-list intact
  (`test_openclaw_safety.py` is the spec).
- **Voice runtime is deployed separately.** FreeSWITCH/COMtrexx live outside the
  compose stack; apply XML changes with `reloadxml` / `sofia profile external
  restart` and re-run `verify_freeswitch.sh`.

---

## 11. Knowledge / database direction

Today, structured state is intentionally lightweight and mostly file/in-memory:

- **Sessions & idempotency** — in-memory, per-process (not multi-instance safe).
- **OAuth tokens** — file-based under `data/tokens/`.
- **Generated media / call logs / audio** — under `data/` (recreated on startup).
- **Company knowledge** — markdown in `backend/voice/knowledge/` (e.g.
  `teleprofi_fulda.md`), the AI-readable Layer 3 client knowledge.
- **Documents / knowledge base** — document QA / RAG storage as implemented in the
  backend services.

**Direction (future):** a single structured store (database) as the one source of
truth for sessions, idempotency, call logs, schedules, and knowledge-base records,
enabling multi-instance operation and durable state across restarts. Until then,
treat persistence as ephemeral and never assume cross-restart memory. Company
knowledge, schedules, emails, documents, and AI-readable markdown should converge
on clearly-owned stores rather than scattered files. **Do not describe this store
as existing — it is a direction, not a feature.**

---

## 12. Known OrganAIzer risks

- **No CI** — safety tests run only when a human runs them **(future fix)**.
- **Frontend Dockerfile missing** — full `docker compose build` / `deploy.sh` fail
  until it is added **(future)**.
- **In-memory session + idempotency** — lost on restart; not multi-instance safe.
- **FreeSWITCH XML drift** — repo templates can diverge from deployed
  `/etc/freeswitch/...`; `verify_freeswitch.sh` detects drift (host-only).
- **Escalation mechanism is fragile.** `bridge sofia/gateway/comtrexx/778` is
  rejected by COMtrexx (cause 88 `INCOMPATIBLE_DESTINATION`); **deflect / SIP REFER
  is the only accepted mechanism** for orbits `778`/`779`. This regressed once and
  is now guarded.
- **No automatic voicemail after deflect.** Orbit `778` does not auto-return to the
  AI; pickup is **manual**. Orbit-return voicemail would need COMtrexx to forward
  the timed-out orbit back to `003010` plus orbit-return detection **(future,
  unimplemented)**.
- **PII surfaces** — caller numbers, transcripts, and recordings flow into the
  escalation email; consent gating and masking discipline must hold
  (`escalation-email-privacy-guardian`).
- **Live telephony untestable in CI** — manual validation only.
- **Scope-creep by AI agents** — the single largest process risk; contained by §3,
  §4, and §6.

---

## 13. Next implementation steps

All items below are **(future)** unless a task explicitly scopes one in:

1. **Add CI** (`.github/workflows/`) running the hermetic safety subset + frontend
   build + `docker compose build backend`, as a required gate; no live-PBX deps.
2. **Add `frontend/Dockerfile`** so the full stack builds and deploys.
3. **Single source of truth for ports / IPs / env vars / Docker / CI / COMtrexx** —
   consolidate per the §3 table and remove drift between config, compose, XML, and
   docs. This is required, not optional.
4. **Durable structured store** for sessions, idempotency, call logs, schedules,
   and knowledge base (§11) to enable multi-instance operation.
5. **Orbit-return voicemail (Phase 2)** — only after COMtrexx is configured to
   forward the timed-out orbit back to `003010` and orbit-return detection exists.
6. **Operationalize agent roles** (§4) with explicit scope contracts so automated
   passes cannot make broad, unrelated changes.

> Guardrail for every step above: **Claude/Codex must not make broad, unrelated
> changes.** Each step is its own scoped task with its own tests and docs. Live
> COMtrexx/SIP validation remains manual throughout.
