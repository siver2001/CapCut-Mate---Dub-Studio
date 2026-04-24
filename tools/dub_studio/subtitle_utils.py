from __future__ import annotations

import re
from typing import Any

from .models import SubtitleLine


_CJK_REPAIR_PATTERN = re.compile(
    r"[\u4e00-\u9fff"
    r"\u3400-\u4dbf"
    r"\u3040-\u309f"
    r"\u30a0-\u30ff"
    r"\uac00-\ud7af"
    r"\u1100-\u11ff"
    r"]"
)
_VIETNAMESE_REPAIR_PATTERN = re.compile(
    r"[A-Za-zÀ-ỹĂăÂâĐđÊêÔôƠơƯư]"
)
_MOJIBAKE_HINT_PATTERN = re.compile(
    r"[ÃÂÄÅÆÇÐÑÒÓÔÕÖØÙÚÛÜÝÞßæçðïñ¢£¤¥¦§¨©ª«¬®¯°±²³´µ¶·¸¹º»¼½¾€™œšž•]"
)

_UNTRANSLATED_SOURCE_PATTERN = re.compile(
    r"[\u4e00-\u9fff"
    r"\u3400-\u4dbf"
    r"\u3040-\u309f"
    r"\u30a0-\u30ff"
    r"\uac00-\ud7af"
    r"\u1100-\u11ff"
    r"]"
)


def _text_quality_score(text: str) -> int:
    compact = text.replace(" ", "")
    cjk_chars = len(_CJK_REPAIR_PATTERN.findall(compact))
    vietnamese_chars = len(_VIETNAMESE_REPAIR_PATTERN.findall(compact))
    mojibake_hints = len(_MOJIBAKE_HINT_PATTERN.findall(compact))
    replacement_chars = compact.count("\ufffd")
    return (cjk_chars * 6) + vietnamese_chars - (mojibake_hints * 4) - (replacement_chars * 8)


def _repair_mojibake_text(text: str) -> str:
    candidate = str(text or "")
    if not candidate or all(ord(char) < 128 for char in candidate):
        return candidate
    best = candidate
    best_score = _text_quality_score(best)
    for _ in range(3):
        improved = False
        for encoding in ("latin1", "cp1252"):
            try:
                repaired = best.encode(encoding).decode("utf-8")
            except Exception:
                continue
            repaired_score = _text_quality_score(repaired)
            if repaired_score > best_score + 2:
                best = repaired
                best_score = repaired_score
                improved = True
                break
        if not improved:
            break
    return best


def normalize_text(text: str) -> str:
    repaired = _repair_mojibake_text(str(text or ""))
    return " ".join(repaired.replace("\n", " ").split()).strip()


def looks_like_untranslated_source(text: str, source_text: str = "") -> bool:
    clean = normalize_text(text)
    if not clean:
        return True
    compact = clean.replace(" ", "")
    cjk_chars = len(_UNTRANSLATED_SOURCE_PATTERN.findall(compact))
    total_chars = max(len(compact), 1)
    if cjk_chars / total_chars > 0.4:
        return True
    normalized_source = normalize_text(source_text)
    if normalized_source and normalized_source == clean:
        if _UNTRANSLATED_SOURCE_PATTERN.search(normalized_source):
            return True
    return False


def pick_best_localized_text(
    translated_text: str = "",
    spoken_text: str = "",
    source_text: str = "",
) -> str:
    for candidate in (translated_text, spoken_text):
        clean = normalize_text(candidate)
        if clean and not looks_like_untranslated_source(clean, source_text):
            return clean
    return ""


VIETNAMESE_FILLER_SUFFIXES = (
    "a",
    "à",
    "á",
    "ạ",
    "ả",
    "ã",
    "ha",
    "ả",
    "mà",
    "nhá",
    "nhé",
    "nhỉ",
    "đấy",
    "chứ",
)
EXPLICIT_FIRST_PERSON_SOURCE_PATTERN = re.compile(
    r"\b(i|me|my|mine|myself|we|our|ours|ourselves)\b|[我俺咱僕私]|(わたし|ぼく|おれ)|[나내저우리]",
    re.IGNORECASE,
)

EXPLICIT_SECOND_PERSON_SOURCE_PATTERN = re.compile(
    r"\b(you|your|yours|yourself|yourselves)\b|[ä½ å¦³æ‚¨]|(ãã¿|ã‚ãªãŸ)|[ë„ˆë„¤ë‹¹ì‹ ]",
    re.IGNORECASE,
)
FORMAL_VIETNAMESE_ADDRESS_PATTERN = re.compile(
    r"\b(ong|ba|anh|chi|em|co|chu|bac|ngai|quy vi|mọi người|các bạn)\b",
    re.IGNORECASE,
)
FIRST_PERSON_PRONOUN_PATTERN = re.compile(
    r"\b(tôi|toi|tao|tớ|to|mình|minh)\b",
    re.IGNORECASE,
)


def strip_stage_direction_tokens(text: str) -> str:
    clean = normalize_text(text)
    if not clean:
        return ""
    clean = re.sub(r"\*+\s*([^*]+?)\s*\*+", r"\1", clean)
    clean = re.sub(r"[\uFF08(]\s*[^()\uFF08\uFF09]{1,18}\s*[)\uFF09]", "", clean)
    clean = re.sub(r"\s{2,}", " ", clean).strip(" ,")
    return clean


def collapse_repeated_pronouns(text: str) -> str:
    clean = normalize_text(text)
    if not clean:
        return ""
    clean = re.sub(
        r"\b(tôi|toi|mình|minh|ta|tao|tớ|to)\s*,\s*\1\b",
        r"\1",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(
        r"([.!?\u2026]\s+)(tôi|toi|mình|minh|ta|tao|tớ|to)\s+(đã|đang|vẫn|cũng|chỉ|sẽ|muốn|thấy|nghĩ|biết|cảm|tự)\b",
        lambda match: f"{match.group(1)}{match.group(3).capitalize()}",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(
        r"\b(tôi|toi|mình|minh|ta|tao|tớ|to)\b(?:\s+\1\b)+",
        r"\1",
        clean,
        flags=re.IGNORECASE,
    )
    clean = clean.replace(" C\u1eadu", " c\u1eadu")
    clean = clean.replace(" M\u00ecnh", " m\u00ecnh")
    return normalize_text(clean)


def collapse_repeated_words(text: str) -> str:
    """Remove consecutive duplicate words or short phrases from text.

    This catches common LLM stuttering patterns and artifacts caused by
    running build_spoken_text multiple times on the same text.  It handles:
    - Single word repeats: "mọi mọi chuyện" → "mọi chuyện"
    - Two-word phrase repeats: "mọi chuyện mọi chuyện" → "mọi chuyện"
    - Three-word phrase repeats for longer text
    """
    clean = normalize_text(text)
    if not clean:
        return ""
    words = clean.split()
    if len(words) < 3:
        return clean

    # Pass 1: collapse consecutive identical single words
    # e.g. "mọi mọi chuyện" → "mọi chuyện"
    def _token_key(word: str) -> str:
        normalized = re.sub(r"^[^\wÀ-ỹ]+|[^\wÀ-ỹ]+$", "", word.lower())
        return normalized or word.lower()

    deduped: list[str] = [words[0]]
    for word in words[1:]:
        previous_word = deduped[-1]
        if (
            _token_key(word) != _token_key(previous_word)
            or re.search(r"[,;:.!?…]", previous_word)
            or re.search(r"[,;:.!?…]", word)
        ):
            deduped.append(word)
    result = " ".join(deduped)

    # Pass 2: collapse consecutive duplicate 2-word phrases
    # e.g. "mọi chuyện mọi chuyện bắt đầu" → "mọi chuyện bắt đầu"
    result = re.sub(
        r"\b(\S+\s+\S+)\s+\1\b",
        r"\1",
        result,
        flags=re.IGNORECASE,
    )

    # Pass 3: collapse consecutive duplicate 3-word phrases (for longer text)
    if len(result.split()) >= 8:
        result = re.sub(
            r"\b(\S+\s+\S+\s+\S+)\s+\1\b",
            r"\1",
            result,
            flags=re.IGNORECASE,
        )

    return normalize_text(result)


def normalize_first_person_pronouns(text: str) -> str:
    clean = normalize_text(text)
    if not clean:
        return ""

    def _replace(match: re.Match[str]) -> str:
        value = match.group(0)
        if value[:1].isupper():
            return "Mình"
        return "mình"

    return normalize_text(FIRST_PERSON_PRONOUN_PATTERN.sub(_replace, clean))


def source_explicitly_uses_first_person(source_text: str) -> bool:
    return bool(EXPLICIT_FIRST_PERSON_SOURCE_PATTERN.search(normalize_text(source_text)))


def source_explicitly_uses_second_person(source_text: str) -> bool:
    return bool(EXPLICIT_SECOND_PERSON_SOURCE_PATTERN.search(normalize_text(source_text)))


def should_prefer_minh_cau(text: str, source_text: str = "") -> bool:
    clean = normalize_text(text)
    if not clean:
        return False
    lowered = clean.lower()
    if FORMAL_VIETNAMESE_ADDRESS_PATTERN.search(lowered):
        return False
    if re.search(r"\b(tôi|toi)\b", lowered) and re.search(r"\b(bạn|ban)\b", lowered):
        return True
    return source_explicitly_uses_first_person(source_text) and source_explicitly_uses_second_person(source_text)


def prefer_minh_cau_pair(text: str, source_text: str = "") -> str:
    clean = normalize_first_person_pronouns(text)
    if not should_prefer_minh_cau(clean, source_text):
        return clean
    clean = re.sub(r"\b[Bb]ạn\b", "Cậu", clean)
    clean = re.sub(r"\bbạn\b", "cậu", clean)
    clean = re.sub(r"\b[Bb]an\b", "Cậu", clean)
    clean = re.sub(r"\bban\b", "cậu", clean)
    return normalize_text(clean)


def soften_literal_leading_pronoun(text: str, source_text: str = "") -> str:
    clean = normalize_text(text)
    if not clean or source_explicitly_uses_first_person(source_text):
        return clean
    match = re.match(
        r"^(tôi|toi|mình|minh|ta|tao|tớ|to)\s+(chỉ\s+)?(cảm thấy|thấy|tự hỏi|nghĩ|đã|đang|vẫn|cũng|muốn|không)\b",
        clean,
        flags=re.IGNORECASE,
    )
    if not match:
        return clean
    if len(clean.split()) < 6:
        return clean
    prefix = match.group(2) or ""
    verb = match.group(3).lower()
    remainder = clean[match.end() :].strip()
    if not remainder:
        return clean
    if verb in {"tự hỏi", "nghĩ"}:
        replacement = "Mình" if match.group(1).lower() in {"tôi", "toi"} else match.group(1).capitalize()
        return normalize_text(f"{replacement} {verb} {remainder}")
    if prefix.strip():
        return normalize_text(f"Chỉ {verb} {remainder}")
    return normalize_text(f"{verb.capitalize()} {remainder}")


def add_light_spoken_filler(text: str, delivery: str) -> str:
    clean = normalize_text(text)
    if not clean:
        return ""
    filler_base = clean.rstrip(" .,!?:;…").lower()
    if any(filler_base.endswith(suffix) for suffix in VIETNAMESE_FILLER_SUFFIXES):
        return clean
    normalized_delivery = str(delivery or "neutral").strip().lower()
    if len(clean.split()) < 4:
        return clean
    if normalized_delivery == "excited" and clean.endswith("!"):
        return clean[:-1].rstrip() + " đấy!"
    if normalized_delivery == "suspense" and clean.endswith("..."):
        return clean[:-3].rstrip() + " nhỉ..."
    return clean


def ensure_terminal_punctuation(text: str, source_text: str = "", *, prefer_soft: bool = False) -> str:
    return _ensure_terminal_punctuation(text, source_text, prefer_soft=prefer_soft)


def smooth_spoken_delivery(text: str, delivery: str) -> str:
    clean = normalize_text(text)
    if not clean:
        return ""
    clean = re.sub(r"\s*,\s*,+", ", ", clean)
    clean = re.sub(r"\s+([,!.?…])", r"\1", clean)
    clean = re.sub(r"([!?.,…])\1+", r"\1", clean)
    normalized_delivery = str(delivery or "neutral").strip().lower()
    if normalized_delivery in {"calm", "neutral"}:
        clean = re.sub(r"!$", ".", clean)
    if normalized_delivery == "urgent":
        clean = re.sub(r"\.\.\.$", ".", clean)
    if clean.count(",") >= 3:
        parts = [part.strip() for part in clean.split(",") if part.strip()]
        if len(parts) >= 4:
            clean = ", ".join(parts[:2]) + " " + " ".join(parts[2:])
    return normalize_text(clean)


def normalize_tts_period_pauses(text: str) -> str:
    clean = normalize_text(text)
    if not clean:
        return ""
    if "..." in clean or "…" in clean:
        clean = clean.replace("…", "...")
    parts = [part.strip(" ,;:.!?") for part in re.split(r"\.\s+", clean) if part.strip(" ,;:.!?")]
    if len(parts) >= 2 and clean.endswith("."):
        rebuilt = [parts[0]]
        for part in parts[1:]:
            rebuilt.append(part[:1].lower() + part[1:] if part[:1].isupper() else part)
        return ", ".join(rebuilt)
    if clean.endswith(".") and clean.count(".") == 1:
        return clean[:-1].rstrip()
    return clean


def _ensure_terminal_punctuation(text: str, source_text: str = "", *, prefer_soft: bool = False) -> str:
    clean = normalize_text(text)
    if not clean:
        return ""
    if clean[-1] in ".!?\u2026":
        return clean
    source = normalize_text(source_text)
    if source.endswith(("?", "？")):
        return f"{clean}?"
    if source.endswith(("!", "！")):
        return f"{clean}!"
    if source.endswith(("\u2026", "...")):
        return f"{clean}..."
    return f"{clean}{'...' if prefer_soft else '.'}"


def inject_mid_sentence_pause(text: str) -> str:
    clean = normalize_text(text)
    if not clean or re.search(r"[,;:!?\u2026]", clean):
        return clean
    words = clean.split()
    if len(words) < 8:
        return clean
    preferred_tokens = {
        "nhưng",
        "mà",
        "nên",
        "rồi",
        "và",
        "thì",
        "là",
        "để",
        "khi",
        "nếu",
        "bởi",
        "vì",
        "thế",
    }
    midpoint = len(words) // 2
    split_index: int | None = None
    for index in range(max(2, midpoint - 3), min(len(words) - 2, midpoint + 4)):
        if words[index].strip(" ,.;:!?").lower() in preferred_tokens:
            split_index = index
            break
    if split_index is None:
        split_index = midpoint
    leading = " ".join(words[:split_index]).strip()
    trailing = " ".join(words[split_index:]).strip()
    if not leading or not trailing:
        return clean
    return f"{leading}, {trailing}"


def build_spoken_text(translated_text: str, source_text: str = "", delivery: str = "neutral") -> str:
    spoken = strip_stage_direction_tokens(translated_text)
    if not spoken:
        return ""

    spoken = normalize_first_person_pronouns(spoken)
    spoken = prefer_minh_cau_pair(spoken, source_text)
    spoken = collapse_repeated_pronouns(spoken)
    spoken = collapse_repeated_words(spoken)
    spoken = soften_literal_leading_pronoun(spoken, source_text)

    if len(spoken) >= 28:
        spoken = inject_mid_sentence_pause(spoken)

    normalized_delivery = str(delivery or "neutral").strip().lower()
    if normalized_delivery == "excited" and spoken[-1] not in "!?":
        spoken = spoken.rstrip(" .") + "!"
    elif normalized_delivery == "suspense" and spoken[-1] not in ".!?\u2026":
        spoken = spoken.rstrip(" .") + "..."
    elif normalized_delivery == "curious" and spoken[-1] not in "?":
        spoken = spoken.rstrip(" .") + "?"
    else:
        spoken = ensure_terminal_punctuation(
            spoken,
            source_text,
            prefer_soft=normalized_delivery in {"calm", "suspense"},
        )
    spoken = add_light_spoken_filler(spoken, normalized_delivery)
    spoken = smooth_spoken_delivery(spoken, normalized_delivery)
    # Final dedup pass: catch any repeated words introduced by
    # delivery/filler/pause injection above.
    return collapse_repeated_words(spoken)


def parse_srt_timestamp(value: str) -> int:
    sec_str, ms_str = value.split(",")
    hh, mm, ss = [int(part) for part in sec_str.split(":")]
    return (((hh * 60) + mm) * 60 + ss) * 1000 + int(ms_str)


def format_srt_timestamp(ms: int) -> str:
    total_ms = max(ms, 0)
    seconds, millis = divmod(total_ms, 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{sec:02d},{millis:03d}"


def parse_srt(content: str) -> list[SubtitleLine]:
    lines: list[SubtitleLine] = []
    blocks = re.split(r"\r?\n\r?\n+", content.strip())
    for block in blocks:
        parts = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        if len(parts) < 3:
            continue
        try:
            index = int(parts[0])
            start_raw, end_raw = [chunk.strip() for chunk in parts[1].split("-->")]
            text = normalize_text(" ".join(parts[2:]))
            if not text:
                continue
            lines.append(
                SubtitleLine(
                    index=index,
                    start_ms=parse_srt_timestamp(start_raw),
                    end_ms=parse_srt_timestamp(end_raw),
                    content=text,
                )
            )
        except Exception:
            continue
    return lines


def compose_srt(lines: list[SubtitleLine]) -> str:
    blocks = []
    for index, item in enumerate(lines, start=1):
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_srt_timestamp(item.start_ms)} --> {format_srt_timestamp(item.end_ms)}",
                    item.content,
                ]
            )
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def merge_short_subtitles(subtitles: list[SubtitleLine]) -> list[SubtitleLine]:
    merged: list[SubtitleLine] = []
    current: SubtitleLine | None = None
    for raw in subtitles:
        item = SubtitleLine(raw.index, raw.start_ms, raw.end_ms, normalize_text(raw.content))
        if not item.content:
            continue
        if current is None:
            current = item
            continue
        gap = item.start_ms - current.end_ms
        merged_span = item.end_ms - current.start_ms
        combined = f"{current.content} {item.content}".strip()
        if gap <= 550 and merged_span <= 6500 and len(combined) <= 110:
            current = SubtitleLine(current.index, current.start_ms, item.end_ms, combined)
            continue
        merged.append(current)
        current = item
    if current is not None:
        merged.append(current)
    for idx, item in enumerate(merged, start=1):
        item.index = idx
    return merged


def split_long_clause(text: str, max_words: int = 4, max_chars: int = 20) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word]).strip()
        if current and (len(current) >= max_words or len(candidate) > max_chars):
            chunks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def split_display_text(text: str, max_words: int = 5, max_chars: int = 22, punctuation_aware: bool = True) -> list[str]:
    clean = normalize_text(text)
    if not clean:
        return []
    if not punctuation_aware:
        return split_long_clause(clean, max_words=max_words, max_chars=max_chars)
    clauses = [part.strip() for part in re.findall(r"[^,;:.!?]+(?:[,;:.!?]+)?", clean) if part.strip()]
    chunks: list[str] = []
    for clause in clauses:
        if len(clause) <= max_chars:
            chunks.append(clause)
        else:
            chunks.extend(split_long_clause(clause, max_words=max_words, max_chars=max_chars))
    return chunks


def create_display_subtitles(
    segments: list[dict[str, Any]],
    *,
    max_words: int,
    max_chars: int,
    punctuation_aware: bool,
) -> list[SubtitleLine]:
    display_items: list[SubtitleLine] = []
    counter = 1
    for segment in segments:
        translated = normalize_text(segment.get("translatedText") or "")
        if not translated:
            continue
        chunks = split_display_text(translated, max_words=max_words, max_chars=max_chars, punctuation_aware=punctuation_aware)
        if not chunks:
            continue
        start_ms = int(segment["startMs"])
        end_ms = int(segment["endMs"])
        total_ms = max(end_ms - start_ms, 400)
        weights = [max(len(chunk.replace(" ", "")), 1) for chunk in chunks]
        total_weight = max(sum(weights), 1)
        cursor = start_ms
        for idx, chunk in enumerate(chunks):
            if idx == len(chunks) - 1:
                chunk_end = end_ms
            else:
                duration = max(int(total_ms * weights[idx] / total_weight), 150)
                chunk_end = min(end_ms, cursor + duration)
            display_items.append(
                SubtitleLine(
                    index=counter,
                    start_ms=cursor,
                    end_ms=max(chunk_end, cursor + 120),
                    content=chunk,
                )
            )
            counter += 1
            cursor = chunk_end
        if display_items:
            display_items[-1].end_ms = end_ms
    return display_items


def subtitle_timeline_to_lines(
    timeline: list[dict[str, Any]],
) -> list[SubtitleLine]:
    items: list[SubtitleLine] = []
    for index, entry in enumerate(
        sorted(
            timeline,
            key=lambda item: (
                int(item.get("startMs") or 0),
                int(item.get("endMs") or 0),
                str(item.get("id") or ""),
            ),
        ),
        start=1,
    ):
        text = normalize_text(entry.get("text") or "")
        if not text:
            continue
        start_ms = max(int(entry.get("startMs") or 0), 0)
        end_ms = max(int(entry.get("endMs") or 0), start_ms + 120)
        items.append(
            SubtitleLine(
                index=index,
                start_ms=start_ms,
                end_ms=end_ms,
                content=text,
            )
        )
    return items


def renumber_subtitle_timeline(
    timeline: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sorted_entries = sorted(
        timeline,
        key=lambda item: (
            int(item.get("startMs") or 0),
            int(item.get("endMs") or 0),
            str(item.get("id") or ""),
        ),
    )
    normalized: list[dict[str, Any]] = []
    for index, source in enumerate(sorted_entries, start=1):
        text = normalize_text(source.get("text") or "")
        if not text:
            continue
        start_ms = max(int(source.get("startMs") or 0), 0)
        end_ms = max(int(source.get("endMs") or 0), start_ms + 120)
        normalized.append(
            {
                "id": str(source.get("id") or source.get("segmentId") or f"sub_{index:04d}"),
                "index": index,
                "startMs": start_ms,
                "endMs": end_ms,
                "text": text,
                "segmentId": str(source.get("segmentId") or ""),
                "speakerId": str(source.get("speakerId") or ""),
                "sourceText": normalize_text(source.get("sourceText") or ""),
            }
        )
    return normalized


def compose_srt_from_timeline(timeline: list[dict[str, Any]]) -> str:
    return compose_srt(subtitle_timeline_to_lines(timeline))


def build_subtitle_timeline(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        source_text = normalize_text(segment.get("sourceText") or "")
        text = pick_best_localized_text(
            segment.get("translatedText") or "",
            segment.get("spokenText") or "",
            source_text,
        )
        if not text:
            continue
        start_ms = max(int(segment.get("startMs") or 0), 0)
        end_ms = max(int(segment.get("endMs") or 0), start_ms + 120)
        timeline.append(
            {
                "id": str(segment.get("id") or f"seg_sub_{index:04d}"),
                "index": index,
                "startMs": start_ms,
                "endMs": end_ms,
                "text": text,
                "segmentId": str(segment.get("id") or ""),
                "speakerId": str(segment.get("speakerId") or ""),
                "sourceText": source_text,
            }
        )
    return renumber_subtitle_timeline(timeline)


def _match_subtitle_segment(
    subtitle: SubtitleLine,
    segments: list[dict[str, Any]],
    *,
    position: int = 0,
) -> dict[str, Any] | None:
    if not segments:
        return None
    best_segment: dict[str, Any] | None = None
    best_score = -1
    for segment in segments:
        seg_start = max(int(segment.get("startMs") or 0), 0)
        seg_end = max(int(segment.get("endMs") or 0), seg_start + 120)
        overlap = min(subtitle.end_ms, seg_end) - max(subtitle.start_ms, seg_start)
        distance = abs(subtitle.start_ms - seg_start) + abs(subtitle.end_ms - seg_end)
        score = max(overlap, 0) * 10 - distance
        if score > best_score:
            best_score = score
            best_segment = segment
    if best_segment is not None and best_score >= -500:
        return best_segment
    if 0 <= position < len(segments):
        return segments[position]
    return None


def parse_srt_to_timeline(
    content: str,
    *,
    fallback_segments: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    fallback_segments = fallback_segments or []
    parsed = parse_srt(content)
    timeline: list[dict[str, Any]] = []
    same_count = len(parsed) == len(fallback_segments) and bool(parsed)
    for index, subtitle in enumerate(parsed, start=1):
        matched_segment = None
        if same_count:
            matched_segment = fallback_segments[index - 1]
        else:
            matched_segment = _match_subtitle_segment(
                subtitle, fallback_segments, position=index - 1
            )
        timeline.append(
            {
                "id": str(
                    (matched_segment or {}).get("id")
                    or (matched_segment or {}).get("segmentId")
                    or f"sub_{index:04d}"
                ),
                "index": index,
                "startMs": int(subtitle.start_ms),
                "endMs": int(subtitle.end_ms),
                "text": normalize_text(subtitle.content),
                "segmentId": str((matched_segment or {}).get("id") or ""),
                "speakerId": str((matched_segment or {}).get("speakerId") or ""),
                "sourceText": normalize_text((matched_segment or {}).get("sourceText") or ""),
            }
        )
    return renumber_subtitle_timeline(timeline)


def apply_subtitle_timeline_to_segments(
    segments: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not segments:
        return []
    updated_segments = [dict(segment) for segment in segments]
    by_segment_id = {
        str(item.get("segmentId") or ""): item for item in renumber_subtitle_timeline(timeline)
    }
    for index, segment in enumerate(updated_segments):
        matched = None
        segment_id = str(segment.get("id") or "")
        if segment_id and segment_id in by_segment_id:
            matched = by_segment_id[segment_id]
        elif len(timeline) == len(updated_segments) and index < len(timeline):
            matched = timeline[index]
        if not matched:
            continue
        translated = normalize_text(matched.get("text") or "")
        if not translated:
            continue
        segment["translatedText"] = translated
        segment["spokenText"] = build_spoken_text(
            translated, segment.get("sourceText") or "", segment.get("delivery") or "neutral"
        )
    return updated_segments
