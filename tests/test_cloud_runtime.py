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


if __name__ == "__main__":
    unittest.main()
