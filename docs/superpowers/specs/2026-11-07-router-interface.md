# Verständlicher lokaler AI Router

Der Nutzer beauftragt die Fertigstellung ohne weitere Entwurfsrunde, mit Freebuff-Integration und einer Oberfläche nach Apple-Vorbild unter Verwendung von Unslop.

## Richtung
- Produkt: Entwicklungsaufgaben lokal an installierte Coding-Agenten geben und Ergebnisse prüfen.
- Charakter: ruhig, verständlich, präzise.
- Welt: ein persönlicher Schreibtisch mit geordneten Arbeitsaufträgen.
- Momente: der aktuelle Auftrag und sein tatsächlicher Fortschritt tragen den visuellen Schwerpunkt.
- Signatur: eine nummerierte Abfolge von Auftrag, Ausführung und Prüfung.

## Befund
Die Cezar-Demo zeigt gleichzeitig Chat, Git, Graph, Workflows, Runner, Modell, Varianten und Terminal. Englische Status und simulierte Kosten sowie PR-Links erschweren dem Nutzer die Einordnung. Die Umsetzung erhält Cezar und seine Dateien als separaten Expertenversuch, stellt jedoch eine eigene einfache deutsche Oberfläche vor die lokalen Agenten. Keine Änderungen an installierten/minifizierten Cezar-Dateien.

## Umsetzung
Python 3.12+ mit Standardbibliothek, SQLite, lokalem HTTP-Server und HTML/CSS/JavaScript ohne Build-Schritt. Keine externe Schrift oder Bildabhängigkeit. Helle neutrale Flächen, Systemschrift, zurückhaltendes Blau, sichtbare Tastaturzustände und responsive Darstellung. Navigation: Übersicht, Aufgaben, Agenten, Einstellungen. Technische Angaben werden bei Bedarf aufgeklappt.

Aufgaben enthalten Repository, Beschreibung, Akzeptanzkriterien, Typ und Schwierigkeit. Immer genau eine aktive Ausführung, getrennte Git-Worktrees, persistierte Ereignisse und Status. Ein Dry-Run simuliert ausdrücklich nur den Ablauf; echte Agenten und Tests werden dabei nicht ausgeführt. Live-Aufrufe benötigen eine Freigabe pro Auftrag. Kosten bleiben unbekannt, wenn sie nicht gemessen werden können; keine erfundenen Werte. Ein Agenten-Exitcode ist kein bestandener Test. Testbefehle sind explizite Argumentlisten und nur nach Nutzerfreigabe auszuführen. Fehler, fehlende Programme, Timeouts und abgebrochene Serverläufe bleiben nachvollziehbar.

Codex wird über `codex exec` im workspace-write-Modus aufgerufen, Gemini über `gemini -p`. Keine Sandbox-Bypass-Flags. Freebuff 0.2.36 wird lokal installiert: der überprüfte Freebuff-Parser unterstützt `--cwd`, aber keinen Prompt-/Print-Modus. Deshalb bereitet die Integration einen isolierten Worktree vor, bietet den Auftrag zum Kopieren und startet nach separatem Klick eine interaktive Terminal-Sitzung. Erst nach dem Schließen der Sitzung kann der Nutzer das Ergebnis prüfen lassen. Kein angeblicher automatischer Freebuff-Lauf. Login bleibt beim Nutzer. Jules und Antigravity werden nicht als funktionierende Adapter ausgegeben.

Kontingente werden als verbleibende manuell konfigurierte Aufgaben geführt. Keine unbestätigten kostenpflichtigen Fallbacks. Budget und Kostenschätzungen sind Vorprüfungen, keine garantierten Provider-Ausgabelimits. Automatische Merges und Deployments gibt es nicht.

## Abnahme
Temporäre Git-Repositories und simulierte Prozesse prüfen Isolation, Freigaben, Single-Task-Sperre, SQLite-Neustartverhalten, Routing, Prozess-Timeouts und die HTTP-Sicherheitsgrenzen. Browserprüfung deckt Anlegen einer Demo-Aufgabe, Ergebnisansicht, Agentenübersicht und mobile Darstellung ab. Ein echter Agentenauftrag wird während der Implementierung nicht ausgeführt.

Unslop von Damir Sokolovsky (@heydamir), CC BY 4.0, dient als Gestaltungsanleitung. Es wird kein Apple-Markenzeichen verwendet.
