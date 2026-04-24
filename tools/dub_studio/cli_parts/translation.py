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

def translate_via_microsoft(text: str, source_lang: str = "auto", target_lang: str = "vi") -> str:
    clean_text = normalize_text(text)
    if not clean_text:
        return ""
    if not MICROSOFT_TRANSLATOR_KEY:
        return ""

    query_params = {"api-version": "3.0", "to": target_lang or "vi"}
    if source_lang and str(source_lang).strip().lower() not in {"", "auto"}:
        query_params["from"] = source_lang
    url = f"{MICROSOFT_TRANSLATOR_ENDPOINT}/translate?{urllib.parse.urlencode(query_params)}"
    request_body = json.dumps([{"Text": clean_text}], ensure_ascii=False).encode("utf-8")
    headers = {
        "Ocp-Apim-Subscription-Key": MICROSOFT_TRANSLATOR_KEY,
        "Content-Type": "application/json; charset=UTF-8",
    }
    if MICROSOFT_TRANSLATOR_REGION:
        headers["Ocp-Apim-Subscription-Region"] = MICROSOFT_TRANSLATOR_REGION

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            request = urllib.request.Request(url, data=request_body, headers=headers, method="POST")
            with urllib.request.urlopen(request, timeout=MICROSOFT_TRANSLATOR_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
            translations = payload[0].get("translations", []) if isinstance(payload, list) and payload else []
            translated = normalize_text(translations[0].get("text") or "") if translations else ""
            return translated
        except Exception:
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            return ""
    return ""


MICROSOFT_TRANSLATION_CACHE_VERSION = 1


def machine_translation_cache_path(cache_path: Path) -> Path:
    suffix = cache_path.suffix or ".json"
    return cache_path.with_name(f"{cache_path.stem}.microsoft{suffix}")


def load_machine_translation_cache(cache_path: Path) -> dict[str, str]:
    if not cache_path.exists():
        return {}
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if cached.get("version") != MICROSOFT_TRANSLATION_CACHE_VERSION:
        return {}
    entries = cached.get("entries", {})
    return entries if isinstance(entries, dict) else {}


def persist_machine_translation_cache(cache_path: Path, entries: dict[str, str]) -> None:
    cache_path.write_text(
        json.dumps({"version": MICROSOFT_TRANSLATION_CACHE_VERSION, "entries": entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def machine_translation_cache_key(text: str, source_lang: str, target_lang: str) -> str:
    return hashlib.sha1(
        json.dumps(
            {
                "sourceLanguage": source_lang or "auto",
                "targetLanguage": target_lang or "vi",
                "text": normalize_text(text),
            },
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def normalize_delivery_choice(value: str | None, *, default: str = "neutral") -> str:
    normalized = normalize_text(value or "").lower()
    if normalized in {"calm", "neutral", "curious", "excited", "urgent", "suspense"}:
        return normalized
    return default


def infer_delivery_from_source(source_text: str, translated_text: str) -> str:
    source = normalize_text(source_text)
    translated = normalize_text(translated_text)
    if not translated:
        return "neutral"
    if source.endswith(("?", "？")):
        return "curious"
    if source.endswith(("!", "！")):
        return "excited"
    if source.endswith(("...", "…")):
        return "suspense" if len(translated.split()) <= 7 else "calm"
    lowered = translated.lower()
    if re.search(r"\b(đừng|mau|nhanh|chạy|trả|nhớ)\b", lowered) and len(translated.split()) <= 9:
        return "urgent"
    if len(translated.split()) >= 14:
        return "calm"
    return "neutral"


def build_machine_fallback_localization(item: dict[str, Any], translated_text: str) -> dict[str, str]:
    source_text = item.get("sourceText") or translated_text
    delivery = infer_delivery_from_source(source_text, translated_text)
    spoken_text = build_spoken_text(translated_text, source_text, delivery=delivery)
    item["translatedText"] = translated_text
    item["spokenText"] = spoken_text or translated_text
    item["delivery"] = delivery
    return {
        "translatedText": item["translatedText"],
        "spokenText": item["spokenText"],
        "delivery": item["delivery"],
        "machineTranslatedText": translated_text,
    }


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


def _has_usable_prefilled_translation(
    source_text: str,
    translated_text: str,
    *,
    source_language: str,
    target_language: str,
) -> bool:
    clean_source = normalize_text(source_text)
    clean_translated = normalize_text(translated_text)
    if not clean_translated:
        return False
    normalized_source_language = normalize_text(source_language).lower()
    normalized_target_language = normalize_text(target_language).lower()
    if (
        clean_source
        and clean_source == clean_translated
        and normalized_source_language
        and normalized_target_language
        and normalized_source_language != normalized_target_language
    ):
        return False
    if normalized_source_language != normalized_target_language and _looks_like_source_language(
        clean_translated,
        clean_source,
    ):
        return False
    return True



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
    lower_bound = OLLAMA_TOKENS_MIN if len(items_payload) == 1 else max(160, min(OLLAMA_TOKENS_MIN, len(items_payload) * 128))
    upper_bound = max(lower_bound, len(items_payload) * OLLAMA_TOKENS_PER_ITEM + 160)
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


def should_review_machine_translation(item: dict[str, Any], translated_text: str) -> bool:
    text = normalize_text(translated_text)
    if not text:
        return False
    source = normalize_text(item.get("sourceText") or "")
    word_count = len([part for part in text.split() if part])
    if word_count <= 3 and len(text) <= 18 and text.count(",") == 0:
        return False
    if re.search(r"[?!…]|\.{3}", source):
        return True
    if word_count >= 6 or len(text) >= 28:
        return True
    if text.count(",") >= 1 or text.count(".") >= 1:
        return True
    if normalize_text(item.get("previousContext") or "") or normalize_text(item.get("nextContext") or ""):
        return word_count >= 4
    return False


def _compact_machine_review_item(
    item: dict[str, Any],
    *,
    index: int,
    batch: list[dict[str, Any]],
) -> dict[str, Any]:
    source_text = normalize_text(item.get("sourceText") or "")
    machine_translated = normalize_text(item.get("translatedText") or "")
    compact_item: dict[str, Any] = {
        "index": index,
        "sourceText": source_text,
        "machineTranslatedText": machine_translated,
        "durationMs": max(int(item.get("endMs", 0)) - int(item.get("startMs", 0)), 400),
        "speakerId": item.get("speakerId") or "speaker_1",
        "maxSpokenChars": _estimate_translation_char_limit(machine_translated or source_text, max(int(item.get("endMs", 0)) - int(item.get("startMs", 0)), 400), spoken=True),
    }
    previous_translated = normalize_text(
        item.get("previousTranslatedText")
        or (batch[index - 1].get("translatedText") if index > 0 else "")
        or ""
    )
    next_translated = normalize_text(
        item.get("nextTranslatedText")
        or (batch[index + 1].get("translatedText") if index + 1 < len(batch) else "")
        or ""
    )
    previous_context = _trim_translation_context(item.get("previousContext") or "", 96)
    next_context = _trim_translation_context(item.get("nextContext") or "", 96)
    if previous_translated:
        compact_item["previousTranslatedText"] = _trim_translation_context(previous_translated, 72)
    if next_translated:
        compact_item["nextTranslatedText"] = _trim_translation_context(next_translated, 72)
    if previous_context:
        compact_item["previousContext"] = previous_context
    if next_context:
        compact_item["nextContext"] = next_context
    return compact_item


def _build_machine_review_items_payload(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _compact_machine_review_item(item, index=index, batch=batch)
        for index, item in enumerate(batch)
    ]


def _estimate_machine_review_max_tokens(items_payload: list[dict[str, Any]]) -> int:
    if not items_payload:
        return 128
    total_chars = sum(
        int(item.get("maxSpokenChars", 48)) + len(normalize_text(item.get("machineTranslatedText") or "")) + 24
        for item in items_payload
    )
    estimated = math.ceil(total_chars / 3.8) + len(items_payload) * 12
    lower_bound = OLLAMA_TOKENS_MIN if len(items_payload) == 1 else max(160, min(OLLAMA_TOKENS_MIN, len(items_payload) * 128))
    upper_bound = max(lower_bound, len(items_payload) * OLLAMA_TOKENS_PER_ITEM + 160)
    return max(lower_bound, min(estimated, upper_bound))


def _build_machine_review_prompt(
    items_payload: list[dict[str, Any]],
    *,
    source_language: str,
) -> str:
    return (
        "You are a Vietnamese dialogue polisher for dubbed video.\n"
        f"Source language: {source_language or 'auto-detected language'}.\n"
          "You will receive Microsoft-translated Vietnamese drafts plus nearby context.\n"
          "Your job is NOT to translate from scratch. Your job is to keep the meaning of machineTranslatedText, but rewrite it into spoken Vietnamese that is smoother, easier to understand, and more natural for voice dubbing.\n"
        "\n"
        "CRITICAL RULES:\n"
        f"1. Return ONLY a valid JSON array with EXACTLY {len(items_payload)} items, same order as input.\n"
          "2. Every spokenText MUST be Vietnamese and must preserve the meaning of machineTranslatedText.\n"
        "3. Keep wording simple, direct, and easy for Vietnamese listeners to follow immediately.\n"
          "4. If machineTranslatedText is already natural, keep it close instead of rewriting aggressively.\n"
          "5. Do NOT add new facts, explanations, or narration that are not in sourceText / machineTranslatedText.\n"
        "6. delivery must be exactly one of: calm, neutral, curious, excited, urgent, suspense.\n"
        "\n"
        "Each output item must be a JSON object with exactly these keys:\n"
        '- "spokenText": rewritten spoken Vietnamese for dubbing / TTS.\n'
        '- "delivery": one of calm, neutral, curious, excited, urgent, suspense.\n'
        "\n"
        "Style rules:\n"
        "- Prefer everyday Vietnamese over literal or stiff wording.\n"
        "- Make the line flow naturally when read aloud.\n"
        "- Smooth broken phrases into a coherent spoken sentence when needed.\n"
        "- Use context to keep pronouns and tone consistent across nearby lines.\n"
        "- Stay within maxSpokenChars when reasonably possible.\n"
        "\n"
        f"{json.dumps(items_payload, ensure_ascii=False)}"
    )


def _normalize_machine_review_items(
    batch: list[dict[str, Any]],
    reviewed: Any,
) -> list[dict[str, str]]:
    if isinstance(reviewed, dict):
        if len(batch) == 1 and "spokenText" in reviewed:
            reviewed = [reviewed]
        else:
            raise RuntimeError("Gemma review response must be a JSON array.")
    if not isinstance(reviewed, list) or len(reviewed) != len(batch):
        raise RuntimeError(
            f"Gemma review trả về không khớp số lượng (nhận {len(reviewed) if isinstance(reviewed, list) else 0}, cần {len(batch)})."
        )
    normalized_items: list[dict[str, str]] = []
    for item, source in zip(reviewed, batch):
        if not isinstance(item, dict):
            raise RuntimeError("Gemma review item must be a JSON object.")
        translated_text = normalize_text(source.get("translatedText") or source.get("sourceText") or "")
        delivery = normalize_delivery_choice(
            item.get("delivery"),
            default=infer_delivery_from_source(source.get("sourceText") or "", translated_text),
        )
        spoken_text = build_spoken_text(
            normalize_text(item.get("spokenText") or translated_text),
            source.get("sourceText") or "",
            delivery=delivery,
        )
        normalized_items.append(
            {
                "spokenText": spoken_text or translated_text,
                "delivery": delivery,
            }
        )
    return normalized_items


def review_machine_batch_via_ollama(
    batch: list[dict[str, Any]],
    source_language: str,
    *,
    timeout: int = OLLAMA_TIMEOUT,
) -> list[dict[str, str]]:
    items_payload = _build_machine_review_items_payload(batch)
    prompt = _build_machine_review_prompt(items_payload, source_language=source_language)
    reviewed = parse_json_response_payload(
        run_ollama_prompt(
            prompt,
            max_tokens=_estimate_machine_review_max_tokens(items_payload),
            temperature=max(0.08, min(OLLAMA_TEMP, 0.18)),
            timeout=timeout,
        )
    )
    return _normalize_machine_review_items(batch, reviewed)


def review_machine_batch_via_llama_cpp(
    batch: list[dict[str, Any]],
    source_language: str,
) -> list[dict[str, str]]:
    items_payload = _build_machine_review_items_payload(batch)
    prompt = _build_machine_review_prompt(items_payload, source_language=source_language)
    reviewed = parse_json_response_payload(
        run_llama_cpp_prompt(
            prompt,
            max_tokens=_estimate_machine_review_max_tokens(items_payload),
            temperature=max(0.08, min(LLAMA_CPP_TEMP, 0.18)),
            timeout=LLAMA_CPP_TIMEOUT,
        )
    )
    return _normalize_machine_review_items(batch, reviewed)


def apply_machine_review_result(
    item: dict[str, Any],
    *,
    translated_text: str,
    reviewed: dict[str, Any] | None = None,
) -> dict[str, str]:
    source_text = item.get("sourceText") or ""
    normalized_translated = pick_best_localized_text(
        translated_text,
        (reviewed or {}).get("spokenText") or "",
        source_text,
    )
    if reviewed is None:
        return build_machine_fallback_localization(item, normalized_translated)
    delivery = normalize_delivery_choice(
        reviewed.get("delivery"),
        default=infer_delivery_from_source(source_text, normalized_translated),
    )
    spoken_seed = pick_best_localized_text(
        reviewed.get("spokenText") or "",
        normalized_translated,
        source_text,
    )
    spoken_text = build_spoken_text(
        normalize_text(spoken_seed or normalized_translated),
        source_text,
        delivery=delivery,
    )
    item["translatedText"] = normalized_translated
    item["spokenText"] = spoken_text or normalized_translated
    item["delivery"] = delivery
    return {
        "translatedText": item["translatedText"],
        "spokenText": item["spokenText"],
        "delivery": item["delivery"],
        "machineTranslatedText": normalized_translated,
    }


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
        # If the model echoed back the source language, fall back to Microsoft Translator
        if not raw_translated or _looks_like_source_language(raw_translated, source_text):
            try:
                raw_translated = translate_via_microsoft(source_text, "auto", "vi")
            except Exception:
                raw_translated = ""
        translated_seed = pick_best_localized_text(
            raw_translated,
            item.get("spokenText") or "",
            source_text,
        )
        translated_text = prefer_minh_cau_pair(
            translated_seed,
            source_text,
        )
        delivery = normalize_text(item.get("delivery") or "neutral").lower()
        if delivery not in {"calm", "neutral", "curious", "excited", "urgent", "suspense"}:
            delivery = "neutral"
        raw_spoken = pick_best_localized_text(
            item.get("spokenText") or "",
            translated_text,
            source_text,
        )
        spoken_text = (
            build_spoken_text(
                raw_spoken,
                source_text,
                delivery=delivery,
            )
            if raw_spoken
            else ""
        )
        normalized_items.append(
            {
                "translatedText": translated_text,
                "spokenText": spoken_text or translated_text,
                "delivery": delivery,
            }
        )
    return normalized_items


def _count_intro_words(text: str) -> int:
    return len([part for part in normalize_text(text).split() if part])


def _count_intro_sentences(text: str) -> int:
    clean = normalize_text(text)
    if not clean:
        return 0
    sentences = [part for part in re.split(r"[.!?…]+", clean) if normalize_text(part)]
    return len(sentences)


def _intro_word_range(clip_duration_ms: int) -> tuple[int, int]:
    clip_seconds = max(int(clip_duration_ms), 7000) / 1000.0
    min_words = max(24, min(58, int(round(clip_seconds * 2.35))))
    max_words = max(min_words + 12, min(84, int(round(clip_seconds * 3.85))))
    return min_words, max_words


def _format_intro_time_label(start_ms: int, end_ms: int) -> str:
    start_seconds = max(int(start_ms), 0) // 1000
    end_seconds = max(int(end_ms), max(int(start_ms), 0)) // 1000
    return f"{start_seconds // 60:02d}:{start_seconds % 60:02d}-{end_seconds // 60:02d}:{end_seconds % 60:02d}"


def _build_intro_generation_payload(window_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for item in window_segments[:18]:
        translated_text = normalize_text(item.get("translatedText") or "")
        source_text = normalize_text(item.get("sourceText") or "")
        payload.append(
            {
                "time": _format_intro_time_label(
                    int(item.get("startMs", 0)),
                    int(item.get("endMs", 0)),
                ),
                "speakerId": normalize_text(item.get("speakerId") or ""),
                "translatedText": translated_text,
                "sourceText": source_text,
            }
        )
    return payload


def _extract_intro_teaser_text(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("teaser", "hook", "narration", "summary"):
            value = normalize_text(payload.get(key) or "")
            if value:
                return value
        parts = [
            normalize_text(payload.get("opening") or ""),
            normalize_text(payload.get("premise") or ""),
            normalize_text(payload.get("stakes") or ""),
            normalize_text(payload.get("turn") or ""),
        ]
        combined = " ".join(part for part in parts if part)
        if combined:
            return combined
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return _extract_intro_teaser_text(payload[0])
    return ""


def _intro_teaser_quality_ok(text: str, *, clip_duration_ms: int) -> bool:
    clean = normalize_text(text)
    if not clean:
        return False
    min_words, max_words = _intro_word_range(clip_duration_ms)
    word_count = _count_intro_words(clean)
    sentence_count = _count_intro_sentences(clean)
    if sentence_count < 2:
        return False
    if word_count < max(16, int(min_words * 0.72)):
        return False
    if word_count > int(max_words * 1.35):
        return False
    if len(clean) < 60:
        return False
    return True


def _build_intro_teaser_prompt(
    window_segments: list[dict[str, Any]],
    *,
    source_language: str,
    clip_duration_ms: int,
    retry_reason: str = "",
) -> str:
    min_words, max_words = _intro_word_range(clip_duration_ms)
    retry_block = (
        "\nPrevious attempt was too short or too vague. Fix that by making the premise much clearer.\n"
        if retry_reason
        else "\n"
    )
    return (
        "You are writing a Vietnamese teaser voice-over for the opening clip of a dubbed short video.\n"
        "Write a teaser that is exciting BUT also easy to understand on first listen.\n"
        "The viewer must understand the premise of the video from the teaser alone.\n"
        "\n"
        "Structure requirements:\n"
        "- Write 3 or 4 Vietnamese sentences.\n"
        "- Sentence 1: hook the viewer with a concrete conflict, event, or surprising setup.\n"
        "- Sentence 2: clearly explain what is happening, who is involved, or what the video will show.\n"
        "- Sentence 3: continue the premise or show how the situation escalates.\n"
        "- Sentence 4, if used: sharpen the stakes, twist, or question that makes people keep watching.\n"
        "\n"
        "Quality requirements:\n"
        "- Use concrete details from the segment context.\n"
        "- Do NOT be vague. Avoid generic lines like 'mọi chuyện chưa dừng lại' unless the teaser already explained the premise clearly.\n"
        "- Do NOT just remix subtitle lines. Compress them into a natural spoken summary.\n"
        "- The narration should sound like a strong Vietnamese voice-over, not subtitles pasted together.\n"
        f"- Keep it around {min_words}-{max_words} spoken Vietnamese words total.\n"
        "- No hashtags. No emojis. No markdown.\n"
        '- Return ONLY a valid JSON object: {"teaser":"..."}.\n'
        f"{retry_block}\n"
        + json.dumps(
            {
                "sourceLanguage": source_language or "auto",
                "clipDurationMs": int(clip_duration_ms),
                "timeline": _build_intro_generation_payload(window_segments),
            },
            ensure_ascii=False,
        )
    )


def generate_intro_hook_via_ollama(
    window_segments: list[dict[str, Any]],
    *,
    source_language: str,
    clip_duration_ms: int,
) -> str:
    """Generate a Vietnamese intro teaser hook using Ollama API."""
    hook = ""
    for attempt in range(2):
        prompt = _build_intro_teaser_prompt(
            window_segments,
            source_language=source_language,
            clip_duration_ms=clip_duration_ms,
            retry_reason=("too_short" if attempt else ""),
        )
        payload = parse_json_response_payload(
            run_ollama_prompt(
                prompt,
                max_tokens=256,
                temperature=max(0.38, OLLAMA_TEMP),
                timeout=55,
            )
        )
        hook = _extract_intro_teaser_text(payload)
        hook = build_spoken_text(hook, delivery="excited")
        if _intro_teaser_quality_ok(hook, clip_duration_ms=clip_duration_ms):
            return hook
    return hook


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
        source_text = source.get("sourceText") or ""
        raw_translated = normalize_text(item.get("translatedText") or "")
        if not raw_translated or _looks_like_source_language(raw_translated, source_text):
            try:
                raw_translated = translate_via_microsoft(source_text, "auto", "vi")
            except Exception:
                raw_translated = ""
        translated_seed = pick_best_localized_text(
            raw_translated,
            item.get("spokenText") or "",
            source_text,
        )
        translated_text = prefer_minh_cau_pair(
            translated_seed,
            source_text,
        )
        delivery = normalize_text(item.get("delivery") or "neutral").lower()
        if delivery not in {"calm", "neutral", "curious", "excited", "urgent", "suspense"}:
            delivery = "neutral"
        spoken_seed = pick_best_localized_text(
            item.get("spokenText") or "",
            translated_text,
            source_text,
        )
        spoken_text = (
            build_spoken_text(
                spoken_seed,
                source_text,
                delivery=delivery,
            )
            if spoken_seed
            else ""
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
    hook = ""
    for attempt in range(2):
        prompt = _build_intro_teaser_prompt(
            window_segments,
            source_language=source_language,
            clip_duration_ms=clip_duration_ms,
            retry_reason=("too_short" if attempt else ""),
        )
        payload = parse_json_response_payload(
            run_llama_cpp_prompt(
                prompt,
                max_tokens=256,
                temperature=max(0.38, LLAMA_CPP_TEMP),
                timeout=80,
            )
        )
        hook = _extract_intro_teaser_text(payload)
        hook = build_spoken_text(hook, delivery="excited")
        if _intro_teaser_quality_ok(hook, clip_duration_ms=clip_duration_ms):
            return hook
    return hook


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
            translated = translate_via_microsoft(text, source_hint, "vi") if text else ""
        except Exception:
            translated = ""
        source_text = source_item.get("sourceText") or ""
        translated_seed = pick_best_localized_text(
            translated,
            source_item.get("spokenText") or "",
            source_text,
        )
        translated = prefer_minh_cau_pair(translated_seed, source_text)
        spoken_seed = pick_best_localized_text(
            source_item.get("spokenText") or "",
            translated,
            source_text,
        )
        spoken = build_spoken_text(spoken_seed or translated, source_text) if (spoken_seed or translated) else ""
        localized_items.append(
            {
                "translatedText": translated,
                "spokenText": spoken or translated,
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


def review_machine_batch_via_ollama_resilient(
    batch: list[dict[str, Any]],
    *,
    source_language: str,
    llama_cpp_available: bool,
    label: str,
    phase: str,
    progress_hint: float,
) -> list[dict[str, str]]:
    try:
        return review_machine_batch_via_ollama(batch, source_language)
    except Exception as exc:
        if len(batch) == 1:
            extended_timeout = min(OLLAMA_MAX_TIMEOUT, OLLAMA_TIMEOUT + 90)
            if extended_timeout > OLLAMA_TIMEOUT:
                emit_progress(
                    phase=phase,
                    step="translate",
                    progress=progress_hint,
                    message=f"Gemma chậm ở cụm {label}, thử lại riêng cụm này với timeout={extended_timeout}s",
                )
                try:
                    return review_machine_batch_via_ollama(
                        batch,
                        source_language,
                        timeout=extended_timeout,
                    )
                except Exception as retry_exc:
                    exc = retry_exc
        if len(batch) > 1:
            emit_progress(
                phase=phase,
                step="translate",
                progress=progress_hint,
                message=f"Gemma chậm ở cụm {label}, đang tách nhỏ để tránh đứng tiến trình",
            )
            midpoint = max(len(batch) // 2, 1)
            left = review_machine_batch_via_ollama_resilient(
                batch[:midpoint],
                source_language=source_language,
                llama_cpp_available=llama_cpp_available,
                label=f"{label}.1",
                phase=phase,
                progress_hint=progress_hint,
            )
            right = review_machine_batch_via_ollama_resilient(
                batch[midpoint:],
                source_language=source_language,
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
            message=f"Gemma lỗi ở cụm {label}, đang fallback cục bộ cho cụm này",
            extra={"warning": normalize_text(str(exc))[:180]},
        )
        if llama_cpp_available:
            try:
                return review_machine_batch_via_llama_cpp(batch, source_language)
            except Exception:
                pass
        return [
            {
                "spokenText": normalize_text(item.get("translatedText") or item.get("sourceText") or ""),
                "delivery": infer_delivery_from_source(
                    item.get("sourceText") or "",
                    item.get("translatedText") or item.get("sourceText") or "",
                ),
            }
            for item in batch
        ]


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
    machine_cache_path = machine_translation_cache_path(cache_path)
    machine_cache = load_machine_translation_cache(machine_cache_path)
    cached_count = 0
    invalidated_cached_entries = 0
    prefilled_override_count = 0
    for item in segments:
        source_text = normalize_text(item.get("sourceText") or "")
        if source_text and _is_non_dialogue_sfx(source_text):
            item["translatedText"] = ""
            item["spokenText"] = ""
            item["delivery"] = "neutral"
            if translations.pop(item["id"], None) is not None:
                invalidated_cached_entries += 1
            continue
        prefilled_translated = normalize_text(item.get("translatedText") or "")
        if _has_usable_prefilled_translation(
            source_text,
            prefilled_translated,
            source_language=source_language,
            target_language=target_language,
        ):
            spoken_text = normalize_text(item.get("spokenText") or prefilled_translated)
            delivery = normalize_delivery_choice(item.get("delivery"))
            localized = translations.get(item["id"], {})
            cached_translated = normalize_text(localized.get("translatedText") or "")
            cached_spoken = normalize_text(localized.get("spokenText") or "")
            cached_delivery = normalize_delivery_choice(localized.get("delivery"))
            item["translatedText"] = prefilled_translated
            item["spokenText"] = spoken_text or prefilled_translated
            item["delivery"] = delivery
            if (
                cached_translated != item["translatedText"]
                or cached_spoken != item["spokenText"]
                or cached_delivery != item["delivery"]
            ):
                translations[item["id"]] = {
                    "translatedText": item["translatedText"],
                    "spokenText": item["spokenText"],
                    "delivery": item["delivery"],
                    "machineTranslatedText": normalize_text(
                        item.get("machineTranslatedText") or item["translatedText"]
                    ),
                }
                prefilled_override_count += 1
            continue
        localized = translations.get(item["id"], {})
        if not isinstance(localized, dict):
            continue
        cached_translated = normalize_text(
            localized.get("translatedText", item.get("translatedText", "")) or ""
        )
        if not _has_usable_prefilled_translation(
            source_text,
            cached_translated,
            source_language=source_language,
            target_language=target_language,
        ):
            if translations.pop(item["id"], None) is not None:
                invalidated_cached_entries += 1
            item["translatedText"] = ""
            item["spokenText"] = ""
            item["delivery"] = "neutral"
            item.pop("machineTranslatedText", None)
            continue
        item["translatedText"] = cached_translated
        item["spokenText"] = normalize_text(localized.get("spokenText") or item["translatedText"])
        item["delivery"] = localized.get("delivery", "neutral")
        if localized.get("machineTranslatedText"):
            item["machineTranslatedText"] = localized.get("machineTranslatedText")
        if item["translatedText"]:
            cached_count += 1
    seeded_translations = 0
    for item in segments:
        source_text = normalize_text(item.get("sourceText") or "")
        if source_text and _is_non_dialogue_sfx(source_text):
            if translations.pop(item["id"], None) is not None:
                invalidated_cached_entries += 1
            continue
        translated_text = normalize_text(item.get("translatedText") or "")
        if not translated_text or item["id"] in translations:
            continue
        if not _has_usable_prefilled_translation(
            source_text,
            translated_text,
            source_language=source_language,
            target_language=target_language,
        ):
            item["translatedText"] = ""
            item["spokenText"] = ""
            item["delivery"] = "neutral"
            item.pop("machineTranslatedText", None)
            continue
        spoken_text = normalize_text(item.get("spokenText") or translated_text)
        delivery = normalize_delivery_choice(item.get("delivery"))
        translations[item["id"]] = {
            "translatedText": translated_text,
            "spokenText": spoken_text or translated_text,
            "delivery": delivery,
            "machineTranslatedText": normalize_text(item.get("machineTranslatedText") or translated_text),
        }
        seeded_translations += 1

    source_hint = source_language if source_language in LANGUAGE_OPTIONS else "auto"
    total = max(len(segments), 1)
    normalized_target_language = normalize_text(target_language).lower() or "vi"
    try:
        use_ollama = normalized_target_language == "vi" and should_use_ollama("auto")
    except Exception:
        use_ollama = False
    try:
        use_llama_cpp = normalized_target_language == "vi" and (not use_ollama) and should_use_llama_cpp("auto")
    except Exception:
        use_llama_cpp = False
    for index, item in enumerate(segments):
        item["previousText"] = normalize_text(segments[index - 1].get("sourceText") or "") if index > 0 else ""
        item["nextText"] = normalize_text(segments[index + 1].get("sourceText") or "") if index + 1 < len(segments) else ""
        item["previousContext"] = joined_source_context(segments[max(0, index - 2):index])
        item["nextContext"] = joined_source_context(segments[index + 1:index + 3])
        source_text = normalize_text(item.get("sourceText") or "")
        translated_seed = normalize_text(item.get("machineTranslatedText") or item.get("translatedText") or "")
        if source_text and translated_seed and _has_usable_prefilled_translation(
            source_text,
            translated_seed,
            source_language=source_language,
            target_language=target_language,
        ):
            machine_cache[machine_translation_cache_key(source_text, source_hint, normalized_target_language)] = translated_seed
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
        if seeded_translations or invalidated_cached_entries or prefilled_override_count:
            persist_translation_cache(cache_path, cache_key, translations)
        return segments

    pending_updates = 0
    pending_machine_updates = 0

    def flush_translation_cache(*, force: bool = False) -> None:
        nonlocal pending_updates
        if not pending_updates:
            return
        if not force and pending_updates < 6:
            return
        persist_translation_cache(cache_path, cache_key, translations)
        pending_updates = 0
    def flush_machine_cache(*, force: bool = False) -> None:
        nonlocal pending_machine_updates
        if not pending_machine_updates:
            return
        if not force and pending_machine_updates < 10:
            return
        persist_machine_translation_cache(machine_cache_path, machine_cache)
        pending_machine_updates = 0

    def microsoft_translate_cached(text: str) -> str:
        nonlocal pending_machine_updates
        cache_entry_key = machine_translation_cache_key(text, source_hint, normalized_target_language)
        cached_translation = normalize_text(machine_cache.get(cache_entry_key) or "")
        if cached_translation:
            return cached_translation
        translated = translate_via_microsoft(text, source_hint, normalized_target_language)
        normalized_translation = normalize_text(translated or "")
        if normalized_translation:
            machine_cache[cache_entry_key] = normalized_translation
            pending_machine_updates += 1
        return normalized_translation

    def machine_progress(end_index: int) -> float:
        safe_total = max(total, 1)
        return 0.32 + (min(end_index, safe_total) / safe_total) * 0.07

    def review_progress(end_index: int) -> float:
        safe_total = max(total, 1)
        return 0.39 + (min(end_index, safe_total) / safe_total) * 0.05

    try:
        llama_cpp_available = should_use_llama_cpp("auto")
    except Exception:
        llama_cpp_available = False

    review_backend = "ollama" if use_ollama else ("llama_cpp" if use_llama_cpp else "")

    for position, item in pending_segments:
        text = normalize_text(item["sourceText"])
        emit_progress(
            phase=phase,
            step="translate",
            progress=machine_progress(position),
            message=f"Đang dịch Microsoft câu {position}/{len(segments)}",
        )
        translated = microsoft_translate_cached(text)
        if not translated or _looks_like_source_language(translated, text):
            localized_items: list[dict[str, str]] = []
            if review_backend == "ollama":
                localized_items = localize_batch_via_ollama_resilient(
                    [item],
                    source_hint=source_hint,
                    target_language=target_language,
                    llama_cpp_available=llama_cpp_available,
                    label=f"{position}",
                    phase=phase,
                    progress_hint=machine_progress(position),
                )
            elif review_backend == "llama_cpp":
                try:
                    localized_items = localize_batch_via_llama_cpp([item], source_hint, "vi")
                except Exception:
                    localized_items = []
            if not localized_items:
                localized_items = fallback_translate_items(
                    [item],
                    texts=[text],
                    source_hint=source_hint,
                    use_llama_cpp=review_backend == "llama_cpp",
                )
            translations[item["id"]] = apply_localized_result(item, localized_items[0], text)
            translations[item["id"]]["machineTranslatedText"] = translations[item["id"]]["translatedText"]
            pending_updates += 1
            flush_translation_cache()
            continue
        item["translatedText"] = translated
        item["machineTranslatedText"] = translated

    flush_machine_cache(force=True)
    for index, item in enumerate(segments):
        item["previousTranslatedText"] = normalize_text(segments[index - 1].get("translatedText") or "") if index > 0 else ""
        item["nextTranslatedText"] = normalize_text(segments[index + 1].get("translatedText") or "") if index + 1 < len(segments) else ""

    review_candidates: list[tuple[int, dict[str, Any]]] = []
    for position, item in pending_segments:
        if item["id"] in translations and normalize_text(item.get("spokenText") or ""):
            continue
        translated_text = normalize_text(item.get("translatedText") or item.get("machineTranslatedText") or "")
        if review_backend and should_review_machine_translation(item, translated_text):
            review_candidates.append((position, item))
            continue
        translations[item["id"]] = apply_machine_review_result(
            item,
            translated_text=translated_text,
            reviewed=None,
        )
        pending_updates += 1
        flush_translation_cache()

    if review_candidates and review_backend == "ollama":
        try:
            warmup_ollama_model(phase=phase, progress=0.39)
        except Exception as exc:
            emit_progress(
                phase=phase,
                step="translate",
                progress=0.39,
                message="Warm-up Gemma không hoàn tất, vẫn tiếp tục rewrite với retry tăng cường",
                extra={"warning": normalize_text(str(exc))[:180]},
            )

    for start, batch in iter_translation_batches(
        [item for _, item in review_candidates],
        batch_size=TRANSLATE_BATCH_SIZE,
        first_batch_size=TRANSLATE_FIRST_BATCH_SIZE,
    ):
        start_position = review_candidates[start][0]
        end_index = review_candidates[start + len(batch) - 1][0]
        emit_progress(
            phase=phase,
            step="translate",
            progress=review_progress(end_index),
            message=translation_progress_message(
                provider_label="Gemma",
                start=start_position - 1,
                end_index=end_index,
                total=len(segments),
            ),
        )
        if review_backend == "ollama":
            reviewed_items = review_machine_batch_via_ollama_resilient(
                batch,
                source_language=source_hint,
                llama_cpp_available=llama_cpp_available,
                label=f"{start_position}-{end_index}",
                phase=phase,
                progress_hint=review_progress(end_index),
            )
        elif review_backend == "llama_cpp":
            try:
                reviewed_items = review_machine_batch_via_llama_cpp(batch, source_hint)
            except Exception:
                reviewed_items = [
                    {
                        "spokenText": normalize_text(item.get("translatedText") or item.get("sourceText") or ""),
                        "delivery": infer_delivery_from_source(
                            item.get("sourceText") or "",
                            item.get("translatedText") or item.get("sourceText") or "",
                        ),
                    }
                    for item in batch
                ]
        else:
            reviewed_items = [
                {
                    "spokenText": normalize_text(item.get("translatedText") or item.get("sourceText") or ""),
                    "delivery": infer_delivery_from_source(
                        item.get("sourceText") or "",
                        item.get("translatedText") or item.get("sourceText") or "",
                    ),
                }
                for item in batch
                ]
        for item, reviewed in zip(batch, reviewed_items):
            translations[item["id"]] = apply_machine_review_result(
                item,
                translated_text=item.get("translatedText") or item.get("machineTranslatedText") or item.get("sourceText") or "",
                reviewed=reviewed,
            )
            pending_updates += 1
        flush_translation_cache()

    missing_dialogue_segments: list[tuple[int, dict[str, Any]]] = []
    for position, item in enumerate(segments, start=1):
        source_text = normalize_text(item.get("sourceText") or "")
        translated_text = normalize_text(
            item.get("translatedText") or item.get("machineTranslatedText") or ""
        )
        if not source_text or _is_non_dialogue_sfx(source_text):
            continue
        if translated_text and not _looks_like_source_language(translated_text, source_text):
            continue
        missing_dialogue_segments.append((position, item))

    for position, item in missing_dialogue_segments:
        source_text = normalize_text(item.get("sourceText") or "")
        emit_progress(
            phase=phase,
            step="translate",
            progress=0.445,
            message=f"Đang vá câu thoại còn thiếu {position}/{len(segments)}",
        )
        localized_items = fallback_translate_items(
            [item],
            texts=[source_text],
            source_hint=source_hint,
            use_llama_cpp=review_backend == "llama_cpp",
        )
        if localized_items:
            translations[item["id"]] = apply_localized_result(item, localized_items[0], source_text)
        translated_text = normalize_text(item.get("translatedText") or "")
        if not translated_text:
            forced_text = normalize_text(item.get("machineTranslatedText") or "") or source_text
            delivery = normalize_delivery_choice(
                item.get("delivery"),
                default=infer_delivery_from_source(source_text, forced_text),
            )
            spoken_text = (
                build_spoken_text(
                    forced_text,
                    source_text,
                    delivery=delivery,
                )
                if forced_text
                else ""
            )
            item["translatedText"] = forced_text
            item["spokenText"] = spoken_text or forced_text
            item["delivery"] = delivery
            translations[item["id"]] = {
                "translatedText": item["translatedText"],
                "spokenText": item["spokenText"],
                "delivery": item["delivery"],
                "machineTranslatedText": normalize_text(
                    item.get("machineTranslatedText") or item["translatedText"]
                ),
            }
        pending_updates += 1
        flush_translation_cache()

    flush_translation_cache(force=True)
    flush_machine_cache(force=True)
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
    clean = re.sub(r"^(video|đoạn video|phan video|phần video)\s+", "", clean, flags=re.IGNORECASE)
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
    target_clip_ms = max(7000, min(int(desired_clip_ms), 22000))
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

    min_start_ms = 0 if safe_video_duration <= 12000 else min(max(int(safe_video_duration * 0.04), 1200), max(safe_video_duration - clip_ms, 0))
    max_start_ms = max(
        min(int(safe_video_duration * 0.68), max(safe_video_duration - clip_ms - 300, 0)),
        min_start_ms,
    )
    candidate_starts: set[int] = {min_start_ms, max_start_ms}
    for segment in segments:
        raw_start_ms = int(segment.get("startMs", 0))
        if raw_start_ms > max_start_ms + clip_ms:
            continue
        for candidate_start in (
            raw_start_ms - int(clip_ms * 0.18),
            raw_start_ms - 900,
            raw_start_ms - int(clip_ms * 0.08),
            raw_start_ms,
        ):
            candidate_starts.add(min(max(int(candidate_start), min_start_ms), max_start_ms))

    best_window: dict[str, Any] | None = None
    best_score = float("-inf")
    for start_ms in sorted(candidate_starts):
        end_ms = min(start_ms + clip_ms, safe_video_duration)
        current_segments: list[dict[str, Any]] = []
        text_lengths: list[int] = []
        punctuation_hits = 0
        long_segments = 0
        for segment in segments:
            segment_start = int(segment.get("startMs", 0))
            segment_end = int(segment.get("endMs", 0))
            if segment_end <= start_ms or segment_start >= end_ms:
                continue
            text = normalize_text(segment.get("translatedText") or segment.get("sourceText") or "")
            if not text:
                continue
            current_segments.append(segment)
            compact_len = len(text.replace(" ", ""))
            text_lengths.append(min(compact_len, 90))
            if re.search(r"[!?…]", text):
                punctuation_hits += 1
            if compact_len >= 30:
                long_segments += 1

        if not current_segments:
            continue

        first_start = max(start_ms, int(current_segments[0].get("startMs", start_ms)))
        last_end = min(end_ms, int(current_segments[-1].get("endMs", end_ms)))
        narrative_span = max(last_end - first_start, 400)
        continuity_hits = 0
        for previous_segment, current_segment in zip(current_segments, current_segments[1:]):
            previous_end = int(previous_segment.get("endMs", 0))
            current_start = int(current_segment.get("startMs", 0))
            if current_start - previous_end <= 1800:
                continuity_hits += 1

        total_chars = sum(text_lengths)
        segment_count = len(current_segments)
        span_bonus = min(narrative_span / max(clip_ms, 1), 1.0)
        density_bonus = min(total_chars, 360) / 360
        continuity_bonus = min(continuity_hits, 4) * 0.18
        punctuation_bonus = min(punctuation_hits, 3) * 0.1
        segment_bonus = min(segment_count, 6) * 0.2
        long_segment_bonus = min(long_segments, 4) * 0.14
        center_ratio = ((start_ms + end_ms) / 2) / max(safe_video_duration, 1)
        position_bonus = 1.0 - min(abs(center_ratio - 0.24), 0.4)
        score = (
            density_bonus * 2.2
            + span_bonus * 1.1
            + continuity_bonus
            + punctuation_bonus
            + segment_bonus
            + long_segment_bonus
            + position_bonus
        )
        if score > best_score:
            best_score = score
            best_window = {
                "startMs": start_ms,
                "endMs": end_ms,
                "durationMs": max(end_ms - start_ms, min(safe_video_duration, 600)),
                "segments": current_segments,
            }

    if best_window:
        return best_window

    chosen = segments[min(1, len(segments) - 1)]
    start_ms = min(max(int(chosen.get("startMs", 0)) - 320, min_start_ms), max_start_ms)
    end_ms = min(start_ms + clip_ms, safe_video_duration)
    if end_ms - start_ms < clip_ms and safe_video_duration > clip_ms:
        start_ms = max(0, end_ms - clip_ms)
    fallback_segments = [
        segment
        for segment in segments
        if int(segment.get("endMs", 0)) > start_ms and int(segment.get("startMs", 0)) < end_ms
    ]
    return {
        "startMs": start_ms,
        "endMs": end_ms,
        "durationMs": max(end_ms - start_ms, min(safe_video_duration, 600)),
        "segments": fallback_segments,
    }


def build_intro_hook_text(window_segments: list[dict[str, Any]]) -> str:
    text_parts: list[str] = []
    for segment in window_segments[:4]:
        translated = normalize_text(segment.get("translatedText") or segment.get("sourceText") or "")
        if len(translated) < 10:
            continue
        fragment = clean_intro_fragment(translated, max_chars=92)
        if not fragment:
            continue
        normalized_fragment = fragment.lower()
        if any(
            normalized_fragment in existing.lower() or existing.lower() in normalized_fragment
            for existing in text_parts
        ):
            continue
        text_parts.append(fragment)
        if len(text_parts) >= 3:
            break

    if not text_parts:
        return "Mở đầu video đã là đoạn đáng chú ý nhất."
    if len(text_parts) == 1:
        return finalize_intro_text(
            "Ngay phần mở đầu, video đặt ra chuyện "
            + text_parts[0].lower().rstrip(" ,;:.!?")
            + ", và đó là nút kéo người xem vào phần còn lại."
        )

    sentences = [
        "Ngay ở mở đầu, video đặt ra chuyện " + text_parts[0].lower().rstrip(" ,;:.!?") + ".",
        "Chỉ ít giây sau, video chuyển sang cảnh " + text_parts[1].lower().rstrip(" ,;:.!?") + ".",
    ]
    if len(text_parts) >= 3:
        sentences.append(
            "Rồi teaser đẩy căng hơn với "
            + text_parts[2].lower().rstrip(" ,;:.!?")
            + "."
        )
    sentences.append("Đó mới chỉ là phần mở đầu của câu chuyện.")
    summary = " ".join(sentences)
    if summary:
        return finalize_intro_text(summary)
    summary = trim_summary_text(" ".join(text_parts), max_chars=156)
    if summary:
        return finalize_intro_text("Video này mở ra bằng cảnh " + summary.lower().rstrip(" ,;:.!?") + ".")
    return "Mở đầu video đã là đoạn đáng chú ý nhất."


def build_structured_intro_hook_text(window_segments: list[dict[str, Any]]) -> str:
    points: list[str] = []
    for segment in window_segments:
        translated = normalize_text(segment.get("translatedText") or segment.get("sourceText") or "")
        if len(translated) < 14:
            continue
        fragment = clean_intro_fragment(translated, max_chars=96)
        if len(fragment) < 10:
            continue
        normalized_fragment = fragment.lower()
        if any(
            normalized_fragment in existing.lower() or existing.lower() in normalized_fragment
            for existing in points
        ):
            continue
        points.append(fragment)
        if len(points) >= 3:
            break

    if not points:
        return "Mở đầu video đã là đoạn đáng chú ý nhất."

    if len(points) == 1:
        return finalize_intro_text(
            "Mở đầu video xoay quanh "
            + points[0].lower().rstrip(" ,;:.!?")
            + ", và chỉ riêng chi tiết này đã đủ mở ra cả phần nội dung phía sau."
        )

    sentences: list[str] = [
        "Mở đầu video cho thấy " + points[0].lower().rstrip(" ,;:.!?") + "."
    ]
    if len(points) >= 2:
        sentences.append(
            "Từ đó, mạch câu chuyện nhanh chóng chuyển sang cảnh "
            + points[1].lower().rstrip(" ,;:.!?")
            + "."
        )
    if len(points) >= 3:
        sentences.append(
            "Rồi diễn biến tiếp tục mở ra với "
            + points[2].lower().rstrip(" ,;:.!?")
            + "."
        )
    sentences.append("Chỉ riêng đoạn mở đầu này đã gợi ra khá rõ chuyện gì đang xảy ra trong video.")
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
            if generated and _intro_teaser_quality_ok(generated, clip_duration_ms=clip_duration_ms):
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
            if generated and _intro_teaser_quality_ok(generated, clip_duration_ms=clip_duration_ms):
                return finalize_intro_text(generated)
        except Exception:
            pass
    fallback_text = build_structured_intro_hook_text(window_segments)
    if _intro_teaser_quality_ok(fallback_text, clip_duration_ms=clip_duration_ms):
        return finalize_intro_text(fallback_text)
    baseline_text = build_intro_hook_text(window_segments)
    if _intro_teaser_quality_ok(baseline_text, clip_duration_ms=clip_duration_ms):
        return finalize_intro_text(baseline_text)
    if len(normalize_text(baseline_text)) > len(normalize_text(fallback_text)):
        return finalize_intro_text(baseline_text)
    return finalize_intro_text(fallback_text)
