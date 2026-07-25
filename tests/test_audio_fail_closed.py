import unittest
from pathlib import Path
from unittest.mock import patch

from tools.dub_studio.cli_parts.audio import _run_tts_chain


class AudioFailClosedTests(unittest.TestCase):
    def test_dialogue_tts_failure_aborts_instead_of_creating_silence(self):
        item = {
            "index": 1,
            "progress_index": 1,
            "speaker_id": "speaker_1",
            "voice": "valtec:test",
            "translated": "Đây là lời thoại.",
            "source_text": "This is dialogue.",
            "delivery": "neutral",
            "target_ms": 1200,
            "provider": "valtec",
            "segment": {"id": "seg_0001"},
        }
        with patch(
            "tools.dub_studio.cli_parts.audio.synthesize_timed_tts_clip",
            side_effect=RuntimeError("provider unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "render stopped"):
                _run_tts_chain(
                    items=[item],
                    total_segments=1,
                    timing_mode="balanced",
                    tts_dir=Path("temp/test_tts_fail_closed"),
                    job_id="test",
                    global_speed=1.0,
                )


if __name__ == "__main__":
    unittest.main()
