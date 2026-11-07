"""Durable task records and a process-wide instance lock."""

import json
import os
import sqlite3
import threading
from pathlib import Path


ACTIVE = ("queued", "running", "checking", "handoff")


class Store:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.instance = (directory / "instance.lock").open("a+b")
        try:
            self.instance.seek(0)
            if self.instance.read(1) == b"":
                self.instance.write(b"0")
                self.instance.flush()
            self.instance.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.instance.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.instance, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.instance.close()
            raise RuntimeError(
                "Der Router läuft bereits mit diesem Datenordner."
            ) from None
        self.db = sqlite3.connect(directory / "router.sqlite", check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, status TEXT NOT NULL, data TEXT NOT NULL)"
        )
        self.db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS one_active ON tasks((1)) WHERE status IN ('queued','running','checking','handoff')"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, data TEXT NOT NULL)"
        )
        self.db.commit()

    def list(self):
        with self.lock:
            return [
                json.loads(row[0])
                for row in self.db.execute("SELECT data FROM tasks ORDER BY rowid DESC")
            ]

    def get(self, task_id):
        with self.lock:
            row = self.db.execute(
                "SELECT data FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
            if row is None:
                raise KeyError("Aufgabe nicht gefunden")
            return json.loads(row[0])

    def save(self, task):
        with self.lock, self.db:
            try:
                self.db.execute(
                    "INSERT INTO tasks VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                    (task["id"], task["status"], json.dumps(task, ensure_ascii=False)),
                )
            except sqlite3.IntegrityError:
                raise ValueError(
                    "Es gibt bereits eine aktive Aufgabe. Beende oder prüfe sie zuerst."
                ) from None

    def settings(self):
        with self.lock:
            row = self.db.execute("SELECT data FROM settings WHERE id=1").fetchone()
            return json.loads(row[0]) if row else {}

    def save_settings(self, value):
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO settings VALUES (1,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (json.dumps(value),),
            )

    def close(self):
        self.db.close()
        self.instance.close()
