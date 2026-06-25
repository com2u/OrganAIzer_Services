---
name: git-guardian
description: Protects the repository by ensuring every commit is safe, reviewable, and meaningful. Activate whenever staging files, proposing or creating a commit, writing a commit message, or performing any git operation (add/commit/push/branch/merge). Enforces no-secrets, clean scope, conventional imperative commit messages built only from the real staged diff, and a pre-commit safety checklist. Complements pipeline-guardian, docker-guardian, backend-guardian, and security-auth-guardian.
---

# Git Guardian

Owns the safety and quality of git history. Git history is part of the project's
documentation: every commit must be safe (no secrets/junk), reviewable (focused
scope, clear message), and meaningful (explains why). This skill **does not** push,
amend, or commit on its own initiative — commit/push only when the user asks
(repo-wide rule), and on the default branch, branch first.

## Purpose

- Keep secrets, credentials, customer data, and generated junk out of history.
- Keep commits **focused** — one logical change, related files grouped.
- Keep commit messages **honest** — derived only from the actual staged diff.
- Surface a clear pre-commit summary so the human can approve with confidence.

## When to activate

Activate before any `git add` / `git commit` / `git push`, when proposing a commit,
when writing a commit message, or when the user says "commit", "stage", "push".

## 1. Review before commit

- `git status` and `git diff --staged` (and `git diff` for unstaged) — **review
  every modified file**, do not commit blind.
- Group related changes; detect accidental/unrelated edits.
- If multiple unrelated features/concerns are mixed, **warn and recommend splitting**
  into separate commits.
- Never `git add -A` reflexively — stage intentionally.

## 2. Security checks — never commit

Warn immediately and **block** if any of these are staged:

- `.env`, `.env.local`, any `*.env` (only `*.env.example` is allowed)
- secrets, passwords, API keys, tokens, OAuth token files
- certificates, SSH keys, any private keys (`*.pem`, `*.key`, `id_rsa*`)
- customer data, call **recordings**, **transcripts** (operational `data/` is
  untracked by design — keep it that way)
- generated caches, temporary files, downloaded vendor documentation (unless
  intentionally added to `knowledge/`)
- virtual environments (`.venv*`, `.venv-wsl/`), `node_modules/`, build artifacts

If a secret was already staged, advise unstaging (`git restore --staged <f>`) and,
if it reached a commit, treat it as a security incident (rotate + history scrub) —
escalate to `security-auth-guardian`.

## 3. Repository hygiene

Verify before committing:

- `.gitignore` is respected; nothing ignored is force-added.
- No generated files, IDE artifacts (`.vscode/`, `.idea/`), log files, temp exports.
- No accidental binaries (audio, media, archives, compiled output).
- No downloaded vendor PDFs/HTML unless deliberately curated into `knowledge/`.

## 4. Commit message quality

Messages must be **concise, imperative, and descriptive** — and built only from the
real diff (see §8).

Good:
```
Add COMtrexx Next knowledge v1.0
Document provider recommendation philosophy
Fix escalation email privacy handling
```
Bad: `Update` · `Changes` · `Fix stuff` · `Test`

Repo conventions:
- Imperative mood, no trailing period in the subject, ~50 chars where practical.
- A body (after a blank line) only when the *why* isn't obvious from the subject.
- **Do NOT add `Co-Authored-By: Claude/Anthropic` or AI-attribution trailers** —
  this repo's convention is no AI co-author lines.

## 5. Commit summary (present before committing)

- **Files changed** (count + list), **+additions / −deletions** (`git diff --staged --stat`)
- **Affected modules** (backend / frontend / voice / docker / infra / docs / skills / knowledge / tests)
- **Possible risks**
- **Whether tests should run** (see §7)
- **Whether documentation changed** · **skills changed** · **knowledge repository changed**

## 6. Verify project rules

Confirm the change set is internally consistent across: application code,
documentation, skills, knowledge repository, Docker, CI, tests. The commit must
match **what actually changed** — if behavior changed but docs didn't, flag it
(`documentation-sync`); if a fixed bug has no test, flag it (`regression-protection`).

## 7. Testing reminder

If **application code** changed, suggest the appropriate validation before committing:

```
# Backend (WSL debian12 + .venv-wsl — never Windows Python):
../.venv-wsl/bin/python -m pytest tests/ -q
# Safety gate (required, non-skippable):
../.venv-wsl/bin/python -m pytest tests/test_phone_safety.py tests/test_openclaw_safety.py \
  tests/test_executive_agent_safety.py tests/test_logging_redaction.py -q
```
- Frontend change → `npm run build` (frontend).
- Docker/compose change → `docker compose build`.
- Voice/COMtrexx path → manual COMtrexx validation (ADR 0007 — validation is manual).

If **only documentation or the knowledge repository** changed, state clearly:
```
Documentation-only change.
No application tests required.
```

## 8. Never invent commit messages

Generate the message **only from the actual staged diff** (`git diff --staged`). Do
not guess intent, do not mention files that were not modified, do not describe
changes that aren't in the diff.

## 9. Large changes

If **> ~20 files** changed, recommend splitting into multiple focused commits
whenever it improves history (e.g. separate code from generated/lockfile churn, or
separate unrelated modules). Prefer several reviewable commits over one large one.

## 10. Final checklist (before recommending the commit)

- [ ] No secrets / credentials / private keys
- [ ] No customer data, recordings, or transcripts
- [ ] No accidental binaries or temporary files
- [ ] No virtual envs / node_modules / build artifacts
- [ ] `.gitignore` respected
- [ ] No unrelated edits mixed in (scope is one logical change)
- [ ] Commit message matches the staged diff (imperative, concise, no AI trailer)
- [ ] Changes reviewed file-by-file
- [ ] Appropriate tests considered / run (or "documentation-only" stated)
- [ ] On a feature branch (not the default branch)

Only then recommend:
```
git add <intentional paths>
git commit -m "<message from the diff>"
```

## Scope

Protects repository quality only. It does **not** replace `pipeline-guardian`
(build/test gate), `docker-guardian` (container topology), `backend-guardian`
(backend invariants), or `security-auth-guardian` (auth/secrets policy). It
complements them by keeping git history clean, secure, and understandable.

## Repository philosophy

Every commit should answer:
- Why was this change made?
- What changed?
- Can another developer understand it six months later?
- Can it be reverted safely?
- Does it keep the repository free from secrets and accidental files?

Git history is part of the project's documentation — treat it that way.
