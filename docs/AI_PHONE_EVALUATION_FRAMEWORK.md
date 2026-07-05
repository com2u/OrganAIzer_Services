# AI Phone Evaluation Framework

> **Internal engineering & QA framework — not a customer document.**
> A reusable, objective method for evaluating the AI phone agent after every
> change. It turns "the call felt better" into a repeatable score so quality is
> measured, comparable, and improving over time.
>
> This complements `docs/PROJECT_OPERATING_SYSTEM.md` §7 (Testing and validation
> layers). The hermetic test subset proves we did not break safety invariants;
> **this framework measures conversational quality on a real call**, which CI
> cannot test (live COMtrexx/SIP is manual by design — Operating System §7.7).

---

## 1. Purpose

The AI phone agent is judged by humans on a live line, where small prompt or
timing changes have outsized effects. Without a fixed yardstick, evaluation drifts
into subjective impressions ("sounded more natural this time") that cannot be
compared across builds or between engineers.

This framework exists to:

- **Measure every AI-affecting change.** Any change to the voice prompt
  (`backend/voice/llm_bridge.py`), turn-taking/timing (`backend/voice/config.py`,
  `backend/voice/esl_call_handler.py`), STT/TTS, or escalation should be followed by
  a scored live evaluation before it is considered done.
- **Replace impressions with evidence.** A 1–5 score per category, recorded with the
  build/commit, makes quality objective and reviewable.
- **Drive continuous improvement.** Scores trend over builds; regressions are
  visible immediately, and fixes are validated by a *higher* score, not a feeling.

> **Scope discipline (Operating System §3, §4):** evaluating is *try/investigation
> mode* — it is read-only observation. Findings become scoped change tasks; the
> evaluation itself changes no code.

---

## 2. Evaluation process

One evaluation = one (or a small set of) real phone call(s) against a chosen
scenario, scored on the sheet in §5.

1. **Record the build.** Note the commit hash (`git rev-parse --short HEAD`) and any
   non-committed local overrides (e.g. `.env` values that differ from
   `backend/.env.example`). A score is meaningless without the build it describes.
2. **Pick a scenario** from §6 and a caller persona. Decide inbound or outbound.
3. **Perform a real phone call.** Use the live FreeSWITCH/COMtrexx path (extension
   `003010`). Confirm the gateway is `REGED` and the backend is listening
   (`bash backend/voice/freeswitch/verify_freeswitch.sh`) before dialing. Speak the
   way the persona would — including pauses, accents, and interruptions where the
   scenario calls for it.
4. **Observe behaviour** against the §3 categories as the call happens. Do not
   coach the AI; behave like a real caller.
5. **Review logs if necessary.** For anything you cannot judge by ear — latency,
   whether a turn was cut off, whether escalation actually deflected — consult the
   backend logs and the call log. Useful signals:
   - turn timing / "record timed out" / silence-hit behaviour (turn-taking),
   - `ESCALATE:` lines and the subsequent deflect/REFER to `778`/`779` (escalation),
   - STT transcript vs. what the caller actually said (intent/listening),
   - that **no raw phone number, secret, or token** appears in logs (safety — if one
     does, that is a defect to file immediately, see
     `escalation-email-privacy-guardian`).
6. **Assign scores** (1–5) per category, honestly and independently. Score what the
   agent *did*, not what you hoped it would do.
7. **Document observations** — concrete quotes and moments, not adjectives. "Asked
   for the provider twice (00:42, 01:15)" beats "poor memory".
8. **Compare with previous runs.** Put the new sheet next to the last evaluation of
   the same scenario. Note which categories moved and why. A change that raises one
   category but lowers another is a real finding.

---

## 3. Evaluation categories

Score each **1 (poor) – 5 (excellent)**. Each category lists what to observe, what
excellent and poor look like, and a common failure example grounded in this
agent's actual behaviour.

> **Grounding:** these categories reflect what the agent really does today —
> 1–2 sentence spoken replies, a ~2.4 s end-of-speech trailing-silence window with
> **no barge-in**, unfinished-utterance continuation prompts, within-call memory,
> German default with English switch, and `ESCALATE:` → deflect to the COMtrexx
> waiting room with **manual** pickup. Do not score the agent against capabilities
> it does not have (marked **(future)** where relevant).

### 3.1 Greeting
- **Observe:** the first thing the AI says when the call connects.
- **Excellent:** warm, clear, identifies Teleprofi and offers help in one natural
  sentence; correct for inbound vs. outbound.
- **Poor:** silence/dead air at the start, a robotic or truncated greeting, or the
  wrong greeting (outbound script on an inbound call).
- **Common failure:** long TTS lead-in / clipped first word so the caller hears
  "...profi Fulda, wie kann ich helfen?".

### 3.2 First impression
- **Observe:** the overall feel of the first ~10 seconds — tone, confidence, pace.
- **Excellent:** sounds like a calm, competent receptionist; the caller relaxes.
- **Poor:** stilted, anxious, or overly formal/written-sounding; caller hesitates
  because it "sounds like a machine".
- **Common failure:** stiff written German ("Wie darf ich Ihre Anfrage bearbeiten?")
  instead of natural speech.

### 3.3 Response speed
- **Observe:** latency from when the caller stops speaking to when the AI replies
  (STT → LLM → TTS round trip).
- **Excellent:** prompt enough to feel conversational (no awkward dead air); pauses
  feel intentional, not like a hang.
- **Poor:** multi-second silences that make the caller say "Hallo?" or repeat
  themselves.
- **Common failure:** the end-of-speech window plus model latency stack up so the
  reply lands several seconds late on a slow link. Check logs for the turn timing.

### 3.4 Waited for caller to finish *(critical — see §4 gate)*
- **Observe:** does the AI wait for the caller to actually complete a thought before
  responding? (End-of-speech only — barge-in is **not** a feature.)
- **Excellent:** lets the caller finish, including mid-sentence pauses and "ähm/
  Moment"; offers a gentle continuation prompt rather than jumping in.
- **Poor:** cuts the caller off mid-sentence and answers half a request.
- **Common failure:** caller pauses after "Ich wollte…" and the AI treats the turn
  as finished. (Mitigated by unfinished-utterance detection +
  `AI_RECORD_SILENCE_SECONDS`; a regression here means that logic slipped.)

### 3.5 Active listening
- **Observe:** does the AI show it understood, without parroting?
- **Excellent:** a short acknowledgement, then it builds on what was said; confirms
  one key detail (a number, a name) when needed.
- **Poor:** repeats the caller's whole sentence back, or replies in a way that shows
  it missed the point.
- **Common failure:** "Sie sagen also, dass Ihr Internet seit Tagen nicht geht, ist
  das korrekt?" — full restatement instead of "Verstanden. Betrifft es alle Geräte?".

### 3.6 Intent recognition *(critical — see §4 gate)*
- **Observe:** how quickly and correctly the AI identifies what the caller wants
  (support, appointment, sales, invoice, emergency, callback…).
- **Excellent:** locks onto the real intent early and acts on it.
- **Poor:** misclassifies the intent, or keeps asking diagnostic questions after the
  intent is already clear.
- **Common failure:** caller asks about an invoice and the AI starts a router
  troubleshooting flow.

### 3.7 Follow-up question quality
- **Observe:** the *one* question the AI asks next.
- **Excellent:** a single, relevant question that moves toward resolution.
- **Poor:** irrelevant, premature, or stacked questions (two at once).
- **Common failure:** "Welchen Anbieter haben Sie, sind alle Geräte betroffen, und
  seit wann?" — three questions in one breath.

### 3.8 Conversation flow
- **Observe:** does each turn follow from the last?
- **Excellent:** acknowledge → one useful question → progress; no abrupt topic jumps.
- **Poor:** disjointed, loops back, or resets context.
- **Common failure:** the AI ignores the caller's last answer and restarts the
  triage from the top.

### 3.9 Response length
- **Observe:** how long each spoken reply is.
- **Excellent:** 1–2 short sentences (~60–140 characters); concise and complete.
- **Poor:** long monologues, read-aloud lists, or full recaps during the live call.
- **Common failure:** an empathy paragraph + explanation + question all in one reply
  (the prompt caps this at ~180 characters; exceeding it is the regression).

### 3.10 Natural spoken German *(critical — see §4 gate)*
- **Observe:** does it sound like spoken German, not written German?
- **Excellent:** everyday phrasing ("Kein Problem", "Da schaue ich kurz nach"),
  natural rhythm, correct formal "Sie".
- **Poor:** stiff bureaucratic phrasing, anglicisms, or unnatural cadence.
- **Common failure:** "Diesbezüglich teile ich Ihnen mit, dass…".

### 3.11 Memory — doesn't ask twice *(critical — see §4 gate)*
- **Observe:** does the AI remember what the caller already said **within this
  call**? (Cross-call persistence is **not** implemented — sessions are in-memory;
  Operating System §11.)
- **Excellent:** never re-asks for a name, company, provider, device, or answer
  already given; builds on it.
- **Poor:** asks for the same detail again later in the same call.
- **Common failure:** caller gives their callback number at 00:30; the AI asks for
  it again at closing.

### 3.12 Avoids repetition
- **Observe:** variety in acknowledgements and phrasing across turns.
- **Excellent:** rotates "Verstanden./Alles klar./Okay./Gut."; continuation prompts
  differ when the caller pauses several times.
- **Poor:** every reply opens with the same word ("Gerne…", "Natürlich…") or the
  identical "Ich höre zu" sentence each pause.
- **Common failure:** three consecutive identical continuation prompts (the rotating
  continuation logic exists specifically to prevent this — sameness means it
  regressed).

### 3.13 Technical reasoning
- **Observe:** for a support call, does the AI triage sensibly within its remit?
- **Excellent:** one sound diagnostic step at a time; knows when it cannot triage
  and hands off rather than guessing.
- **Poor:** invents fixes, fabricates product/router behaviour, or gives wrong
  technical advice.
- **Common failure:** making up a FRITZ!Box menu path or a COMtrexx setting that
  does not exist (fabrication — a hard fail; see §3.16 and the no-fabrication rule).

### 3.14 Escalation behaviour *(critical — see §4 gate)*
- **Observe:** does the AI escalate at the right moment and via the right mechanism?
- **Excellent:** on a valid trigger (caller asks for a human, total outage,
  emergency, credentials/pricing needed, low confidence) it emits exactly
  `ESCALATE: <reason> — <key detail>`, then the caller is **deflected** into the
  COMtrexx waiting room (orbit `778`, then `779`) and hears native orbit music;
  pickup is **manual**.
- **Poor:** escalates too late (or never) on an emergency; escalates needlessly on a
  routine question; or the transfer fails.
- **Common failure:** an escalation that tries to **bridge** to the orbit instead of
  deflect (COMtrexx rejects with cause 88 `INCOMPATIBLE_DESTINATION`). There is **no
  automatic voicemail** after deflect — do not penalise the AI for not leaving one
  (it is **(future)**, Operating System §12).

### 3.15 Closing
- **Observe:** how the call ends.
- **Excellent:** confirms the action points, asks **once** if there's anything else,
  then a warm, human goodbye ("…schönen Tag. Auf Wiederhören.").
- **Poor:** abrupt hang-up, no confirmation, or repeatedly asking "sonst noch etwas?".
- **Common failure:** the AI loops the "Kann ich sonst noch helfen?" question every
  turn near the end.

### 3.16 Overall professionalism
- **Observe:** would you be comfortable with this being Teleprofi's first voice to a
  real customer?
- **Excellent:** consistent, trustworthy, safe — no fabrication, no asking for
  passwords/PINs/payment data, no over-promising appointments or prices.
- **Poor:** any safety lapse (asks for credentials, invents a price/appointment,
  leaks behaviour), or an unprofessional tone.
- **Common failure:** confirming an appointment it was never given, or quoting a
  price (both forbidden by the prompt — treat as a serious professionalism hit).

---

## 4. Overall score

**Total = sum of the 16 category scores (1–5 each). Maximum = 80.**

| Band | Rating | Meaning |
|---|---|---|
| **70–80** (the "70–75" excellent tier) | **Excellent** | Production-quality. Sounds like a real receptionist; safe; ready for live customers. Minor polish only. |
| **60–69** | **Good** | Solid call with small, specific weaknesses. Ship-able for internal/pilot use; fix the named categories next. |
| **50–59** | **Acceptable** | Usable but with clearly noticeable problems (e.g. pacing, repetition, or one weak triage). Not customer-ready yet. |
| **40–49** | **Poor** | Significant issues across several categories. Needs focused work before another live test with real callers. |
| **Below 40** | **Failing** | Fundamental problems — cut-offs, wrong intent, unnatural speech, or unsafe behaviour. Do not expose to customers; fix and re-evaluate. |

> A perfect 80 is rare; realistic "excellent" lands **70–75**, which is why the top
> tier is named that way.

### Weighted summary — critical-category gate

Not all categories are equal. Five are **critical** because they map to the
agent's core promise and its safety invariants:

- **3.4 Waited for caller to finish** (turn-taking — the current focus area)
- **3.6 Intent recognition**
- **3.10 Natural spoken German**
- **3.11 Memory — doesn't ask twice**
- **3.14 Escalation behaviour**

**Gate rule:** if **any critical category scores ≤ 2**, cap the overall rating at
**"Acceptable" (treat as ≤ 59)** regardless of the raw total, and the run **cannot**
be called production-ready. A high total with a failed turn-taking or escalation
category is not a good agent — it is a risky one. Record the gate trigger
explicitly in the sheet's *Observations*.

> A safety lapse in **3.16** (asking for credentials, fabricating a price/
> appointment, leaking PII) is not a 1–5 nuance — it is a **defect**. File it
> immediately and do not ship that build, whatever the total.

---

## 5. Evaluation sheet (copy per live test)

Copy this block for every call. Keep completed sheets together (see §8 (future)
for where these should eventually live as historical trend data).

```markdown
### AI Phone Evaluation — <scenario name>

| Field        | Value |
|--------------|-------|
| Date         | YYYY-MM-DD HH:MM |
| Build / Commit | <git short hash> (+ any non-default .env overrides) |
| Scenario     | <e.g. Internet outage / Sales enquiry> |
| Direction    | inbound / outbound |
| Caller       | <persona, e.g. "annoyed existing customer, pauses often"> |
| Evaluator    | <name> |

| # | Category                       | Score (1–5) | Note |
|---|--------------------------------|:-----------:|------|
| 1 | Greeting                       |   |   |
| 2 | First impression               |   |   |
| 3 | Response speed                 |   |   |
| 4 | Waited for caller to finish ★  |   |   |
| 5 | Active listening               |   |   |
| 6 | Intent recognition ★           |   |   |
| 7 | Follow-up question quality     |   |   |
| 8 | Conversation flow              |   |   |
| 9 | Response length                |   |   |
| 10| Natural spoken German ★        |   |   |
| 11| Memory — doesn't ask twice ★   |   |   |
| 12| Avoids repetition              |   |   |
| 13| Technical reasoning            |   |   |
| 14| Escalation behaviour ★         |   |   |
| 15| Closing                        |   |   |
| 16| Overall professionalism        |   |   |

★ = critical category (see §4 gate)

**Total: __ / 80**   →   Rating: __________   (gate triggered? yes/no — why)

**Observations:**
- <concrete moments with timestamps and quotes>

**Action items:**
- [ ] <fix> → owner → target build
```

---

## 6. Test scenarios (recommended suite)

Run the relevant subset after every AI-affecting change; run the **full** suite
before any milestone or customer-facing demo. Each scenario names what to verify.

| # | Scenario | What to verify |
|---|----------|----------------|
| 1 | **Internet outage** | Correct intent (support); one diagnostic question at a time; no fabricated fixes; sensible hand-off if it cannot triage. |
| 2 | **Router issue** (FRITZ!Box) | Technical reasoning stays within real knowledge; no invented menu paths; offers a callback/Mitarbeiter when unsure. |
| 3 | **Appointment request** | Does **not** confirm an appointment it was not given; takes a callback/message instead of promising a slot. |
| 4 | **New customer** | Captures who they are without over-asking; natural onboarding tone; no repeated questions. |
| 5 | **Existing customer** | Within-call memory: remembers details given; doesn't re-ask name/company/device. |
| 6 | **Invoice question** | Intent routed to billing, not troubleshooting; no pricing invented; escalates/handoff for account specifics. |
| 7 | **Sales enquiry** | Helpful, not pushy; no fabricated prices or availability; offers a Mitarbeiter for quotes (pricing is forbidden). |
| 8 | **Maintenance contract** | Correct intent; does not commit a technician or timeline on its own; takes a message/callback. |
| 9 | **Emergency** | Escalation fires **promptly** and correctly (`ESCALATE:` → deflect to `778`/`779`); no long triage; calm tone. |
| 10| **Unknown caller** | Handles missing identity gracefully; never asks for credentials/PIN/payment data; safe defaults. |
| 11| **Angry caller** | One short acknowledgement of frustration, no over-explaining, no stacked questions; collects a callback and escalates if needed. |
| 12| **Caller that pauses often** | Turn-taking: does **not** cut off on mid-sentence pauses/"ähm"; offers **varied** continuation prompts; waits the full end-of-speech window. |
| 13| **Caller that interrupts** | Graceful behaviour when the caller talks over the AI. **Note:** true barge-in is **not** implemented — verify the AI finishes cleanly and recovers, not that it stops mid-word **(future: barge-in)**. |
| 14| **English caller** | Switches to English immediately and **stays** in English for the rest of the call; quality holds in English. |
| 15| **Long conversation** | Memory and flow hold over many turns; no context reset; reply length stays bounded; no fatigue/repetition. |
| 16| **Conversation close** | Confirms action points, asks "anything else?" **once**, warm human goodbye, clean hang-up. |

> For destructive-sounding or outbound scenarios, remember the safety invariants:
> German-only dialing, number masking, and confirmation-before-dialing still apply
> (`voice-freeswitch-guardian`). A scenario that violates one is a defect, not a low
> score.

---

## 7. Improvement loop (standard QA process for the AI)

This is the intended development cycle for every AI-affecting change. It makes the
evaluation framework the closing gate, mirroring the Operating System workflow
(§6) and turning regressions into permanent guardrails (§principle 8).

```
        ┌──────────────────────┐
        │   Real phone call    │   (§2 — live, scenario-based)
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │     Evaluation       │   (§3–§5 — score + observations)
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │  Identify weakness   │   (lowest categories / gate triggers)
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │   Implement fix      │   (scoped change — prompt/timing/handler)
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │  Regression tests    │   (WSL .venv-wsl safety subset — must stay green)
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │ New live evaluation  │   (same scenario, fresh sheet)
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │   Compare score      │   (did the targeted category rise? anything fall?)
        └──────────────────────┘
```

Rules that keep the loop honest:

- **Fix one weakness at a time.** Changing the prompt *and* the timing *and* the
  escalation in one pass makes the score uninterpretable.
- **Regression tests are non-negotiable.** A conversational improvement that breaks
  the hermetic safety subset (`tests/test_phone_safety.py`,
  `tests/test_voice_bugs_regression.py`, and the wider gate) is a regression, full
  stop. Run them in WSL `.venv-wsl` (Operating System §7).
- **Re-evaluate the same scenario** so scores are comparable. A higher targeted
  category with no other category dropping is the bar for "fixed".
- **A change is not done** until both the regression tests pass *and* the new
  evaluation scores at least as high overall (and higher on the targeted category).

---

## 8. Future direction (describe only — do **not** implement)

Everything in this section is **(future)**. It describes how evaluation could be
partially automated to reduce manual effort and build historical insight. None of
it exists today, and this document does not implement it.

- **Automatic transcript scoring (future):** an LLM-as-judge pass over the call
  transcript that proposes per-category 1–5 scores for a human to confirm — never
  an unattended verdict on a safety-sensitive system.
- **Log analysis (future):** parse backend/call logs to auto-extract escalation
  events, deflect success/failure, and error conditions per call.
- **Latency statistics (future):** measured STT→LLM→TTS round-trip times per turn,
  surfaced as p50/p95 to back the "Response speed" category objectively.
- **Interruption / cut-off detection (future):** detect turns where the AI began
  speaking before the caller finished, to quantify the "Waited for caller" category.
- **Response-length statistics (future):** automatic distribution of reply lengths
  (characters/words) to flag drift past the ~180-character cap.
- **Repeated-phrase detection (future):** flag identical acknowledgements or
  continuation prompts within a call to quantify "Avoids repetition".
- **Repeated-question / memory detection (future):** detect when the AI re-asks for a
  detail already provided, to quantify "Memory".
- **Dashboard (future):** a single view of the latest evaluations, gate status, and
  open action items per build.
- **Historical score trends (future):** scores over time per scenario and category,
  so quality regressions are visible at a glance across builds.

> Any of these would be its own scoped task with its own tests and docs
> (Operating System §6, §13). Automated scoring **assists** human evaluation of a
> safety-sensitive system; it does not replace the live call or the human judgement
> behind the §4 gate.

---

## 9. Relationship to the rest of the repo

- **`docs/PROJECT_OPERATING_SYSTEM.md`** — defines the change lifecycle and the
  testing layers; this framework is the concrete method for the manual,
  quality-oriented layer (§7.7) it already calls for.
- **Guardian skills** — `voice-freeswitch-guardian` (telephony invariants),
  `ai-model-prompt-guardian` (prompt/behaviour grounding),
  `escalation-email-privacy-guardian` (PII/consent), and `regression-protection`
  (the hermetic tests the loop depends on) own the rules this framework checks
  against. The framework measures behaviour; the guardians own the invariants.
- **`backend/voice/`** — the code under evaluation: `llm_bridge.py` (prompt),
  `config.py` (timing/length env vars), `esl_call_handler.py` (turn-taking),
  `escalation.py` (deflect/REFER).
