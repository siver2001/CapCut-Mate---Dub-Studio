from __future__ import annotations

from pathlib import Path
import importlib.util
import json
import sys

from gui.utils import resolve_intro_voice_preset


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "dub_studio_pipeline.py"
SPEC = importlib.util.spec_from_file_location("dub_studio_pipeline", MODULE_PATH)
dub_studio_pipeline = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = dub_studio_pipeline
SPEC.loader.exec_module(dub_studio_pipeline)


def test_parse_json_response_payload_handles_fenced_json():
    payload = dub_studio_pipeline.parse_json_response_payload(
        "```json\n[{\"translatedText\":\"Xin chao\",\"spokenText\":\"Xin chao!\",\"delivery\":\"excited\"}]\n```"
    )
    assert isinstance(payload, list)
    assert payload[0]["delivery"] == "excited"


def test_build_spoken_text_adds_natural_pause_and_punctuation():
    spoken = dub_studio_pipeline.build_spoken_text(
        "Đây là một tình huống rất nguy hiểm nhưng anh ấy vẫn tiếp tục bước tới",
        "This is a dangerous situation but he keeps moving forward!",
        "urgent",
    )
    assert "," in spoken
    assert spoken.endswith(("!", "."))


def test_build_tts_delivery_profile_varies_pitch_and_volume():
    profile = dub_studio_pipeline.build_tts_delivery_profile(
        text="Sao chuyện này lại xảy ra được",
        source_text="How could this happen?",
        voice="vi-VN-HoaiMyNeural",
        delivery="curious",
    )
    assert profile["pitch"].startswith("+")
    assert profile["spokenText"].endswith("?")


def test_resolve_segment_target_ms_respects_spoken_pressure():
    segments = [
        {
            "startMs": 0,
            "endMs": 1100,
            "sourceText": "Anh ta đến rồi",
            "translatedText": "Anh ta tới rồi",
            "spokenText": "Anh ta tới rồi!",
        },
        {
            "startMs": 1500,
            "endMs": 4200,
            "sourceText": "Không thể tin được là mọi chuyện lại tệ đến mức này",
            "translatedText": "Không ngờ mọi chuyện lại tệ đến mức này",
            "spokenText": "Không ngờ mọi chuyện lại tệ đến mức này...",
        },
    ]
    target_ms = dub_studio_pipeline.resolve_segment_target_ms(
        segments,
        1,
        video_duration_ms=5000,
        timing_mode="balanced_natural",
        text=segments[1]["spokenText"],
    )
    assert target_ms >= 2000


def test_build_spoken_text_softens_repeated_pronouns():
    spoken = dub_studio_pipeline.build_spoken_text(
        "T\u00f4i ch\u1ec9 c\u1ea3m th\u1ea5y m\u00ecnh \u0111\u00e3 th\u1ea5t b\u1ea1i. T\u00f4i \u0111ang r\u1ea5t m\u1ec7t, t\u00f4i, t\u00f4i",
        "A long reflective line with omitted subject.",
        "neutral",
    )
    assert "t\u00f4i, t\u00f4i" not in spoken.lower()
    assert "t\u00f4i" not in spoken.lower()
    assert "m\u00ecnh" in spoken.lower()


def test_prefer_minh_cau_pair_always_normalizes_first_person_to_minh():
    normalized = dub_studio_pipeline.prefer_minh_cau_pair(
        "Tao đã nói rồi, tôi không quay lại đâu.",
        "I told you, I'm not going back.",
    )
    lowered = normalized.lower()
    assert "tao" not in lowered
    assert "t\u00f4i" not in lowered
    assert lowered.count("m\u00ecnh") >= 2


def test_build_spoken_text_prefers_minh_cau_for_casual_dialogue():
    spoken = dub_studio_pipeline.build_spoken_text(
        "Tôi biết bạn đang lo lắng",
        "I know you're worried",
        "neutral",
    )
    lowered = spoken.lower()
    assert "mình" in lowered
    assert "cậu" in lowered
    assert "tôi" not in lowered
    assert "bạn" not in lowered


def test_build_tts_delivery_profile_keeps_pitch_more_even():
    profile = dub_studio_pipeline.build_tts_delivery_profile(
        text="Mình biết cậu đang sốc, nhưng cứ bình tĩnh đã.",
        source_text="I know you're shocked, but stay calm.",
        voice="vi-VN-HoaiMyNeural",
        delivery="excited",
    )
    pitch_value = int(profile["pitch"].replace("Hz", ""))
    volume_value = int(profile["volume"].replace("%", ""))
    assert pitch_value <= 14
    assert volume_value <= 6


def test_expand_subtitle_region_adds_cover_padding():
    expanded = dub_studio_pipeline.expand_subtitle_region(
        {"x": 400, "y": 900, "w": 320, "h": 54, "confidence": 0.26},
        video_meta={"width": 1440, "height": 1080},
    )
    assert expanded["x"] < 400
    assert expanded["y"] < 900
    assert expanded["w"] > 320
    assert expanded["h"] > 54


def test_smooth_rate_transition_limits_big_jumps():
    rate = dub_studio_pipeline.smooth_rate_transition(
        "+22%",
        "-6%",
        timing_mode="balanced_natural",
        target_ms=2400,
        delivery="neutral",
    )
    assert dub_studio_pipeline.parse_rate_percent(rate) <= 4


def test_resolve_voice_preset_preserves_custom_edge_voice():
    voice = "en-US-AvaNeural"
    assert dub_studio_pipeline.resolve_voice_preset(voice) == voice
    assert dub_studio_pipeline.resolve_edge_voice_name(voice) == voice


def test_sanitize_edge_tts_text_normalizes_hidden_characters():
    cleaned = dub_studio_pipeline.sanitize_edge_tts_text("\ufeffXin\u200b chào…")
    assert cleaned == "Xin chào..."


def test_sanitize_edge_tts_text_softens_period_boundaries_for_tts():
    cleaned = dub_studio_pipeline.sanitize_edge_tts_text(
        "Anh ấy quay lại. Mọi thứ bắt đầu thay đổi."
    )
    assert cleaned == "Anh ấy quay lại, mọi thứ bắt đầu thay đổi"


def test_resolve_intro_voice_preset_accepts_custom_edge_voice():
    preset = resolve_intro_voice_preset("en-US-AvaNeural")
    assert preset["key"] == "en-US-AvaNeural"
    assert preset["voice"] == "en-US-AvaNeural"
    assert preset["rateDeltaPercent"] == 0


def test_resolve_intro_voice_preset_normalizes_legacy_preset_key():
    preset = resolve_intro_voice_preset("female_story")
    assert preset["key"] == "edge:female"
    assert preset["voice"] == "edge:female"
    assert preset["rateDeltaPercent"] == 0


def test_resolve_intro_voice_preset_defaults_to_edge_male():
    preset = resolve_intro_voice_preset(None)
    assert preset["key"] == "male_story"
    assert preset["voice"] == "vi-VN-NamMinhNeural"
    assert preset["rateDeltaPercent"] == 0


def test_ensure_edge_tts_terminal_punctuation_adds_sentence_stop():
    cleaned = dub_studio_pipeline.ensure_edge_tts_terminal_punctuation("Xin chao nhe")
    assert cleaned == "Xin chao nhe."


def test_edge_tts_output_looks_hallucinated_flags_short_line_with_too_long_audio():
    assert dub_studio_pipeline.edge_tts_output_looks_hallucinated("Ve thoi.", 4200) is True
    assert dub_studio_pipeline.edge_tts_output_looks_hallucinated("Ve thoi.", 1100) is False


def test_ollama_resilient_split_and_cache_persist():
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    original_localize_batch_via_ollama = runtime_module.localize_batch_via_ollama
    original_localize_batch_via_llama_cpp = runtime_module.localize_batch_via_llama_cpp
    original_translate_via_google = runtime_module.translate_via_google
    original_should_use_ollama = runtime_module.should_use_ollama
    original_should_use_llama_cpp = runtime_module.should_use_llama_cpp
    original_emit_progress = runtime_module.emit_progress
    calls = {"ollama": 0}

    def fake_ollama(batch, source_hint, target):
        calls["ollama"] += 1
        if len(batch) > 1:
            raise RuntimeError("simulated ollama stall")
        return [{"translatedText": "ok", "spokenText": "ok.", "delivery": "neutral"}]

    try:
        runtime_module.localize_batch_via_ollama = fake_ollama
        runtime_module.localize_batch_via_llama_cpp = lambda batch, source_hint, target: [
            {"translatedText": "llama", "spokenText": "llama.", "delivery": "neutral"} for _ in batch
        ]
        runtime_module.translate_via_google = lambda text, source_hint, target: "google"
        runtime_module.should_use_ollama = lambda provider: True
        runtime_module.should_use_llama_cpp = lambda provider: False
        runtime_module.emit_progress = lambda **kwargs: None
        segments = [
            {"id": "a", "sourceText": "one", "translatedText": "", "spokenText": "", "delivery": "neutral"},
            {"id": "b", "sourceText": "two", "translatedText": "", "spokenText": "", "delivery": "neutral"},
            {"id": "c", "sourceText": "three", "translatedText": "", "spokenText": "", "delivery": "neutral"},
            {"id": "d", "sourceText": "four", "translatedText": "", "spokenText": "", "delivery": "neutral"},
        ]
        cache_path = Path(__file__).resolve().parents[1] / "scratch" / "translated_resume_test.json"
        if cache_path.exists():
            cache_path.unlink()
        dub_studio_pipeline.translate_segments(segments, "zh", cache_path)
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        assert sorted(payload["translations"].keys()) == ["a", "b", "c", "d"]
        assert calls["ollama"] >= 3
        cache_path.unlink(missing_ok=True)
    finally:
        runtime_module.localize_batch_via_ollama = original_localize_batch_via_ollama
        runtime_module.localize_batch_via_llama_cpp = original_localize_batch_via_llama_cpp
        runtime_module.translate_via_google = original_translate_via_google
        runtime_module.should_use_ollama = original_should_use_ollama
        runtime_module.should_use_llama_cpp = original_should_use_llama_cpp
        runtime_module.emit_progress = original_emit_progress


def test_ollama_resilient_single_item_retries_with_extended_timeout_before_fallback():
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    original_localize_batch_via_ollama = runtime_module.localize_batch_via_ollama
    original_emit_progress = runtime_module.emit_progress
    call_timeouts: list[int | None] = []
    progress_messages: list[str] = []

    def fake_localize(batch, source_hint, target_language="vi", *, timeout=None):
        call_timeouts.append(timeout)
        if timeout and timeout > runtime_module.OLLAMA_TIMEOUT:
            return [{"translatedText": "on dinh", "spokenText": "on dinh.", "delivery": "neutral"}]
        raise RuntimeError("simulated ollama timeout")

    try:
        runtime_module.localize_batch_via_ollama = fake_localize
        runtime_module.emit_progress = lambda **kwargs: progress_messages.append(kwargs.get("message", ""))
        result = runtime_module.localize_batch_via_ollama_resilient(
            [
                {
                    "id": "seg-1",
                    "sourceText": "hello there",
                    "translatedText": "",
                    "spokenText": "",
                    "delivery": "neutral",
                }
            ],
            source_hint="en",
            target_language="vi",
            llama_cpp_available=False,
            label="1-1",
            phase="analysis",
            progress_hint=0.342,
        )
        assert result[0]["translatedText"] == "on dinh"
        assert call_timeouts[0] is None
        assert len(call_timeouts) >= 2
        assert isinstance(call_timeouts[1], int)
        assert call_timeouts[1] > runtime_module.OLLAMA_TIMEOUT
        assert any("timeout=" in message for message in progress_messages)
    finally:
        runtime_module.localize_batch_via_ollama = original_localize_batch_via_ollama
        runtime_module.emit_progress = original_emit_progress


def test_ollama_resilient_retry_messages_keep_batch_progress_hint():
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    original_localize_batch_via_ollama = runtime_module.localize_batch_via_ollama
    original_emit_progress = runtime_module.emit_progress
    progress_values: list[float] = []

    def fake_localize(batch, source_hint, target_language="vi", *, timeout=None):
        if len(batch) > 1:
            raise RuntimeError("simulated ollama split")
        return [{"translatedText": "ok", "spokenText": "ok.", "delivery": "neutral"}]

    try:
        runtime_module.localize_batch_via_ollama = fake_localize
        runtime_module.emit_progress = lambda **kwargs: progress_values.append(float(kwargs.get("progress") or 0.0))
        result = runtime_module.localize_batch_via_ollama_resilient(
            [
                {"id": "a", "sourceText": "one", "translatedText": "", "spokenText": "", "delivery": "neutral"},
                {"id": "b", "sourceText": "two", "translatedText": "", "spokenText": "", "delivery": "neutral"},
            ],
            source_hint="en",
            target_language="vi",
            llama_cpp_available=False,
            label="18-19",
            phase="analysis",
            progress_hint=0.3656,
        )
        assert len(result) == 2
        assert progress_values
        assert all(value == 0.3656 for value in progress_values)
    finally:
        runtime_module.localize_batch_via_ollama = original_localize_batch_via_ollama
        runtime_module.emit_progress = original_emit_progress


def test_estimate_ollama_timeout_does_not_balloon_for_long_prompt():
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    prompt = "x" * 12000
    timeout_first_try = runtime_module.estimate_ollama_timeout(prompt, max_tokens=4096, attempt=0)
    timeout_retry = runtime_module.estimate_ollama_timeout(prompt, max_tokens=4096, attempt=2)

    assert timeout_first_try == runtime_module.OLLAMA_TIMEOUT
    assert timeout_retry == min(runtime_module.OLLAMA_TIMEOUT + 30, runtime_module.OLLAMA_MAX_TIMEOUT)


def test_translation_progress_message_uses_sentence_label_for_single_item():
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    message = runtime_module.translation_progress_message(
        provider_label="Ollama",
        start=18,
        end_index=19,
        total=50,
    )
    assert message == "Đang dịch Ollama câu 19/50"


def test_localize_batch_via_ollama_uses_global_neighbor_context_for_single_item():
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    original_run_ollama_prompt = runtime_module.run_ollama_prompt
    captured: dict[str, str] = {}

    def fake_run(prompt, *, max_tokens=2048, temperature=None, timeout=None):
        captured["prompt"] = prompt
        return '[{"translatedText":"Xin chào","spokenText":"Xin chào.","delivery":"neutral"}]'

    try:
        runtime_module.run_ollama_prompt = fake_run
        result = runtime_module.localize_batch_via_ollama(
            [
                {
                    "id": "seg-2",
                    "sourceText": "How are you?",
                    "previousText": "Hello there.",
                    "previousContext": "Hello there. We just got inside.",
                    "nextText": "Let's go.",
                    "nextContext": "Let's go. The train is leaving.",
                    "translatedText": "",
                    "spokenText": "",
                    "delivery": "neutral",
                }
            ],
            "en",
            "vi",
        )
        assert result[0]["translatedText"]
        assert "Hello there." in captured["prompt"]
        assert "Let's go." in captured["prompt"]
        assert "We just got inside." in captured["prompt"]
        assert "The train is leaving." in captured["prompt"]
    finally:
        runtime_module.run_ollama_prompt = original_run_ollama_prompt


def test_localize_batch_via_ollama_prompt_emphasizes_fidelity_and_low_temperature():
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    original_run_ollama_prompt = runtime_module.run_ollama_prompt
    captured: dict[str, object] = {}

    def fake_run(prompt, *, max_tokens=2048, temperature=None, timeout=None):
        captured["prompt"] = prompt
        captured["max_tokens"] = max_tokens
        captured["temperature"] = temperature
        return '[{"translatedText":"Giữ nguyên ý","spokenText":"Giữ nguyên ý.","delivery":"neutral"}]'

    try:
        runtime_module.run_ollama_prompt = fake_run
        runtime_module.localize_batch_via_ollama(
            [
                {
                    "id": "seg-3",
                    "sourceText": "Don't make anything up.",
                    "translatedText": "",
                    "spokenText": "",
                    "delivery": "neutral",
                }
            ],
            "en",
            "vi",
        )
        prompt = str(captured["prompt"])
        assert "semantic fidelity" in prompt
        assert "Preserve the original meaning exactly" in prompt
        assert "keep that ambiguity instead of guessing" in prompt
        assert "must NOT change the meaning or add new information" in prompt
        assert "instantly understandable after one hearing" in prompt
        assert "Each subtitle should still make sense on its own" in prompt
        assert "maxSubtitleChars" in prompt
        assert "maxSpokenChars" in prompt
        assert int(captured["max_tokens"]) <= 160
        assert float(captured["temperature"]) <= 0.18
    finally:
        runtime_module.run_ollama_prompt = original_run_ollama_prompt


def test_generate_intro_hook_prompt_requires_summary_not_line_stitching():
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    original_run_ollama_prompt = runtime_module.run_ollama_prompt
    captured: dict[str, object] = {}

    def fake_run(prompt, *, max_tokens=2048, temperature=None, timeout=None):
        captured["prompt"] = prompt
        return '{"hook":"Video này hé lộ một tình huống nguy hiểm."}'

    try:
        runtime_module.run_ollama_prompt = fake_run
        runtime_module.generate_intro_hook_via_ollama(
            [
                {
                    "sourceText": "Run now!",
                    "translatedText": "Chạy đi!",
                    "startMs": 0,
                    "endMs": 1200,
                }
            ],
            source_language="en",
            clip_duration_ms=4500,
        )
        prompt = str(captured["prompt"])
        assert "summarize the main content or central conflict" in prompt
        assert "not stitch together original dialogue lines" in prompt
        assert "Do NOT copy or lightly rearrange individual source sentences" in prompt
        assert "Sentence 2 must clearly say what the video will show" in prompt
    finally:
        runtime_module.run_ollama_prompt = original_run_ollama_prompt


def test_iter_ollama_translation_batches_keeps_complex_line_isolated():
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    indexed_segments = [
        (
            1,
            {
                "id": "a",
                "sourceText": "Short line.",
                "previousContext": "",
                "nextContext": "",
                "startMs": 0,
                "endMs": 1300,
            },
        ),
        (
            2,
            {
                "id": "b",
                "sourceText": (
                    "This is a much longer sentence with several clauses, extra qualifiers, "
                    "and a compressed timing window that makes localization harder."
                ),
                "previousContext": "Short lead-in before the difficult line.",
                "nextContext": "Follow-up context after the difficult line.",
                "startMs": 1400,
                "endMs": 2300,
            },
        ),
        (
            3,
            {
                "id": "c",
                "sourceText": "Another short line.",
                "previousContext": "",
                "nextContext": "",
                "startMs": 2400,
                "endMs": 3800,
            },
        ),
    ]

    batches = list(runtime_module.iter_ollama_translation_batches(indexed_segments))

    assert [len(batch) for _, batch, _ in batches] == [1, 1, 1]


def test_translate_segments_uses_adaptive_batches_for_ollama():
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    original_localize_batch_via_ollama_resilient = runtime_module.localize_batch_via_ollama_resilient
    original_should_use_ollama = runtime_module.should_use_ollama
    original_should_use_llama_cpp = runtime_module.should_use_llama_cpp
    original_warmup_ollama_model = runtime_module.warmup_ollama_model
    original_emit_progress = runtime_module.emit_progress
    seen_batch_sizes: list[int] = []
    seen_neighbors: list[tuple[str, str]] = []

    def fake_localize(batch, **kwargs):
        seen_batch_sizes.append(len(batch))
        seen_neighbors.extend(
            (item.get("previousText") or "", item.get("nextText") or "")
            for item in batch
        )
        return [
            {
                "translatedText": f"vi:{item['sourceText']}",
                "spokenText": f"vi:{item['sourceText']}.",
                "delivery": "neutral",
            }
            for item in batch
        ]

    try:
        runtime_module.localize_batch_via_ollama_resilient = fake_localize
        runtime_module.should_use_ollama = lambda provider: True
        runtime_module.should_use_llama_cpp = lambda provider: False
        runtime_module.warmup_ollama_model = lambda **kwargs: None
        runtime_module.emit_progress = lambda **kwargs: None
        cache_path = Path(__file__).resolve().parents[1] / "scratch" / "translated_single_sentence_test.json"
        cache_path.unlink(missing_ok=True)
        segments = [
            {"id": "a", "sourceText": "one", "translatedText": "", "spokenText": "", "delivery": "neutral"},
            {"id": "b", "sourceText": "two", "translatedText": "", "spokenText": "", "delivery": "neutral"},
            {"id": "c", "sourceText": "three", "translatedText": "", "spokenText": "", "delivery": "neutral"},
        ]
        runtime_module.translate_segments(segments, "en", cache_path)
        assert seen_batch_sizes == [1, 2]
        assert seen_neighbors == [("", "two"), ("one", "three"), ("two", "")]
        cache_path.unlink(missing_ok=True)
    finally:
        runtime_module.localize_batch_via_ollama_resilient = original_localize_batch_via_ollama_resilient
        runtime_module.should_use_ollama = original_should_use_ollama
        runtime_module.should_use_llama_cpp = original_should_use_llama_cpp
        runtime_module.warmup_ollama_model = original_warmup_ollama_model
        runtime_module.emit_progress = original_emit_progress


def test_translate_segments_populates_wider_neighbor_contexts():
    cache_path = Path(__file__).resolve().parents[1] / "scratch" / "translate_context_cache.json"
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    original_localize_batch_via_ollama_resilient = runtime_module.localize_batch_via_ollama_resilient
    original_should_use_ollama = runtime_module.should_use_ollama
    original_should_use_llama_cpp = runtime_module.should_use_llama_cpp
    original_warmup_ollama_model = runtime_module.warmup_ollama_model
    original_emit_progress = runtime_module.emit_progress
    captured_context: dict[str, tuple[str, str]] = {}

    def fake_localize(batch, **kwargs):
        for item in batch:
            captured_context[item["id"]] = (item["previousContext"], item["nextContext"])
        return [
            {"translatedText": "ok", "spokenText": "ok", "delivery": "neutral"}
            for _ in batch
        ]

    try:
        runtime_module.localize_batch_via_ollama_resilient = fake_localize
        runtime_module.should_use_ollama = lambda provider: True
        runtime_module.should_use_llama_cpp = lambda provider: False
        runtime_module.warmup_ollama_model = lambda **kwargs: None
        runtime_module.emit_progress = lambda **kwargs: None
        runtime_module.translate_segments(
            [
                {"id": "s1", "sourceText": "Line 1", "translatedText": "", "spokenText": "", "delivery": "neutral"},
                {"id": "s2", "sourceText": "Line 2", "translatedText": "", "spokenText": "", "delivery": "neutral"},
                {"id": "s3", "sourceText": "Line 3", "translatedText": "", "spokenText": "", "delivery": "neutral"},
                {"id": "s4", "sourceText": "Line 4", "translatedText": "", "spokenText": "", "delivery": "neutral"},
                {"id": "s5", "sourceText": "Line 5", "translatedText": "", "spokenText": "", "delivery": "neutral"},
            ],
            "en",
            cache_path,
            target_language="vi",
            phase="analysis",
        )
        assert captured_context["s3"] == ("Line 1 Line 2", "Line 4 Line 5")
    finally:
        cache_path.unlink(missing_ok=True)
        runtime_module.localize_batch_via_ollama_resilient = original_localize_batch_via_ollama_resilient
        runtime_module.should_use_ollama = original_should_use_ollama
        runtime_module.should_use_llama_cpp = original_should_use_llama_cpp
        runtime_module.warmup_ollama_model = original_warmup_ollama_model
        runtime_module.emit_progress = original_emit_progress


def test_translate_segments_seeds_cache_from_existing_translations():
    cache_path = Path(__file__).resolve().parents[1] / "scratch" / "translate_seed_cache.json"
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    original_should_use_ollama = runtime_module.should_use_ollama
    original_should_use_llama_cpp = runtime_module.should_use_llama_cpp

    try:
        runtime_module.should_use_ollama = lambda provider: False
        runtime_module.should_use_llama_cpp = lambda provider: False
        cache_path.unlink(missing_ok=True)
        segments = [
            {
                "id": "seg-1",
                "sourceText": "Hello there",
                "translatedText": "Xin chào nhé",
                "spokenText": "Xin chào nhé.",
                "delivery": "neutral",
            }
        ]
        runtime_module.translate_segments(segments, "en", cache_path)
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        assert payload["translations"]["seg-1"]["translatedText"] == "Xin chào nhé"
        assert payload["translations"]["seg-1"]["spokenText"] == "Xin chào nhé"
    finally:
        cache_path.unlink(missing_ok=True)
        runtime_module.should_use_ollama = original_should_use_ollama
        runtime_module.should_use_llama_cpp = original_should_use_llama_cpp


def test_run_llama_cpp_prompt_uses_default_timeout_when_not_provided():
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    original_discover_binary = runtime_module.discover_llama_cpp_binary
    original_discover_model = runtime_module.discover_llama_cpp_model
    original_run = runtime_module.run
    seen: dict[str, object] = {}
    dummy_path = Path(__file__).resolve()

    class CompletedProcess:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    try:
        runtime_module.discover_llama_cpp_binary = lambda: dummy_path
        runtime_module.discover_llama_cpp_model = lambda: dummy_path

        def fake_run(cmd, cwd=None, capture_output=False, timeout=None):
            seen["timeout"] = timeout
            return CompletedProcess('[{"translatedText":"ok","spokenText":"ok.","delivery":"neutral"}]')

        runtime_module.run = fake_run
        output = runtime_module.run_llama_cpp_prompt("hello", max_tokens=32)
        assert '"translatedText":"ok"' in output
        assert seen["timeout"] == runtime_module.LLAMA_CPP_TIMEOUT
    finally:
        runtime_module.discover_llama_cpp_binary = original_discover_binary
        runtime_module.discover_llama_cpp_model = original_discover_model
        runtime_module.run = original_run


def test_ffprobe_audio_duration_ms_rejects_missing_audio():
    missing = Path(__file__).resolve().parents[1] / "scratch" / "does_not_exist_audio.mp3"
    try:
        dub_studio_pipeline.ffprobe_audio_duration_ms(missing)
        assert False, "Expected ffprobe_audio_duration_ms to fail for missing audio"
    except RuntimeError as exc:
        assert "was not created" in str(exc)


def test_merge_whisperx_segments_keeps_speaker_boundaries():
    segments = [
        {"startMs": 0, "endMs": 900, "text": "Xin chao", "speaker": "SPEAKER_00"},
        {"startMs": 950, "endMs": 1700, "text": "ban nhe", "speaker": "SPEAKER_00"},
        {"startMs": 1750, "endMs": 2400, "text": "toi la A", "speaker": "SPEAKER_01"},
    ]
    merged = dub_studio_pipeline.merge_whisperx_segments(segments)
    assert len(merged) == 2
    assert merged[0]["speaker"] == "SPEAKER_00"
    assert merged[1]["speaker"] == "SPEAKER_01"


def test_remap_speaker_segments_promotes_primary_speaker():
    segments = [
        {"startMs": 0, "endMs": 1600, "text": "mot doan hoi dai", "speaker": "SPEAKER_09"},
        {"startMs": 1700, "endMs": 3200, "text": "them mot doan nua", "speaker": "SPEAKER_09"},
        {"startMs": 3300, "endMs": 3600, "text": "ngan", "speaker": "SPEAKER_02"},
    ]
    remapped, speaker_stats, main_speaker_id = dub_studio_pipeline.remap_speaker_segments(segments)
    assert remapped[0]["speakerId"] == "speaker_1"
    assert speaker_stats["speaker_1"]["segmentCount"] == 2
    assert main_speaker_id == "speaker_1"


def test_build_speakers_prefers_confident_sample_gender_for_voice_mapping():
    runtime_module = sys.modules[dub_studio_pipeline.build_speakers.__module__]
    original_estimate_gender = runtime_module.estimate_gender_from_sample_audio
    try:
        runtime_module.estimate_gender_from_sample_audio = lambda sample_path: {
            "gender": "female",
            "confidence": 0.81,
            "medianPitchHz": 212.4,
        }
        speakers = runtime_module.build_speakers(
            1,
            refinement={"speaker_1": {"displayName": "Nhân vật", "gender": "unknown"}},
            sample_paths={"speaker_1": Path("speaker_1_sample.wav")},
        )
        assert speakers[0]["estimatedGender"] == "female"
        assert speakers[0]["voicePreset"] == "edge:female"
        assert speakers[0]["samplePitchHz"] == 212.4
    finally:
        runtime_module.estimate_gender_from_sample_audio = original_estimate_gender


def test_collapse_segments_to_gender_buckets_limits_to_male_and_female():
    runtime_module = sys.modules[dub_studio_pipeline.collapse_segments_to_gender_buckets.__module__]
    original_estimate_gender_slice = runtime_module.estimate_gender_from_audio_slice
    responses = iter(
        [
            {"gender": "male", "confidence": 0.82, "medianPitchHz": 128.0},
            {"gender": "female", "confidence": 0.86, "medianPitchHz": 214.0},
            {"gender": "female", "confidence": 0.79, "medianPitchHz": 207.0},
        ]
    )

    try:
        runtime_module.estimate_gender_from_audio_slice = lambda audio, sr, start_ms, end_ms: next(responses)
        segments = [
            {"startMs": 0, "endMs": 1100, "text": "A", "speakerId": "speaker_3"},
            {"startMs": 1200, "endMs": 2400, "text": "B", "speakerId": "speaker_9"},
            {"startMs": 2500, "endMs": 3600, "text": "C", "speakerId": "speaker_2"},
        ]
        remapped, speaker_stats, main_speaker_id, speaker_count, speaker_confidence, voice_layout = (
            runtime_module.collapse_segments_to_gender_buckets(
                segments,
                audio=[0] * 160000,
                sr=16000,
            )
        )
        assert [item["speakerId"] for item in remapped] == ["speaker_1", "speaker_2", "speaker_2"]
        assert speaker_count == 2
        assert main_speaker_id == "speaker_2"
        assert speaker_confidence >= 0.62
        assert voice_layout == "multi_character"
        assert sorted(speaker_stats.keys()) == ["speaker_1", "speaker_2"]
    finally:
        runtime_module.estimate_gender_from_audio_slice = original_estimate_gender_slice


def test_build_default_render_options_defaults_to_preserve_background_audio():
    options = dub_studio_pipeline.build_default_render_options({"subtitleRegion": {}, "speakers": []})
    assert options["audioMixMode"] == "preserve_background"
    assert options["keepOriginalAudio"] is True
    assert options["subtitlePreset"]["cleanupBlurStrength"] == 14


def test_build_dynamic_subtitle_regions_returns_no_cleanup_regions_without_detected_source_subtitles(tmp_path: Path):
    runtime_module = sys.modules[dub_studio_pipeline.build_dynamic_subtitle_regions.__module__]
    video_meta = {"width": 1080, "height": 1920}
    fallback_region = dub_studio_pipeline.default_subtitle_region(video_meta)
    subtitles = dub_studio_pipeline.subtitles_from_analysis_segments(
        [
            {"id": "seg_0001", "startMs": 0, "endMs": 1200, "translatedText": "Xin chao"},
        ]
    )
    expected_position = {
        "centerX": fallback_region["x"] + fallback_region["w"] // 2,
        "centerY": fallback_region["y"] + fallback_region["h"] // 2,
    }

    original_extract_gray_frame = runtime_module.extract_gray_frame
    original_detect_subtitle_region_in_frame = runtime_module.detect_subtitle_region_in_frame
    try:
        runtime_module.extract_gray_frame = lambda *args, **kwargs: b"frame"
        runtime_module.detect_subtitle_region_in_frame = (
            lambda *args, **kwargs: {
                **fallback_region,
                "centerX": expected_position["centerX"],
                "centerY": expected_position["centerY"],
                "detected": False,
                "confidence": 0.0,
            }
        )

        dynamic_regions, subtitle_positions = dub_studio_pipeline.build_dynamic_subtitle_regions(
            video_path=tmp_path / "input.mp4",
            video_meta=video_meta,
            subtitles=subtitles,
            fallback_region=fallback_region,
        )
        assert dynamic_regions == []
        assert subtitle_positions == [expected_position]
    finally:
        runtime_module.extract_gray_frame = original_extract_gray_frame
        runtime_module.detect_subtitle_region_in_frame = original_detect_subtitle_region_in_frame


def test_normalize_audio_mix_mode_prefers_background_when_requested():
    assert (
        dub_studio_pipeline.normalize_audio_mix_mode(
            "preserve_background",
            keep_original_audio=True,
        )
        == "preserve_background"
    )
    assert dub_studio_pipeline.normalize_audio_mix_mode("", keep_original_audio=False) == "dub_only"


def test_prepare_background_audio_track_warns_and_falls_back_when_separation_fails():
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    original_separate_background_audio = runtime_module.separate_background_audio
    try:
        runtime_module.separate_background_audio = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("mock failure"))
        background_audio_path, warnings = runtime_module.prepare_background_audio_track(
            video_path=Path("input.mp4"),
            video_meta={"hasAudio": True},
            work_dir=Path("temp"),
            audio_mix_mode="preserve_background",
            keep_original_audio=True,
            phase="render",
            progress=0.6,
        )
        assert background_audio_path is None
        assert warnings and "fallback sang trộn audio gốc mức rất thấp" in warnings[0]
    finally:
        runtime_module.separate_background_audio = original_separate_background_audio


def test_create_final_audio_prefers_separated_background_track(tmp_path: Path):
    runtime_module = sys.modules[dub_studio_pipeline.translate_segments.__module__]
    original_run = runtime_module.run
    commands: list[list[str]] = []
    background = tmp_path / "no_vocals.wav"
    dub = tmp_path / "dub.wav"
    output = tmp_path / "mixed.wav"
    background.write_bytes(b"bg")
    dub.write_bytes(b"dub")

    try:
        runtime_module.run = lambda command, **kwargs: commands.append(command)
        runtime_module.create_final_audio(
            Path("video.mp4"),
            dub,
            output,
            audio_mix_mode="preserve_background",
            keep_original_audio=True,
            background_audio_path=background,
        )
        assert commands
        assert str(background) in commands[0]
        assert str(dub) in commands[0]
        assert "[0:a]volume=" in " ".join(commands[0])
    finally:
        runtime_module.run = original_run


def test_parse_srt_to_timeline_maps_back_to_segments():
    segments = [
        {
            "id": "seg_0001",
            "startMs": 0,
            "endMs": 1500,
            "speakerId": "speaker_1",
            "sourceText": "Hello there",
        },
        {
            "id": "seg_0002",
            "startMs": 1700,
            "endMs": 3200,
            "speakerId": "speaker_2",
            "sourceText": "General Kenobi",
        },
    ]
    timeline = dub_studio_pipeline.parse_srt_to_timeline(
        "1\n00:00:00,000 --> 00:00:01,500\nXin chào\n\n2\n00:00:01,700 --> 00:00:03,200\nTướng quân Kenobi\n",
        fallback_segments=segments,
    )
    assert [item["segmentId"] for item in timeline] == ["seg_0001", "seg_0002"]
    assert timeline[1]["speakerId"] == "speaker_2"


def test_apply_subtitle_timeline_to_segments_updates_translated_text():
    segments = [
        {
            "id": "seg_0001",
            "startMs": 0,
            "endMs": 1500,
            "speakerId": "speaker_1",
            "sourceText": "Hello there",
            "translatedText": "",
            "spokenText": "",
            "delivery": "neutral",
        }
    ]
    timeline = [
        {
            "id": "seg_0001",
            "segmentId": "seg_0001",
            "startMs": 0,
            "endMs": 1500,
            "text": "Xin chào nhé",
        }
    ]
    updated = dub_studio_pipeline.apply_subtitle_timeline_to_segments(segments, timeline)
    assert updated[0]["translatedText"] == "Xin chào nhé"
    assert "Xin chào nhé" in updated[0]["spokenText"]


def test_do_render_uses_current_subtitle_timeline_for_exported_srt(tmp_path: Path):
    runtime_module = sys.modules[dub_studio_pipeline.do_render.__module__]
    job_root = tmp_path / "job"
    dirs = {
        "root": job_root,
        "analysis": job_root / "analysis",
        "render": job_root / "render",
        "audio": job_root / "audio",
        "tts": job_root / "tts",
    }
    for path in dirs.values():
        if isinstance(path, Path):
            path.mkdir(parents=True, exist_ok=True)

    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"fake-video")
    analysis_path = tmp_path / "analysis.json"
    render_options_path = tmp_path / "render_options.json"
    output_json = tmp_path / "render_result.json"
    analysis_payload = {
        "jobId": "job-test",
        "inputPath": str(input_path),
        "videoMeta": {"width": 1080, "height": 1920, "durationMs": 3200},
        "sourceLanguage": "en",
        "targetLanguage": "vi",
        "subtitleRegion": {"x": 0, "y": 1600, "w": 1080, "h": 220, "cleanupMode": "localized_blur"},
        "segments": [
            {
                "id": "seg_0001",
                "startMs": 0,
                "endMs": 1500,
                "speakerId": "speaker_1",
                "sourceText": "Hello there",
                "translatedText": "Bản AI cũ",
                "spokenText": "Bản AI cũ.",
                "delivery": "neutral",
            }
        ],
        "subtitleTimeline": [
            {
                "id": "seg_0001",
                "segmentId": "seg_0001",
                "speakerId": "speaker_1",
                "startMs": 0,
                "endMs": 1500,
                "text": "Bản đã sửa cuối cùng",
                "sourceText": "Hello there",
            }
        ],
        "renderDefaults": {
            "subtitlePreset": {"enabled": True, "fontSize": 28, "fontFamilyName": "Arial", "fontColor": "#ffffff", "strokeColor": "#000000", "strokeWidth": 2, "positionPreset": "bottom", "bottomOffset": 54},
            "voiceMapping": {"speaker_1": "edge:male"},
            "introHook": {"enabled": False},
            "videoCodecMode": "gpu_preferred",
            "targetLanguage": "vi",
        },
        "warnings": [],
    }
    analysis_path.write_text(json.dumps(analysis_payload, ensure_ascii=False), encoding="utf-8")
    render_options_path.write_text(
        json.dumps({"outputTargets": {"mp4": False, "draft": False}}, ensure_ascii=False),
        encoding="utf-8",
    )

    original_prepare_runtime = runtime_module.prepare_runtime
    original_ensure_job_dirs = runtime_module.ensure_job_dirs
    original_choose_video_codec = runtime_module.choose_video_codec
    original_translate_segments = runtime_module.translate_segments
    original_build_dynamic_subtitle_regions = runtime_module.build_dynamic_subtitle_regions
    original_compose_ass = runtime_module.compose_ass
    original_create_dub_audio = runtime_module.create_dub_audio
    original_create_final_audio = runtime_module.create_final_audio
    original_emit_progress = runtime_module.emit_progress
    original_emit = runtime_module.emit
    try:
        runtime_module.prepare_runtime = lambda target: None
        runtime_module.ensure_job_dirs = lambda job_id: dirs
        runtime_module.choose_video_codec = lambda: ("libx264", "libx264")
        runtime_module.translate_segments = (
            lambda segments, source_language, cache_path, target_language="vi", phase="render": segments
        )
        runtime_module.build_dynamic_subtitle_regions = (
            lambda input_path, video_meta, subtitles, fallback_region: ([], [])
        )
        runtime_module.compose_ass = lambda subtitles, video_meta, subtitle_preset, subtitle_positions: "ASS"

        def fake_create_dub_audio(**kwargs):
            Path(kwargs["dub_audio_path"]).write_bytes(b"dub-audio")
            return []

        def fake_create_final_audio(input_path, dub_audio_path, mixed_audio_path, keep_original_audio=False):
            Path(mixed_audio_path).write_bytes(b"mixed-audio")

        runtime_module.create_dub_audio = fake_create_dub_audio
        runtime_module.create_final_audio = fake_create_final_audio
        runtime_module.emit_progress = lambda **kwargs: None
        runtime_module.emit = lambda *_args, **_kwargs: None

        result = dub_studio_pipeline.do_render(
            analysis_path=analysis_path,
            render_options_path=render_options_path,
            output_json=output_json,
        )
        subtitle_srt_path = Path(result["subtitleSrtPath"])
        assert subtitle_srt_path.exists()
        srt_text = subtitle_srt_path.read_text(encoding="utf-8-sig")
        assert "Bản đã sửa cuối cùng" in srt_text
        assert "Bản AI cũ" not in srt_text
    finally:
        runtime_module.prepare_runtime = original_prepare_runtime
        runtime_module.ensure_job_dirs = original_ensure_job_dirs
        runtime_module.choose_video_codec = original_choose_video_codec
        runtime_module.translate_segments = original_translate_segments
        runtime_module.build_dynamic_subtitle_regions = original_build_dynamic_subtitle_regions
        runtime_module.compose_ass = original_compose_ass
        runtime_module.create_dub_audio = original_create_dub_audio
        runtime_module.create_final_audio = original_create_final_audio
        runtime_module.emit_progress = original_emit_progress
        runtime_module.emit = original_emit


def test_do_render_keeps_preview_video_internal_until_user_exports(tmp_path: Path):
    runtime_module = sys.modules[dub_studio_pipeline.do_render.__module__]
    job_root = tmp_path / "job"
    dirs = {
        "root": job_root,
        "analysis": job_root / "analysis",
        "render": job_root / "render",
        "audio": job_root / "audio",
        "tts": job_root / "tts",
    }
    for path in dirs.values():
        if isinstance(path, Path):
            path.mkdir(parents=True, exist_ok=True)

    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"fake-video")
    analysis_path = tmp_path / "analysis.json"
    render_options_path = tmp_path / "render_options.json"
    output_json = tmp_path / "render_result.json"
    export_dir = tmp_path / "exports"
    analysis_payload = {
        "jobId": "job-preview",
        "inputPath": str(input_path),
        "videoMeta": {"width": 1080, "height": 1920, "durationMs": 3200},
        "sourceLanguage": "en",
        "targetLanguage": "vi",
        "subtitleRegion": {
            "x": 0,
            "y": 1600,
            "w": 1080,
            "h": 220,
            "cleanupMode": "localized_blur",
        },
        "segments": [
            {
                "id": "seg_0001",
                "startMs": 0,
                "endMs": 1500,
                "speakerId": "speaker_1",
                "sourceText": "Hello there",
                "translatedText": "Xin chào",
                "spokenText": "Xin chào.",
                "delivery": "neutral",
            }
        ],
        "renderDefaults": {
            "subtitlePreset": {"enabled": False},
            "voiceMapping": {"speaker_1": "edge:male"},
            "introHook": {"enabled": False},
            "videoCodecMode": "gpu_preferred",
            "targetLanguage": "vi",
        },
        "warnings": [],
    }
    analysis_path.write_text(
        json.dumps(analysis_payload, ensure_ascii=False), encoding="utf-8"
    )
    render_options_path.write_text(
        json.dumps(
            {
                "outputTargets": {"mp4": True, "draft": False},
                "outputDirectory": str(export_dir),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    original_prepare_runtime = runtime_module.prepare_runtime
    original_ensure_job_dirs = runtime_module.ensure_job_dirs
    original_choose_video_codec = runtime_module.choose_video_codec
    original_translate_segments = runtime_module.translate_segments
    original_create_dub_audio = runtime_module.create_dub_audio
    original_create_final_audio = runtime_module.create_final_audio
    original_mux_video_with_audio = runtime_module.mux_video_with_audio
    original_finalize_main_render_output = runtime_module.finalize_main_render_output
    original_emit_progress = runtime_module.emit_progress
    original_emit = runtime_module.emit
    try:
        runtime_module.prepare_runtime = lambda target: None
        runtime_module.ensure_job_dirs = lambda job_id: dirs
        runtime_module.choose_video_codec = lambda: ("libx264", "libx264")
        runtime_module.translate_segments = (
            lambda segments, source_language, cache_path, target_language="vi", phase="render": segments
        )

        def fake_create_dub_audio(**kwargs):
            Path(kwargs["dub_audio_path"]).write_bytes(b"dub-audio")
            return []

        def fake_create_final_audio(
            input_path, dub_audio_path, mixed_audio_path, keep_original_audio=False
        ):
            Path(mixed_audio_path).write_bytes(b"mixed-audio")

        def fake_mux_video_with_audio(*, video_path, audio_path, output_path):
            Path(output_path).write_bytes(b"render-main")

        def fake_finalize_main_render_output(main_render_path, final_output_path):
            final_output_path.write_bytes(Path(main_render_path).read_bytes())
            return final_output_path

        runtime_module.create_dub_audio = fake_create_dub_audio
        runtime_module.create_final_audio = fake_create_final_audio
        runtime_module.mux_video_with_audio = fake_mux_video_with_audio
        runtime_module.finalize_main_render_output = fake_finalize_main_render_output
        runtime_module.emit_progress = lambda **kwargs: None
        runtime_module.emit = lambda *_args, **_kwargs: None

        result = dub_studio_pipeline.do_render(
            analysis_path=analysis_path,
            render_options_path=render_options_path,
            output_json=output_json,
        )
        preview_video_path = Path(result["previewVideoPath"])
        output_video_path = Path(result["outputVideoPath"])
        assert preview_video_path.exists()
        assert output_video_path.exists()
        assert preview_video_path == output_video_path
        assert output_video_path.parent == dirs["render"]
        assert not export_dir.exists()
    finally:
        runtime_module.prepare_runtime = original_prepare_runtime
        runtime_module.ensure_job_dirs = original_ensure_job_dirs
        runtime_module.choose_video_codec = original_choose_video_codec
        runtime_module.translate_segments = original_translate_segments
        runtime_module.create_dub_audio = original_create_dub_audio
        runtime_module.create_final_audio = original_create_final_audio
        runtime_module.mux_video_with_audio = original_mux_video_with_audio
        runtime_module.finalize_main_render_output = (
            original_finalize_main_render_output
        )
        runtime_module.emit_progress = original_emit_progress
        runtime_module.emit = original_emit


def test_do_render_disables_cleanup_when_source_subtitles_are_not_detected(tmp_path: Path):
    runtime_module = sys.modules[dub_studio_pipeline.do_render.__module__]
    job_root = tmp_path / "job"
    dirs = {
        "root": job_root,
        "analysis": job_root / "analysis",
        "render": job_root / "render",
        "audio": job_root / "audio",
        "tts": job_root / "tts",
    }
    for path in dirs.values():
        if isinstance(path, Path):
            path.mkdir(parents=True, exist_ok=True)

    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"fake-video")
    analysis_path = tmp_path / "analysis.json"
    render_options_path = tmp_path / "render_options.json"
    output_json = tmp_path / "render_result.json"
    analysis_payload = {
        "jobId": "job-no-baked-sub",
        "inputPath": str(input_path),
        "videoMeta": {"width": 1080, "height": 1920, "durationMs": 3200},
        "sourceLanguage": "en",
        "targetLanguage": "vi",
        "subtitleRegion": {
            "x": 0,
            "y": 1600,
            "w": 1080,
            "h": 220,
            "cleanupMode": "localized_blur",
            "detected": False,
        },
        "segments": [
            {
                "id": "seg_0001",
                "startMs": 0,
                "endMs": 1500,
                "speakerId": "speaker_1",
                "sourceText": "Hello there",
                "translatedText": "Xin chao",
                "spokenText": "Xin chao.",
                "delivery": "neutral",
            }
        ],
        "renderDefaults": {
            "subtitlePreset": {
                "enabled": True,
                "fontSize": 28,
                "fontFamilyName": "Arial",
                "fontColor": "#ffffff",
                "strokeColor": "#000000",
                "strokeWidth": 2,
                "positionPreset": "bottom",
                "bottomOffset": 54,
            },
            "voiceMapping": {"speaker_1": "edge:male"},
            "introHook": {"enabled": False},
            "videoCodecMode": "gpu_preferred",
            "targetLanguage": "vi",
        },
        "warnings": [],
    }
    analysis_path.write_text(json.dumps(analysis_payload, ensure_ascii=False), encoding="utf-8")
    render_options_path.write_text(
        json.dumps({"outputTargets": {"mp4": True, "draft": False}}, ensure_ascii=False),
        encoding="utf-8",
    )

    captured: dict[str, str] = {}
    original_prepare_runtime = runtime_module.prepare_runtime
    original_ensure_job_dirs = runtime_module.ensure_job_dirs
    original_choose_video_codec = runtime_module.choose_video_codec
    original_translate_segments = runtime_module.translate_segments
    original_build_dynamic_subtitle_regions = runtime_module.build_dynamic_subtitle_regions
    original_compose_ass = runtime_module.compose_ass
    original_create_dub_audio = runtime_module.create_dub_audio
    original_create_final_audio = runtime_module.create_final_audio
    original_burn_subtitles = runtime_module.burn_subtitles
    original_finalize_main_render_output = runtime_module.finalize_main_render_output
    original_emit_progress = runtime_module.emit_progress
    original_emit = runtime_module.emit
    try:
        runtime_module.prepare_runtime = lambda target: None
        runtime_module.ensure_job_dirs = lambda job_id: dirs
        runtime_module.choose_video_codec = lambda: ("libx264", "libx264")
        runtime_module.translate_segments = (
            lambda segments, source_language, cache_path, target_language="vi", phase="render": segments
        )
        runtime_module.build_dynamic_subtitle_regions = (
            lambda input_path, video_meta, subtitles, fallback_region: (
                [],
                [{"centerX": 540, "centerY": 1710}],
            )
        )
        runtime_module.compose_ass = (
            lambda subtitles, video_meta, subtitle_preset, subtitle_positions: "ASS"
        )

        def fake_create_dub_audio(**kwargs):
            Path(kwargs["dub_audio_path"]).write_bytes(b"dub-audio")
            return []

        def fake_create_final_audio(
            input_path, dub_audio_path, mixed_audio_path, keep_original_audio=False
        ):
            Path(mixed_audio_path).write_bytes(b"mixed-audio")

        def fake_burn_subtitles(**kwargs):
            captured["cleanup_mode"] = kwargs["cleanup_mode"]
            Path(kwargs["output_path"]).write_bytes(b"render-main")

        def fake_finalize_main_render_output(main_render_path, final_output_path):
            final_output_path.write_bytes(Path(main_render_path).read_bytes())
            return final_output_path

        runtime_module.create_dub_audio = fake_create_dub_audio
        runtime_module.create_final_audio = fake_create_final_audio
        runtime_module.burn_subtitles = fake_burn_subtitles
        runtime_module.finalize_main_render_output = fake_finalize_main_render_output
        runtime_module.emit_progress = lambda **kwargs: None
        runtime_module.emit = lambda *_args, **_kwargs: None

        result = dub_studio_pipeline.do_render(
            analysis_path=analysis_path,
            render_options_path=render_options_path,
            output_json=output_json,
        )
        assert captured["cleanup_mode"] == "none"
        assert Path(result["outputVideoPath"]).exists()
    finally:
        runtime_module.prepare_runtime = original_prepare_runtime
        runtime_module.ensure_job_dirs = original_ensure_job_dirs
        runtime_module.choose_video_codec = original_choose_video_codec
        runtime_module.translate_segments = original_translate_segments
        runtime_module.build_dynamic_subtitle_regions = original_build_dynamic_subtitle_regions
        runtime_module.compose_ass = original_compose_ass
        runtime_module.create_dub_audio = original_create_dub_audio
        runtime_module.create_final_audio = original_create_final_audio
        runtime_module.burn_subtitles = original_burn_subtitles
        runtime_module.finalize_main_render_output = (
            original_finalize_main_render_output
        )
        runtime_module.emit_progress = original_emit_progress
        runtime_module.emit = original_emit


def test_build_structured_intro_hook_text_creates_short_multi_sentence_teaser():
    teaser = dub_studio_pipeline.build_structured_intro_hook_text(
        [
            {
                "translatedText": "Một cô gái vừa phát hiện bí mật động trời trong căn phòng khóa kín.",
                "startMs": 2000,
                "endMs": 5200,
            },
            {
                "translatedText": "Ngay sau đó, cả nhóm buộc phải chạy trốn trước khi quá muộn.",
                "startMs": 5300,
                "endMs": 8600,
            },
            {
                "translatedText": "Nhưng người đứng sau mọi chuyện lại là kẻ không ai ngờ tới.",
                "startMs": 8700,
                "endMs": 11800,
            },
        ]
    )
    assert teaser.count(".") >= 2
    lowered = teaser.lower()
    assert "mọi chuyện bắt đầu khi" in lowered
    assert "video này sẽ theo chân diễn biến khi" in lowered
    assert "và điều khiến mọi thứ bùng lên là" in lowered
