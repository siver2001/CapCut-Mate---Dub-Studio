import unittest

from tools.dub_studio.quality import (
    assert_translation_renderable,
    audit_timeline,
    audit_translation_segments,
)


class DubQualityTests(unittest.TestCase):
    def test_translation_audit_blocks_source_language_leak(self):
        segments = [{
            "id": "seg_1",
            "sourceText": "这是测试",
            "translatedText": "这是测试",
            "startMs": 0,
            "endMs": 1200,
        }]
        report = audit_translation_segments(segments, source_language="zh")
        self.assertEqual(report["criticalCount"], 1)
        with self.assertRaises(RuntimeError):
            assert_translation_renderable(report)


    def test_translation_audit_accepts_vietnamese(self):
        segments = [{
            "id": "seg_1",
            "sourceText": "这是测试",
            "translatedText": "Đây là một phép thử.",
            "startMs": 0,
            "endMs": 1800,
        }]
        report = audit_translation_segments(segments, source_language="zh")
        self.assertEqual(report["criticalCount"], 0)

    def test_translation_audit_allows_marked_non_dialogue(self):
        segments = [{
            "id": "seg_sfx",
            "sourceText": "[music]",
            "translatedText": "",
            "isNonDialogue": True,
            "startMs": 0,
            "endMs": 900,
        }]
        report = audit_translation_segments(segments, source_language="en")
        self.assertEqual(report["criticalCount"], 0)

    def test_valid_fallback_is_warning_not_blocked(self):
        segments = [{
            "id": "seg_fallback",
            "sourceText": "source",
            "translatedText": "bản dịch tạm",
            "translationProvider": "fallback",
            "startMs": 0,
            "endMs": 1200,
        }]
        report = audit_translation_segments(segments, source_language="en")
        self.assertEqual(report["status"], "warning")
        self.assertEqual(report["criticalCount"], 0)
        self.assertEqual(report["findingCounts"]["fallback_translation_used"], 1)

    def test_cloud_review_quota_failure_is_blocked_before_tts(self):
        segments = [{
            "id": "seg_unreviewed",
            "sourceText": "This is a long source sentence.",
            "translatedText": "Đây là một câu nguồn dài.",
            "translationProvider": "ai_unreviewed",
            "reviewStatus": "skipped_cloud_error",
            "startMs": 0,
            "endMs": 2500,
        }]
        report = audit_translation_segments(segments, source_language="en")
        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "cloud_review_incomplete",
            report["findingCounts"],
        )

    def test_english_output_left_in_english_is_blocked(self):
        segments = [{
            "id": "seg_en",
            "sourceText": "This is the place where we can see the old bridge.",
            "translatedText": "This is a place where we can see that old bridge.",
            "startMs": 0,
            "endMs": 3000,
        }]
        report = audit_translation_segments(segments, source_language="en")
        self.assertEqual(report["status"], "blocked")

    def test_missing_significant_number_is_blocked(self):
        segments = [{
            "id": "seg_number",
            "sourceText": "The bridge was built in 1987.",
            "translatedText": "Cây cầu được xây từ rất lâu.",
            "startMs": 0,
            "endMs": 2500,
        }]
        report = audit_translation_segments(segments, source_language="en")
        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "missing_source_number",
            {finding["code"] for finding in segments[0]["quality"]["findings"]},
        )

    def test_spelled_out_number_is_not_falsely_blocked(self):
        segments = [{
            "id": "seg_number_words",
            "sourceText": "The bridge was built in 1987.",
            "translatedText": "Cây cầu được xây vào năm một nghìn chín trăm tám mươi bảy.",
            "startMs": 0,
            "endMs": 3500,
        }]
        report = audit_translation_segments(segments, source_language="en")
        self.assertEqual(report["criticalCount"], 0)
        self.assertEqual(report["status"], "warning")


    def test_timeline_audit_detects_video_overflow(self):
        report = audit_timeline(
            [{"startMs": 0, "endMs": 12_000}],
            video_duration_ms=10_000,
        )
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["overflowMs"], 2_000)


if __name__ == "__main__":
    unittest.main()
