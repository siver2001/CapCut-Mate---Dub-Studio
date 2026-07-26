import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.dub_studio import key_pool
from tools.dub_studio.cli_parts import runtime


class _Response:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = str(payload)

    def json(self):
        return self._payload


def _success(text="Xin chào"):
    return _Response(
        200,
        {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": text}]},
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 4,
                "totalTokenCount": 14,
            },
        },
    )


@unittest.skipUnless(os.name == "nt", "Windows DPAPI only")
class GeminiKeyPoolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pool = key_pool.GeminiKeyPool(
            Path(self.temp.name) / "gemini_key_pool.json"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_dpapi_roundtrip_and_crud_never_persists_plaintext(self):
        key_id = self.pool.add_key(
            name="Key A",
            secret="secret-value-for-test",
            priority=2,
        )
        raw = self.pool.path.read_text(encoding="utf-8")
        self.assertNotIn("secret-value-for-test", raw)
        self.assertEqual(self.pool.candidate(key_id).secret, "secret-value-for-test")

        self.pool.update_key(key_id, name="Key B", priority=1)
        row = self.pool.rows()[0]
        self.assertEqual(row["name"], "Key B")
        self.assertEqual(row["priority"], 1)

        self.pool.delete_key(key_id)
        self.assertFalse(self.pool.has_keys())

    def test_quota_failover_uses_next_key_and_records_usage(self):
        first = self.pool.add_key(
            name="Key 1",
            secret="first-test-secret",
            priority=1,
        )
        second = self.pool.add_key(
            name="Key 2",
            secret="second-test-secret",
            priority=2,
        )
        responses = [
            _Response(
                429,
                {
                    "error": {
                        "message": "Quota exceeded: requests per day",
                        "details": [{"quotaId": "GenerateRequestsPerDay"}],
                    }
                },
            ),
            _success(),
        ]
        seen_keys = []

        def fake_post(url, headers, json, timeout):
            seen_keys.append(headers["x-goog-api-key"])
            return responses.pop(0)

        with (
            patch.dict(
                os.environ,
                {
                    "DUB_AI_MODE": "cloud",
                    "DUB_CLOUD_API_KEY": "",
                    "DUB_CLOUD_KEY_POOL_ENABLED": "true",
                    "DUB_CLOUD_MODEL": "gemini-3.5-flash",
                    "DUB_CLOUD_FREE_ONLY": "true",
                },
                clear=False,
            ),
            patch.object(runtime, "get_gemini_key_pool", return_value=self.pool),
            patch.object(runtime.requests, "post", side_effect=fake_post),
        ):
            result = runtime.run_ollama_prompt("return json", max_tokens=64)

        self.assertEqual(result, "Xin chào")
        self.assertEqual(seen_keys, ["first-test-secret", "second-test-secret"])
        rows = {row["id"]: row for row in self.pool.rows()}
        self.assertEqual(rows[first]["status"], "daily_exhausted")
        self.assertEqual(rows[second]["requestsToday"], 1)
        self.assertEqual(rows[second]["tokensToday"], 14)

    def test_rotation_continues_mid_job_without_manual_switch(self):
        first = self.pool.add_key(
            name="Key 1",
            secret="first-test-secret",
            priority=1,
        )
        second = self.pool.add_key(
            name="Key 2",
            secret="second-test-secret",
            priority=2,
        )
        responses = [
            _success("request-1"),
            _Response(
                429,
                {
                    "error": {
                        "message": "Quota exceeded: requests per day",
                        "details": [{"quotaId": "GenerateRequestsPerDay"}],
                    }
                },
            ),
            _success("request-2"),
            _success("request-3"),
        ]
        seen_keys = []

        def fake_post(url, headers, json, timeout):
            seen_keys.append(headers["x-goog-api-key"])
            return responses.pop(0)

        with (
            patch.dict(
                os.environ,
                {
                    "DUB_AI_MODE": "cloud",
                    "DUB_CLOUD_API_KEY": "",
                    "DUB_CLOUD_KEY_POOL_ENABLED": "true",
                    "DUB_CLOUD_MODEL": "gemini-3.5-flash",
                    "DUB_CLOUD_FREE_ONLY": "true",
                },
                clear=False,
            ),
            patch.object(runtime, "get_gemini_key_pool", return_value=self.pool),
            patch.object(runtime.requests, "post", side_effect=fake_post),
        ):
            self.assertEqual(runtime.run_ollama_prompt("prompt 1"), "request-1")
            self.assertEqual(runtime.run_ollama_prompt("prompt 2"), "request-2")
            self.assertEqual(runtime.run_ollama_prompt("prompt 3"), "request-3")

        self.assertEqual(
            seen_keys,
            [
                "first-test-secret",
                "first-test-secret",
                "second-test-secret",
                "second-test-secret",
            ],
        )
        rows = {row["id"]: row for row in self.pool.rows()}
        self.assertEqual(rows[first]["status"], "daily_exhausted")
        self.assertEqual(rows[second]["status"], "ready")
        self.assertTrue(rows[second]["active"])

    def test_invalid_key_rotates_without_leaking_secret(self):
        first = self.pool.add_key(
            name="Bad key",
            secret="invalid-test-secret",
            priority=1,
        )
        self.pool.add_key(
            name="Good key",
            secret="valid-test-secret",
            priority=2,
        )
        responses = [
            _Response(401, {"error": {"message": "API key not valid"}}),
            _success("ổn"),
        ]
        with (
            patch.dict(
                os.environ,
                {
                    "DUB_AI_MODE": "cloud",
                    "DUB_CLOUD_API_KEY": "",
                    "DUB_CLOUD_KEY_POOL_ENABLED": "true",
                    "DUB_CLOUD_MODEL": "gemini-3.5-flash",
                    "DUB_CLOUD_FREE_ONLY": "true",
                },
                clear=False,
            ),
            patch.object(runtime, "get_gemini_key_pool", return_value=self.pool),
            patch.object(runtime.requests, "post", side_effect=responses),
        ):
            self.assertEqual(runtime.run_ollama_prompt("return json"), "ổn")
        rows = {row["id"]: row for row in self.pool.rows()}
        self.assertEqual(rows[first]["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
