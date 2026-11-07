"""Verified CLI entry points. Interactive Freebuff is never disguised as headless."""

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


def process_identity(pid):
    """Creation timestamp prevents a recycled Windows PID identifying a different session."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [
        ctypes.POINTER(wintypes.FILETIME)
    ] * 4
    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return "unverifiable" if ctypes.get_last_error() == 5 else None
    try:
        created, exited, kernel_time, user_time = (
            wintypes.FILETIME() for _ in range(4)
        )
        if not kernel.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        ):
            return "unverifiable"
        if exited.dwLowDateTime or exited.dwHighDateTime:
            return None
        return str((created.dwHighDateTime << 32) | created.dwLowDateTime)
    finally:
        kernel.CloseHandle(handle)


def output_tail(output):
    output.seek(0, os.SEEK_END)
    size = output.tell()
    output.seek(max(0, size - 100_000))
    return output.read().decode("utf-8", errors="replace")


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=10,
        )
    else:
        import signal

        os.killpg(process.pid, signal.SIGKILL)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_command(command, cwd, timeout=600, cancel=None):
    """Bound wall time and memory use; retain a log tail even for noisy CLIs."""
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt",
        )
        started = time.monotonic()
        try:
            while process.poll() is None:
                if cancel and cancel.is_set():
                    raise InterruptedError("Ausführung abgebrochen")
                if time.monotonic() - started > timeout:
                    raise TimeoutError("Zeitlimit erreicht; Prozess wurde beendet")
                time.sleep(0.05)
        except BaseException as error:
            stop_process(process)
            error.output = output_tail(output)
            raise
        return process.returncode, output_tail(output)


class AgentRegistry:
    def __init__(self, root):
        self.root = Path(root)

    def command(self, agent):
        if agent == "codex":
            path = shutil.which("codex")
            if path and Path(path).suffix.lower() not in (".cmd", ".bat"):
                return [path]
        node = shutil.which("node")
        if not node:
            candidate = (
                Path.home()
                / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
            )
            node = str(candidate) if candidate.is_file() else None
        module = {
            "freebuff": "freebuff/index.js",
            "gemini": "@google/gemini-cli/dist/index.js",
        }.get(agent)
        if module and node:
            entry = self.root / ".local/agents/node_modules" / module
            if entry.is_file():
                return [node, str(entry)]
        path = shutil.which(agent)
        if path and Path(path).suffix.lower() not in (".cmd", ".bat", ".ps1"):
            return [path]
        return None

    def list(self):
        descriptions = [
            (
                "codex",
                "Codex",
                "automatic",
                "Setzt Aufgaben direkt in einer isolierten Arbeitskopie um",
            ),
            (
                "freebuff",
                "Freebuff",
                "interactive",
                "Im Terminal arbeiten, Änderungen anschließend hier prüfen",
            ),
            (
                "gemini",
                "Gemini CLI",
                "automatic",
                "Analyse und Umsetzung über eine lokale Gemini-Installation",
            ),
        ]
        return [
            dict(
                id=key,
                name=name,
                kind=kind,
                description=description,
                installed=bool(self.command(key)),
                authenticated=None,
                quota_source="manual",
                cost_known=False,
            )
            for key, name, kind, description in descriptions
        ]

    def choose(self, requested, task_type, difficulty, quotas):
        if requested != "auto":
            if quotas.get(requested, 1) == 0:
                raise ValueError(
                    "Das konfigurierte Kontingent dieses Agenten ist aufgebraucht."
                )
            return requested
        preferred = (
            ["gemini", "codex", "freebuff"]
            if task_type == "research" or difficulty == "easy"
            else ["codex", "gemini", "freebuff"]
        )
        for agent in preferred:
            if quotas.get(agent, 1) != 0 and (
                self.command(agent) or agent == "freebuff"
            ):
                return agent
        raise ValueError("Kein Agent mit verfügbarem Kontingent gefunden.")

    def execution(self, agent, prompt):
        command = self.command(agent)
        if not command:
            raise ValueError(
                f"{agent} ist nicht installiert. Öffne die Agentenübersicht."
            )
        if agent == "codex":
            return command + [
                "exec",
                "--sandbox",
                "workspace-write",
                "--color",
                "never",
                prompt,
            ]
        if agent == "gemini":
            return command + ["-p", prompt, "--output-format", "json"]
        raise ValueError("Freebuff benötigt eine interaktive Terminal-Sitzung.")
