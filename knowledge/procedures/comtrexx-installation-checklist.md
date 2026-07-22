---
id: comtrexx-installation-checklist
type: procedure
owner: unassigned
status: draft
last_reviewed: 2026-07-22
sources:
  - "Teleprofi candidate interview-answer document (unconfirmed, 2026-07-22)"
---

> **Status: Candidate draft from the Teleprofi interview-answer document.**
> **Requires Patrick/Renato confirmation before merge.**

# Telephone System Installation Checklist

> The generic preparation → preconfiguration → bench-test → on-site checklist
> a Teleprofi installation follows. Fills the "Technician View" placeholder
> in
> [`../services/telephone-system-installation.md`](../services/telephone-system-installation.md).
> This is a **generic** checklist across telephone-system installations, not
> COMtrexx-Next-specific — the Next-specific preconfiguration/bench-test
> detail `products/comtrexx-next.md`'s own "Interview Backlog (Patrick)"
> asks for is only **partially** addressed here; that backlog item should
> stay open until Patrick confirms Next-specific detail separately.
>
> Distinct from
> [`common-fault-triage.md`](./common-fault-triage.md) (post-installation
> fault diagnosis) and
> [`installation-final-qa-checklist.md`](./installation-final-qa-checklist.md)
> (what to verify before closing the project) — keep these three separate,
> do not merge them.

## When to use

Preparing for, and executing, a telephone-system installation or migration.

## Preconditions

`pre-project-expectations-checklist.md` is complete.

## Steps — preparation

> Candidate list — from the interview draft's "Wie bereiten Sie eine
> Installation vor?" answer.

1. Anforderungen und Angebot abgleichen (reconcile requirements against the
   offer).
2. Ansprechpartner und Zeitfenster bestätigen (confirm contact person and
   time window).
3. Netzwerk- und Providerdaten prüfen (check network/provider data).
4. Rufnummern und Portierung klären (clarify numbers and porting).
5. Endgeräte und Lizenzen kontrollieren (check endpoints and licences).
6. Konfiguration vorbereiten (prepare configuration).
7. Sicherungen bestehender Systeme erstellen (back up existing systems).
8. Rückfallplan definieren (define a rollback plan).
9. Testfälle vorbereiten (prepare test cases).
10. Zuständigkeiten und Erreichbarkeit am Installationstag klären (clarify
    responsibilities/reachability on installation day).

## Steps — what gets preconfigured (soweit möglich)

> Candidate list, same source.

Benutzer, Rufnummern, Gruppen, Berechtigungen, Endgeräte, Zeitsteuerungen,
Ansagen, Weiterleitungen, Providerprofile, Basis-Sicherheitskonfiguration,
Update- und Wartungseinstellungen.

## Steps — what is bench-tested before the customer sees it

> Candidate list, same source.

Registrierung und Gesprächsaufbau; eingehende und ausgehende Gespräche;
interne Gespräche; Rufgruppen; Weiterleitungen; Besetzt-/Nichtannahmefälle;
Ansagen; Zeitsteuerungen; Notruf- und Sondernummern; Endgeräte; mobile
Nutzung; Türsprechstellen und analoge Geräte; Wiederanlauf nach Neustart;
Dokumentation der Testresultate.

## Validation

> Candidate 12-point checklist, from the interview draft's "Welche
> Checkliste arbeitet Teleprofi grundsätzlich ab?" answer — presented there
> as a minimum outline, explicitly marked in the source as needing
> Teleprofi's own confirmation and later maintenance as its own source.

1. Voraussetzungen
2. Backup
3. Konfiguration
4. Hardware und Verkabelung
5. Provider
6. Funktionsprüfung
7. Sicherheitsprüfung
8. Ausfallszenario
9. Dokumentation
10. Einweisung
11. Abnahme
12. Nachkontrolle

## Rollback / if it fails

Use the rollback plan defined during preparation (step 8 above) and the
pre-installation backups (step 7). Escalate to the responsible internal
decision-maker rather than improvising on-site.

## Notes

Candidate content, unconfirmed — requires Patrick/Renato sign-off before
this is treated as Teleprofi's actual internal checklist, per the source
draft's own caveat: "Die tatsächliche interne Checkliste muss durch
Teleprofi bestätigt und später als eigene Wissensquelle gepflegt werden."
