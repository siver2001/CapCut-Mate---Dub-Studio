import os
import unittest
from unittest.mock import patch

from tools.dub_studio.cli_parts import runtime


class _FakeResponse:
    status_code = 200
    text = ""

    def json(self):
        return {
            "candidates": [{
                "finishReason": "STOP",
                "content": {"parts": [
                    {"thought": True, "text": "internal reasoning [not json]"},
                    {"text": '[{"sourceId":"s1","translatedText":"Xin chào","delivery":"neutral"}]'},
                ]},
            }]
        }


class _QuotaResponse:
    status_code = 429
    text = "quota"
    headers = {}

    def json(self):
        return {"error": {"message": "Resource exhausted"}}


class _InvalidKeyResponse:
    status_code = 400
    text = "API key not valid"
    headers = {}

    def json(self):
        return {"error": {"message": "API key not valid. Please pass a valid API key."}}


class CloudRuntimeTests(unittest.TestCase):
    def test_gemini_ignores_thought_parts_and_uses_schema(self):
        runtime._CLOUD_AI_UNAVAILABLE_REASON = ""
        captured = {}

        def fake_post(url, headers, json, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return _FakeResponse()

        with patch.dict(os.environ, {
            "DUB_AI_MODE": "cloud",
            "DUB_CLOUD_API_KEY": "test-key",
            "DUB_CLOUD_MODEL": "gemini-2.5-flash",
        }, clear=False), patch.object(runtime.requests, "post", side_effect=fake_post):
            output = runtime.run_ollama_prompt(
                "return json",
                max_tokens=512,
                json_schema={"type": "array", "items": {"type": "object"}},
            )

        self.assertTrue(output.startswith("["))
        config = captured["payload"]["generationConfig"]
        self.assertEqual(config["thinkingConfig"]["thinkingBudget"], 0)
        self.assertIn("responseJsonSchema", config)
        self.assertNotIn("test-key", captured["url"])
        self.assertEqual(captured["headers"]["x-goog-api-key"], "test-key")

    def test_cloud_circuit_breaker_can_be_reset_for_next_job(self):
        runtime._CLOUD_AI_UNAVAILABLE_REASON = "quota from previous job"
        runtime.reset_cloud_ai_circuit_breaker()
        self.assertEqual(runtime._CLOUD_AI_UNAVAILABLE_REASON, "")

    def test_gemini_quota_has_structured_error_code(self):
        runtime.reset_cloud_ai_circuit_breaker()
        with (
            patch.dict(
                os.environ,
                {
                    "DUB_AI_MODE": "cloud",
                    "DUB_CLOUD_API_KEY": "test-key",
                    "DUB_CLOUD_MODEL": "gemini-2.5-flash",
                },
                clear=False,
            ),
            patch.object(runtime.requests, "post", return_value=_QuotaResponse()),
            self.assertRaises(runtime.CloudAIError) as raised,
        ):
            runtime.run_ollama_prompt("return json", max_tokens=64)
        self.assertEqual(raised.exception.code, "gemini_quota_exhausted")

    def test_invalid_gemini_key_has_structured_error_code(self):
        runtime.reset_cloud_ai_circuit_breaker()
        with (
            patch.dict(
                os.environ,
                {
                    "DUB_AI_MODE": "cloud",
                    "DUB_CLOUD_API_KEY": "bad-key",
                    "DUB_CLOUD_MODEL": "gemini-2.5-flash",
                },
                clear=False,
            ),
            patch.object(runtime.requests, "post", return_value=_InvalidKeyResponse()),
            self.assertRaises(runtime.CloudAIError) as raised,
        ):
            runtime.run_ollama_prompt("return json", max_tokens=64)
        self.assertEqual(raised.exception.code, "gemini_api_key_invalid")


if __name__ == "__main__":
    unittest.main()
