from tools.dub_studio.cli_parts.audio import build_tts_text_candidates
from tools.dub_studio.subtitle_utils import build_spoken_text, collapse_repeated_words


def test_collapse_repeated_words_preserves_emphatic_repetition_with_punctuation():
    text = "Ở đây không vui sao? Không, không. Mình, mình..."

    assert collapse_repeated_words(text) == text


def test_build_spoken_text_does_not_duplicate_curious_filler():
    spoken = build_spoken_text("Tại sao lại rời khỏi đây nhỉ?", "为什么要离开这里", delivery="curious")

    assert "nhỉ nhỉ" not in spoken.lower()


def test_build_tts_text_candidates_keep_original_pause_and_safe_question_rewrite():
    candidates = build_tts_text_candidates(
        "Tại sao lại rời khỏi đây nhỉ nhỉ?",
        "Tại sao lại rời khỏi đây?",
    )

    assert "Tại sao lại rời khỏi đây?" in candidates
    assert "Sao phải rời khỏi đây?" in candidates


def test_build_tts_text_candidates_preserve_pause_heavy_translation():
    translated = "Ở đây không vui sao? Không, không. Mình, mình..."
    candidates = build_tts_text_candidates(
        "Ở đây không vui sao? Không, không. mình nhỉ nhỉ?",
        translated,
    )

    assert translated in candidates
