"""Single-task orchestration, isolated git worktrees, explicit review."""

import concurrent.futures
import datetime as dt
import json
import math
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path

from .agents import AgentRegistry, process_identity, run_command
from .kit import DEFAULT_OUTPUT_LIMIT, KitClient, messages_for, reserve_tokens
from .store import ACTIVE, Store


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def git(repo, *arguments):
    code, output = run_command(["git", "-C", str(repo), *arguments], repo, 30)
    if code:
        raise ValueError(output.strip() or "Git-Aufruf fehlgeschlagen")
    return output.strip()


def repository_path(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Bitte einen lokalen Projektordner angeben.")
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise ValueError("Der Projektordner existiert nicht.")
    top = Path(git(path, "rev-parse", "--show-toplevel")).resolve()
    if top != path:
        raise ValueError("Bitte den Hauptordner des Git-Projekts auswählen.")
    git(path, "rev-parse", "--verify", "HEAD")
    return path


class Router:
    def __init__(self, directory, default_repo, root=None, kit=None):
        self.directory = Path(directory).resolve()
        self.store = Store(self.directory)
        self.kit = kit if kit is not None else KitClient()
        self.registry = AgentRegistry(
            root or Path(__file__).resolve().parents[1], self.kit.configured
        )
        self.default_repo = str(default_repo)
        self.mutex = threading.RLock()
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.cancel = threading.Event()
        self.terminals = {}
        self.closed = False
        for task in self.store.list():
            if task["status"] in ACTIVE:
                if self.terminal_active(task):
                    task["status"] = "handoff"
                    task["events"].append(
                        dict(
                            time=now(),
                            message="Die Freebuff-Sitzung läuft noch. Vor der Prüfung das Terminal schließen.",
                        )
                    )
                    self.store.save(task)
                    continue
                task["status"] = "interrupted"
                task["events"].append(
                    dict(
                        time=now(),
                        message="Server neu gestartet. Arbeitskopie bleibt zur Prüfung erhalten.",
                    )
                )
                self.store.save(task)

    def settings(self):
        return (
            dict(
                repo=self.default_repo,
                quotas={"codex": None, "gemini": None, "freebuff": None},
                tests=[],
                estimated_costs={"codex": None, "gemini": None, "freebuff": None},
                kit_budget=0,
                kit_used=0,
                kit_output_limit=DEFAULT_OUTPUT_LIMIT,
            )
            | self.store.settings()
        )

    def save_settings(self, value):
        with self.mutex:
            return self._save_settings(value)

    def _save_settings(self, value):
        if not isinstance(value, dict):
            raise ValueError("Einstellungen müssen ein Objekt sein.")
        settings = self.settings()
        for field, minimum, maximum in (
            ("kit_budget", 0, 2**53 - 1),
            ("kit_output_limit", 1, 4096),
        ):
            if field in value:
                number = value[field]
                if type(number) is not int or not minimum <= number <= maximum:
                    raise ValueError(
                        f"KIT-Tokenlimit muss eine ganze Zahl zwischen {minimum} und {maximum} sein."
                    )
                settings[field] = number
        if "repo" in value:
            settings["repo"] = str(repository_path(value["repo"]))
        for key in ("quotas", "estimated_costs"):
            if key in value:
                if not isinstance(value[key], dict) or set(value[key]) - {
                    "codex",
                    "gemini",
                    "freebuff",
                }:
                    raise ValueError("Unbekannte Agenten-Konfiguration.")
                for agent, number in value[key].items():
                    if number is not None and (
                        type(number) not in (int, float)
                        or not math.isfinite(number)
                        or number < 0
                    ):
                        raise ValueError(
                            "Kontingente und Schätzungen müssen positive Zahlen sein."
                        )
                    if key == "quotas" and number is not None and int(number) != number:
                        raise ValueError("Kontingente müssen ganze Aufgaben zählen.")
                    settings[key][agent] = number
        if "tests" in value:
            tests = value["tests"]
            if not isinstance(tests, list) or len(tests) > 8:
                raise ValueError("Maximal acht Testkommandos als JSON-Liste angeben.")
            if any(
                not isinstance(cmd, list)
                or not cmd
                or len(cmd) > 32
                or any(
                    not isinstance(arg, str) or not arg or len(arg) > 2000
                    for arg in cmd
                )
                for cmd in tests
            ):
                raise ValueError(
                    'Testkommandos brauchen Argumentlisten, etwa [["python", "-m", "pytest"]].'
                )
            settings["tests"] = tests
        self.store.save_settings(settings)
        return settings

    def task(self, task_id):
        return self.store.get(task_id)

    def terminal_active(self, task):
        process = self.terminals.get(task["id"])
        if process is not None:
            return process.poll() is None
        pid = task.get("terminal_pid")
        if not pid:
            return False
        identity = process_identity(pid)
        return identity is not None and (
            identity == "unverifiable" or identity == task.get("terminal_identity")
        )

    def update(self, task_id, message=None, **values):
        with self.mutex:
            task = self.task(task_id)
            task.update(values)
            if message:
                task["events"].append(dict(time=now(), message=message))
            self.store.save(task)
            return task

    def create(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Ungültiger Auftrag.")
        with self.mutex:
            if any(task["status"] in ACTIVE for task in self.store.list()):
                raise ValueError(
                    "Es gibt bereits eine aktive Aufgabe. Beende oder prüfe sie zuerst."
                )
            task = self.validate(payload)
            self.cancel.clear()
            self.store.save(task)
            self.pool.submit(self.execute, task["id"])
            return task

    def validate(self, payload):
        settings = self.settings()
        task = dict(payload)
        for field in ("title", "description"):
            if (
                not isinstance(task.get(field), str)
                or not task[field].strip()
                or len(task[field]) > (200 if field == "title" else 20000)
            ):
                raise ValueError(
                    "Titel und Beschreibung werden benötigt (maximal 200 / 20.000 Zeichen)."
                )
        if (
            not isinstance(task.get("criteria", ""), str)
            or len(task.get("criteria", "")) > 10000
        ):
            raise ValueError("Akzeptanzkriterien sind zu lang oder ungültig.")
        if task.get("agent") not in (
            "auto",
            "codex",
            "gemini",
            "freebuff",
            "kit",
        ) or task.get("mode") not in ("demo", "live"):
            raise ValueError("Ungültiger Agent oder Modus.")
        if task.get("task_type") not in (
            "bugfix",
            "feature",
            "research",
            "tests",
        ) or task.get("difficulty") not in ("easy", "medium", "hard"):
            raise ValueError("Ungültiger Aufgabentyp oder Schwierigkeitsgrad.")
        if task["mode"] == "live" and task.get("consent") is not True:
            raise ValueError(
                "Ein echter Agentenaufruf benötigt deine ausdrückliche Freigabe."
            )
        timeout = task.get("timeout", 900)
        budget = task.get("budget", None)
        if type(timeout) is not int or not 1 <= timeout <= 7200:
            raise ValueError("Das Zeitlimit muss zwischen 1 und 7200 Sekunden liegen.")
        if budget is not None and (
            type(budget) not in (int, float) or not math.isfinite(budget) or budget < 0
        ):
            raise ValueError("Das Budget muss eine positive Zahl sein.")
        repo = repository_path(task.get("repo", settings["repo"]))
        eligible_quotas = dict(settings["quotas"])
        if task["mode"] == "live" and budget is not None and task["agent"] == "auto":
            for agent, estimate in settings["estimated_costs"].items():
                if estimate is None or estimate > budget:
                    eligible_quotas[agent] = 0
        selected = self.registry.choose(
            task["agent"], task["task_type"], task["difficulty"], eligible_quotas
        )
        estimate = 0 if selected == "kit" else settings["estimated_costs"].get(selected)
        if (
            task["mode"] == "live"
            and budget is not None
            and (estimate is None or estimate > budget)
        ):
            raise ValueError(
                "Für dieses Budget fehlt eine passende Kostenschätzung. Agentenübersicht prüfen."
            )
        if (
            task["mode"] == "live"
            and selected not in ("freebuff", "kit")
            and not self.registry.command(selected)
        ):
            raise ValueError(f"{selected} ist nicht installiert.")
        if selected == "kit" and task["mode"] == "live":
            if not self.kit.configured:
                raise ValueError(
                    "Hinterlege zuerst deinen KIT-API-Key beim Start des Routers."
                )
            task.setdefault("criteria", "")
            self.check_kit_budget(
                settings,
                reserve_tokens(messages_for(task), settings["kit_output_limit"]),
            )
        return dict(
            id=uuid.uuid4().hex,
            title=task["title"].strip(),
            description=task["description"].strip(),
            criteria=task.get("criteria", "").strip(),
            repo=str(repo),
            requested_agent=task["agent"],
            agent=selected,
            mode=task["mode"],
            timeout=timeout,
            budget=budget,
            task_type=task["task_type"],
            difficulty=task["difficulty"],
            status="queued",
            created_at=now(),
            started_at=None,
            finished_at=None,
            duration=None,
            cost_actual=None,
            cost_estimate=estimate,
            kit_output_limit=settings["kit_output_limit"]
            if selected == "kit"
            else None,
            worktree=None,
            branch=None,
            tests=settings["tests"],
            test_status="not_run",
            test_results=[],
            diff="",
            files=[],
            events=[
                dict(
                    time=now(),
                    message=(
                        "KIT KI-Toolbox für einen Umsetzungsplan ausgewählt."
                        if selected == "kit"
                        else f"{selected} ausgewählt: zulässig und Kontingent verfügbar."
                    ),
                )
            ],
            output="",
            error=None,
        )

    def prepare_worktree(self, task):
        path = self.directory / "worktrees" / task["id"]
        path.parent.mkdir(exist_ok=True)
        branch = f"codex/router-{task['id'][:10]}"
        git(task["repo"], "worktree", "add", "-b", branch, str(path), "HEAD")
        return self.update(
            task["id"],
            "Isolierte Arbeitskopie erstellt; dein Projektordner bleibt unverändert.",
            worktree=str(path),
            branch=branch,
            base_commit=git(path, "rev-parse", "HEAD"),
        )

    def execute(self, task_id):
        started = time.monotonic()
        try:
            task = self.update(
                task_id, "Aufgabe wird vorbereitet.", status="running", started_at=now()
            )
            if task["mode"] == "demo":
                self.update(
                    task_id,
                    "Demo: Auswahl und Ablauf geprüft. Kein Agent und kein Testkommando aufgerufen.",
                    status="demo_complete",
                    finished_at=now(),
                    duration=round(time.monotonic() - started, 2),
                    output="Der Ablauf ist bereit. Für echte Änderungen wähle „Echte Aufgabe“ und gib den Aufruf frei.",
                )
                return
            if self.cancel.is_set():
                raise InterruptedError("Ausführung abgebrochen")
            if task["agent"] == "kit":
                self.execute_kit(task)
                return
            task = self.prepare_worktree(task)
            if self.cancel.is_set():
                raise InterruptedError("Ausführung abgebrochen")
            if task["agent"] == "freebuff":
                self.update(
                    task_id,
                    "Freebuff braucht ein Terminal. Kopiere den Auftrag und öffne die Sitzung.",
                    status="handoff",
                )
                return
            prompt = self.prompt(task)
            command = self.registry.execution(task["agent"], prompt)
            with self.mutex:
                settings = self.settings()
                quota = settings["quotas"].get(task["agent"])
                if quota is not None:
                    settings["quotas"][task["agent"]] = max(0, quota - 1)
                    self.store.save_settings(settings)
            self.update(
                task_id,
                "Agent arbeitet. Die Ausgabe erscheint nach Abschluss des CLI-Aufrufs.",
            )
            code, output = run_command(
                command, task["worktree"], task["timeout"], self.cancel
            )
            self.update(task_id, output=output)
            if code:
                raise RuntimeError(
                    f"Agent mit Exitcode {code} beendet. Details stehen unter Agentenausgabe."
                )
            self.collect(task_id)
        except Exception as error:
            self.update(
                task_id,
                str(error),
                status="cancelled" if isinstance(error, InterruptedError) else "failed",
                error=str(error),
                output=getattr(error, "output", self.task(task_id)["output"]),
                finished_at=now(),
            )
        finally:
            self.update(task_id, duration=round(time.monotonic() - started, 2))

    @staticmethod
    def check_kit_budget(settings, needed):
        available = max(0, settings["kit_budget"] - settings["kit_used"])
        if needed > available:
            raise ValueError(
                f"KIT-Tokenbudget zu klein: {available} verfügbar, {needed} geschätzt. Kürze den Auftrag oder passe das Budget an."
            )

    def execute_kit(self, task):
        messages = messages_for(task)
        reserved = reserve_tokens(messages, task["kit_output_limit"])
        task_id = task["id"]
        with self.mutex:
            settings = self.settings()
            self.check_kit_budget(settings, reserved)
            # Persist before sending. A failed or interrupted response may still consume tokens.
            settings["kit_used"] += reserved
            self.store.save_settings(settings)
            self.update(
                task_id,
                "KIT erstellt den Plan aus dem Auftragstext.",
                kit_tokens_reserved=reserved,
            )
        output, total, truncated = self.kit.complete(
            messages, task["kit_output_limit"], min(task["timeout"], 90)
        )
        if total is not None:
            with self.mutex:
                settings = self.settings()
                settings["kit_used"] += total - reserved
                self.store.save_settings(settings)
        self.update(task_id, kit_tokens_actual=total, output=output)
        if self.cancel.is_set():
            raise InterruptedError(
                "KIT-Aufruf beendet. Der Tokenverbrauch bleibt erfasst."
            )
        if not output.strip():
            raise RuntimeError(
                "KIT hat keinen Plan zurückgegeben. Prüfe das Antwortlimit."
            )
        message = "KIT-Plan bereit."
        if truncated:
            message = "KIT-Plan am Antwortlimit abgeschnitten."
        self.update(task_id, message, status="done", finished_at=now())

    @staticmethod
    def prompt(task):
        return (
            f"{task['title']}\n\n{task['description']}\n\nAkzeptanzkriterien:\n{task['criteria']}\n\n"
            "Arbeite nur in dieser Git-Arbeitskopie. Keine Merges, Pushes, Deployments oder kostenpflichtigen Zusatzdienste. "
            "Fasse Änderungen, Prüfungen und offene Punkte zum Schluss zusammen."
        )

    def launch_freebuff(self, task_id):
        with self.mutex:
            task = self.task(task_id)
            if task["agent"] != "freebuff" or task["status"] != "handoff":
                raise ValueError("Diese Aufgabe wartet nicht auf Freebuff.")
            if self.terminal_active(task):
                raise ValueError("Die Freebuff-Sitzung ist bereits geöffnet.")
            command = self.registry.command("freebuff")
            if not command:
                raise ValueError(
                    "Freebuff fehlt. Installationsanleitung in der Agentenübersicht öffnen."
                )
            if os.name != "nt":
                raise ValueError(
                    "Terminal-Start derzeit unter Windows unterstützt. Starte freebuff --cwd mit dem angezeigten Arbeitsordner."
                )
            # A file holds literal arguments; the task prompt never becomes PowerShell code.
            config = self.directory / f"freebuff-{task_id}.json"
            config.write_text(
                json.dumps(
                    dict(
                        command=command + ["--cwd", task["worktree"]],
                        prompt=self.prompt(task),
                    )
                ),
                encoding="utf-8",
            )
            script = Path(__file__).with_name("freebuff-session.ps1")
            shell = shutil_which_powershell()
            process = subprocess.Popen(
                [shell, "-NoProfile", "-File", str(script), "-ConfigPath", str(config)],
                cwd=task["worktree"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            self.terminals[task_id] = process
            self.update(
                task_id,
                "Freebuff-Terminal geöffnet. Anmeldung und Auftrag dort bestätigen; danach die Sitzung schließen.",
                terminal_pid=process.pid,
                terminal_identity=process_identity(process.pid),
            )
            return self.task(task_id)

    def review(self, task_id, run_tests=False):
        with self.mutex:
            task = self.task(task_id)
            if (
                task["status"]
                not in ("handoff", "review", "failed", "interrupted", "cancelled")
                or not task["worktree"]
            ):
                raise ValueError(
                    "Für diese Aufgabe gibt es noch keine prüfbare Arbeitskopie."
                )
            if self.terminal_active(task):
                raise ValueError("Bitte die Freebuff-Terminalsitzung zuerst schließen.")
            if run_tests:
                commands = self.settings()["tests"]
                if not commands:
                    raise ValueError(
                        "Bitte zuerst Testkommandos in den Einstellungen konfigurieren."
                    )
                self.update(
                    task_id, tests=commands, test_status="not_run", test_results=[]
                )
            self.cancel.clear()
            self.update(task_id, "Änderungen werden geprüft.", status="checking")
            self.pool.submit(self.collect_safe, task_id, run_tests)
            return self.task(task_id)

    def collect_safe(self, task_id, run_tests):
        try:
            self.collect(task_id, run_tests)
        except Exception as error:
            self.update(
                task_id,
                str(error),
                status="failed",
                error=str(error),
                finished_at=now(),
                output=getattr(error, "output", self.task(task_id)["output"]),
            )

    def collect(self, task_id, run_tests=False):
        task = self.task(task_id)
        path = task["worktree"]
        base = task["base_commit"]
        diff = git(path, "diff", base, "--")
        files = git(path, "diff", "--name-only", base, "--").splitlines()
        untracked = git(path, "ls-files", "--others", "--exclude-standard", "-z").split(
            "\0"
        )
        for name in filter(None, untracked):
            files.append(name)
            candidate = Path(path) / name
            if candidate.is_symlink() or not candidate.is_file():
                continue
            if candidate.stat().st_size <= 100_000:
                diff += f"\n+++ {name} (neu)\n" + candidate.read_text(
                    encoding="utf-8", errors="replace"
                )
            else:
                diff += f"\n+++ {name} (neu, Vorschau zu groß)\n"
        self.update(task_id, diff=diff[:200_000], files=files)
        results = []
        if run_tests:
            for command in task["tests"]:
                self.update(task_id, "Test: " + " ".join(command))
                try:
                    code, output = run_command(
                        command, path, min(task["timeout"], 600), self.cancel
                    )
                except (OSError, InterruptedError) as error:
                    results.append(
                        dict(
                            command=command,
                            exit_code=None,
                            output=getattr(error, "output", str(error)),
                        )
                    )
                    self.update(task_id, test_status="failed", test_results=results)
                    raise
                results.append(dict(command=command, exit_code=code, output=output))
        test_status = (
            ("passed" if all(item["exit_code"] == 0 for item in results) else "failed")
            if results
            else "not_run"
        )
        self.update(
            task_id,
            "Änderungen bereit. Bitte Akzeptanzkriterien und Prüfungen selbst bestätigen.",
            status="review",
            finished_at=now(),
            diff=diff[:200_000],
            files=files,
            test_status=test_status,
            test_results=results,
            duration=round(
                (
                    dt.datetime.now(dt.timezone.utc)
                    - dt.datetime.fromisoformat(task["started_at"])
                ).total_seconds(),
                2,
            ),
        )

    def finish(self, task_id):
        task = self.task(task_id)
        if task["status"] != "review":
            raise ValueError("Bitte zuerst das Ergebnis prüfen.")
        return self.update(
            task_id,
            "Prüfung bestätigt. Änderungen bleiben im Arbeitsbranch; kein Merge ausgeführt.",
            status="done",
        )

    def abort(self, task_id):
        task = self.task(task_id)
        if task["status"] not in ACTIVE:
            raise ValueError("Die Aufgabe läuft nicht.")
        if self.terminal_active(task):
            raise ValueError("Bitte zuerst die interaktive Freebuff-Sitzung schließen.")
        self.cancel.set()
        if task["status"] == "handoff":
            return self.update(
                task_id,
                "Aufgabe beendet; Arbeitskopie bleibt erhalten.",
                status="cancelled",
                finished_at=now(),
            )
        return self.update(
            task_id, "Abbruch angefordert. Warte, bis der Prozess beendet wurde."
        )

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.cancel.set()
        self.pool.shutdown(wait=True, cancel_futures=False)
        self.store.close()


def shutil_which_powershell():
    import shutil

    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise ValueError("PowerShell wurde nicht gefunden.")
    return shell
