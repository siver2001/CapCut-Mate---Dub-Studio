import unittest
import os
from unittest.mock import patch
from pathlib import Path

from tools.dub_studio.cli_parts.analysis import is_same_speaker_continuation
from tools.dub_studio.cli_parts.render import _split_segments_into_sentences
from tools.dub_studio.subtitle_utils import SubtitleLine
from tools.dub_studio.cli_parts.runtime import TRANSLATION_PROMPT_VERSION
from tools.dub_studio.cli_parts.translation import (
    _build_localization_items_payload,
    _build_localization_prompt,
    _cloud_action_extra,
    _prefilled_translation_is_authoritative,
    apply_machine_review_result,
    iter_ollama_translation_batches,
    translate_segments,
)


class TranslationPipelineTests(unittest.TestCase):
    def test_cloud_quota_maps_to_gui_action(self):
        class QuotaError(RuntimeError):
            code = "gemini_quota_exhausted"

        extra = _cloud_action_extra(QuotaError("quota"))
        self.assertTrue(extra["actionRequired"])
        self.assertEqual(extra["recommendedAction"], "update_cloud_api_key")

    def test_long_silence_is_not_assumed_same_speaker(self):
        previous = SubtitleLine(1, 0, 500, "First line")
        current = SubtitleLine(2, 2500, 3000, "Second line")
        self.assertFalse(is_same_speaker_continuation(previous, current))

    def test_reviewed_spoken_adaptation_is_preferred(self):
        item = {"sourceText": "测试", "id": "seg_1"}
        result = apply_machine_review_result(
            item,
            machine_translated_text="Đây là bản dịch thô dài dòng.",
            reviewed={"translatedText": "Bản nói tự nhiên.", "delivery": "neutral"},
        )
        self.assertEqual(result["finalText"], "Bản nói tự nhiên.")
        self.assertEqual(result["faithfulTranslation"], "Đây là bản dịch thô dài dòng.")

    def test_legacy_prefilled_translation_is_not_authoritative(self):
        self.assertFalse(_prefilled_translation_is_authoritative({"translatedText": "Bản cũ"}))
        self.assertTrue(_prefilled_translation_is_authoritative({"translationEditedByUser": True}))

    def test_prompt_is_faithful_and_id_addressed(self):
        batch = [{
            "id": "src_42",
            "sourceText": "测试文本",
            "startMs": 0,
            "endMs": 1800,
            "speakerId": "speaker_1",
        }]
        payload = _build_localization_items_payload(batch)
        prompt = _build_localization_prompt(
            payload,
            source_language="zh",
            target_language="vi",
            localization_mode="creative",
            global_context={"theme": "documentary"},
        )
        self.assertEqual(payload[0]["sourceId"], "src_42")
        self.assertIn("Never invent", prompt)
        self.assertIn("Natural silence is allowed", prompt)
        self.assertNotIn("pet vlog topic", prompt)

    def test_dynamic_batches_keep_multiple_short_segments_together(self):
        indexed = []
        for position in range(1, 9):
            indexed.append((position, {
                "id": f"seg_{position}",
                "sourceText": f"short segment {position}",
                "startMs": position * 1000,
                "endMs": position * 1000 + 800,
                "previousContext": "",
                "nextContext": "",
            }))
        batches = list(iter_ollama_translation_batches(indexed))
        self.assertGreaterEqual(len(batches[0][1]), 2)

    def test_cloud_batching_does_not_degrade_to_one_request_per_segment(self):
        indexed = [
            (position, {
                "id": f"seg_{position}",
                "sourceText": "测" * 50,
                "startMs": position * 1000,
                "endMs": position * 1000 + 900,
                "previousContext": "测" * 80,
                "nextContext": "测" * 80,
            })
            for position in range(1, 13)
        ]
        with patch.dict(os.environ, {"DUB_AI_MODE": "cloud"}, clear=False):
            batches = list(iter_ollama_translation_batches(indexed))
        self.assertLessEqual(len(batches), 3)

    def test_canonical_segmentation_does_not_merge_complete_sentence(self):
        result = _split_segments_into_sentences([
            {"startMs": 0, "endMs": 1000, "text": "Câu thứ nhất.", "speakerId": "speaker_1"},
            {"startMs": 1100, "endMs": 2100, "text": "Câu thứ hai.", "speakerId": "speaker_1"},
        ])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["sourceSegmentId"], result[0]["id"])

    def test_repeated_dialogue_at_different_times_is_not_deduplicated(self):
        result = _split_segments_into_sentences([
            {"startMs": 0, "endMs": 500, "text": "No!", "speakerId": "speaker_1"},
            {"startMs": 700, "endMs": 1200, "text": "No!", "speakerId": "speaker_1"},
        ])
        self.assertEqual(len(result), 2)

    def test_overlapping_duplicate_asr_result_is_deduplicated(self):
        result = _split_segments_into_sentences([
            {"startMs": 0, "endMs": 900, "text": "Duplicate", "speakerId": "speaker_1"},
            {"startMs": 20, "endMs": 920, "text": "Duplicate", "speakerId": "speaker_1"},
        ])
        self.assertEqual(len(result), 1)

    def test_unpunctuated_cjk_is_bounded_without_duplication(self):
        source = "测" * 145
        result = _split_segments_into_sentences([
            {"startMs": 0, "endMs": 9000, "text": source, "speakerId": "speaker_1"},
        ])
        self.assertEqual("".join(item["sourceText"] for item in result), source)
        self.assertTrue(all(len(item["sourceText"]) <= 60 for item in result))

    def test_current_prefilled_translation_passes_without_network(self):
        segments = [{
            "id": "seg_0001",
            "sourceText": "这是测试",
            "translatedText": "Đây là phép thử.",
            "translationPromptVersion": TRANSLATION_PROMPT_VERSION,
            "startMs": 0,
            "endMs": 1800,
            "speakerId": "speaker_1",
        }]
        cache_path = Path("temp/test_translation_pipeline_cache.json")
        cache_path.unlink(missing_ok=True)
        try:
            result = translate_segments(
                segments,
                "zh",
                cache_path,
            )
        finally:
            cache_path.unlink(missing_ok=True)
            cache_path.with_name("test_translation_pipeline_cache.microsoft.json").unlink(missing_ok=True)
        self.assertEqual(result[0]["finalText"], "Đây là phép thử.")
        self.assertEqual(result[0]["quality"]["status"], "pass")

    def test_bad_current_cache_is_requeued_and_repaired(self):
        segments = [{
            "id": "seg_0001",
            "sourceText": "This is the place where we can see the old bridge.",
            "translatedText": "This is a place where we can see that old bridge.",
            "translationPromptVersion": TRANSLATION_PROMPT_VERSION,
            "startMs": 0,
            "endMs": 3000,
            "speakerId": "speaker_1",
        }]
        cache_path = Path("temp/test_translation_repair_cache.json")
        cache_path.unlink(missing_ok=True)
        try:
            with (
                patch.dict(
                    os.environ,
                    {"DUB_TRANSLATE_PROVIDER": "google", "DUB_AI_MODE": "local"},
                    clear=False,
                ),
                patch(
                    "tools.dub_studio.cli_parts.translation.translate_via_google_free",
                    return_value="Đây là nơi chúng ta có thể nhìn thấy cây cầu cổ.",
                ),
            ):
                result = translate_segments(segments, "en", cache_path)
        finally:
            cache_path.unlink(missing_ok=True)
            cache_path.with_name(
                "test_translation_repair_cache.microsoft.json"
            ).unlink(missing_ok=True)

        self.assertEqual(result[0]["quality"]["status"], "pass")
        self.assertIn("cây cầu", result[0]["finalText"])


if __name__ == "__main__":
    unittest.main()
