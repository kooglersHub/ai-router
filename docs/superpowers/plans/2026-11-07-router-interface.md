# Router interface implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ein verständlicher lokaler Router mit ehrlicher Freebuff-Übergabe und prüfbaren Ergebnissen.
**Architecture:** Python-Standardbibliothek für HTTP, SQLite und sequenzielle Hintergrundaufgaben; statisches Webinterface; CLI-Adapter ohne Shell-Prompts.
**Tech Stack:** Python 3.12+, SQLite, HTML/CSS/JS.
**Spec:** docs/superpowers/specs/2026-11-07-router-interface.md

## Global constraints
Nur localhost. Keine automatischen Merges, Deployments oder kostenpflichtigen API-Aufrufe. Dry-Run standardmäßig. Eine aktive Aufgabe. Keine Änderungen am installierten Cezar.

## Review focus
- Fehlende Programme und Anmeldung: klarer Fehler statt behaupteter erfolgreicher Integration.
- Pfade mit Leerzeichen und Unicode: Argumentlisten, keine interpolierten Shell-Aufgaben.
- Gleichzeitige Starts: transaktionale Sperre vor dem Hintergrundstart.
- Neustart: aktive Aufträge unterbrochen markieren und Worktrees erhalten.
- Fremde HTTP-Origin und übergroße Eingaben: abweisen.

## Task 1: Lokale Ausführung und Persistenz
- [x] Tests in tests/test_router.py für Dry-Run, Freigabe, Worktrees, Routing, Timeout und Neustart schreiben und fehlschlagen sehen.
- [x] router/store.py, router/agents.py, router/service.py implementieren.
- [x] Tests ausführen und Fehler beheben.

## Task 2: HTTP und Oberfläche
- [x] Tests in tests/test_server.py für JSON, Eingabevalidierung, Origin- und Host-Prüfung schreiben.
- [x] router/server.py und router/web/index.html, app.js, styles.css implementieren.
- [x] Helle deutsche Oberfläche in neun Unslop-Pässen umsetzen: Abstand, Farbe, Icons, Texte, Typografie, Layout, Details, Inhalte, Bewegung.
- [x] Oberfläche im Browser mit einer Demo-Aufgabe und Agentenstatus prüfen.

## Task 3: Betrieb und Übergabe
- [x] start-router.ps1, README und Installationsanleitung aktualisieren.
- [x] Gesamte Testsuite, Syntaxprüfung und git diff --check ausführen.
- [x] Abschließende Codeprüfung und Browserbeleg; lokalen Stand committen.

## Ledger
Entscheidung: Ausführung direkt über geprüfte lokale CLI-Adapter, anstatt die installierten Cezar-Bundles zu verändern. So bleibt die neue Oberfläche wartbar. Freebuff ist ein interaktiver Handoff, keine erfundene Headless-API.


Verifikation: 21 Tests bestanden. Ruff, Prettier, JavaScript- und PowerShell-Syntaxpruefungen bestanden. Browser: Demo-Auftrag erstellt, Ergebnis und Agenten geprueft, Einstellungen gespeichert, mobiler Viewport 390 px ohne horizontalen Ueberlauf. Review-Funde zu Instanzsperre, Freebuff-Neustart, Testkonfiguration und Diagnoseausgaben mit Regressionstests behoben. Kein echter KI-Auftrag ausgefuehrt.
