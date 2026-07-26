from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from .subtitle_utils import normalize_text


_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
_PLACEHOLDER_RE = re.compile(r"^\s*(?:\[?\.{3}\]?|n/?a|không rõ)\s*$", re.IGNORECASE)
_VIETNAMESE_NUMBER_WORDS = {
    "không", "một", "hai", "ba", "bốn", "tư", "năm", "sáu", "bảy", "tám",
    "chín", "mười", "mươi", "trăm", "nghìn", "ngàn", "triệu", "tỷ", "lẻ",
}


def _significant_numbers(text: str) -> set[str]:
    values: set[str] = set()
    for raw in re.findall(r"(?<!\w)\d[\d.,]*(?!\w)", normalize_text(text)):
        normalized = re.sub(r"[.,]", "", raw)
        # Single digits are commonly and correctly spelled out in speech.
        if len(normalized) >= 2:
            values.add(normalized.lstrip("0") or "0")
    return values


def _source_leaked(source: str, translated: str, source_language: str) -> bool:
    source = normalize_text(source)
    translated = normalize_text(translated)
    if not translated:
        return True
    normalized_language = source_language.lower()
    if source and normalized_language not in {"vi", "vietnamese"}:
        source_key = re.sub(r"[^\w]+", "", source, flags=re.UNICODE).casefold()
        translated_key = re.sub(r"[^\w]+", "", translated, flags=re.UNICODE).casefold()
        if source_key and (
            source_key == translated_key
            or SequenceMatcher(None, source_key, translated_key).ratio() >= 0.94
        ):
            return True
    if normalized_language in {"zh", "ja", "ko", "cn", "jp", "kr"}:
        compact = translated.replace(" ", "")
        return bool(compact) and len(_CJK_RE.findall(compact)) / len(compact) > 0.08
    if normalized_language in {"en", "english"}:
        words = re.findall(r"[a-zA-Z']+", translated.lower())
        english_markers = {
            "the", "this", "that", "these", "those", "is", "are", "was", "were",
            "and", "but", "with", "from", "have", "has", "will", "would", "can",
            "could", "you", "your", "we", "our", "they", "their", "what", "why",
            "when", "where", "how",
        }
        vietnamese_markers = {
            "là", "và", "của", "có", "không", "được", "một", "những", "này",
            "đó", "tôi", "mình", "chúng", "bạn", "với", "cho", "khi", "nhưng",
        }
        marker_count = sum(word in english_markers for word in words)
        vi_words = re.findall(r"\w+", translated.lower(), flags=re.UNICODE)
        if (
            len(words) >= 6
            and marker_count >= 3
            and marker_count / len(words) >= 0.3
            and not any(token in vietnamese_markers for token in vi_words)
        ):
            return True
    return False


def audit_translation_segments(
    segments: list[dict[str, Any]],
    *,
    source_language: str,
) -> dict[str, Any]:
    """Attach deterministic quality findings and return an aggregate report.

    The audit deliberately treats missing/untranslated dialogue as critical. Less
    certain style and pacing findings remain warnings so a good translation is
    never silently replaced by a heuristic rewrite.
    """
    critical = 0
    warnings = 0
    duplicate_runs = 0
    critical_segments: list[dict[str, Any]] = []
    finding_counts: dict[str, int] = {}
    previous_translation = ""
    previous_source = ""

    for item in segments:
        source = normalize_text(item.get("sourceText") or "")
        translated = normalize_text(
            item.get("finalText")
            or item.get("spokenAdaptation")
            or item.get("translatedText")
            or ""
        )
        findings: list[dict[str, str]] = []

        translation_provider = normalize_text(
            item.get("translationProvider") or ""
        ).lower()
        if translation_provider == "ai_unreviewed":
            # In quality-first mode a quota/key failure during the review pass
            # must never silently export the longer, unpolished draft.
            findings.append(
                {"severity": "critical", "code": "cloud_review_incomplete"}
            )
        elif translation_provider == "fallback":
            # A fallback provider is a provenance warning, not proof that the
            # sentence is broken. Missing text, source-language leakage and
            # dropped numbers are still independently blocked below.
            findings.append({"severity": "warning", "code": "fallback_translation_used"})
        is_non_dialogue = bool(item.get("isNonDialogue"))
        if source and not is_non_dialogue and (not translated or _PLACEHOLDER_RE.match(translated)):
            findings.append({"severity": "critical", "code": "missing_translation"})
        elif source and not is_non_dialogue and _source_leaked(source, translated, source_language):
            findings.append({"severity": "critical", "code": "source_language_leak"})
        if source and translated and not is_non_dialogue:
            source_numbers = _significant_numbers(source)
            translated_numbers = _significant_numbers(translated)
            if source_numbers - translated_numbers:
                translated_tokens = set(
                    re.findall(r"\w+", translated.lower(), flags=re.UNICODE)
                )
                if translated_tokens & _VIETNAMESE_NUMBER_WORDS:
                    findings.append(
                        {
                            "severity": "warning",
                            "code": "source_number_spelled_out_unverified",
                        }
                    )
                else:
                    findings.append(
                        {"severity": "critical", "code": "missing_source_number"}
                    )

        duration_ms = max(int(item.get("endMs", 0)) - int(item.get("startMs", 0)), 1)
        spoken_chars_per_second = len(translated) / (duration_ms / 1000.0)
        # Keep a small tolerance above the 22 cps repair target. Rounding,
        # punctuation and the TTS speed controller can absorb this margin;
        # flagging 22.01 cps caused otherwise production-ready translations to
        # fail after the selective timing repair had already done its job.
        if translated and spoken_chars_per_second > 22.5:
            findings.append({"severity": "warning", "code": "timing_pressure_high"})

        if (
            translated
            and translated == previous_translation
            and source
            and source != previous_source
        ):
            findings.append({"severity": "warning", "code": "duplicate_translation"})
            duplicate_runs += 1

        item_critical = sum(1 for finding in findings if finding["severity"] == "critical")
        item_warnings = sum(1 for finding in findings if finding["severity"] == "warning")
        for finding in findings:
            code = finding["code"]
            finding_counts[code] = finding_counts.get(code, 0) + 1
        critical += item_critical
        warnings += item_warnings
        if item_critical:
            critical_segments.append(
                {
                    "id": str(item.get("id") or ""),
                    "sourceText": source[:160],
                    "codes": [
                        finding["code"]
                        for finding in findings
                        if finding["severity"] == "critical"
                    ],
                }
            )
        item["quality"] = {
            "status": "blocked" if item_critical else ("warning" if item_warnings else "pass"),
            "findings": findings,
            "spokenCharsPerSecond": round(spoken_chars_per_second, 2),
        }
        previous_translation = translated
        previous_source = source

    return {
        "status": "blocked" if critical else ("warning" if warnings else "pass"),
        "segmentCount": len(segments),
        "criticalCount": critical,
        "warningCount": warnings,
        "duplicateRuns": duplicate_runs,
        "findingCounts": finding_counts,
        "criticalSegments": critical_segments,
    }


def assert_translation_renderable(report: dict[str, Any]) -> None:
    if int(report.get("criticalCount") or 0) > 0:
        details = ", ".join(
            f"{item.get('id') or '?'}:{'/'.join(item.get('codes') or [])}"
            for item in (report.get("criticalSegments") or [])[:8]
        )
        raise RuntimeError(
            "Bản dịch không vượt qua quality gate: "
            f"{report['criticalCount']} đoạn chưa đạt điều kiện xuất bản. "
            f"Chi tiết: {details or 'không xác định'}. "
            "Đã dừng trước bước lồng tiếng để tránh xuất video lỗi."
        )


def audit_timeline(
    segments: list[dict[str, Any]],
    *,
    video_duration_ms: int,
    max_end_tolerance_ms: int = 250,
) -> dict[str, Any]:
    overlaps = 0
    backward = 0
    previous_end = 0
    max_end = 0
    for item in segments:
        start = max(int(item.get("startMs", 0)), 0)
        end = max(int(item.get("endMs", start)), start)
        if start < previous_end:
            overlaps += 1
        if end < previous_end:
            backward += 1
        previous_end = max(previous_end, end)
        max_end = max(max_end, end)
    overflow_ms = max(max_end - int(video_duration_ms), 0)
    return {
        "status": "blocked" if backward or overflow_ms > max_end_tolerance_ms else (
            "warning" if overlaps else "pass"
        ),
        "overlapCount": overlaps,
        "backwardCount": backward,
        "maxEndMs": max_end,
        "videoDurationMs": int(video_duration_ms),
        "overflowMs": overflow_ms,
    }
