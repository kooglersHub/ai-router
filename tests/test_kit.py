import json
import unittest
from unittest.mock import patch

from router.kit import HOST, MODEL, KitClient


class KitClientTests(unittest.TestCase):
    @patch("router.kit.http.client.HTTPSConnection")
    def test_sends_bounded_request_to_kit_and_redacts_echoed_key(self, connect):
        connection = connect.return_value
        response = connection.getresponse.return_value
        response.status = 200
        response.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {"content": "Plan fixture-key"},
                        "finish_reason": "length",
                    }
                ],
                "usage": {"total_tokens": 103},
            }
        ).encode()
        result = KitClient("fixture-key").complete([], 64, 3)
        connect.assert_called_once_with(HOST, timeout=3)
        method, path, body, headers = connection.request.call_args.args
        self.assertEqual((method, path), ("POST", "/api/v1/chat/completions"))
        self.assertEqual(headers["Authorization"], "Bearer fixture-key")
        self.assertEqual(json.loads(body)["max_tokens"], 64)
        self.assertEqual(json.loads(body)["model"], MODEL)
        self.assertEqual(result, ("Plan [API-Key entfernt]", 103, True))
        connection.close.assert_called_once()
