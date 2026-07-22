---
id: common-fault-triage
type: procedure
owner: unassigned
status: draft
last_reviewed: 2026-07-22
sources:
  - "Teleprofi candidate interview-answer document (unconfirmed, 2026-07-22)"
---

> **Status: Candidate draft from the Teleprofi interview-answer document.**
> **Requires Patrick/Renato confirmation before merge.**

# Common Fault Triage (Technician Root-Cause Reference)

> Technician-facing root-cause guidance for the 20 most common faults, each
> with a first-check step, a follow-up step, and a typical remote-vs-onsite
> call. This is deliberately **separate** from
> `backend/voice/knowledge/teleprofi_fulda.md` §8, which holds the
> caller-facing intake questions the phone AI asks — that file is **not**
> modified by this entry and should not be. Do not blend the two: this file
> is root-cause reasoning for a technician; §8 is what the AI asks a caller.
> This file also does not duplicate `installation-final-qa-checklist.md`
> (pre-close verification) or `comtrexx-installation-checklist.md`
> (installation-time steps) — it is post-installation fault diagnosis only.

## When to use

Triaging a reported fault on an installed system.

## Preconditions

None.

## Steps — fault-by-fault triage

> Candidate content — from the interview draft's Interview 5 answer (20
> items). Every "Typischer Weg" (typical remote-vs-onsite call) below is
> the draft's own general judgement, explicitly **not** independently
> verified against real fault history — flagged for Patrick's confirmation
> before this is relied on operationally.

1. **Keine ausgehenden Anrufe.** Erste Prüfung: Umfang, Fehlermeldung,
   Providerstatus. Danach: Registrierung, Routing, Berechtigung. Typischer
   Weg: meist Fernwartung.
2. **Keine eingehenden Anrufe.** Erste Prüfung: alle Nummern oder einzelne?
   Danach: Provider, Rufverteilung, Zeitsteuerung. Typischer Weg: meist
   Fernwartung.
3. **Einzelnes Telefon ohne Funktion.** Erste Prüfung: Strom, Netzwerk,
   Display. Danach: Port, Provisionierung, Gerätetausch. Typischer Weg:
   zuerst Fernwartung.
4. **Gesamte Anlage nicht erreichbar.** Erste Prüfung: Strom, Internet,
   Netzwerk. Danach: Anlage, Router, Provider, Neustartstatus. Typischer
   Weg: Fernwartung, gegebenenfalls vor Ort.
5. **Schlechte Sprachqualität.** Erste Prüfung: alle Gespräche? Welche
   Richtung? Danach: Bandbreite, Paketverlust, QoS, Verkabelung. Typischer
   Weg: Fernanalyse plus Messung.
6. **Gesprächsabbrüche.** Erste Prüfung: Zeitpunkt, Häufigkeit, Muster.
   Danach: Router, NAT, SIP, Provider, Netzwerk. Typischer Weg: meist
   Fernwartung.
7. **Einseitige Sprache.** Erste Prüfung: intern oder extern? VPN beteiligt?
   Danach: NAT, Firewall, RTP. Typischer Weg: Fernwartung.
8. **Falsche Rufnummernanzeige.** Erste Prüfung: betroffene Benutzer oder
   Nummern. Danach: CLIP-Einstellungen, Provider. Typischer Weg:
   Fernwartung.
9. **Rufgruppe klingelt falsch.** Erste Prüfung: Soll-Ablauf aufnehmen.
   Danach: Gruppen, Zeiten, Weiterleitungen. Typischer Weg: Fernwartung.
10. **Weiterleitung funktioniert nicht.** Erste Prüfung: Ziel und Auslöser.
    Danach: Berechtigung, Provider, Regel. Typischer Weg: Fernwartung.
11. **DECT-Reichweitenprobleme.** Erste Prüfung: Ort und Bewegungsmuster.
    Danach: Basisposition, Funkmessung. Typischer Weg: häufig vor Ort.
12. **WLAN instabil.** Erste Prüfung: Fläche, Nutzer, Uhrzeiten. Danach:
    Kanäle, Signal, Verkabelung, Ausleuchtung. Typischer Weg: oft vor Ort.
13. **Headset ohne Ton.** Erste Prüfung: Verbindung und Standardgerät.
    Danach: Treiber, Softphone, Kompatibilität. Typischer Weg: Fernwartung.
14. **Softphone registriert nicht.** Erste Prüfung: Zugang, Internet, VPN.
    Danach: Konto, Firewall, Provisionierung. Typischer Weg: Fernwartung.
15. **Homeoffice nicht erreichbar.** Erste Prüfung: lokales Internet, VPN.
    Danach: Router, Rechte, Client. Typischer Weg: Fernwartung.
16. **Türsprechstelle funktioniert nicht.** Erste Prüfung: Klingeln oder
    Audio? Danach: Verkabelung, Relais, SIP oder Analog. Typischer Weg: oft
    vor Ort.
17. **Faxprobleme.** Erste Prüfung: sporadisch oder vollständig? Danach:
    Provider, T.38, Codec, Leitung. Typischer Weg: Fernwartung,
    gegebenenfalls Umbau.
18. **Zeitsteuerung falsch.** Erste Prüfung: Zeitpunkt und Regel. Danach:
    Kalender, Feiertage, Zeitzone. Typischer Weg: Fernwartung.
19. **Nach Update fehlen Funktionen.** Erste Prüfung: Version und Änderung.
    Danach: Release Notes, Backup, Konfiguration. Typischer Weg:
    Fernwartung.
20. **Providerwechsel oder Portierung.** Erste Prüfung: betroffene Nummern.
    Danach: Schalttermin, Routing, Zugangsdaten. Typischer Weg: Fernwartung
    plus Koordination.

## Validation

Fault resolved and, where the fix touched configuration, verified against
`installation-final-qa-checklist.md`'s relevant items.

## Rollback / if it fails

Escalate to on-site visit per the general rule below if remote diagnosis is
inconclusive.

## Notes — general remote-vs-onsite rule

> Candidate content, same source. This closes a real gap: the live voice-AI
> runtime file has no remote-vs-onsite guidance at all today. This file does
> **not** modify that runtime file — any future promotion of this rule into
> `backend/voice/knowledge/teleprofi_fulda.md` is a separate, deliberate
> decision requiring its own review, not an automatic consequence of this
> entry existing.

**Fernwartung reicht**, wenn: Anlage und Netzwerk erreichbar sind; keine
physische Beschädigung vermutet wird; Konfiguration oder Protokolle
ausreichen; der Kunde einfache Sichtprüfungen durchführen kann; kein
Messgerät oder Hardwaretausch erforderlich ist.

**Ein Vor-Ort-Termin ist notwendig**, wenn: Verkabelung oder
Stromversorgung unklar ist; Funkabdeckung gemessen werden muss; Hardware
ausgetauscht wird; mehrere Systeme physisch zusammenspielen; die
Bestandsdokumentation fehlt; wiederkehrende Fehler remote nicht
reproduzierbar sind; Sicherheits- oder Betriebsrisiken eine direkte Prüfung
erfordern.

All fault-specific triage steps above are candidate content, unconfirmed —
requires Patrick's confirmation before operational use. Wrong guidance here
has real consequences given how close this content sits to the live phone
AI's own troubleshooting categories.
