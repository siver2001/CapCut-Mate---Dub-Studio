import unittest

from gui.window.workflow import _available_gemini_models
from tools.dub_studio.key_pool import mask_key


class GeminiModelSelectionTests(unittest.TestCase):
    def test_masked_key_is_recognizable_without_revealing_secret(self):
        secret = "demoKey_1234567890_safeExample_Z9x7"
        masked = mask_key(secret)
        self.assertEqual(masked, "demoKey_…Z9x7")
        self.assertNotIn("1234567890", masked)

    def test_available_models_only_keeps_generate_content_free_models(self):
        payload = {
            "models": [
                {
                    "name": "models/gemini-3.5-flash-lite",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-3.5-flash",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-paid-pro",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-embedding",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ]
        }
        self.assertEqual(
            _available_gemini_models(payload, free_only=True),
            ["gemini-3.5-flash", "gemini-3.5-flash-lite"],
        )


if __name__ == "__main__":
    unittest.main()
