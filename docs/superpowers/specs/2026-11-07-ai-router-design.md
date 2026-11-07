# Lokaler AI Task Router – MVP-Entwurf

> Stand 7. November 2026: Der folgende Eigenbau-Entwurf ist zurueckgestellt. Nach Pruefung der vom Nutzer eingebrachten Open-Source-Projekte wurde mit seiner Zustimmung zunaechst Cezar 0.18.0 lokal im Dry-Run installiert und getestet. Ergebnisse und Grenzen stehen in der README. Ein eigener Python-Router wurde nicht implementiert.

## Ziel

Eine lokale Weboberfläche delegiert Entwicklungsaufgaben an Coding-Agenten und macht Ausführung und Prüfung nachvollziehbar. Der MVP verwaltet ein ausgewähltes lokales Git-Repository und führt höchstens eine Aufgabe gleichzeitig aus.

## Oberfläche und Ablauf

1. Repository-Pfad und erlaubte Agenten konfigurieren.
2. Aufgabe mit Beschreibung, Akzeptanzkriterien, Typ, Schwierigkeit, Priorität und Budget eingeben.
3. Dry-Run zeigt den gewählten Agenten, Auswahlgründe, Aufruf und geplanten Worktree. Dabei startet kein Agent.
4. Aufgabe ausdrücklich starten. Der Router erstellt einen eigenen Branch und Worktree und ruft den ausgewählten Adapter auf.
5. Oberfläche zeigt Status, Laufzeit, Agentenausgabe, Fehler und Testergebnis. Änderungen bleiben im Worktree zur Prüfung erhalten.

GitHub Issues sind eine optionale Importquelle. Aufgaben können vollständig in der Oberfläche erstellt werden. Ein vorbereiteter PR besteht zunächst aus Titel, Beschreibung und Branch-Informationen; ein veröffentlichter PR ist kein Erfolgskriterium dieses MVP.

## Technische Entscheidung und Alternativen

Gewählt ist das vom Nutzer bestätigte lokale Webinterface. Als technische Umsetzung schlägt der Implementierer Python 3.12, FastAPI und serverseitige HTML-Templates mit etwas JavaScript vor. Das hält Installation und Betrieb in einem Prozess. SQLite speichert Aufgaben, Versuche und Ereignisse; ein Hintergrund-Worker bearbeitet die Warteschlange sequenziell.

Eine separate React-Anwendung bietet mehr Möglichkeiten für eine große Oberfläche, benötigt aber zusätzliche Build-Werkzeuge und Schnittstellenpflege. Ein reines CLI wäre kleiner, entspricht aber nicht dem gewünschten Bedienweg. Beide Alternativen werden für den MVP zurückgestellt.

## Adapter und Routing

Ein gemeinsamer Adaptervertrag kapselt Verfügbarkeit, Fähigkeiten, Aufruf, Timeout und Ergebnis. Gemini CLI und Codex CLI erhalten dokumentationsgeprüfte Aufrufe. Antigravity wird nur mit einer verifizierten Headless-Schnittstelle oder ausdrücklich konfigurierbarem Kommando aktiviert; eine angenommene `agy -p`-Schnittstelle gilt nicht als zugesichert. Jules ist optional und standardmäßig deaktiviert.

Der Router filtert nach erlaubten Agenten, Aufgabentyp, Schwierigkeit, konfiguriertem Kontingent und Budget. Innerhalb geeigneter Agenten nutzt er eine einfache nachvollziehbare Reihenfolge. Kontingente werden im MVP manuell konfiguriert; automatische Abfragen werden nicht vorausgesetzt. Fallbacks sind begrenzt und werden protokolliert. Jeder Implementierungsversuch erhält einen eigenen Worktree, damit ein gescheiterter Versuch den nächsten nicht beeinflusst.

## Schutzgrenzen

- Bindung standardmäßig nur an localhost.
- Keine automatischen Merges, Deployments oder Veröffentlichungen.
- Externe APIs und als kostenpflichtig konfigurierte Adapter sind ohne ausdrückliche Freigabe für den konkreten Lauf gesperrt. Ein vorhandenes CLI-Abonnement garantiert keine kostenlose Ausführung; unbekannte Abrechnung wird konservativ behandelt.
- Budgetprüfung basiert auf konfigurierten Schätzungen. Harte Kostenlimits eines externen Dienstes kann der Router nicht garantieren. Unbekannte Ist-Kosten werden als unbekannt gespeichert, nicht als null.
- Agenten verändern ausschließlich ihren Worktree; der Router erteilt keine Freigabe zum Umgehen von Agenten-Sicherheitsmechanismen.
- Testkommandos werden vom lokalen Nutzer konfiguriert, nicht ungeprüft aus importierten Issues ausgeführt.
- Secrets werden aus Umgebungsvariablen gelesen und nicht absichtlich in Logs gespeichert.
- Gleichzeitige Läufe werden auch auf Serverebene verhindert. Unterbrochene Läufe werden beim Neustart als unterbrochen markiert.

## Tests und Ergebnisprotokoll

SQLite erfasst Agent, Status, Start und Ende, Dauer, Fehlerkategorie, Testausgabe sowie bekannte oder geschätzte Kosten mit Kennzeichnung. Ein Agenten-Exitcode allein bedeutet keinen erfolgreich geprüften Auftrag. Akzeptanzkriterien bleiben sichtbar zur menschlichen Prüfung.

Automatisierte Tests prüfen Routing, Freigaben, Budget- und Kontingentfilter, Dry-Run, Timeouts, Fallbacks, Worktree-Isolation, Persistenz und zentrale Webabläufe. Tests verwenden simulierte Adapter und temporäre Git-Repositories; echte Agenten und kostenpflichtige APIs werden nicht aufgerufen.

## Lieferumfang und Abnahme

- Installierbares Python-Projekt mit lokal startbarer Weboberfläche.
- Aufgaben können angelegt, geplant, gestartet und mit Ergebnissen angesehen werden.
- Deterministischer Dry-Run funktioniert ohne installierte Agenten.
- Mindestens ein vollständig simulierter Ende-zu-Ende-Lauf prüft Aufgabe, isolierte Ausführung und Tests.
- README beschreibt Windows-Setup, Konfiguration, Start, Tests, Adaptergrenzen und den ersten Versuch mit einem echten Repository.
- Keine lernende Agentenauswahl, parallelen Agentenschwärme oder automatische Gemini-Aufgabenzerlegung im ersten MVP.

Offen für den ersten echten Versuch bleiben Repository-Pfad, konkrete Entwicklungsaufgabe und tatsächlich installierte beziehungsweise freigegebene Agenten. Diese Angaben sind keine Voraussetzung für den Bau und die simulierte Prüfung des MVP.
