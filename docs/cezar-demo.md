# AI Router – lokaler Cezar-Test

Dieser Ordner nutzt Cezar statt eines neu entwickelten Python-Routers. Installiert ist die veroeffentlichte Version **0.18.0**, lokal unter `.local/cezar`. Es gibt keine globale Installation.

## Start unter Windows

```powershell
cd 'C:\Users\karl\Documents\ChatGPT\ai router'
.\start-cezar-demo.ps1
```

Die Oberflaeche ist standardmaessig unter http://127.0.0.1:4321 erreichbar. Bei belegtem Port kann Cezar einen anderen Port verwenden; die Serverausgabe nennt ihn. Mit `-NoOpen` startet der Server ohne Browser. Strg+C beendet einen im Terminal gestarteten Server.

Der Start setzt immer `CEZ_DRY_RUN=1`: Die Agenten werden simuliert. Aufgaben bearbeiten nur das lokale Test-Repository `.local/demo`. Die Demo nutzt ein eigenes `CEZ_HOME` unter `.local/cezar-home`, maximal eine aktive Aufgabe und keine automatisch importierten Team-Skills. Der Launcher bietet absichtlich keinen Echtbetrieb-Schalter.

## Installation wiederherstellen

Node.js 20+ und pnpm benoetigt. Die lokale Installation und deren Lockfile liegen unter `.local/cezar`:

```powershell
pnpm --dir .local/cezar add --save-exact cezar-run@0.18.0
```

Auf diesem Rechner wurde das mit Codex gebuendelte pnpm ueber Node gestartet, da npm/npx nicht im Suchpfad liegen. Das Demo-Repository und die isolierte Konfiguration sind lokale Testdaten; sie werden nicht versioniert.

## Was der Test belegt

Die Demo prueft Installation, Weboberflaeche und einen simulierten Aufgabenlauf. Sie belegt keine echte Agenten-Authentifizierung, automatische Kontingenterkennung, Budgetgrenzen oder Codequalitaet. Angezeigte Token und Kosten im Dry-Run sind simulierte Werte.

Es werden keine echten Agentenauftraege gestartet, keine Pull Requests veroeffentlicht und keine Merges oder Deployments ausgefuehrt. Ein echter Test am Kleinanzeigen-Projekt ist ein separater naechster Schritt.

### Ergebnis vom 7. November 2026

- Health-Endpunkt: HTTP 200, Version 0.18.0, Demo-Repository.
- Server bindet ausschliesslich an `127.0.0.1:4321`.
- Aufgabe in der Weboberflaeche angelegt und mit dem Claude-Mock ausgefuehrt.
- Eigener Branch `cez/806599ce` und eigener Worktree erfolgreich angelegt.
- Mock erzeugt `notes.md`; Demo-Hauptbranch bleibt sauber.
- Sitzung beendet; Ergebnis wartet im Status `review` auf menschliche Pruefung.
- Server-Fehlerlog nach dem Test leer; PowerShell-Launcher ohne Syntaxfehler.

Der Mock zeigt einen erfundenen GitHub-PR-Link und simulierte Kosten. Das Demo-Repository hat keinen Remote; es wurde kein PR erstellt. Die veroeffentlichte Version bietet in der getesteten Runner-Auswahl Claude, Codex, Junie, OpenCode, Cursor, Pi und Copilot. Gemini, Antigravity und Jules sind in dieser Version dort nicht verfuegbar; die neuere GitHub-Dokumentation darf nicht mit der installierten Version gleichgesetzt werden.

Die laufende Hintergrundinstanz protokolliert unter `.local/cezar.stdout.log` und `.local/cezar.stderr.log`. Ihr PowerShell-Launcher ist in `.local/cezar-server.pid` vermerkt. Das Webinterface bleibt waehrend dieses lokalen Tests erreichbar; nach einem Rechnerneustart den Launcher erneut ausfuehren.

## Quellen

- https://github.com/open-mercato/cezar
- https://github.com/open-mercato/cezar#quick-start
