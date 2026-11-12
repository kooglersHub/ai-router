"""Single, text-only requests to the KIT-hosted planning model."""

import http.client
import json


HOST = "ki-toolbox.scc.kit.edu"
MODEL = "alias.simple-local"
KEY_ENV = "KIT_TOOLBOX_API_KEY"
DEFAULT_OUTPUT_LIMIT = 512


def messages_for(task):
    return [
        {
            "role": "system",
            "content": "Erstelle einen kurzen technischen Umsetzungsplan mit Prüfschritten. Weise auf fehlende Informationen hin. Behaupte nicht, Dateien bearbeitet oder Tests ausgeführt zu haben.",
        },
        {
            "role": "user",
            "content": f"{task['title']}\n\n{task['description']}\n\nAkzeptanzkriterien:\n{task['criteria']}",
        },
    ]


def reserve_tokens(messages, output_limit):
    # A conservative estimate for the supplied text plus chat framing.
    return (
        sum(len(message["content"].encode("utf-8")) for message in messages)
        + 128
        + output_limit
    )


class KitClient:
    def __init__(self, key=""):
        self.key = key.strip()

    @property
    def configured(self):
        return bool(self.key)

    def complete(self, messages, output_limit, timeout):
        if not self.configured:
            raise ValueError("KIT-API-Key fehlt.")
        body = json.dumps(
            {
                "model": MODEL,
                "messages": messages,
                "max_tokens": output_limit,
                "stream": False,
            }
        )
        connection = http.client.HTTPSConnection(HOST, timeout=timeout)
        try:
            connection.request(
                "POST",
                "/api/v1/chat/completions",
                body,
                {
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": "application/json",
                },
            )
            response = connection.getresponse()
            if response.status in (401, 403):
                raise RuntimeError(
                    "KIT-Zugriff abgelehnt. Prüfe API-Key und Berechtigung."
                )
            if response.status == 429:
                raise RuntimeError(
                    "Die KIT-Toolbox meldet ein erreichtes Limit (HTTP 429)."
                )
            if response.status != 200:
                raise RuntimeError(
                    f"Die KIT-Toolbox antwortet mit HTTP {response.status}."
                )
            data = response.read(65_537)
        except (OSError, http.client.HTTPException, ValueError):
            raise RuntimeError(
                "KIT-Toolbox nicht erreichbar. Prüfe KIT-Netz oder VPN und das Zeitlimit."
            ) from None
        finally:
            connection.close()
        try:
            result = json.loads(data) if len(data) <= 65_536 else {}
            choice = result["choices"][0]
            output = choice["message"].get("content") or ""
            if not isinstance(output, str):
                raise TypeError
            usage = result.get("usage")
            total = usage.get("total_tokens") if isinstance(usage, dict) else None
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise RuntimeError(
                "Die KIT-Toolbox hat eine unerwartete Antwort geliefert."
            ) from None
        return (
            output.replace(self.key, "[API-Key entfernt]"),
            total if type(total) is int and total > 0 else None,
            choice.get("finish_reason") == "length",
        )
