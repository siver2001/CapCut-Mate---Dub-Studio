import unittest
from tools.dub_studio.subtitle_utils import apply_subtitle_timeline_to_segments


class UnmatchedSubtitlesTests(unittest.TestCase):
    def test_apply_subtitle_timeline_inserts_new_text_segments(self):
        # Existing whisper audio segments (only 1 speech segment from 0 to 2s)
        segments = [
            {
                "id": "seg_0001",
                "startMs": 0,
                "endMs": 2000,
                "sourceText": "Hello",
                "translatedText": "Xin chào",
                "speakerId": "speaker_1",
            }
        ]
        # Subtitle timeline has 3 lines (2 additional text-only lines at 3s and 6s)
        timeline = [
            {
                "id": "sub_0001",
                "segmentId": "seg_0001",
                "startMs": 0,
                "endMs": 2000,
                "text": "Xin chào mọi người",
            },
            {
                "id": "sub_0002",
                "startMs": 3000,
                "endMs": 5000,
                "text": "Đoạn này không có tiếng nói gốc",
                "speakerId": "speaker_1",
            },
            {
                "id": "sub_0003",
                "startMs": 6000,
                "endMs": 8000,
                "text": "Đoạn này cũng là chữ trên màn hình",
            },
        ]

        result = apply_subtitle_timeline_to_segments(segments, timeline)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["finalText"], "Xin chào mọi người")
        self.assertEqual(result[1]["finalText"], "Đoạn này không có tiếng nói gốc")
        self.assertEqual(result[1]["startMs"], 3000)
        self.assertEqual(result[1]["isNonDialogue"], False)
        self.assertEqual(result[2]["finalText"], "Đoạn này cũng là chữ trên màn hình")
        self.assertEqual(result[2]["startMs"], 6000)
        self.assertEqual(result[2]["isNonDialogue"], False)
        # Check chronological ordering
        self.assertEqual([s["index"] for s in result], [1, 2, 3])

    def test_apply_subtitle_timeline_with_empty_audio_segments(self):
        # Video with 0 speech segments (pure music / silent video with 2 subtitle lines)
        segments = []
        timeline = [
            {
                "id": "sub_0001",
                "startMs": 1000,
                "endMs": 3000,
                "text": "Phim câm có phụ đề",
            },
            {
                "id": "sub_0002",
                "startMs": 4000,
                "endMs": 6000,
                "text": "Câu thứ hai của phim",
            },
        ]
        result = apply_subtitle_timeline_to_segments(segments, timeline)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["finalText"], "Phim câm có phụ đề")
        self.assertEqual(result[0]["speakerId"], "speaker_1")
        self.assertEqual(result[1]["finalText"], "Câu thứ hai của phim")

    def test_apply_subtitle_timeline_resets_is_non_dialogue(self):
        # A segment previously flagged as non-dialogue sfx
        segments = [
            {
                "id": "seg_0001",
                "startMs": 0,
                "endMs": 2000,
                "sourceText": "[music]",
                "translatedText": "",
                "isNonDialogue": True,
            }
        ]
        # User entered a subtitle for it
        timeline = [
            {
                "id": "sub_0001",
                "segmentId": "seg_0001",
                "startMs": 0,
                "endMs": 2000,
                "text": "Tiếng đàn piano du dương",
            }
        ]
        result = apply_subtitle_timeline_to_segments(segments, timeline)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["isNonDialogue"], False)
        self.assertEqual(result[0]["finalText"], "Tiếng đàn piano du dương")


if __name__ == "__main__":
    unittest.main()
