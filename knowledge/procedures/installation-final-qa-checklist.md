---
id: installation-final-qa-checklist
type: procedure
owner: unassigned
status: draft
last_reviewed: 2026-07-22
sources:
  - "Teleprofi candidate interview-answer document (unconfirmed, 2026-07-22)"
---

> **Status: Candidate draft from the Teleprofi interview-answer document.**
> **Requires Patrick/Renato confirmation before merge.**

# Installation Final QA Checklist

> What is checked immediately before a project is closed out, and the
> mistakes this step exists to catch. Distinct from
> [`comtrexx-installation-checklist.md`](./comtrexx-installation-checklist.md)
> (preparation/preconfig/bench-test, done *during* installation) — this
> file is the closing verification pass. Also distinct from the qualitative
> "what makes an installation clean" principle in
> [`../business-philosophy/installation-philosophy.md`](../business-philosophy/installation-philosophy.md)
> — that file holds the *why*, this file holds the *checklist*.

## When to use

Immediately before declaring a telephone-system project complete /
handed over.

## Preconditions

`comtrexx-installation-checklist.md`'s bench-test and on-site steps are
done.

## Steps — what to verify before closing

> Candidate list — from the interview draft's "Was kontrollieren Sie immer
> vor Projektabschluss?" answer.

Vereinbarte Funktionen; Gesprächsqualität; Erreichbarkeit; Rufverteilung;
Rechte; Zeitsteuerung; Notrufverhalten; mobile und interne Nutzung;
Sicherung; Dokumentation; Kennzeichnung; Kundeneinweisung; offene Punkte;
Abnahme.

## Validation

All items above are confirmed working and documented; open points are
explicitly listed, not silently dropped.

## Steps — errors this checklist exists to catch

> Candidate list, same source ("Welche Fehler möchten Sie grundsätzlich
> vermeiden?").

- Ungesicherte Änderungen (unsecured/unbacked-up changes).
- Falsche Rufnummernzuordnung (wrong number assignment).
- Fehlende Notrufprüfung (emergency-number check skipped).
- Undokumentierte Passwörter oder Zugänge (undocumented passwords/access).
- Unklare Administratorrechte (unclear admin rights).
- Nicht getestete Weiterleitungen (untested call forwarding).
- Überraschende Lizenzen oder Folgekosten (surprise licences/follow-on
  costs — should have been caught by `sales-offer-checklist.md` already).
- Provisorische Verkabelung als Dauerlösung (a temporary cabling fix left
  in place as if permanent).
- Fehlende Beschriftung (missing labelling).
- Übergabe ohne Backup und Dokumentation (handover without backup/docs).

## Rollback / if it fails

If any item fails verification, the project is not closed — return to the
relevant installation step rather than handing over with a known gap.

## Notes

Candidate content, unconfirmed — requires Patrick/Renato sign-off. The
interview draft's INSTALLATION and QUALITÄT sections had two
partially-overlapping checklists; this file is the reconciled, single
canonical "final QA" list — `comtrexx-installation-checklist.md` owns the
separate preparation/preconfig/bench-test checklist. Do not re-split these
again without updating both files' cross-references.
