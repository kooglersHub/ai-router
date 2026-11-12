# AI Router

Ein lokales Webinterface für Entwicklungsaufgaben: Auftrag beschreiben, Agent auswählen, getrennt vom Hauptprojekt arbeiten und das Ergebnis prüfen. Die Oberfläche ist deutsch und verwendet helle Flächen, Systemschrift und eine klare Schrittfolge nach Apple-Vorbild.

## Starten

Voraussetzungen: **Python 3.12+** und **Git** im Suchpfad. Der Router selbst benötigt keine Python-Pakete und keinen Frontend-Build.

```powershell
cd 'C:\Users\karl\Documents\ChatGPT\ai router'
.\start-router.ps1
```

Öffne [den lokalen Arbeitsbereich](http://127.0.0.1:4321). Das Startskript öffnet den Browser und startet den Server im Hintergrund. Eine bereits laufende Router-Instanz wird wiederverwendet.

```powershell
.\start-router.ps1 -NoOpen
.\stop-router.ps1
```

Alternativ im Terminal, mit sichtbarer Serverausgabe und Strg+C zum Beenden:

```powershell
python -m router.server --port 4321
```

Nach einem Rechnerneustart das Startskript erneut ausführen. Es wird kein Autostart eingerichtet. Logs liegen unter `.local/router/stdout.log` und `stderr.log`.

## Der erste Auftrag

1. Auf **Übersicht** beschreiben, was erledigt werden soll. Ein Titel ist optional.
2. Projektordner und Agent wählen. Das mitgelieferte `router-demo` ist ein separates Testprojekt.
3. Mit **Erst ausprobieren** den Ablauf ohne Agentenaufruf testen. Dabei werden weder Dateien geändert noch Tests ausgeführt.
4. Für eine echte Umsetzung **Echte Aufgabe** wählen und den konkreten Aufruf freigeben.
5. **Ergebnis prüfen** zeigt Änderungen. **Tests ausführen** startet ausschließlich deine konfigurierten Kommandos.
6. **Prüfung bestätigen** schließt die Aufgabe ab. Es wird nichts gemergt, gepusht oder veröffentlicht.

Jede echte Aufgabe bekommt eine eigene Git-Arbeitskopie und einen Branch. Grundlage ist der aktuelle HEAD-Commit; nicht eingecheckte Änderungen werden nicht kopiert. Der Pfad steht in den Aufgabendetails. **Es läuft höchstens eine aktive Aufgabe gleichzeitig.** Worktrees bleiben zur manuellen Prüfung erhalten. Sie sind Versionsisolation, keine Betriebssystem-Sandbox.

## Freebuff

Die vom Nutzer gewünschte [Freebuff CLI](https://freebuff.com/cli) ist als interaktiver Agent angebunden. Installiert und mit `--help` geprüft wurde **0.2.36**. Diese Version unterstützt `--cwd`, aber keinen Prompt-/Headless-Modus.

1. In der Aufgabe **Freebuff** und **Echte Aufgabe** auswählen.
2. **Freebuff vorbereiten** legt die isolierte Arbeitskopie an; es sendet noch keinen Auftrag.
3. **Auftrag kopieren**, dann **Freebuff öffnen** anklicken.
4. Im Terminal bei Bedarf anmelden, den Auftrag einfügen und bearbeiten lassen.
5. Freebuff beenden und das Terminal schließen; anschließend im Router **Ergebnis prüfen** wählen.

Der Windows-Terminalstart wird vom Router ausgeführt. Laufende Sitzungen werden über PID und Prozesserstellungszeit erkannt, auch nach einem Router-Neustart. Solange Freebuff läuft, bleiben Testausführung und weitere aktive Aufträge gesperrt. Die interaktive Sitzung hat kein automatisch erzwungenes Agentenzeitlimit. Der Router führt weder Login noch einen KI-Auftrag beim Start automatisch aus.

Lokale Installation wiederherstellen:

```powershell
.\install-agents.ps1
```

Dafür werden Node.js 20+ sowie npm oder pnpm benötigt; auf diesem Rechner kann das Skript auch das mit Codex gebündelte pnpm nutzen. Die Installation liegt unter `.local/agents`, ohne globale Installation.

## Weitere Agenten

### KIT KI-Toolbox

Beende eine laufende Router-Instanz und starte sie mit `.\start-router.ps1 -Kit`. PowerShell fragt den API-Key verdeckt ab. Der Key gilt für diese Server-Sitzung und wird weder in SQLite noch im Git-Repository gespeichert. Alternativ liest der Server `KIT_TOOLBOX_API_KEY` beim Start aus der Umgebung.

Trage unter **Einstellungen → KIT-Tokenbudget** das Gesamtkontingent ein, das dieser Router verwenden darf. Standardmäßig beträgt es 0. Das Antwortlimit beginnt bei 512 Tokens. Der Router reserviert vor dem Aufruf eine konservative Schätzung für Eingabe, Chat-Overhead und Antwort. Falls KIT einen Verbrauch meldet, ersetzt dieser die Schätzung. Bei fehlender Verbrauchsmeldung oder einem Fehler bleibt die Reservierung erhalten. Andere Clients und serverseitige Prompt-Zusätze kann der lokale Zähler nicht vorab erfassen.

Wähle **KIT KI-Toolbox · Umsetzungsplan** für einen freigegebenen Auftrag. Der Router sendet Titel, Beschreibung und Erfolgskriterien einmal an das KIT-Modell `alias.simple-local`. Der Plan erscheint im Ergebnis und lässt sich für einen separaten Umsetzungsauftrag verwenden. Zugriff und Modell-ID sind in der [KIT-Dokumentation](https://www.scc.kit.edu/dienste/ki-toolbox.php) beschrieben. Bei Verbindungsproblemen prüfe KIT-Netz oder VPN.

### Lokale CLIs

- **Codex:** vorhandene native `codex`-CLI im Suchpfad; `codex exec --sandbox workspace-write` setzt Aufgaben um. Agenten-Schutzmechanismen werden nicht deaktiviert.
- **Gemini:** Adapter für `gemini -p` vorhanden; derzeit auf diesem Rechner noch nicht installiert. Mit `install-agents.ps1 -WithGemini` lokal installieren und im Terminal anmelden. Berechtigungen und Abrechnung richten sich nach der Gemini-Konfiguration.
- **Antigravity und Jules:** keine aktive Integration in dieser Version. Sie werden nicht als einsatzbereit ausgegeben.

Die Agentenübersicht unterscheidet Installation von Anmeldung. Eine echte Authentifizierung oder erfolgreiche Modellanfrage wurde bei der Implementierung nicht getestet. Kostenpflichtige Modellaufrufe wurden nicht ausgeführt.

## Tests und Kontingente konfigurieren

Unter **Einstellungen** lassen sich der Standardordner, manuell verbleibende Aufgaben pro Agent und Kostenschätzungen angeben. Bei `0` Aufgaben wird der Agent nicht ausgewählt. Leere Felder bedeuten unbekannt. Automatische CLI-Versuche reduzieren den manuellen Zähler; Freebuff-Zähler werden von dir gepflegt.

Die Auswahl bevorzugt Gemini bei Analyse/kleinen Aufgaben und Codex bei mittleren/großen Umsetzungen, berücksichtigt Installation, manuelle Kontingente und bei gesetztem Budget die Kostenschätzung. Sie ist eine feste Heuristik, kein lernendes System. Ist kein geeigneter automatischer Agent vorhanden, kann Freebuff als interaktiver Übergang vorbereitet werden.

Ein Budget ist eine **Vorprüfung anhand deiner Schätzung**, kein hartes Provider-Ausgabenlimit. Tatsächliche Kosten werden nicht erfunden: ohne Rückmeldung des Dienstes bleiben sie unbekannt. Es gibt keinen automatischen Wechsel auf einen kostenpflichtigen Dienst. Nach Fehlern kannst du vorhandene Änderungen prüfen und einen weiteren Auftrag mit einem anderen Agenten starten.

Testkommandos werden als JSON-Argumentlisten gespeichert, zum Beispiel:

```json
[["python", "-m", "unittest", "discover", "-s", "tests"]]
```

Die Befehle laufen nach ausdrücklichem Klick lokal in der Arbeitskopie. Änderungen an der Testkonfiguration lassen sich auch auf bestehende Aufgaben anwenden. CLI-Ausgaben und Testprotokolle sind auf die letzten 100 KB je Prozess begrenzt, Diffs auf eine begrenzte Vorschau. Eine erfolgreiche Agenten-Ausführung gilt nicht automatisch als bestandener Test. Eine nicht bestandene Prüfung bleibt sichtbar.

## Entwicklung und Prüfung

```powershell
python -m unittest discover -s tests -v
python -m pip install ruff==0.14.3
ruff check router tests
ruff format --check router tests
node --check router/web/app.js
```

Die Tests verwenden temporäre Git-Repositories und lokale Python-Testprozesse; sie rufen keine echten Coding-Dienste auf. Sie prüfen Freigaben, Routing/Budgetfilter, SQLite-Neustartverhalten, Single-Task-Sperren, Worktree-Isolation, Terminal-Wiedererkennung, Timeouts, nachträgliche Testkonfiguration sowie HTTP-Origin-/Host-Schutz. GitHub Actions ist für Windows mit Python 3.12 und 3.14 vorbereitet; lokal geprüft wurde Python 3.14.6.

Python wird mit Ruff formatiert. HTML/CSS/JavaScript werden mit Prettier 3.5.3 formatiert (lokal unter `.local/agents/node_modules/prettier`). Der Server bindet nur an `127.0.0.1`. Schreibzugriffe brauchen ein lokales Sitzungstoken und werden bei fremder Origin oder fremdem Host abgewiesen. Dieser persönliche lokale Server ist nicht für öffentliche Bereitstellung ausgelegt.

## Aufbau

- `router/server.py`: lokaler HTTP-Server und statische Oberfläche
- `router/service.py`: Aufgaben, Worktrees und Ergebnisprüfung
- `router/store.py`: SQLite und Instanzsperre
- `router/agents.py`: Agentenerkennung, Routing und Prozessausführung
- `router/web/`: Oberfläche ohne Build-Schritt
- `.local/router/`: lokale Aufgaben, Datenbank, Logs und Arbeitskopien (nicht versioniert)

Die frühere Cezar-Demo bleibt unverändert erhalten. Sie wird nicht als Backend der neuen Oberfläche verwendet; der aktuelle Router ruft die lokalen CLIs direkt auf. Die alte Demo kann separat mit `start-cezar-demo.ps1 -Port 4323` gestartet werden. Historische Prüfergebnisse stehen unter `docs/cezar-demo.md`.

## Gestaltung und Quellen

Unslop von **Damir Sokolovsky ([@heydamir](https://x.com/heydamir))**, CC BY 4.0, wurde als Gestaltungsanleitung verwendet. Lucide-Icons: ISC-Lizenz unter `router/web/icons/LICENSE`. Die Gestaltung ist Apple-inspiriert; es werden keine Apple-Markenassets verwendet.

- [Freebuff-CLI-Quellcode und Argumente](https://github.com/CodebuffAI/freebuff/blob/main/cli/src/cli-args.ts)
- [Gemini Headless-Dokumentation](https://geminicli.com/docs/cli/headless/)
- [Cezar](https://github.com/open-mercato/cezar)
