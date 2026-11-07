import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from router.server import make_server
from router.service import Router


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.router = Router(Path(self.temp.name) / "state", Path(self.temp.name))
        self.server = make_server(self.router, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.router.close()
        self.temp.cleanup()

    def request(self, path, data=None, headers=None):
        request = urllib.request.Request(
            self.url + path, data=data, headers=headers or {}
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            with error:
                return error.code, error.read(), error.headers

    def test_state_and_frontend_are_served(self):
        code, body, headers = self.request("/api/state")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["tasks"], [])
        self.assertIn("token", json.loads(body))
        code, body, headers = self.request("/")
        self.assertEqual(code, 200)
        self.assertIn("AI Router", body.decode())
        self.assertIn("Content-Security-Policy", headers)

    def test_post_requires_token_and_same_origin(self):
        body = b"{}"
        self.assertEqual(
            self.request("/api/tasks", body, {"Content-Type": "application/json"})[0],
            403,
        )
        token = json.loads(self.request("/api/state")[1])["token"]
        self.assertEqual(
            self.request(
                "/api/tasks",
                body,
                {
                    "Content-Type": "application/json",
                    "X-Router-Token": token,
                    "Origin": "https://attacker.example",
                },
            )[0],
            403,
        )
        self.assertEqual(
            self.request(
                "/api/tasks",
                body,
                {
                    "Content-Type": "application/json",
                    "X-Router-Token": token,
                    "Origin": self.url,
                },
            )[0],
            400,
        )

    def test_rebinding_host_and_path_traversal_are_rejected(self):
        self.assertEqual(
            self.request("/api/state", headers={"Host": "attacker.example"})[0], 403
        )
        self.assertEqual(self.request("/%2e%2e/store.py")[0], 404)
        self.assertEqual(self.request("/api/unknown")[0], 404)

    def test_invalid_json_and_content_type_are_rejected(self):
        token = json.loads(self.request("/api/state")[1])["token"]
        headers = {"X-Router-Token": token, "Content-Type": "application/json"}
        self.assertEqual(self.request("/api/tasks", b"{", headers)[0], 400)
        self.assertEqual(self.request("/api/tasks", b"[]", headers)[0], 400)
        self.assertEqual(
            self.request("/api/tasks", b"{}", {"X-Router-Token": token})[0], 415
        )


if __name__ == "__main__":
    unittest.main()
