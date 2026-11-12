"""Loopback-only HTTP interface; no third-party server dependencies."""

import argparse
import json
import logging
import mimetypes
import os
import secrets
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .kit import KEY_ENV, KitClient
from .service import Router


LOG = logging.getLogger("router")
WEB = Path(__file__).with_name("web")


def make_server(router, port=4321):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, format, *args):
            LOG.info(format, *args)

        def origin_allowed(self):
            allowed = {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }
            if self.headers.get("Host") not in allowed:
                return False
            origin = self.headers.get("Origin")
            return origin is None or origin in {f"http://{host}" for host in allowed}

        def respond(
            self, status, value, content_type="application/json; charset=utf-8"
        ):
            body = (
                json.dumps(value, ensure_ascii=False).encode("utf-8")
                if not isinstance(value, bytes)
                else value
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            )
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                LOG.debug("Client disconnected")

        def do_GET(self):
            if not self.origin_allowed():
                return self.respond(403, {"error": "Nur lokale Zugriffe sind erlaubt."})
            path = unquote(urlsplit(self.path).path)
            if path == "/api/state":
                return self.respond(
                    200,
                    dict(
                        token=token,
                        tasks=router.store.list(),
                        agents=router.registry.list(),
                        settings=router.settings(),
                        version="0.1.0",
                    ),
                )
            if path.startswith("/api/"):
                return self.respond(404, {"error": "Schnittstelle nicht gefunden."})
            relative = (
                "index.html"
                if path in ("/", "/tasks", "/agents", "/settings")
                or path.startswith("/task/")
                else path.lstrip("/")
            )
            target = (WEB / relative).resolve()
            if not target.is_relative_to(WEB.resolve()) or not target.is_file():
                return self.respond(404, {"error": "Datei nicht gefunden."})
            kind = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if kind.startswith("text/") or kind in (
                "application/javascript",
                "image/svg+xml",
            ):
                kind += "; charset=utf-8"
            self.respond(200, target.read_bytes(), kind)

        def do_POST(self):
            if not self.origin_allowed() or not secrets.compare_digest(
                self.headers.get("X-Router-Token", ""), token
            ):
                return self.respond(
                    403, {"error": "Lokale Freigabe fehlt. Bitte die Seite neu laden."}
                )
            if self.headers.get_content_type() != "application/json":
                return self.respond(415, {"error": "JSON wird benötigt."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 64000:
                    return self.respond(413, {"error": "Anfrage zu groß oder leer."})
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Ein JSON-Objekt wird benötigt.")
                path = urlsplit(self.path).path
                if path == "/api/tasks":
                    return self.respond(201, router.create(payload))
                if path == "/api/settings":
                    return self.respond(200, router.save_settings(payload))
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[:2] == ["api", "tasks"]:
                    task_id, action = parts[2:]
                    actions = {
                        "review": lambda: router.review(
                            task_id, payload.get("run_tests") is True
                        ),
                        "finish": lambda: router.finish(task_id),
                        "abort": lambda: router.abort(task_id),
                        "terminal": lambda: router.launch_freebuff(task_id),
                    }
                    if action in actions:
                        return self.respond(200, actions[action]())
                return self.respond(404, {"error": "Aktion nicht gefunden."})
            except (ValueError, TypeError) as error:
                self.respond(400, {"error": str(error)})
            except KeyError:
                self.respond(404, {"error": "Aufgabe nicht gefunden."})
            except Exception:
                LOG.exception("Request failed")
                self.respond(
                    500,
                    {
                        "error": "Lokaler Serverfehler. Details stehen im Serverprotokoll."
                    },
                )

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def ensure_demo(root):
    repo = root / ".local/router-demo"
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        commands = [["git", "init", "-b", "main", str(repo)]]
        (repo / "README.md").write_text(
            "# AI Router Testprojekt\n\nEin lokales Projekt zum sicheren Ausprobieren.\n",
            encoding="utf-8",
        )
        commands += [
            ["git", "-C", str(repo), "add", "README.md"],
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=AI Router Demo",
                "-c",
                "user.email=demo@localhost",
                "commit",
                "-m",
                "chore: initialize demo",
            ],
        ]
        for command in commands:
            subprocess.run(command, check=True, capture_output=True)
    return repo


def main():
    parser = argparse.ArgumentParser(description="Lokaler AI Task Router")
    parser.add_argument("--port", type=int, default=4321)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    root = Path(__file__).resolve().parents[1]
    kit = KitClient(os.environ.pop(KEY_ENV, ""))
    with_router = Router(root / ".local/router", ensure_demo(root), root, kit=kit)
    server = None
    try:
        server = make_server(with_router, args.port)
        print(f"AI Router: http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if server:
            server.server_close()
        with_router.close()


if __name__ == "__main__":
    main()
