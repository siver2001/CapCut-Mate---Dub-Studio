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

    max_retries = 5
    for attempt in range(max_retries + 1):
        try:
            request = urllib.request.Request(url, data=request_body, headers=headers, method="POST")
            with urllib.request.urlopen(request, timeout=MICROSOFT_TRANSLATOR_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
            translations = payload[0].get("translations", []) if isinstance(payload, list) and payload else []
            translated = normalize_text(translations[0].get("text") or "") if translations else ""
            if translated:
                return translated
            if attempt < max_retries:
                time.sleep(2.0)
                continue
            return ""
        except urllib.error.HTTPError as e:
            if e.code == 429:
                if attempt < max_retries:
                    time.sleep(4.0 * (attempt + 1))
                    continue
            elif attempt < max_retries:
                time.sleep(2.0 * (attempt + 1))
                continue
            return ""
        except Exception:
            if attempt < max_retries:
                time.sleep(2.0 * (attempt + 1))
                continue
            return ""
    return ""


def translate_via_google_free(text: str, source_lang: str = "auto", target_lang: str = "vi") -> str:
    clean_text = normalize_text(text)
    if not clean_text:
        return ""
    
    sl = source_lang if source_lang and source_lang.lower() != "auto" else "auto"
    tl = target_lang or "vi"
    
    query_params = {
        "client": "gtx",
        "sl": sl,
        "tl": tl,
        "dt": "t",
        "q": clean_text
    }
    url = f"https://translate.googleapis.com/translate_a/single?{urllib.parse.urlencode(query_params)}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    max_retries = 5
    for attempt in range(max_retries + 1):
        try:
            request = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(request, timeout=10.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            
            if isinstance(payload, list) and len(payload) > 0 and isinstance(payload[0], list):
                translated_parts = []
                for chunk in payload[0]:
                    if isinstance(chunk, list) and len(chunk) > 0 and chunk[0]:
                        translated_parts.append(str(chunk[0]))
                if translated_parts:
                    return normalize_text("".join(translated_parts))
            
            return ""
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2.0 * (attempt + 1))
                continue
            time.sleep(1.0 * (attempt + 1))
        except Exception:
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue
    return ""


_LOCAL_TRANSLATION_CACHE = {}

def translate_via_local_seq2seq(text: str, source_lang: str = "auto", target_lang: str = "vi") -> str:
    """Tự động tải mô hình dịch local tương ứng với ngôn ngữ nguồn để tạo bản dịch thô."""
    clean_text = normalize_text(text)
    if not clean_text:
        return ""
    
    from ..config import (
        DUB_MT5_EN2VI_MODEL,
        DUB_MT5_ZH2VI_MODEL,
        DUB_MT5_JA2VI_MODEL,
        DUB_MT5_KO2VI_MODEL,
        DUB_USE_GPU,
        HUGGINGFACE_HUB_CACHE,
    )
    
    src = str(source_lang).strip().lower()
    
    # Ánh xạ model tương ứng với 4 ngôn ngữ nguồn sang tiếng Việt
    if src in {"zh", "cn", "chinese"}:
        model_name = DUB_MT5_ZH2VI_MODEL
    elif src in {"ja", "jp", "japanese"}:
        model_name = DUB_MT5_JA2VI_MODEL
    elif src in {"ko", "kr", "korean"}:
        model_name = DUB_MT5_KO2VI_MODEL
    else:
        model_name = DUB_MT5_EN2VI_MODEL
        
    global _LOCAL_TRANSLATION_CACHE
    if model_name not in _LOCAL_TRANSLATION_CACHE:
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            
            device = "cuda" if (torch.cuda.is_available() and DUB_USE_GPU) else "cpu"
            safe_print(f"[info] Đang nạp mô hình dịch thô {src.upper()}->VI: {model_name} lên {device}...", flush=True)
            tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=HUGGINGFACE_HUB_CACHE)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name, cache_dir=HUGGINGFACE_HUB_CACHE).to(device)
            _LOCAL_TRANSLATION_CACHE[model_name] = (tokenizer, model, device)
        except Exception as e:
            safe_print(f"[error] Lỗi nạp mô hình local {model_name}: {e}. Fallback sang Google Free.", flush=True)
            return translate_via_google_free(text, source_lang, target_lang)
            
    tokenizer, model, device = _LOCAL_TRANSLATION_CACHE[model_name]
    
    try:
        if "envt5" in model_name.lower():
            input_text = f"en2vi: {clean_text}"
        else:
            input_text = clean_text
            
        import torch
        inputs = tokenizer(input_text, return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)
        with torch.no_grad():
            outputs = model.generate(**inputs, max_length=256, num_beams=4, early_stopping=True)
        translated = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return normalize_text(translated)
    except Exception as e:
        safe_print(f"[warn] Lỗi dịch qua model local {model_name}: {e}. Fallback sang Google Free.", flush=True)
        return translate_via_google_free(text, source_lang, target_lang)


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
    delivery = infer_delivery_from_source(item.get("sourceText") or translated_text, translated_text)
    item["translatedText"] = translated_text
    item["delivery"] = delivery
    item.pop("spoken" + "Text", None)
    return {
        "translatedText": item["translatedText"],
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


_PLACEHOLDER_TRANSLATION_RE = re.compile(
    r"(?:đoạn này|phần này)\s+(?:tiếp tục\s+)?(?:mô tả|nói về|trình bày)|"
    r"mô tả chi tiết trong video|"
    r"không rõ lời|không nghe rõ",
    re.IGNORECASE,
)


def _looks_like_placeholder_translation(text: str) -> bool:
    clean = normalize_text(text)
    if not clean:
        return False
    return bool(_PLACEHOLDER_TRANSLATION_RE.search(clean))


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
    if _looks_like_placeholder_translation(clean_translated):
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


def _calculate_target_spoken_chars(duration_ms: int) -> int:
    """Calculate target character count for a segment to ensure natural pacing."""
    duration_seconds = max(duration_ms, 400) / 1000.0
    # Natural Vietnamese speaking rate is around 14-16 characters per second (including spaces).
    return int(duration_seconds * 14.5)


def _estimate_translation_char_limit(
    source_text: str,
    duration_ms: int,
    *,
    spoken: bool,
) -> int:
    clean = normalize_text(source_text)
    source_len = max(len(clean), 1)
    duration_seconds = max(duration_ms, 400) / 1000.0
    # Proportional scaling: target ~13.5 chars/sec for spoken, ~11.0 for subtitles.
    # We add a small constant for short segments to allow at least 2-3 words.
    timing_cap = int(duration_seconds * (13.8 if spoken else 11.5)) + (12 if spoken else 8)
    source_cap = int(source_len * (1.2 if spoken else 1.05)) + (6 if spoken else 4)
    floor = 22 if spoken else 16
    ceiling = 110 if spoken else 84
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
        "targetSpokenChars": _calculate_target_spoken_chars(duration_ms),
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


def _ollama_translation_array_schema(item_count: int) -> dict[str, Any]:
    safe_count = max(int(item_count), 1)
    return {
        "type": "array",
        "minItems": safe_count,
        "maxItems": safe_count,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["translatedText", "delivery"],
            "properties": {
                "translatedText": {"type": "string"},
                "delivery": {
                    "type": "string",
                    "enum": ["calm", "neutral", "curious", "excited", "urgent", "suspense"],
                },
            },
        },
    }


def _build_localization_prompt(
    items_payload: list[dict[str, Any]],
    *,
    source_language: str,
    target_language: str,
    localization_mode: str = "creative",
) -> str:
    mode_instructions = ""
    if localization_mode == "creative":
        mode_instructions = (
            "- CREATIVE REWRITE: Do not just translate. Re-imagine the sentences to be as engaging, catchy, and smooth as possible for a Vietnamese audience.\n"
            "- NATURAL FLOW: Use natural Vietnamese connectors and sentence structures that sound like a professional storyteller.\n"
        )
    elif localization_mode == "vietnamese_slang":
        mode_instructions = (
            "- VIETNAMESE SLANG & GEN Z STYLE: Use natural, trendy Vietnamese slang and informal language where appropriate.\n"
            "- TRENDY PRONOUNS: Use informal pronouns like 'tui', 'ông', 'bà', 'mấy bác' if it fits the vibe.\n"
            "- CATCHY & FUN: Make the text sound like a viral TikTok video or a fun vlog.\n"
        )
    else: # literal
        mode_instructions = (
            "- ACCURATE & LITERAL: Stick closer to the original meaning while maintaining correct Vietnamese grammar.\n"
            "- FORMAL TONE: Use standard, neutral Vietnamese suitable for documentaries or news.\n"
        )

    return (
        "You are an elite Vietnamese subtitle translator and expert localization editor.\n"
        f"Source language: {source_language or 'auto-detected language'}. Target language: Vietnamese ({target_language}).\n"
        f"Localization Style: {localization_mode.replace('_', ' ').title()}\n"
        "\n"
        "CRITICAL OUTPUT RULES:\n"
        f"1. Return ONLY a valid JSON array with EXACTLY {len(items_payload)} items, same order as input.\n"
        "2. Do NOT include markdown, notes, explanations, comments, or any text outside the JSON array.\n"
        "3. Every translatedText MUST be in Vietnamese. Never echo the source language, except proper names, brands, or places.\n"
        "4. Translate every sourceText, including single words, short phrases, reactions, interjections, slang, jokes, and idioms.\n"
        "5. Do NOT leave meaningful source-language words untranslated.\n"
        "6. STRICT BAN ON CHINESE CHARACTERS: Absolutely ZERO Chinese hanzi (e.g., 堆积如山) must remain in the output. Translate EVERY single word into standard, natural Vietnamese.\n"
        "7. TRANSLATE PROPER NAMES TO SINO-VIETNAMESE: Translate all proper names, character names, and titles (especially Chinese character names and historical terms) into standard Sino-Vietnamese (Hán-Việt) for easy understanding (e.g. translate 'Zhen Huan' -> 'Chân Hoàn', 'Chunyuan' -> 'Thuần Nguyên', 'Duan' or 'Duan Fei' -> 'Đoan Phi', 'Jing' or 'Jing Fei' -> 'Kính Phi', 'Longyue' -> 'Long Nguyệt', 'Eniang' -> 'Ngạch nương', 'Wei Lin' -> 'Ngụy Lâm', etc.). Do not keep them in Pinyin/English.\n"
        "\n"
        "Each item must be a JSON object with exactly these keys:\n"
        '- "translatedText": natural, concise, captivating Vietnamese subtitle text. It MUST fit within the provided "maxSubtitleChars" or "maxSpokenChars" limits.\n'
        '- "delivery": exactly one of: calm, neutral, curious, excited, urgent, suspense.\n'
        "\n"
        "LOCALIZATION & WRITING EXCELLENCE RULES:\n"
        f"{mode_instructions}"
        "- IDIOMATIC & COHERENT: Do NOT translate word-for-word. Do not use direct literal meanings. Translate the complete contextual meaning to make sense in Vietnamese. For example, do not translate '打' as 'đánh' unless it makes sense.\n"
        "- CLARITY & FLOW: The translation must sound like a human storyteller, not a machine. Use natural Vietnamese discourse markers (nhé, nha, nè, hén) to make it sound friendly and alive.\n"
        "- WRITING EXCELLENCE: Every sentence must be 'hay' (beautiful, engaging, and catchy). Use expressive verbs and warm adjectives. Avoid stiff, formal, or robotic phrasing. If a sentence sounds dry, rewrite it to be more playful and cute.\n"
        "- ADAPTIVE LENGTH & PACING: You MUST aim for the 'targetSpokenChars' length to ensure the narrator speaks at a natural pace. If the translation is significantly shorter than the target, add natural filler words or expand the sentence. If it's too long, condense it. DO NOT leave silence gaps at the end of segments.\n"
        "- NO NONSENSE & GIBBERISH: Completely eliminate gibberish sentences and Whisper hallucinations. Rewrite them smoothly to match the pet vlog topic.\n"
        "- CONTEXTUAL COHERENCE: Ensure that the story flows logically from one segment to the next. Use the provided context to resolve ambiguities.\n"
        "- GLOBAL THEME ALIGNMENT: Ensure the vocabulary and style match the overall topic of the video (e.g., technical for tech reviews, playful for vlogs).\n"
        "- PUPPY PERSONA RULES (If Pet Vlog):\n"
        "  - Host/Narrator self-reference: 'mình' or 'Wantuan'/'Nuomin'.\n"
        "  - Addressing audience ('姨们'/'Yimen'): Use 'Các cô chú' or 'Cả nhà'. NEVER 'Các dì'.\n"
        "  - Owner reference: 'Mẹ' or 'Ba'.\n"
        "  - Specific names: 'Wantuan' (Vằn Thầu), 'Nuomin' (Nhu Mễ). Keep these names consistent.\n"
        "\n"
        "\n"
        f"{json.dumps(items_payload, ensure_ascii=False)}"
    )


def _build_global_analysis_prompt(full_transcript: str) -> str:
    """Build a prompt to analyze the global theme and style of the video."""
    return (
        "You are a master video content strategist and expert localization editor.\n"
        "Analyze the following full transcript from a video to build a deep understanding of its context.\n"
        "\n"
        "YOUR MISSION:\n"
        "1. THEME & TOPIC: Precisely identify what the video is about (e.g., 'A review of cat dental hygiene products', 'A tutorial on fixing a leaky faucet').\n"
        "2. AUDIENCE & TONE: Describe the target audience and the required emotional tone (e.g., 'Friendly advice for pet owners', 'Urgent news update', 'Playful children vlog').\n"
        "3. CHARACTER ROLES: Identify who is speaking and their relationship (e.g., 'An expert host talking to viewers', 'A person talking to their pet cat').\n"
        "4. DOMAIN GLOSSARY: List specific technical terms, brand names, or recurring nouns that must be translated correctly and consistently (e.g., 'nha chu', 'cao răng', 'kem đánh răng dành cho mèo').\n"
        "5. VIETNAMESE PRONOUNS: Choose the most natural and professional Vietnamese pronouns. Mandatory: Use 'mình' for the host/narrator self-reference unless the context is extremely formal or very specific (like child to parent).\n"
        "\n"
        "OUTPUT FORMAT: Return ONLY a valid JSON object with these keys:\n"
        '- "theme": string\n'
        '- "audience": string\n'
        '- "tone": string\n'
        '- "pronouns": string (preferred Vietnamese pronouns, mandatory: narrator self-reference = "mình")\n'
        '- "glossary": array of strings (the specific terminology to use)\n'
        "\n"
        "TRANSCRIPT FOR ANALYSIS:\n"
        f"{full_transcript[:7500]}"
    )


def analyze_global_context_via_ollama(
    segments: list[dict[str, Any]],
    *,
    phase: str = "render",
) -> dict[str, Any]:
    """Analyze the full transcript to provide global context for translation."""
    full_text = " ".join([normalize_text(s.get("sourceText") or "") for s in segments])
    if not full_text.strip():
        return {}

    emit_progress(
        phase=phase,
        step="translate",
        progress=0.31,
        message="Đang phân tích toàn bộ ngữ cảnh video để tối ưu hóa bản dịch...",
    )

    try:
        prompt = _build_global_analysis_prompt(full_text)
        response = run_ollama_prompt(
            prompt,
            max_tokens=800,
            temperature=0.1,
            timeout=60,
        )
        
        # Resilient JSON extraction
        clean_response = response.strip()
        if "```json" in clean_response:
            clean_response = clean_response.split("```json")[-1].split("```")[0].strip()
        elif "```" in clean_response:
            clean_response = clean_response.split("```")[-1].split("```")[0].strip()
            
        # Aggressive cleanup of trailing commas and non-JSON text
        clean_response = re.sub(r',\s*([\]}])', r'\1', clean_response)
        
        try:
            analysis = json.loads(clean_response)
        except Exception:
            # Last resort: find the first { and last }
            start = clean_response.find('{')
            end = clean_response.rfind('}')
            if start != -1 and end != -1:
                try:
                    analysis = json.loads(clean_response[start:end+1])
                except:
                    analysis = {}
            else:
                analysis = {}
                
        if isinstance(analysis, dict):
            safe_print(f"[info] Đã xác định ngữ cảnh video: {analysis.get('theme', 'N/A')} ({analysis.get('tone', 'N/A')})", flush=True)
            return analysis
    except Exception as exc:
        safe_print(f"[warn] Không thể phân tích ngữ cảnh toàn cục: {exc}", flush=True)
        # Fallback: try one more time with a simpler prompt if JSON failed
        try:
             simple_response = run_ollama_prompt("Summarize the theme and character pronouns of this transcript as JSON: " + full_text[:2000], max_tokens=200)
             return parse_json_response_payload(simple_response) or {}
        except:
             pass
    return {}


def should_review_machine_translation(item: dict[str, Any], translated_text: str) -> bool:
    # Luôn review toàn bộ bản dịch máy để đạt chất lượng văn phong thuyết minh cao nhất,
    # đặc biệt với các video tài liệu động vật/khoa học hoặc ngôn ngữ phi Trung Quốc.
    if not normalize_text(translated_text):
        return False
    return True


def _compact_machine_review_item(
    item: dict[str, Any],
    *,
    index: int,
    batch: list[dict[str, Any]],
) -> dict[str, Any]:
    source_text = normalize_text(item.get("sourceText") or "")
    machine_translated = normalize_text(item.get("translatedText") or "")
    duration_ms = max(int(item.get("endMs", 0)) - int(item.get("startMs", 0)), 400)
    compact_item: dict[str, Any] = {
        "index": index,
        "sourceText": source_text,
        "machineTranslatedText": machine_translated,
        "durationMs": duration_ms,
        "speakerId": item.get("speakerId") or "speaker_1",
        "maxSpokenChars": _estimate_translation_char_limit(machine_translated or source_text, duration_ms, spoken=True),
        "targetSpokenChars": _calculate_target_spoken_chars(duration_ms),
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
    localization_mode: str = "creative",
) -> str:
    mode_instructions = ""
    if localization_mode == "creative":
        mode_instructions = (
            "- CREATIVE STORYTELLING: Rewrite the draft to be catchy, smooth, and emotionally engaging.\n"
            "- NATURAL CADENCE: Sentences must sound like they are spoken by a native human narrator, not a machine.\n"
        )
    elif localization_mode == "vietnamese_slang":
        mode_instructions = (
            "- SLANG & VIBE: Use Gen Z slang and informal expressions naturally where it fits the tone.\n"
        )
    else: # literal
        mode_instructions = (
            "- ACCURATE & FORMAL: Ensure high fidelity to the original meaning with a professional tone.\n"
        )

    return (
        "You are a Senior Vietnamese Script Editor. Your goal is to make the video script 'cực kỳ hay' (exceptionally engaging and natural).\n"
        "Your mission is to fix broken machine translations and turn them into professional, charming, and logical video scripts.\n"
        f"Source language: {source_language or 'auto-detected language'}.\n"
        f"Style: {localization_mode.replace('_', ' ').title()}\n"
        "\n"
        "WRITING EXCELLENCE & PET VLOG RULES:\n"
        "1. BE CREATIVE: Rewrite sentences to be catchy and emotionally resonant. Use natural Vietnamese idioms and wordplay where appropriate.\n"
        "2. PUPPY CHARM: The narrator is a cute puppy. Use cute particles (nè, nha, nhé, cơ, á). Self-reference = 'mình'.\n"
        "3. PROPER NAMES: Strictly keep 'Wantuan' and 'Nuomin'. Avoid literal transliterations.\n"
        "4. AUDIENCE: Translate audience labels as 'Các cô chú' or 'Cả nhà'.\n"
        "5. TONE: High energy, playful, and expressive. Every segment must sound like it was written by a professional content creator.\n"
        "6. PACING: Aim for 'targetSpokenChars'. If a segment is long (high duration), expand the text to avoid silence. If short, condense it.\n"
        "7. LANGUAGE-SPECIFIC POLISHING:\n"
        "   - English: Avoid literal word-by-word translations, use natural spoken Vietnamese structures.\n"
        "   - Chinese: Convert rigid Sino-Vietnamese (Hán-Việt) terms into standard modern colloquial Vietnamese.\n"
        "   - Japanese & Korean: Since the raw translation might be stiff due to agglutinative grammar and particles (e.g. passive voices, auxiliary verbs), smooth it out into direct, active, and clean Vietnamese sentences.\n"
        "\n"
        "OUTPUT REQUIREMENT:\n"
        f"- Return ONLY a valid JSON array of exactly {len(items_payload)} items.\n"
        "- Format: [{\"translatedText\": \"...\", \"delivery\": \"...\"}, ...]\n"
        "\n"
        "BATCH TO PROCESS:\n"
        + json.dumps(items_payload, ensure_ascii=False)
    )


def _clean_filler_words(text: str) -> str:
    """Remove common filler words and stutters from the source text before translation."""
    # List of common fillers across languages (English, Vietnamese, Chinese, etc.)
    fillers = [
        r"\b(uhm|uh|ah|erm|um|well|you\s+know|like|actually|basically|i\s+mean)\b",
        r"\b(ừm|ờ|hà|vâng|dạ|thì|là|mà|ấy|cái)\b",
    ]
    cleaned = text
    for pattern in fillers:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    # Remove redundant whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # If cleaning made it empty but original had content, return original to be safe
    return cleaned if (cleaned or not text) else text


def review_machine_batch_via_ollama(
    batch, source_language, timeout=150, global_context=None
) -> list[dict[str, str]]:
    items_payload = _build_machine_review_items_payload(batch)
    
    # Inject global context into the prompt
    context_str = ""
    if global_context:
        context_str = (
            "\nGLOBAL VIDEO CONTEXT:\n"
            f"- Theme: {global_context.get('theme', 'N/A')}\n"
            f"- Tone: {global_context.get('tone', 'N/A')}\n"
            f"- Preferred Pronouns: {global_context.get('pronouns', 'N/A')}\n"
            f"- Key Terms: {', '.join(global_context.get('glossary', []))}\n"
        )

    base_prompt = _build_machine_review_prompt(items_payload, source_language=source_language)
    if context_str:
        # Insert context after the first couple of lines of the prompt
        lines = base_prompt.split("\n")
        # Find where to insert (usually after "Localization Style: ...")
        insert_idx = 4
        for i, line in enumerate(lines):
            if "Localization Style:" in line:
                insert_idx = i + 1
                break
        lines.insert(insert_idx, context_str)
        prompt = "\n".join(lines)
    else:
        prompt = base_prompt

    reviewed = parse_json_response_payload(
        run_ollama_prompt(
            prompt,
            max_tokens=_estimate_machine_review_max_tokens(items_payload),
            temperature=0.35,
            timeout=timeout,
            json_schema=_ollama_translation_array_schema(len(items_payload)),
        )
    )
    return _normalize_machine_review_items(batch, reviewed)


def _normalize_machine_review_items(
    batch: list[dict[str, Any]],
    reviewed: Any,
) -> list[dict[str, str]]:
    if isinstance(reviewed, dict):
        if len(batch) == 1 and "translatedText" in reviewed:
            reviewed = [reviewed]
        else:
            raise RuntimeError("Ollama review response must be a JSON array.")
    if not isinstance(reviewed, list) or len(reviewed) != len(batch):
        raise RuntimeError(
            f"Ollama review trả về không khớp số lượng (nhận {len(reviewed) if isinstance(reviewed, list) else 0}, cần {len(batch)})."
        )
    normalized_items: list[dict[str, str]] = []
    for item, source in zip(reviewed, batch):
        if not isinstance(item, dict):
            raise RuntimeError("Ollama review item must be a JSON object.")
        translated_text = normalize_text(
            item.get("translatedText")
            or source.get("translatedText")
            or source.get("sourceText")
            or ""
        )
        delivery = normalize_delivery_choice(
            item.get("delivery"),
            default=infer_delivery_from_source(source.get("sourceText") or "", translated_text),
        )
        normalized_items.append(
            {
                "translatedText": translated_text,
                "delivery": delivery,
            }
        )
    return normalized_items


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
    machine_translated_text: str,
    reviewed: dict[str, Any] | None = None,
) -> dict[str, str]:
    source_text = item.get("sourceText") or ""
    reviewed_text = (reviewed or {}).get("translatedText") or ""
    
    # Final result is chosen from machine draft vs AI refinement
    final_text = pick_best_localized_text(
        machine_translated_text,
        reviewed_text,
        source_text,
    )
    
    delivery = normalize_delivery_choice(
        (reviewed or {}).get("delivery"),
        default=infer_delivery_from_source(source_text, final_text),
    )
    
    item["translatedText"] = final_text
    item["delivery"] = delivery
    item["machineTranslatedText"] = machine_translated_text
    item.pop("spoken" + "Text", None)
    
    return {
        "translatedText": final_text,
        "delivery": delivery,
        "machineTranslatedText": machine_translated_text,
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
    localization_mode: str = "creative",
) -> list[dict[str, str]]:
    """Translate a batch of segments using Ollama API."""
    items_payload = _build_localization_items_payload(batch)
    prompt = _build_localization_prompt(
        items_payload,
        source_language=source_language,
        target_language=target_language,
        localization_mode=localization_mode,
    )
    localized = parse_json_response_payload(
        run_ollama_prompt(
            prompt,
            max_tokens=_estimate_localize_max_tokens(items_payload),
            temperature=max(0.05, min(OLLAMA_TEMP, 0.12)),
            timeout=timeout,
            json_schema=_ollama_translation_array_schema(len(items_payload)),
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
            f"Ollama trả về kết quả không khớp số lượng (nhận {len(localized) if isinstance(localized, list) else 0}, cần {len(batch)})."
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
            "",
            source_text,
        )
        translated_text = prefer_minh_cau_pair(
            translated_seed,
            source_text,
        )
        delivery = normalize_text(item.get("delivery") or "neutral").lower()
        if delivery not in {"calm", "neutral", "curious", "excited", "urgent", "suspense"}:
            delivery = "neutral"
        normalized_items.append(
            {
                "translatedText": translated_text,
                "delivery": delivery,
            }
        )

    for i in range(1, len(normalized_items)):
        if normalize_text(normalized_items[i]["translatedText"]) == normalize_text(normalized_items[i-1]["translatedText"]):
            s_prev = normalize_text(batch[i-1].get("sourceText") or "")
            s_curr = normalize_text(batch[i].get("sourceText") or "")
            if s_prev != s_curr:
                try:
                    new_t = translate_via_microsoft(batch[i].get("sourceText") or "", "auto", "vi")
                    if normalize_text(new_t) != normalize_text(normalized_items[i-1]["translatedText"]):
                        normalized_items[i]["translatedText"] = new_t
                except Exception:
                    pass

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
    clip_seconds = max(int(clip_duration_ms), 2000) / 1000.0
    # Natural Vietnamese speaking rate is around 3.0 to 3.5 words per second.
    # We calibrate exact boundaries to ensure TTS narration doesn't get slowed down or too fast.
    min_words = max(12, min(65, int(round(clip_seconds * 2.8))))
    max_words = max(min_words + 6, min(75, int(round(clip_seconds * 3.4))))
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
    word_count = _count_intro_words(clean)
    sentence_count = _count_intro_sentences(clean)
    if sentence_count < 3:
        return False
    min_words, max_words = _intro_word_range(clip_duration_ms)
    # Enforce a rich, detailed storytelling teaser
    if word_count < min_words:
        return False
    if word_count > max_words:
        return False
    if len(clean) < 140:
        return False
    return True


def _load_copywriting_patterns(video_theme: str = "") -> list[dict[str, Any]]:
    """
    Loads copywriting hook patterns from config/copywriting_hooks_db.json.
    If video_theme is provided, uses LlamaIndex semantic retrieval to select the
    top 3 most contextually relevant hook templates based on the video's theme/climax.
    """
    hooks_path = ROOT / "config" / "copywriting_hooks_db.json"
    if not hooks_path.exists():
        # Fallback default patterns
        return [
            {
                "name": "contrarian",
                "description": "Đi ngược lại lầm tưởng số đông để kích thích phản biện.",
                "hook_format": "Mọi người thường nghĩ {misconception}, nhưng thực tế là {reality}."
            },
            {
                "name": "curiosity_gap",
                "description": "Tạo ra một khoảng trống tò mò về một sự kiện bất ngờ.",
                "hook_format": "Đây là lý do tại sao {surprise_event} lại xảy ra, và nó sẽ khiến bạn kinh ngạc."
            },
            {
                "name": "result_first",
                "description": "Đưa ngay kết quả hoặc thành tựu bất ngờ nhất lên làm điểm nhấn.",
                "hook_format": "Chúng mình đã đạt được {result} chỉ bằng cách {unexpected_action}."
            }
        ]

    try:
        raw_db = json.loads(hooks_path.read_text(encoding="utf-8"))
        all_hooks = raw_db.get("hooks", [])
        if not video_theme or not all_hooks:
            return all_hooks[:3]

        # Use LlamaIndex to semantically search the best hooks!
        from .runtime import ensure_llamaindex_runtime
        ensure_llamaindex_runtime(phase="render", step="intro_hook", progress=0.86)

        from llama_index.core import Document, VectorStoreIndex, Settings
        from llama_index.llms.gemini import Gemini
        from llama_index.embeddings.gemini import GeminiEmbedding

        api_key = os.getenv("DUB_CLOUD_API_KEY", "").strip()
        if not api_key:
            return all_hooks[:3]

        # Configure LlamaIndex to use Gemini Cloud Services
        Settings.llm = Gemini(model="models/gemini-2.5-flash", api_key=api_key)
        Settings.embed_model = GeminiEmbedding(model_name="models/gemini-embedding-001", api_key=api_key)

        documents = []
        for hook in all_hooks:
            text = f"Category: {hook.get('category')}\nMood: {hook.get('mood')}\nTemplate: {hook.get('template')}\nExample: {hook.get('example')}"
            doc = Document(text=text, extra_info={"id": hook.get("id"), "category": hook.get("category"), "template": hook.get("template")})
            documents.append(doc)
        index = VectorStoreIndex.from_documents(documents)
        retriever = index.as_retriever(similarity_top_k=3)
        retrieved_nodes = retriever.retrieve(video_theme)

        selected_hooks = []
        for node in retrieved_nodes:
            metadata = node.node.metadata
            selected_hooks.append({
                "name": metadata.get("category"),
                "description": f"Emotional style: {node.node.text.splitlines()[1]}",
                "hook_format": metadata.get("template")
            })
        
        if selected_hooks:
            safe_print(f"[llamaindex] Retrieved {len(selected_hooks)} matching copywriting hooks semantically.", flush=True)
            return selected_hooks
    except Exception as exc:
        safe_print(f"[llamaindex] Error during copywriting retrieval: {exc}", flush=True)
        
    return all_hooks[:3]


def _score_teaser_copy(text: str) -> float:
    """
    Algorithmic NLP Copywriting Scorer:
    Evaluates a teaser draft based on word count, audience engagement, kịch tính (but-therefore),
    direct addressing words, and strong viral starting hook phrases.
    """
    if not text or len(text.strip()) < 10:
        return 0.0
    
    score = 0.0
    words = text.split()
    word_count = len(words)
    
    # 1. Optimal teaser length: target 35 to 65 words, cap at 75
    if 35 <= word_count <= 65:
        score += 15.0
    elif 15 <= word_count < 35:
        score += 8.0
    elif 65 < word_count <= 75:
        score += 5.0
    else:
        score -= 10.0  # Penalize over 75 words or under 15 words
        
    # 2. Audience engagement & Direct address (Xưng hô trực tiếp)
    lower = text.lower()
    address_words = ("bạn", "của bạn", "chúng mình", "chúng ta", "mình")
    for aw in address_words:
        if aw in lower:
            score += 4.0
            
    # 3. Dynamic Narrative and Tension (But-Therefore connectors)
    # Checks for presence of contrast/cause-and-effect transitions
    tension_connectors = ("nhưng", "tuy nhiên", "do đó", "vì thế", "thế nên", "bất ngờ", "lý do tại sao")
    for tc in tension_connectors:
        if tc in lower:
            score += 3.0
            
    # 4. Curiosity-triggering power words
    power_words = ("bí mật", "sự thật", "không ngờ", "kinh ngạc", "tiết lộ", "khám phá", "lần đầu tiên")
    for pw in power_words:
        if pw in lower:
            score += 3.0

    # 5. High-Retention Hook Sentence (first 7 words)
    first_sentence = re.split(r'[.!?…]+', text)[0].strip().lower() if text else ""
    first_words = first_sentence.split()[:7]
    first_phrase = " ".join(first_words)
    
    viral_hooks = ("đừng bao giờ", "sự thật", "bất ngờ", "lý do tại sao", "tiết lộ", "bí mật", "cảnh báo", "tin được không", "chưa từng", "ai cũng nghĩ", "mọi người thường")
    for hook in viral_hooks:
        if hook in first_phrase:
            score += 8.0
            
    return max(0.0, score)


def _build_intro_teaser_prompt(
    window_segments: list[dict[str, Any]],
    *,
    all_segments: list[dict[str, Any]] | None = None,
    source_language: str,
    clip_duration_ms: int,
    video_theme: str = "",
    retry_reason: str = "",
) -> str:
    # A rich, detailed storytelling teaser
    min_words, max_words = _intro_word_range(clip_duration_ms)
    patterns = _load_copywriting_patterns(video_theme)
    patterns_str = json.dumps(patterns, ensure_ascii=False, indent=2)
    
    # Format the full timeline context if available
    full_timeline = all_segments if all_segments is not None else window_segments
    full_timeline_payload = _build_intro_generation_payload(full_timeline)
    highlight_timeline_payload = _build_intro_generation_payload(window_segments)
    
    retry_block = (
        f"\nPrevious attempt failed because of this issue: {retry_reason}. "
        "Remember, do NOT use generic sentences or cliches. Write a concrete story with concrete facts!\n"
        if retry_reason
        else "\n"
    )
    
    return (
        "You are an expert Vietnamese social media copywriter and storytelling strategist.\n"
        "Your task is to analyze the full video kịch bản/timeline and draft exactly THREE distinct "
        "variations of a short, highly engaging, high-retention teaser script in Vietnamese (about 3-4 sentences, 35-70 words total).\n"
        "\n"
        "CONTEXT:\n"
        f"- Full Video Timeline (The entire story): {json.dumps(full_timeline_payload, ensure_ascii=False)}\n"
        f"- Highlight Scenes to show during teaser: {json.dumps(highlight_timeline_payload, ensure_ascii=False)}\n"
        "\n"
        "STORYTELLING REQUIREMENTS:\n"
        "- The teaser MUST be 100% true and accurate to the full video timeline. Use names, facts, and concrete actions from the kịch bản.\n"
        "- Focus on grabbing the audience's attention by highlighting the main conflict/climax described in the timeline.\n"
        "- Open with a strong, punchy hook sentence (first 6 words / under 1.5 seconds) designed to instantly trigger curiosity (e.g. 'Đừng bao giờ...', 'Sự thật bất ngờ về...', 'Đây là lý do tại sao...').\n"
        "- Write in a conversational, enthusiastic spoken Vietnamese tone. Avoid formal, robotic, or direct translations. Use natural pronouns ('mình', 'các bạn', 'chúng mình').\n"
        f"- Target word count: Write exactly between {min_words} and {max_words} spoken Vietnamese words per version.\n"
        "- Never use hashtags, emojis, or markdown formatting.\n"
        "\n"
        "Each variation should be inspired by one of the three copywriting frameworks retrieved semantically below:\n"
        f"{patterns_str}\n"
        "\n"
        "OUTPUT FORMAT:\n"
        "You MUST return a single JSON object containing a list of the three candidates exactly like this:\n"
        '{\n'
        '  "candidates": [\n'
        '    {\n'
        '      "pattern": "<first framework name>",\n'
        '      "teaser": "<Vietnamese teaser text adhering to the first structure>"\n'
        '    },\n'
        '    {\n'
        '      "pattern": "<second framework name>",\n'
        '      "teaser": "<Vietnamese teaser text adhering to the second structure>"\n'
        '    },\n'
        '    {\n'
        '      "pattern": "<third framework name>",\n'
        '      "teaser": "<Vietnamese teaser text adhering to the third structure>"\n'
        '    }\n'
        '  ]\n'
        '}\n'
        f"{retry_block}"
    )


def generate_intro_hook_via_ollama(
    window_segments: list[dict[str, Any]],
    *,
    all_segments: list[dict[str, Any]] | None = None,
    source_language: str,
    clip_duration_ms: int,
) -> str:
    """Generate a Vietnamese intro teaser hook using LlamaIndex to structure the narrative and score it via Python."""
    video_theme = ""
    api_key = os.getenv("DUB_CLOUD_API_KEY", "").strip()
    
    # Step 1: Use LlamaIndex to query the climax/theme of the segments
    full_timeline = all_segments if all_segments is not None else window_segments
    if api_key and full_timeline:
        try:
            from .runtime import ensure_llamaindex_runtime
            ensure_llamaindex_runtime(phase="render", step="intro_hook", progress=0.86)

            from llama_index.core import Document, SummaryIndex, Settings
            from llama_index.llms.gemini import Gemini
            from llama_index.embeddings.gemini import GeminiEmbedding

            Settings.llm = Gemini(model="models/gemini-2.5-flash", api_key=api_key)
            Settings.embed_model = GeminiEmbedding(model_name="models/gemini-embedding-001", api_key=api_key)

            docs = [Document(text=f"Time: {s.get('startMs')}-{s.get('endMs')}ms. Context: {s.get('translatedText') or s.get('sourceText')}") for s in full_timeline]
            summary_index = SummaryIndex.from_documents(docs)
            query_engine = summary_index.as_query_engine()
            
            # Semantic narrative analysis of the whole video kịch bản
            response = query_engine.query("Tóm tắt ngắn gọn chủ đề chính, mâu thuẫn chính hoặc điểm cao trào kịch tính nhất của kịch bản video này bằng một câu ngắn tiếng Việt.")
            video_theme = str(response).strip()
            safe_print(f"[llamaindex] Extracted video story theme: '{video_theme}'", flush=True)
        except Exception as exc:
            safe_print(f"[llamaindex] Error querying story theme: {exc}", flush=True)

    # Step 2: Request kịch bản drafts matching the semantically-retrieved hooks
    for attempt in range(2):
        prompt = _build_intro_teaser_prompt(
            window_segments,
            all_segments=all_segments,
            source_language=source_language,
            clip_duration_ms=clip_duration_ms,
            video_theme=video_theme,
            retry_reason=("too_short" if attempt else ""),
        )
        try:
            raw_response = run_ollama_prompt(
                prompt,
                max_tokens=768,
                temperature=0.4,
                timeout=55,
            )
            payload = parse_json_response_payload(raw_response)
        except Exception:
            payload = {}
            
        candidates = payload.get("candidates") or []
        if not candidates and isinstance(payload, dict) and "teaser" in payload:
            candidates = [{"pattern": "default", "teaser": payload["teaser"]}]
            
        scored_candidates = []
        for cand in candidates:
            teaser_text = cand.get("teaser") or ""
            score = _score_teaser_copy(teaser_text)
            scored_candidates.append((score, teaser_text))
            
        if scored_candidates:
            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_teaser = scored_candidates[0]
            if best_teaser and len(best_teaser.strip()) > 15:
                safe_print(f"[copywriting] Best candidate chosen: score={best_score:.1f}, text='{best_teaser}'", flush=True)
                return best_teaser
                
    return build_structured_intro_hook_text(window_segments)


def localize_batch_via_llama_cpp(
    batch: list[dict[str, Any]],
    source_language: str,
    target_language: str = "vi",
    localization_mode: str = "creative",
) -> list[dict[str, str]]:
    items_payload = _build_localization_items_payload(batch)
    prompt = _build_localization_prompt(
        items_payload,
        source_language=source_language,
        target_language=target_language,
        localization_mode=localization_mode,
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
            "",
            source_text,
        )
        translated_text = prefer_minh_cau_pair(
            translated_seed,
            source_text,
        )
        delivery = normalize_text(item.get("delivery") or "neutral").lower()
        if delivery not in {"calm", "neutral", "curious", "excited", "urgent", "suspense"}:
            delivery = "neutral"
        normalized_items.append(
            {
                "translatedText": translated_text,
                "delivery": delivery,
            }
        )
    return normalized_items


def generate_intro_hook_via_llama_cpp(
    window_segments: list[dict[str, Any]],
    *,
    all_segments: list[dict[str, Any]] | None = None,
    source_language: str,
    clip_duration_ms: int,
) -> str:
    hook = ""
    for attempt in range(2):
        prompt = _build_intro_teaser_prompt(
            window_segments,
            all_segments=all_segments,
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
        if _intro_teaser_quality_ok(hook, clip_duration_ms=clip_duration_ms):
            return hook
    return hook


def fallback_translate_items(
    batch: list[dict[str, Any]],
    *,
    texts: list[str],
    source_hint: str,
    use_llama_cpp: bool,
    localization_mode: str = "creative",
) -> list[dict[str, str]]:
    if use_llama_cpp:
        try:
            return localize_batch_via_llama_cpp(batch, source_hint, "vi", localization_mode=localization_mode)
        except Exception:
            pass
    localized_items: list[dict[str, str]] = []
    for text, source_item in zip(texts, batch):
        translated = ""
        try:
            if MICROSOFT_TRANSLATOR_KEY:
                translated = translate_via_microsoft(text, source_hint, "vi") if text else ""
        except Exception:
            translated = ""
            
        if not translated:
            try:
                translated = translate_via_google_free(text, source_hint, "vi") if text else ""
            except Exception:
                translated = ""

        source_text = source_item.get("sourceText") or ""
        translated_seed = pick_best_localized_text(
            translated,
            "",
            source_text,
        )
        translated = prefer_minh_cau_pair(translated_seed, source_text)
        localized_items.append(
            {
                "translatedText": translated,
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
    localization_mode: str = "creative",
) -> list[dict[str, str]]:
    texts = [normalize_text(item.get("sourceText") or "") for item in batch]
    try:
        return localize_batch_via_ollama(batch, source_hint, target_language, localization_mode=localization_mode)
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
                        localization_mode=localization_mode,
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
        localization_mode=localization_mode,
    )


def review_machine_batch_via_ollama_resilient(
    batch: list[dict[str, Any]],
    *,
    source_language: str,
    llama_cpp_available: bool,
    label: str,
    phase: str,
    progress_hint: float,
    global_context: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    try:
        return review_machine_batch_via_ollama(batch, source_language, global_context=global_context)
    except Exception as exc:
        if len(batch) == 1:
            extended_timeout = min(OLLAMA_MAX_TIMEOUT, OLLAMA_TIMEOUT + 90)
            if extended_timeout > OLLAMA_TIMEOUT:
                emit_progress(
                    phase=phase,
                    step="translate",
                    progress=progress_hint,
                    message=f"Ollama chậm ở cụm {label}, thử lại riêng cụm này với timeout={extended_timeout}s",
                )
                try:
                    return review_machine_batch_via_ollama(
                        batch,
                        source_language,
                        timeout=extended_timeout,
                        global_context=global_context,
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
            left = review_machine_batch_via_ollama_resilient(
                batch[:midpoint],
                source_language=source_language,
                llama_cpp_available=llama_cpp_available,
                label=f"{label}.1",
                phase=phase,
                progress_hint=progress_hint,
                global_context=global_context,
            )
            right = review_machine_batch_via_ollama_resilient(
                batch[midpoint:],
                source_language=source_language,
                llama_cpp_available=llama_cpp_available,
                label=f"{label}.2",
                phase=phase,
                progress_hint=progress_hint,
                global_context=global_context,
            )
            return left + right
        emit_progress(
            phase=phase,
            step="translate",
            progress=progress_hint,
            message=f"Ollama lỗi ở cụm {label}, đang fallback cục bộ cho cụm này",
            extra={"warning": normalize_text(str(exc))[:180]},
        )
        if llama_cpp_available:
            try:
                return review_machine_batch_via_llama_cpp(batch, source_language)
            except Exception:
                pass
        return [
            {
                "translatedText": normalize_text(item.get("translatedText") or item.get("sourceText") or ""),
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
    localization_mode: str = "creative",
) -> list[dict[str, Any]]:
    cache_key = hashlib.sha1(
        json.dumps(
            {
                "translationPromptVersion": TRANSLATION_PROMPT_VERSION,
                "sourceLanguage": source_language,
                "targetLanguage": target_language,
                "localizationMode": localization_mode,
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
            item["delivery"] = "neutral"
            item.pop("spoken" + "Text", None)
            if translations.pop(item["id"], None) is not None:
                invalidated_cached_entries += 1
            continue
        localized = translations.get(item["id"], {})
        if isinstance(localized, dict):
            cached_translated = normalize_text(
                localized.get("translatedText", item.get("translatedText", "")) or ""
            )
            if _has_usable_prefilled_translation(
                source_text,
                cached_translated,
                source_language=source_language,
                target_language=target_language,
            ):
                item["translatedText"] = cached_translated
                item["delivery"] = localized.get("delivery", "neutral")
                item.pop("spoken" + "Text", None)
                if localized.get("machineTranslatedText"):
                    item["machineTranslatedText"] = localized.get("machineTranslatedText")
                if item["translatedText"]:
                    cached_count += 1
                continue
            if translations.pop(item["id"], None) is not None:
                invalidated_cached_entries += 1
        prefilled_translated = normalize_text(item.get("translatedText") or "")
        if _has_usable_prefilled_translation(
            source_text,
            prefilled_translated,
            source_language=source_language,
            target_language=target_language,
        ):
            delivery = normalize_delivery_choice(item.get("delivery"))
            localized = translations.get(item["id"], {})
            cached_translated = normalize_text(localized.get("translatedText") or "")
            cached_delivery = normalize_delivery_choice(localized.get("delivery"))
            item["translatedText"] = prefilled_translated
            item["delivery"] = delivery
            item.pop("spoken" + "Text", None)
            if (
                cached_translated != item["translatedText"]
                or cached_delivery != item["delivery"]
            ):
                translations[item["id"]] = {
                    "translatedText": item["translatedText"],
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
            item["delivery"] = "neutral"
            item.pop("spoken" + "Text", None)
            item.pop("machineTranslatedText", None)
            continue
        item["translatedText"] = cached_translated
        item["delivery"] = localized.get("delivery", "neutral")
        item.pop("spoken" + "Text", None)
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
            item["delivery"] = "neutral"
            item.pop("spoken" + "Text", None)
            item.pop("machineTranslatedText", None)
            continue
        delivery = normalize_delivery_choice(item.get("delivery"))
        translations[item["id"]] = {
            "translatedText": translated_text,
            "delivery": delivery,
            "machineTranslatedText": normalize_text(item.get("machineTranslatedText") or translated_text),
        }
        seeded_translations += 1

    source_hint = source_language if source_language in LANGUAGE_OPTIONS else "auto"
    total = max(len(segments), 1)
    normalized_target_language = normalize_text(target_language).lower() or "vi"
    try:
        provider = str(os.getenv("DUB_TRANSLATE_PROVIDER") or DUB_TRANSLATE_PROVIDER).lower().strip()
        if provider == "microsoft":
            use_ollama = False
            use_llama_cpp = False
        elif provider == "google":
            use_ollama = False
            use_llama_cpp = False
        else:
            use_ollama = normalized_target_language == "vi" and should_use_ollama(provider if provider == "ollama" else "auto")
            use_llama_cpp = normalized_target_language == "vi" and (not use_ollama) and should_use_llama_cpp("auto")
    except Exception:
        use_ollama = False
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
            item["delivery"] = "neutral"
            item.pop("spoken" + "Text", None)
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
        # Pre-process: Clean filler words from source text to improve MT quality
        raw_source = item.get("sourceText") or ""
        cleaned_source = _clean_filler_words(raw_source)
        item["sourceText"] = cleaned_source
        
        text = normalize_text(cleaned_source)
        provider = str(os.getenv("DUB_TRANSLATE_PROVIDER") or DUB_TRANSLATE_PROVIDER).lower().strip()
        if provider in {"ollama", "auto"}:
            translated = ""
        elif provider == "mt5":
            emit_progress(
                phase=phase,
                step="translate",
                progress=machine_progress(position),
                message=f"Đang dịch thô local (Seq2Seq) câu {position}/{len(segments)}",
            )
            try:
                translated = translate_via_local_seq2seq(text, source_hint, normalized_target_language)
            except Exception as e:
                safe_print(f"[warn] Lỗi dịch thô local câu {position}: {e}, fallback Google Free", flush=True)
                try:
                    translated = translate_via_google_free(text, source_hint, normalized_target_language)
                except Exception:
                    translated = ""
        elif provider == "google":
            try:
                translated = translate_via_google_free(text, source_hint, normalized_target_language)
            except Exception:
                translated = ""
        else:
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
            translations[item["id"]]["machineTranslatedText"] = text if _looks_like_source_language(text, source_text) else text
            pending_updates += 1
            flush_translation_cache()
            continue
        item["translatedText"] = translated
        # Do not overwrite machineTranslatedText here if it already exists
        if not item.get("machineTranslatedText"):
            item["machineTranslatedText"] = translated

    flush_machine_cache(force=True)
    
    review_candidates: list[tuple[int, dict[str, Any]]] = []
    
    # NEW: Global Context Analysis - understand the whole video before refining
    global_context = None
    if review_backend == "ollama":
        global_context = analyze_global_context_via_ollama(segments, phase=phase)

    for index, item in enumerate(segments):
        item["previousTranslatedText"] = normalize_text(segments[index - 1].get("translatedText") or "") if index > 0 else ""
        item["nextTranslatedText"] = normalize_text(segments[index + 1].get("translatedText") or "") if index + 1 < len(segments) else ""

    for position, item in pending_segments:
        translated_text = normalize_text(item.get("translatedText") or item.get("machineTranslatedText") or "")
        if review_backend and should_review_machine_translation(item, translated_text):
            review_candidates.append((position, item))
            continue
        translations[item["id"]] = apply_machine_review_result(
            item,
            machine_translated_text=translated_text,
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
                message="AI tối ưu hóa bản dịch không hoàn tất, vẫn tiếp tục với bản dịch máy",
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
                provider_label="AI",
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
                global_context=global_context,
            )
        elif review_backend == "llama_cpp":
            try:
                reviewed_items = review_machine_batch_via_llama_cpp(batch, source_hint)
            except Exception:
                reviewed_items = [
                    {
                        "translatedText": normalize_text(item.get("translatedText") or item.get("sourceText") or ""),
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
                    "translatedText": normalize_text(item.get("translatedText") or item.get("sourceText") or ""),
                    "delivery": infer_delivery_from_source(
                        item.get("sourceText") or "",
                        item.get("translatedText") or item.get("sourceText") or "",
                    ),
                }
                for item in batch
                ]
        for item, reviewed in zip(batch, reviewed_items):
            raw_machine = item.get("machineTranslatedText") or item.get("translatedText") or ""
            translations[item["id"]] = apply_machine_review_result(
                item,
                machine_translated_text=raw_machine,
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
            forced_text = normalize_text(item.get("machineTranslatedText") or "")
            if (
                not forced_text
                or _looks_like_source_language(forced_text, source_text)
                or _looks_like_placeholder_translation(forced_text)
            ):
                emit_progress(
                    phase=phase,
                    step="translate",
                    progress=0.45,
                    message=f"Bỏ qua câu {position}/{len(segments)} do không dịch được an toàn",
                    extra={"warning": f"Translation failed for segment {position}"}
                )
                forced_text = "[...]"
                
            delivery = normalize_delivery_choice(
                item.get("delivery"),
                default=infer_delivery_from_source(source_text, forced_text),
            )
            item["translatedText"] = forced_text
            item["delivery"] = delivery
            item.pop("spoken" + "Text", None)
            translations[item["id"]] = {
                "translatedText": item["translatedText"],
                "delivery": item["delivery"],
                "machineTranslatedText": normalize_text(
                    item.get("machineTranslatedText") or item["translatedText"]
                ),
            }
        pending_updates += 1
        flush_translation_cache()

    # Final step: Audit and fix common translation artifacts to ensure persona consistency
    # This must happen BEFORE flushing the cache so that the clean versions are persisted.
    segments = validate_translation_quality(segments)

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


def _score_segment_engagement(segment: dict[str, Any]) -> float:
    """
    Score how engaging a segment is for use as a teaser hook.
    Higher score = more likely to hook viewers.
    """
    text = normalize_text(segment.get("translatedText") or segment.get("sourceText") or "")
    if not text:
        return 0.0
    score = 0.0
    # Questions are extremely engaging - they create curiosity
    if "?" in text:
        score += 5.0
    # Exclamations show emotion/energy
    if "!" in text:
        score += 3.0
    # "You" / "bạn" / direct address creates connection
    lower = text.lower()
    if any(word in lower for word in ("bạn", "bạn ", " bạn", "bạn.", "bạn,", "you ", " you", "everyone", "chúng ta", "mọi người")):
        score += 2.5
    # Words that indicate conflict, drama, or emotion
    drama_words = (
        "không ngờ", "bất ngờ", "shock", "kinh ngạc", "sốc", "điên", "phát",
        "không thể", "tại sao", "sao ", " sao", "vì sao", "làm sao", "thế nhưng",
        "nhưng mà", "rồi ", "đợi đã", "nghe này", "nhìn này", "xem này",
        "surprise", "wait", "what", "how", "why", "no way", "wait", "listen",
        "suddenly", "unexpected", "but then", "and then",
    )
    for word in drama_words:
        if word in lower:
            score += 1.5
    # Numbers and specifics feel concrete/real
    if re.search(r"\d+", text):
        score += 1.0
    # Length: too short = not enough info, too long = generic
    word_count = len(text.split())
    if 5 <= word_count <= 25:
        score += 2.0
    elif 26 <= word_count <= 40:
        score += 1.0
    # Penalize very generic/empty words
    generic_words = ("uh", "um", "uhm", "vâng", "ừ", "à", "ờ", "okay", "ok", "vậy đó", "thôi")
    for gw in generic_words:
        if gw in lower:
            score -= 1.0
    return max(0.0, score)


def select_intro_hook_window(
    segments: list[dict[str, Any]],
    *,
    video_duration_ms: int,
    desired_clip_ms: int,
) -> dict[str, Any]:
    """
    Find the MOST engaging window in the video for the teaser.
    Instead of defaulting to position 24%, we score every segment for
    engagement potential (questions, drama, emotion, direct address)
    and pick the best window around the highest-scoring segment.
    """
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

    # Score all segments for engagement
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for idx, seg in enumerate(segments):
        score = _score_segment_engagement(seg)
        start_ms = int(seg.get("startMs", 0))
        scored.append((score, start_ms, seg))

    # Sort by score descending, then pick the best segment
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # Try to build windows around the top-scoring segments
    def build_window_around(anchor_seg: dict[str, Any]) -> dict[str, Any]:
        anchor_start = int(anchor_seg.get("startMs", 0))
        # Center the window around the anchor segment
        window_start = max(0, anchor_start - int(clip_ms * 0.3))
        window_end = min(safe_video_duration, window_start + clip_ms)
        if window_end - window_start < clip_ms * 0.7:
            window_start = max(0, window_end - clip_ms)
        # Collect segments within this window
        window_segments: list[dict[str, Any]] = []
        for seg in segments:
            seg_start = int(seg.get("startMs", 0))
            seg_end = int(seg.get("endMs", 0))
            if seg_end <= window_start or seg_start >= window_end:
                continue
            text = normalize_text(seg.get("translatedText") or seg.get("sourceText") or "")
            if text:
                window_segments.append(seg)
        return {
            "startMs": window_start,
            "endMs": window_end,
            "durationMs": max(window_end - window_start, min(safe_video_duration, 600)),
            "segments": window_segments,
        }

    # Try top 3 scored segments for variety
    tried_starts: set[int] = set()
    for score, seg_start, seg in scored:
        if score < 0.1:
            break  # Not enough engagement signal
        window = build_window_around(seg)
        # Avoid duplicate windows
        if window["startMs"] in tried_starts:
            continue
        tried_starts.add(window["startMs"])
        if window["segments"]:
            return window

    # Fallback: build window around the earliest non-empty segment
    for seg in segments:
        text = normalize_text(seg.get("translatedText") or seg.get("sourceText") or "")
        if text:
            return build_window_around(seg)

    # Absolute fallback: first 24% of video
    start_ms = 0
    end_ms = min(start_ms + clip_ms, safe_video_duration)
    return {
        "startMs": start_ms,
        "endMs": end_ms,
        "durationMs": max(end_ms - start_ms, min(safe_video_duration, 600)),
        "segments": [
            s for s in segments
            if int(s.get("endMs", 0)) > start_ms and int(s.get("startMs", 0)) < end_ms
        ],
    }


def select_intro_hook_montage(
    segments: list[dict[str, Any]],
    *,
    video_duration_ms: int,
    desired_clip_ms: int,
) -> dict[str, Any]:
    """
    Select up to 3 non-overlapping highly engaging segments from across the video
    to create a multi-scene montage trailer, inspired by OpenMontage and ai_trailer.
    """
    safe_video_duration = max(int(video_duration_ms), 600)
    target_clip_ms = max(7000, min(int(desired_clip_ms), 22000))
    clip_ms = max(600, min(target_clip_ms, safe_video_duration))

    if not segments:
        return select_intro_hook_window(segments, video_duration_ms=video_duration_ms, desired_clip_ms=desired_clip_ms)

    scored: list[tuple[float, int, dict[str, Any]]] = []
    for idx, seg in enumerate(segments):
        score = _score_segment_engagement(seg)
        start_ms = int(seg.get("startMs", 0))
        scored.append((score, start_ms, seg))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    engaging_candidates = [item for item in scored if item[0] >= 0.5]
    if len(engaging_candidates) < 2:
        return select_intro_hook_window(segments, video_duration_ms=video_duration_ms, desired_clip_ms=desired_clip_ms)

    selected_highlights: list[dict[str, Any]] = []
    for score, start_ms, seg in engaging_candidates:
        seg_start = int(seg.get("startMs", 0))
        seg_end = int(seg.get("endMs", 0))
        overlap = False
        for hl in selected_highlights:
            hl_start = int(hl.get("startMs", 0))
            hl_end = int(hl.get("endMs", 0))
            if not (seg_end + 4000 <= hl_start or seg_start - 4000 >= hl_end):
                overlap = True
                break
        if not overlap:
            selected_highlights.append(seg)
            if len(selected_highlights) >= 3:
                break

    if len(selected_highlights) < 2:
        return select_intro_hook_window(segments, video_duration_ms=video_duration_ms, desired_clip_ms=desired_clip_ms)

    selected_highlights.sort(key=lambda x: int(x.get("startMs", 0)))

    num_clips = len(selected_highlights)
    clip_dur = clip_ms // num_clips

    clips: list[dict[str, Any]] = []
    window_segments: list[dict[str, Any]] = []

    for seg in selected_highlights:
        seg_start = int(seg.get("startMs", 0))
        seg_end = int(seg.get("endMs", 0))
        seg_mid = (seg_start + seg_end) // 2

        c_start = max(0, seg_mid - clip_dur // 2)
        c_end = min(safe_video_duration, c_start + clip_dur)
        if c_end - c_start < clip_dur:
            c_start = max(0, c_end - clip_dur)

        clips.append({
            "startMs": c_start,
            "endMs": c_end,
            "durationMs": c_end - c_start,
        })

        for s in segments:
            s_start = int(s.get("startMs", 0))
            s_end = int(s.get("endMs", 0))
            if s_end > c_start and s_start < c_end:
                window_segments.append(s)

    seen_ids = set()
    dedup_segments = []
    for s in window_segments:
        s_id = s.get("id") or s.get("startMs")
        if s_id not in seen_ids:
            seen_ids.add(s_id)
            dedup_segments.append(s)

    return {
        "mode": "montage",
        "clips": clips,
        "segments": dedup_segments,
        "durationMs": sum(c["durationMs"] for c in clips),
        "startMs": clips[0]["startMs"],
        "endMs": clips[-1]["endMs"],
    }


def build_intro_hook_text(window_segments: list[dict[str, Any]]) -> str:
    """Fallback teaser generator: picks the most engaging segment and writes a direct hook."""
    # Find the most engaging segment
    best_segment: dict[str, Any] | None = None
    best_score = 0.0
    for seg in window_segments:
        score = _score_segment_engagement(seg)
        if score > best_score:
            best_score = score
            best_segment = seg

    if best_segment is None:
        for seg in window_segments:
            text = normalize_text(seg.get("translatedText") or seg.get("sourceText") or "")
            if text:
                best_segment = seg
                break

    if best_segment is None:
        return ""

    hook_text = normalize_text(
        best_segment.get("translatedText") or best_segment.get("sourceText") or ""
    )
    if not hook_text:
        return ""

    opener = clean_intro_fragment(hook_text, max_chars=90)

    # Collect context from other segments
    context_parts: list[str] = []
    for seg in window_segments:
        if seg is best_segment:
            continue
        text = normalize_text(seg.get("translatedText") or seg.get("sourceText") or "")
        if len(text) < 10:
            continue
        frag = clean_intro_fragment(text, max_chars=80)
        if frag and frag.lower() not in opener.lower():
            context_parts.append(frag.rstrip(".,;:!?"))
            if len(context_parts) >= 2:
                break

    sentences: list[str] = []
    sentences.append(opener.rstrip(".,;:!?") + ".")
    for cp in context_parts:
        sentences.append(cp.rstrip(".,;:!?") + ".")

    result = " ".join(sentences)
    return finalize_intro_text(result) if result else finalize_intro_text(opener)


def build_structured_intro_hook_text(window_segments: list[dict[str, Any]]) -> str:
    """
    Structured fallback: builds a teaser around the most engaging moment.
    Uses concrete details from segments to create a specific, compelling narrative.
    """
    # Score and sort segments by engagement
    scored: list[tuple[float, dict[str, Any]]] = [
        (_score_segment_engagement(s), s) for s in window_segments
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored or scored[0][0] < 0.1:
        return build_intro_hook_text(window_segments)

    best_score, best_seg = scored[0]
    hook_text = normalize_text(
        best_seg.get("translatedText") or best_seg.get("sourceText") or ""
    )
    if not hook_text:
        return build_intro_hook_text(window_segments)

    # Use remaining scored segments for context
    context_segs = [s for _, s in scored[1:] if normalize_text(s.get("translatedText") or s.get("sourceText") or "")]

    hook_clean = clean_intro_fragment(hook_text, max_chars=88)
    opener = hook_clean

    sentences = [opener.rstrip(".,;:!?") + "."]

    # Add context sentences
    for seg in context_segs[:3]:
        ctx_text = normalize_text(seg.get("translatedText") or seg.get("sourceText") or "")
        if not ctx_text or len(ctx_text) < 12:
            continue
        ctx_clean = clean_intro_fragment(ctx_text, max_chars=72)
        if ctx_clean and ctx_clean.lower() not in opener.lower():
            sentences.append(ctx_clean.rstrip(".,;:!?") + ".")
            break

    result = " ".join(sentences)
    if len(normalize_text(result)) < 40:
        return finalize_intro_text(hook_clean)
    return finalize_intro_text(result)


def build_intro_hook_text_with_context(
    window_segments: list[dict[str, Any]],
    *,
    all_segments: list[dict[str, Any]] | None = None,
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
                all_segments=all_segments,
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
                all_segments=all_segments,
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


def validate_translation_quality(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Final audit of translation results to fix common ASR and translation artifacts."""
    for item in segments:
        text = item.get("translatedText") or ""
        if not text:
            continue
            
        # 1. Enforce pronoun 'mình' consistency
        if text.startswith("Tôi ") or text.startswith("Tui "):
            text = "Mình " + text[4:]
        if text.startswith("Chúng tôi"):
            text = text.replace("Chúng tôi", "Chúng mình", 1)
            
        # 2. Remove any leftover hanzi
        text = re.sub(r'[\u4e00-\u9fff]+', '', text)
        
        # 3. Final cleanup of multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        item["translatedText"] = text
    return segments
