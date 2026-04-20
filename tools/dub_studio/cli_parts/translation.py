from __future__ import annotations

from .common import *
from .runtime import (
    TRANSLATION_PROMPT_VERSION,
    apply_localized_result,
    estimate_ollama_timeout,
    iter_translation_batches,
    joined_source_context,
    load_translation_cache,
    parse_json_response_payload,
    persist_translation_cache,
    run_llama_cpp_prompt,
    run_ollama_prompt,
    should_use_llama_cpp,
    should_use_ollama,
    translation_batch_progress,
    translation_progress_message,
    warmup_ollama_model,
)

def translate_via_google(text: str, source_lang: str = "auto", target_lang: str = "vi") -> str:
    query = urllib.parse.urlencode({"client": "gtx", "sl": source_lang, "tl": target_lang, "dt": "t", "q": text})
    url = f"https://translate.googleapis.com/translate_a/single?{query}"
    
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            parts = [part[0] for part in payload[0] if part and part[0]]
            return normalize_text("".join(parts))
        except Exception:
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            return normalize_text(text)
    return normalize_text(text)


_NON_DIALOGUE_PATTERN = re.compile(
    r"^\s*"
    r"[\[\(\uFF08\u3010]"
    r"\s*"
    r"(.{0,30})"
    r"\s*"
    r"[\]\)\uFF09\u3011]"
    r"\s*$"
)

_SFX_KEYWORDS_ZH = {
    "笑", "哭", "叹气", "鼓掌", "拍手", "音乐", "音效", "掌声",
    "欢呼", "尖叫", "咳嗽", "叹", "呻吟", "喘气", "沉默",
    "嘘", "吹口哨", "打嗝", "敲门", "铃声", "脚步声",
    "爆炸", "枪声", "雷声", "风声", "雨声", "水声",
}
_SFX_KEYWORDS_EN = {
    "laugh", "laughing", "laughter", "cry", "crying", "sigh", "sighing",
    "applause", "clap", "clapping", "music", "sfx", "sound",
    "cheer", "cheering", "scream", "screaming", "cough", "coughing",
    "groan", "gasp", "silence", "shush", "whistle",
    "knock", "ring", "footstep", "explosion", "gunshot",
    "thunder", "wind", "rain", "water", "breathing", "snoring",
    "inaudible", "unintelligible", "noise",
}
_SFX_KEYWORDS_JA = {
    "笑い", "拍手", "音楽", "効果音", "歓声", "叫び", "咳",
    "ため息", "沈黙", "足音", "雷", "風", "雨",
}
_SFX_KEYWORDS_KO = {
    "웃음", "박수", "음악", "효과음", "환호", "비명", "기침",
    "한숨", "침묵", "발소리", "천둥", "바람", "비",
}
_ALL_SFX_KEYWORDS = _SFX_KEYWORDS_ZH | _SFX_KEYWORDS_EN | _SFX_KEYWORDS_JA | _SFX_KEYWORDS_KO


def _is_non_dialogue_sfx(text: str) -> bool:
    """Return True if *text* is a non-dialogue sound-effect annotation.

    Matches patterns like (笑), [音乐], （拍手）, 【效果音】, (laughing), etc.
    These should NOT be translated – they are not spoken dialogue.
    """
    clean = normalize_text(text)
    if not clean:
        return False
    match = _NON_DIALOGUE_PATTERN.match(clean)
    if not match:
        return False
    inner = match.group(1).strip().lower()
    if not inner:
        return True  # empty brackets like () or []
    # Check against known SFX keywords
    if inner in _ALL_SFX_KEYWORDS:
        return True
    # Partial match for compound descriptions like "观众笑" or "background music"
    for keyword in _ALL_SFX_KEYWORDS:
        if keyword in inner:
            return True
    return False


# CJK character ranges for detecting non-Vietnamese text
_CJK_PATTERN = re.compile(
    r"[\u4e00-\u9fff"           # CJK Unified Ideographs (Chinese/Japanese Kanji)
    r"\u3400-\u4dbf"            # CJK Extension A
    r"\u3040-\u309f"            # Hiragana
    r"\u30a0-\u30ff"            # Katakana
    r"\uac00-\ud7af"            # Korean Hangul Syllables
    r"\u1100-\u11ff"            # Korean Hangul Jamo
    r"]"
)


def _looks_like_source_language(text: str, source_text: str = "") -> bool:
    """Return True if *text* appears to still be in a CJK source language.

    This catches cases where the LLM echoes back the source text instead
    of actually translating it into Vietnamese.
    """
    clean = normalize_text(text)
    if not clean:
        return True  # empty is considered untranslated
    # Count CJK characters
    cjk_chars = len(_CJK_PATTERN.findall(clean))
    total_chars = max(len(clean.replace(" ", "")), 1)
    # If more than 40% of the text is CJK characters, it's likely source language
    if cjk_chars / total_chars > 0.4:
        return True
    # If the translated text is identical to the source text, it wasn't translated
    if source_text and normalize_text(source_text) == clean:
        cjk_in_source = len(_CJK_PATTERN.findall(normalize_text(source_text)))
        if cjk_in_source > 0:
            return True
    return False



def _trim_translation_context(text: str, max_chars: int) -> str:
    clean = normalize_text(text)
    if len(clean) <= max_chars:
        return clean
    shortened = clean[: max_chars - 1].rsplit(" ", 1)[0].strip()
    return (shortened or clean[: max_chars - 1].strip()).rstrip(" ,;:")


def _estimate_translation_char_limit(
    source_text: str,
    duration_ms: int,
    *,
    spoken: bool,
) -> int:
    clean = normalize_text(source_text)
    source_len = max(len(clean), 1)
    duration_seconds = max(duration_ms, 400) / 1000.0
    timing_cap = 28 + int(duration_seconds * (16 if spoken else 12))
    source_cap = int(source_len * (1.34 if spoken else 1.14)) + (8 if spoken else 4)
    floor = 26 if spoken else 18
    ceiling = 104 if spoken else 78
    return max(floor, min(max(timing_cap, source_cap), ceiling))


def _compact_translation_item(
    item: dict[str, Any],
    *,
    index: int,
    batch: list[dict[str, Any]],
) -> dict[str, Any]:
    source_text = normalize_text(item.get("sourceText") or "")
    duration_ms = max(int(item.get("endMs", 0)) - int(item.get("startMs", 0)), 400)
    previous_text = normalize_text(
        item.get("previousText")
        or (batch[index - 1].get("sourceText") if index > 0 else "")
        or ""
    )
    next_text = normalize_text(
        item.get("nextText")
        or (batch[index + 1].get("sourceText") if index + 1 < len(batch) else "")
        or ""
    )
    previous_context = normalize_text(item.get("previousContext") or item.get("previousText") or "")
    next_context = normalize_text(item.get("nextContext") or item.get("nextText") or "")

    compact_item: dict[str, Any] = {
        "index": index,
        "sourceText": source_text,
        "durationMs": duration_ms,
        "speakerId": item.get("speakerId") or "speaker_1",
        "maxSubtitleChars": _estimate_translation_char_limit(source_text, duration_ms, spoken=False),
        "maxSpokenChars": _estimate_translation_char_limit(source_text, duration_ms, spoken=True),
    }

    if previous_text:
        compact_item["previousText"] = _trim_translation_context(previous_text, 72)
    if next_text:
        compact_item["nextText"] = _trim_translation_context(next_text, 72)

    trimmed_previous_context = _trim_translation_context(previous_context, 112)
    trimmed_next_context = _trim_translation_context(next_context, 112)
    if trimmed_previous_context and trimmed_previous_context != compact_item.get("previousText", ""):
        compact_item["previousContext"] = trimmed_previous_context
    if trimmed_next_context and trimmed_next_context != compact_item.get("nextText", ""):
        compact_item["nextContext"] = trimmed_next_context
    return compact_item


def _build_localization_items_payload(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _compact_translation_item(item, index=index, batch=batch)
        for index, item in enumerate(batch)
    ]


def _estimate_localize_max_tokens(items_payload: list[dict[str, Any]]) -> int:
    if not items_payload:
        return 96
    total_chars = 0
    for item in items_payload:
        total_chars += int(item.get("maxSubtitleChars", 24))
        total_chars += int(item.get("maxSpokenChars", 36))
        total_chars += 30
    estimated = math.ceil(total_chars / 3.4) + len(items_payload) * 10
    lower_bound = 96 if len(items_payload) == 1 else 160
    upper_bound = max(lower_bound, len(items_payload) * 96 + 64)
    return max(lower_bound, min(estimated, upper_bound))


def _build_localization_prompt(
    items_payload: list[dict[str, Any]],
    *,
    source_language: str,
    target_language: str,
) -> str:
    return (
        "You are a professional Vietnamese subtitle translator.\n"
        f"Source language: {source_language or 'auto-detected language'}. Target language: Vietnamese ({target_language}).\n"
        "\n"
        "CRITICAL RULES (violation = failure):\n"
        f"1. Return ONLY a valid JSON array with EXACTLY {len(items_payload)} items, same order as input.\n"
        "2. EVERY translatedText and spokenText MUST be in Vietnamese. NEVER echo back the source language.\n"
        "3. If the sourceText is a single word, interjection, or very short phrase, still translate it into Vietnamese.\n"
        "4. Do NOT leave any field in the source language (Chinese, Japanese, Korean, English, etc.).\n"
        "\n"
        "Each item must be a JSON object with exactly these keys:\n"
        '- "translatedText": the Vietnamese subtitle text — concise, natural, instantly understandable.\n'
        '- "spokenText": natural Vietnamese phrasing optimized for voice acting / TTS. May be slightly smoother than translatedText but must preserve the same meaning.\n'
        '- "delivery": exactly one of: calm, neutral, curious, excited, urgent, suspense.\n'
        "\n"
        "Translation quality rules:\n"
        "- Semantic fidelity first, but adapt the sentence structure to flow naturally in spoken Vietnamese.\n"
        "- Do NOT translate literally word-for-word. Rephrase idioms, slang, and jokes into natural Vietnamese equivalents.\n"
        "- Make the spokenText sound exactly like a native Vietnamese speaker talking casually in a vlog or video.\n"
        "- If the source is a fragmented sentence, smooth it out so it makes sense to the listener.\n"
        "- Translate only sourceText. Use previousText/nextText/previousContext/nextContext to understand the ongoing conversation.\n"
        "- Keep translatedText within maxSubtitleChars and spokenText within maxSpokenChars when possible.\n"
        "- Use appropriate Vietnamese pronouns (mình/cậu, anh/em, mọi người) based on the context and tone of the video.\n"
        "- Do NOT add notes, markdown fences, or any text outside the JSON array.\n"
        "\n"
        f"{json.dumps(items_payload, ensure_ascii=False)}"
    )


def _translation_entry_complexity(item: dict[str, Any]) -> float:
    source_text = normalize_text(item.get("sourceText") or "")
    previous_context = normalize_text(item.get("previousContext") or "")
    next_context = normalize_text(item.get("nextContext") or "")
    duration_ms = max(int(item.get("endMs", 0)) - int(item.get("startMs", 0)), 400)
    punctuation_weight = len(re.findall(r"[,:;.!?…]", source_text)) * 3
    short_timing_penalty = 34 if duration_ms < 1200 and len(source_text) > 34 else 0
    return (
        len(source_text)
        + 0.35 * (len(previous_context) + len(next_context))
        + max(len(source_text.split()) - 10, 0) * 4
        + punctuation_weight
        + short_timing_penalty
    )


def _translation_item_should_stand_alone(item: dict[str, Any]) -> bool:
    source_text = normalize_text(item.get("sourceText") or "")
    combined_context = normalize_text(
        " ".join(
            part
            for part in (
                item.get("previousContext") or "",
                item.get("nextContext") or "",
            )
            if part
        )
    )
    return (
        len(source_text) >= 84
        or len(combined_context) >= 220
        or _translation_entry_complexity(item) >= 170
    )


def localize_batch_via_ollama(
    batch: list[dict[str, Any]],
    source_language: str,
    target_language: str = "vi",
    *,
    timeout: int | None = None,
) -> list[dict[str, str]]:
    """Translate a batch of segments using Ollama API."""
    items_payload = _build_localization_items_payload(batch)
    prompt = _build_localization_prompt(
        items_payload,
        source_language=source_language,
        target_language=target_language,
    )
    localized = parse_json_response_payload(
        run_ollama_prompt(
            prompt,
            max_tokens=_estimate_localize_max_tokens(items_payload),
            temperature=max(0.05, min(OLLAMA_TEMP, 0.12)),
            timeout=timeout,
        )
    )
    if isinstance(localized, dict):
        if len(batch) == 1 and "translatedText" in localized:
            localized = [localized]
        else:
            for value in localized.values():
                if isinstance(value, list) and len(value) == len(batch):
                    localized = value
                    break

    if not isinstance(localized, list) or len(localized) != len(batch):
        raise RuntimeError(
            f"Ollama tráº£ vá» káº¿t quáº£ khÃ´ng khá»›p sá»‘ lÆ°á»£ng (nháº­n {len(localized) if isinstance(localized, list) else 0}, cáº§n {len(batch)})."
        )

    normalized_items: list[dict[str, str]] = []
    for item, source in zip(localized, batch):
        if not isinstance(item, dict):
            raise RuntimeError("Ollama localization item must be a JSON object.")
        raw_translated = normalize_text(item.get("translatedText") or "")
        source_text = source.get("sourceText") or ""
        # If the model echoed back the source language, fall back to Google Translate
        if not raw_translated or _looks_like_source_language(raw_translated, source_text):
            try:
                raw_translated = translate_via_google(source_text, "auto", "vi")
            except Exception:
                raw_translated = source_text
        translated_text = prefer_minh_cau_pair(
            normalize_text(raw_translated),
            source_text,
        )
        delivery = normalize_text(item.get("delivery") or "neutral").lower()
        if delivery not in {"calm", "neutral", "curious", "excited", "urgent", "suspense"}:
            delivery = "neutral"
        raw_spoken = normalize_text(item.get("spokenText") or "")
        if not raw_spoken or _looks_like_source_language(raw_spoken, source_text):
            raw_spoken = translated_text
        spoken_text = build_spoken_text(
            raw_spoken,
            source_text,
            delivery=delivery,
        )
        normalized_items.append(
            {
                "translatedText": translated_text,
                "spokenText": spoken_text or translated_text,
                "delivery": delivery,
            }
        )
    return normalized_items


def generate_intro_hook_via_ollama(
    window_segments: list[dict[str, Any]],
    *,
    source_language: str,
    clip_duration_ms: int,
) -> str:
    """Generate a Vietnamese intro teaser hook using Ollama API."""
    prompt = (
        "You are writing a Vietnamese spoken teaser for a short-form dubbed video.\n"
        "Use the segment context below to create a short teaser in 2 or 3 short Vietnamese sentences that sounds exciting and natural when read aloud.\n"
        "This teaser must summarize the main content or central conflict of the video segment, not stitch together original dialogue lines.\n"
        "Do NOT copy or lightly rearrange individual source sentences. Compress them into a higher-level summary.\n"
        "Sentence 1 should hook the viewer immediately.\n"
        "Sentence 2 must clearly say what the video will show, follow, or reveal so the viewer understands the premise.\n"
        "Sentence 3, if used, should sharpen the tension, stakes, or twist without turning into a full recap.\n"
        "It should feel genuinely intriguing while still making the video's main idea easy to understand.\n"
        f"It should fit roughly {max(18, round(clip_duration_ms / 450))}-{max(35, round(clip_duration_ms / 300))} spoken Vietnamese words total.\n"
        "No hashtags. No emojis. No clickbait nonsense.\n"
        'Return ONLY a valid JSON object: {"hook":"..."}.\n\n'
        + json.dumps(
            [
                {
                    "sourceText": normalize_text(item.get("sourceText") or ""),
                    "translatedText": normalize_text(item.get("translatedText") or ""),
                    "startMs": item.get("startMs"),
                    "endMs": item.get("endMs"),
                }
                for item in window_segments[:15]
            ],
            ensure_ascii=False,
        )
        + f"\n\nSource language: {source_language or 'auto'}."
    )
    payload = parse_json_response_payload(
        run_ollama_prompt(
            prompt,
            max_tokens=160,
            temperature=max(0.45, OLLAMA_TEMP),
            timeout=35,
        )
    )
    if isinstance(payload, dict):
        hook = normalize_text(payload.get("hook") or "")
    elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
        hook = normalize_text(payload[0].get("hook") or "")
    else:
        hook = ""
    return build_spoken_text(hook, delivery="excited")


def localize_batch_via_llama_cpp(
    batch: list[dict[str, Any]],
    source_language: str,
    target_language: str = "vi",
) -> list[dict[str, str]]:
    items_payload = _build_localization_items_payload(batch)
    prompt = _build_localization_prompt(
        items_payload,
        source_language=source_language,
        target_language=target_language,
    )
    localized = parse_json_response_payload(
        run_llama_cpp_prompt(
            prompt,
            max_tokens=max(160, _estimate_localize_max_tokens(items_payload)),
            temperature=max(0.08, min(LLAMA_CPP_TEMP, 0.16)),
        )
    )
    if not isinstance(localized, list) or len(localized) != len(batch):
        raise RuntimeError("llama.cpp localization response did not return the expected JSON array.")

    normalized_items: list[dict[str, str]] = []
    for item, source in zip(localized, batch):
        if not isinstance(item, dict):
            raise RuntimeError("llama.cpp localization item must be a JSON object.")
        translated_text = prefer_minh_cau_pair(
            normalize_text(item.get("translatedText") or source.get("sourceText") or ""),
            source.get("sourceText") or "",
        )
        delivery = normalize_text(item.get("delivery") or "neutral").lower()
        if delivery not in {"calm", "neutral", "curious", "excited", "urgent", "suspense"}:
            delivery = "neutral"
        spoken_text = build_spoken_text(
            item.get("spokenText") or translated_text,
            source.get("sourceText") or "",
            delivery=delivery,
        )
        normalized_items.append(
            {
                "translatedText": translated_text,
                "spokenText": spoken_text or translated_text,
                "delivery": delivery,
            }
        )
    return normalized_items


def generate_intro_hook_via_llama_cpp(
    window_segments: list[dict[str, Any]],
    *,
    source_language: str,
    clip_duration_ms: int,
) -> str:
    prompt = (
        "You are writing a Vietnamese spoken teaser for a short-form dubbed video.\n"
        "Use the segment context below to create a short teaser in 2 or 3 short Vietnamese sentences that sounds exciting and natural when read aloud.\n"
        "This teaser must summarize the main content or central conflict of the video segment, not stitch together original dialogue lines.\n"
        "Do NOT copy or lightly rearrange individual source sentences. Compress them into a higher-level summary.\n"
        "Sentence 1 should hook the viewer immediately.\n"
        "Sentence 2 must clearly say what the video will show, follow, or reveal so the viewer understands the premise.\n"
        "Sentence 3, if used, should sharpen the tension, stakes, or twist without turning into a full recap.\n"
        "It should feel genuinely intriguing while still making the video's main idea easy to understand.\n"
        f"It should fit roughly {max(18, round(clip_duration_ms / 450))}-{max(35, round(clip_duration_ms / 300))} spoken Vietnamese words total.\n"
        "No hashtags. No emojis. No clickbait nonsense.\n"
        'Return ONLY a valid JSON object: {"hook":"..."}.\n\n'
        + json.dumps(
            [
                {
                    "sourceText": normalize_text(item.get("sourceText") or ""),
                    "translatedText": normalize_text(item.get("translatedText") or ""),
                    "startMs": item.get("startMs"),
                    "endMs": item.get("endMs"),
                }
                for item in window_segments[:15]
            ],
            ensure_ascii=False,
        )
        + f"\n\nSource language: {source_language or 'auto'}."
    )
    payload = parse_json_response_payload(
        run_llama_cpp_prompt(
            prompt,
            max_tokens=160,
            temperature=max(0.45, LLAMA_CPP_TEMP),
            timeout=60,
        )
    )
    if isinstance(payload, dict):
        hook = normalize_text(payload.get("hook") or "")
    elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
        hook = normalize_text(payload[0].get("hook") or "")
    else:
        hook = ""
    return build_spoken_text(hook, delivery="excited")


def fallback_translate_items(
    batch: list[dict[str, Any]],
    *,
    texts: list[str],
    source_hint: str,
    use_llama_cpp: bool,
) -> list[dict[str, str]]:
    if use_llama_cpp:
        try:
            return localize_batch_via_llama_cpp(batch, source_hint, "vi")
        except Exception:
            pass
    localized_items: list[dict[str, str]] = []
    for text, source_item in zip(texts, batch):
        try:
            translated = translate_via_google(text, source_hint, "vi") if text else ""
        except Exception:
            translated = ""
        translated = prefer_minh_cau_pair(translated or text, source_item.get("sourceText") or "")
        spoken = build_spoken_text(translated or text, source_item.get("sourceText") or "")
        localized_items.append(
            {
                "translatedText": translated or text,
                "spokenText": spoken or translated or text,
                "delivery": "neutral",
            }
        )
    return localized_items


def localize_batch_via_ollama_resilient(
    batch: list[dict[str, Any]],
    *,
    source_hint: str,
    target_language: str,
    llama_cpp_available: bool,
    label: str,
    phase: str,
    progress_hint: float,
) -> list[dict[str, str]]:
    texts = [normalize_text(item.get("sourceText") or "") for item in batch]
    try:
        return localize_batch_via_ollama(batch, source_hint, target_language)
    except Exception as exc:
        if len(batch) == 1:
            extended_timeout = min(
                OLLAMA_MAX_TIMEOUT,
                max(estimate_ollama_timeout(texts[0], max_tokens=OLLAMA_TOKENS_MIN, attempt=2), OLLAMA_TIMEOUT + 90),
            )
            if extended_timeout > OLLAMA_TIMEOUT:
                emit_progress(
                    phase=phase,
                    step="translate",
                    progress=progress_hint,
                    message=f"Ollama chậm ở cụm {label}, thử lại riêng cụm này với timeout={extended_timeout}s",
                )
                try:
                    return localize_batch_via_ollama(
                        batch,
                        source_hint,
                        target_language,
                        timeout=extended_timeout,
                    )
                except Exception as retry_exc:
                    exc = retry_exc
        if len(batch) > 1:
            emit_progress(
                phase=phase,
                step="translate",
                progress=progress_hint,
                message=f"Ollama chậm ở cụm {label}, đang tách nhỏ để tránh đứng tiến trình",
            )
            midpoint = max(len(batch) // 2, 1)
            left = localize_batch_via_ollama_resilient(
                batch[:midpoint],
                source_hint=source_hint,
                target_language=target_language,
                llama_cpp_available=llama_cpp_available,
                label=f"{label}.1",
                phase=phase,
                progress_hint=progress_hint,
            )
            right = localize_batch_via_ollama_resilient(
                batch[midpoint:],
                source_hint=source_hint,
                target_language=target_language,
                llama_cpp_available=llama_cpp_available,
                label=f"{label}.2",
                phase=phase,
                progress_hint=progress_hint,
            )
            return left + right
        emit_progress(
            phase=phase,
            step="translate",
            progress=progress_hint,
            message=f"Ollama lỗi ở cụm {label}, đang fallback cục bộ cho cụm này",
            extra={"warning": normalize_text(str(exc))[:180]},
        )
        return fallback_translate_items(
            batch,
            texts=texts,
            source_hint=source_hint,
            use_llama_cpp=llama_cpp_available,
        )


def iter_ollama_translation_batches(
    indexed_segments: list[tuple[int, dict[str, Any]]],
):
    configured_batch_size = max(TRANSLATE_BATCH_SIZE, 1)
    warmup_batch_size = max(min(TRANSLATE_FIRST_BATCH_SIZE, configured_batch_size), 1)
    steady_batch_size = max(configured_batch_size, 3)
    cursor = 0
    is_first = True

    while cursor < len(indexed_segments):
        target_size = warmup_batch_size if is_first else steady_batch_size
        source_char_budget = max(150, target_size * 82)
        context_char_budget = max(260, target_size * 170)
        complexity_budget = 110 if target_size == 1 else 110 + target_size * 68
        batch_entries: list[tuple[int, dict[str, Any]]] = []
        source_chars = 0
        context_chars = 0
        complexity = 0.0

        while cursor < len(indexed_segments) and len(batch_entries) < target_size:
            position, item = indexed_segments[cursor]
            source_text = normalize_text(item.get("sourceText") or "")
            item_context = " ".join(
                part
                for part in (
                    source_text,
                    normalize_text(item.get("previousContext") or ""),
                    normalize_text(item.get("nextContext") or ""),
                )
                if part
            )
            item_complexity = _translation_entry_complexity(item)
            if not batch_entries and _translation_item_should_stand_alone(item):
                batch_entries.append((position, item))
                source_chars += len(source_text)
                context_chars += len(item_context)
                complexity += item_complexity
                cursor += 1
                break
            next_source_chars = source_chars + len(source_text)
            next_context_chars = context_chars + len(item_context)
            next_complexity = complexity + item_complexity
            if batch_entries and (
                next_source_chars > source_char_budget
                or next_context_chars > context_char_budget
                or next_complexity > complexity_budget
            ):
                break
            batch_entries.append((position, item))
            source_chars = next_source_chars
            context_chars = next_context_chars
            complexity = next_complexity
            cursor += 1

        if not batch_entries:
            batch_entries = [indexed_segments[cursor]]
            cursor += 1

        is_first = False
        yield (
            batch_entries[0][0],
            [item for _, item in batch_entries],
            batch_entries[-1][0],
        )


def translate_segments(
    segments: list[dict[str, Any]],
    source_language: str,
    cache_path: Path,
    *,
    target_language: str = "vi",
    phase: str = "render",
) -> list[dict[str, Any]]:
    cache_key = hashlib.sha1(
        json.dumps(
            {
                "translationPromptVersion": TRANSLATION_PROMPT_VERSION,
                "sourceLanguage": source_language,
                "targetLanguage": target_language,
                "texts": [item["sourceText"] for item in segments],
            },
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    translations = load_translation_cache(cache_path, cache_key)
    cached_count = 0
    for item in segments:
        localized = translations.get(item["id"], {})
        if not isinstance(localized, dict):
            continue
        item["translatedText"] = localized.get("translatedText", item.get("translatedText", ""))
        item["spokenText"] = localized.get("spokenText", item["translatedText"])
        item["delivery"] = localized.get("delivery", "neutral")
        if item["translatedText"]:
            cached_count += 1
    seeded_translations = 0
    for item in segments:
        translated_text = normalize_text(item.get("translatedText") or "")
        if not translated_text or item["id"] in translations:
            continue
        spoken_text = normalize_text(item.get("spokenText") or translated_text)
        delivery = normalize_text(item.get("delivery") or "neutral").lower() or "neutral"
        translations[item["id"]] = {
            "translatedText": translated_text,
            "spokenText": spoken_text or translated_text,
            "delivery": delivery,
        }
        seeded_translations += 1

    source_hint = source_language if source_language in LANGUAGE_OPTIONS else "auto"
    total = max(len(segments), 1)
    normalized_target_language = normalize_text(target_language).lower() or "vi"
    try:
        use_ollama = should_use_ollama(DUB_TRANSLATE_PROVIDER)
    except Exception:
        use_ollama = False
    try:
        use_llama_cpp = (not use_ollama) and should_use_llama_cpp(DUB_TRANSLATE_PROVIDER)
    except Exception:
        use_llama_cpp = False
    if normalized_target_language != "vi":
        use_ollama = False
        use_llama_cpp = False
    for index, item in enumerate(segments):
        item["previousText"] = normalize_text(segments[index - 1].get("sourceText") or "") if index > 0 else ""
        item["nextText"] = normalize_text(segments[index + 1].get("sourceText") or "") if index + 1 < len(segments) else ""
        item["previousContext"] = joined_source_context(segments[max(0, index - 2):index])
        item["nextContext"] = joined_source_context(segments[index + 1:index + 3])
    pending_segments = []
    sfx_count = 0
    for index, item in enumerate(segments):
        source_text = normalize_text(item.get("sourceText") or "")
        if not source_text:
            continue
        if normalize_text(item.get("translatedText") or ""):
            continue
        # Skip non-dialogue sound effects — they are not spoken dialogue
        if _is_non_dialogue_sfx(source_text):
            sfx_count += 1
            item["translatedText"] = ""  # keep empty so TTS skips it
            item["spokenText"] = ""
            item["delivery"] = "neutral"
            continue
        pending_segments.append((index + 1, item))
    if sfx_count:
        emit_progress(
            phase=phase,
            step="translate",
            progress=0.32,
            message=f"Đã bỏ qua {sfx_count} đoạn âm thanh/hiệu ứng không phải lời thoại",
        )
    if not pending_segments:
        if seeded_translations:
            persist_translation_cache(cache_path, cache_key, translations)
        return segments

    pending_updates = 0

    def flush_translation_cache(*, force: bool = False) -> None:
        nonlocal pending_updates
        if not pending_updates:
            return
        if not force and pending_updates < 6:
            return
        persist_translation_cache(cache_path, cache_key, translations)
        pending_updates = 0
    llama_cpp_available = should_use_llama_cpp("auto")
    if use_ollama:
        try:
            warmup_ollama_model(phase=phase, progress=0.315)
        except Exception as exc:
            emit_progress(
                phase=phase,
                step="translate",
                progress=0.315,
                message="Warm-up Ollama không hoàn tất, vẫn tiếp tục dịch với retry tăng cường",
                extra={"warning": normalize_text(str(exc))[:180]},
            )
        for start_position, batch, end_position in iter_ollama_translation_batches(
            pending_segments
        ):
            texts = [normalize_text(item["sourceText"]) for item in batch]
            batch_progress = translation_batch_progress(end_position, total)
            start = start_position - 1
            end_index = end_position
            batch_note = " (batch đầu có thể chậm do Ollama warm-up)" if start == 0 else ""
            emit_progress(
                phase=phase,
                step="translate",
                progress=batch_progress,
                message=translation_progress_message(
                    provider_label="Ollama",
                    start=start,
                    end_index=end_index,
                    total=len(segments),
                    note=batch_note,
                ),
            )
            localized_items = localize_batch_via_ollama_resilient(
                batch,
                source_hint=source_hint,
                target_language=target_language,
                llama_cpp_available=llama_cpp_available,
                label=f"{start + 1}-{end_index}",
                phase=phase,
                progress_hint=batch_progress,
            )
            for item, localized, source_text in zip(batch, localized_items, texts):
                translations[item["id"]] = apply_localized_result(item, localized, source_text)
                pending_updates += 1
            flush_translation_cache()
    elif use_llama_cpp:
        for start, batch in iter_translation_batches(
            [item for _, item in pending_segments],
            batch_size=TRANSLATE_BATCH_SIZE,
            first_batch_size=TRANSLATE_FIRST_BATCH_SIZE,
        ):
            texts = [normalize_text(item["sourceText"]) for item in batch]
            start_position = pending_segments[start][0]
            end_index = pending_segments[start + len(batch) - 1][0]
            emit_progress(
                phase=phase,
                step="translate",
                progress=translation_batch_progress(end_index, total),
                message=translation_progress_message(
                    provider_label="local",
                    start=start_position - 1,
                    end_index=end_index,
                    total=len(segments),
                ),
            )
            try:
                localized_items = localize_batch_via_llama_cpp(batch, source_hint, "vi")
            except Exception:
                localized_items = fallback_translate_items(
                    batch,
                    texts=texts,
                    source_hint=source_hint,
                    use_llama_cpp=False,
                )
            for item, localized, source_text in zip(batch, localized_items, texts):
                translations[item["id"]] = apply_localized_result(item, localized, source_text)
                pending_updates += 1
            flush_translation_cache()
    else:
        for index, item in pending_segments:
            text = normalize_text(item["sourceText"])
            emit_progress(
                phase=phase,
                step="translate",
                progress=translation_batch_progress(index, total),
                message=f"Đang dịch câu {index}/{len(segments)}",
            )
            translated = translate_via_google(text, source_hint, normalized_target_language)
            item["translatedText"] = prefer_minh_cau_pair(
                translated or text,
                item.get("sourceText") or text,
            )
            item["spokenText"] = build_spoken_text(item["translatedText"], item.get("sourceText") or "")
            item["delivery"] = "neutral"
            translations[item["id"]] = {
                "translatedText": item["translatedText"],
                "spokenText": item["spokenText"],
                "delivery": item["delivery"],
            }
            pending_updates += 1
            flush_translation_cache()

    flush_translation_cache(force=True)
    return segments


def trim_summary_text(text: str, max_chars: int = 92) -> str:
    clean = normalize_text(text).rstrip(" ,;:.!?")
    if len(clean) <= max_chars:
        return clean
    shortened = clean[: max_chars - 1].rsplit(" ", 1)[0].strip()
    return shortened or clean[: max_chars - 1].strip()


def clean_intro_fragment(text: str, max_chars: int = 58) -> str:
    clean = trim_summary_text(text, max_chars=max_chars)
    clean = re.sub(r"^(và|va|nhưng|nhung|rồi|roi|sau đó|sau do)\s+", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+(?:và|va|nhưng|nhung|rồi|roi|với|voi)$", "", clean, flags=re.IGNORECASE)
    return clean.rstrip(" ,;:.!?")


def to_sentence_case(text: str) -> str:
    clean = normalize_text(text).strip()
    if not clean:
        return ""
    return clean[0].upper() + clean[1:]


def finalize_intro_text(text: str) -> str:
    clean = normalize_text(text).strip().rstrip(" ,;:")
    if not clean:
        return "Mở đầu video đã là đoạn đáng chú ý nhất."
    if clean[-1] not in ".!?…":
        clean = f"{clean}."
    return to_sentence_case(clean)


def select_intro_hook_window(
    segments: list[dict[str, Any]],
    *,
    video_duration_ms: int,
    desired_clip_ms: int,
) -> dict[str, Any]:
    safe_video_duration = max(int(video_duration_ms), 600)
    target_clip_ms = max(5000, min(int(desired_clip_ms), 16000))
    clip_ms = max(600, min(target_clip_ms, safe_video_duration))
    if not segments:
        start_ms = 0 if safe_video_duration <= clip_ms + 800 else min(1800, max(safe_video_duration - clip_ms, 0))
        end_ms = min(start_ms + clip_ms, safe_video_duration)
        return {
            "startMs": start_ms,
            "endMs": end_ms,
            "durationMs": max(end_ms - start_ms, min(safe_video_duration, 600)),
            "segments": [],
        }

    min_start_ms = 0 if safe_video_duration <= 9000 else min(max(int(safe_video_duration * 0.08), 2500), max(safe_video_duration - clip_ms, 0))
    max_start_ms = max(min(int(safe_video_duration * 0.72), max(safe_video_duration - clip_ms - 500, 0)), min_start_ms)
    candidates = []
    for segment in segments:
        start_ms = int(segment.get("startMs", 0))
        if start_ms < min_start_ms or start_ms > max_start_ms:
            continue
        text = normalize_text(segment.get("translatedText") or segment.get("sourceText") or "")
        if not text:
            continue
        density = min(len(text.replace(" ", "")), 70) / 70
        punctuation_bonus = 0.22 if re.search(r"[!?…]", text) else 0.0
        position_ratio = start_ms / max(safe_video_duration, 1)
        position_bonus = 1.0 - min(abs(position_ratio - 0.32), 0.32)
        candidates.append((density + punctuation_bonus + position_bonus, segment))

    chosen = max(candidates, key=lambda item: item[0])[1] if candidates else segments[min(1, len(segments) - 1)]
    start_ms = min(max(int(chosen.get("startMs", 0)) - 320, min_start_ms), max_start_ms)
    end_ms = min(start_ms + clip_ms, safe_video_duration)
    if end_ms - start_ms < clip_ms and safe_video_duration > clip_ms:
        start_ms = max(0, end_ms - clip_ms)
    window_segments = [
        segment
        for segment in segments
        if int(segment.get("endMs", 0)) > start_ms and int(segment.get("startMs", 0)) < end_ms
    ]
    return {
        "startMs": start_ms,
        "endMs": end_ms,
        "durationMs": max(end_ms - start_ms, min(safe_video_duration, 600)),
        "segments": window_segments,
    }


def build_intro_hook_text(window_segments: list[dict[str, Any]]) -> str:
    text_parts: list[str] = []
    for segment in window_segments[:2]:
        translated = normalize_text(segment.get("translatedText") or segment.get("sourceText") or "")
        if translated:
            text_parts.append(trim_summary_text(translated, max_chars=68))
    summary = trim_summary_text(" ".join(text_parts), max_chars=96)
    if summary:
        return finalize_intro_text(
            f"Video này sẽ cho thấy {summary.lower().rstrip(' ,;:.!?')}."
        )
    return "Mở đầu video đã là đoạn đáng chú ý nhất."


def build_structured_intro_hook_text(window_segments: list[dict[str, Any]]) -> str:
    candidates: list[tuple[float, int, str]] = []
    for segment in window_segments:
        translated = normalize_text(segment.get("translatedText") or segment.get("sourceText") or "")
        if len(translated) < 14:
            continue
        duration_ms = max(int(segment.get("endMs", 0)) - int(segment.get("startMs", 0)), 400)
        score = min(len(translated.replace(" ", "")), 70) / 70 + min(duration_ms, 3200) / 6400
        if re.search(r"[!?…]", translated):
            score += 0.14
        candidates.append((score, int(segment.get("startMs", 0)), clean_intro_fragment(translated, max_chars=52)))

    if not candidates:
        return "Mở đầu video đã là đoạn đáng chú ý nhất."

    top_points = sorted(
        sorted(candidates, key=lambda item: item[0], reverse=True)[:3],
        key=lambda item: item[1],
    )
    points: list[str] = []
    for _, _, fragment in top_points:
        if not fragment:
            continue
        normalized_fragment = fragment.lower()
        if any(normalized_fragment in existing.lower() or existing.lower() in normalized_fragment for existing in points):
            continue
        points.append(fragment)

    if not points:
        return "Mở đầu video đã là đoạn đáng chú ý nhất."
    if len(points) == 1:
        return finalize_intro_text(
            "Video này sẽ cho thấy "
            + points[0].lower().rstrip(" ,;:.!?")
            + ", và đây mới chỉ là khởi đầu."
        )

    sentences: list[str] = [
        "Mọi chuyện bắt đầu khi " + points[0].lower().rstrip(" ,;:.!?") + "."
    ]
    if len(points) >= 2:
        sentences.append(
            "Video này sẽ theo chân diễn biến khi "
            + points[1].lower().rstrip(" ,;:.!?")
            + "."
        )
    if len(points) >= 3:
        sentences.append(
            "Và điều khiến mọi thứ bùng lên là "
            + points[2].lower().rstrip(" ,;:.!?")
            + "."
        )
    return finalize_intro_text(" ".join(sentences))


def build_intro_hook_text_with_context(
    window_segments: list[dict[str, Any]],
    *,
    source_language: str,
    clip_duration_ms: int,
) -> str:
    try:
        use_ollama = should_use_ollama(DUB_TRANSLATE_PROVIDER)
    except Exception:
        use_ollama = False
    try:
        use_llama_cpp = should_use_llama_cpp(DUB_TRANSLATE_PROVIDER)
    except Exception:
        use_llama_cpp = False
    if use_ollama:
        try:
            generated = generate_intro_hook_via_ollama(
                window_segments,
                source_language=source_language,
                clip_duration_ms=clip_duration_ms,
            )
            if generated:
                return finalize_intro_text(generated)
        except Exception:
            pass
    if use_llama_cpp or should_use_llama_cpp("auto"):
        try:
            generated = generate_intro_hook_via_llama_cpp(
                window_segments,
                source_language=source_language,
                clip_duration_ms=clip_duration_ms,
            )
            if generated:
                return finalize_intro_text(generated)
        except Exception:
            pass
    return build_structured_intro_hook_text(window_segments)
