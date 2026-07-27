import unittest
from pathlib import Path

from tools.dub_studio.cli_parts.audio import (
    _parse_silencedetect_profile,
    build_tts_delivery_profile,
    detect_tts_speech_profile,
    resolve_segment_target_ms,
)
from tools.dub_studio.models import SubtitleLine
from tools.dub_studio.subtitle_utils import split_subtitle_lines_for_display


class TimingSyncTests(unittest.TestCase):
    def test_silence_profile_excludes_leading_and_trailing_padding(self):
        profile = _parse_silencedetect_profile(
            "\n".join(
                [
                    "silence_start: 0",
                    "silence_end: 0.12 | silence_duration: 0.12",
                    "silence_start: 1.00",
                    "silence_end: 1.18 | silence_duration: 0.18",
                    "silence_start: 2.60",
                    "silence_end: 3.00 | silence_duration: 0.40",
                ]
            ),
            3000,
        )
        self.assertEqual(profile["activeStartMs"], 140)
        self.assertEqual(profile["activeEndMs"], 2640)
        self.assertEqual(profile["pauseOffsetsMs"], [1090])

    def test_balanced_timing_reserves_a_breath_before_next_segment(self):
        segments = [
            {"startMs": 0, "endMs": 4000, "translatedText": "Một câu ngắn."},
            {"startMs": 4000, "endMs": 8000, "translatedText": "Câu tiếp theo."},
        ]
        target_ms = resolve_segment_target_ms(
            segments,
            0,
            video_duration_ms=8000,
            timing_mode="balanced_natural",
            text=segments[0]["translatedText"],
        )
        self.assertLessEqual(target_ms, 3900)

    def test_long_unpunctuated_tts_text_gets_a_natural_pause(self):
        profile = build_tts_delivery_profile(
            text="Đây là một câu khá dài cần được đọc tự nhiên và rõ ràng hơn",
            source_text="A long sentence",
            voice="valtec:test",
            delivery="neutral",
        )
        self.assertIn(",", profile["text"])

    def test_subtitle_chunk_boundaries_follow_detected_audio_pauses(self):
        chunks = split_subtitle_lines_for_display(
            [
                SubtitleLine(
                    index=1,
                    start_ms=0,
                    end_ms=3000,
                    content="Một hai, ba bốn, năm sáu.",
                )
            ],
            max_words=2,
            max_chars=12,
            punctuation_aware=True,
            timing_anchors=[[900, 2100]],
        )
        self.assertEqual([item.content for item in chunks], [
            "Một hai,",
            "ba bốn,",
            "năm sáu.",
        ])
        self.assertEqual(chunks[0].end_ms, 900)
        self.assertEqual(chunks[1].end_ms, 2100)

    def test_detect_profile_on_missing_file_fails_loudly(self):
        with self.assertRaises(Exception):
            detect_tts_speech_profile(Path("missing-audio.wav"))


if __name__ == "__main__":
    unittest.main()
