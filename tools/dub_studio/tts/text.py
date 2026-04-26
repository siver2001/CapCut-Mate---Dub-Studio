from __future__ import annotations

import re
import unicodedata

from ..subtitle_utils import (
    VIETNAMESE_FILLER_SUFFIXES,
    collapse_repeated_words,
    normalize_text,
    normalize_tts_period_pauses,
)


_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
DEFAULT_TTS_REPAIR_FALLBACK = "Đoạn này tiếp tục mô tả chi tiết trong video."


def contains_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def normalize_edge_tts_text(text: str, *, preserve_pauses: bool) -> str:
    clean = unicodedata.normalize("NFC", normalize_text(text).replace("\ufeff", ""))
    clean = re.sub(r"[\u200b-\u200f\u2060]", "", clean)
    clean = (
        clean.replace("â€œ", '"')
        .replace("Ã¢â‚¬Â", '"')
        .replace("â€™", "'")
        .replace("â€¦", "...")
    )
    if not preserve_pauses:
        clean = normalize_tts_period_pauses(clean)
    return normalize_text(clean)


def sanitize_edge_tts_text(text: str) -> str:
    clean = normalize_edge_tts_text(text, preserve_pauses=False)
    clean = collapse_repeated_words(clean)
    clean = re.sub(r"[\u0000-\u001f\u007f]", " ", clean)
    return normalize_text(clean)


def ensure_edge_tts_terminal_punctuation(text: str) -> str:
    clean = normalize_text(text)
    if not clean:
        return ""
    clean = clean.rstrip(" ,;:")
    if not clean:
        return ""
    if clean.endswith(("...", "…", "?", "!")):
        return clean.replace("…", "...")
    if clean.endswith("."):
        return clean
    if len(clean.split()) < 4:
        return clean
    return f"{clean}."


def strip_trailing_vietnamese_filler(text: str) -> str:
    clean = normalize_text(text)
    if not clean:
        return ""
    punctuation = ""
    while clean and clean[-1] in ".!?…":
        punctuation = clean[-1] + punctuation
        clean = clean[:-1].rstrip()
    lowered = clean.lower()
    for suffix in sorted(VIETNAMESE_FILLER_SUFFIXES, key=len, reverse=True):
        if lowered.endswith(f" {suffix}"):
            clean = clean[: -len(suffix)].rstrip(" ,;:-")
            break
    clean = clean.strip()
    if not clean:
        return ""
    return f"{clean}{punctuation}"


def build_edge_tts_safe_rewrites(text: str) -> list[str]:
    clean = normalize_text(text)
    if not clean:
        return []
    rewrites: list[str] = []
    patterns = (
        (r"^Tại sao lại (.+)\?$", lambda body: [f"Sao phải {body}?", f"Vì sao {body}?"]),
        (r"^Tại sao (.+)\?$", lambda body: [f"Vì sao {body}?", f"Sao {body}?"]),
        (r"^Vì sao lại (.+)\?$", lambda body: [f"Vì sao {body}?", f"Sao phải {body}?"]),
    )
    for pattern, builder in patterns:
        match = re.match(pattern, clean, flags=re.IGNORECASE)
        if not match:
            continue
        body = match.group(1).strip()
        for candidate in builder(body):
            normalized = normalize_text(candidate)
            if normalized and normalized not in rewrites:
                rewrites.append(normalized)
    punctuation = ""
    body = clean
    while body.endswith(("...", ".", "?", "!")):
        if body.endswith("..."):
            punctuation = "..." + punctuation
            body = body[:-3].rstrip()
            break
        punctuation = body[-1] + punctuation
        body = body[:-1].rstrip()
    if body.count(",") == 1 and not re.search(r"\d", body):
        left, right = [part.strip(" ,;:") for part in body.split(",", 1)]
        if len(left.split()) >= 2 and len(right.split()) >= 2:
            for candidate in (
                f"{left} và {right}",
                f"{left}, và {right}",
            ):
                normalized = normalize_text(candidate)
                if punctuation:
                    normalized = f"{normalized}{punctuation}"
                if normalized and normalized not in rewrites:
                    rewrites.append(normalized)
    return rewrites


def sanitize_for_tts_or_raise(
    text: str,
    *,
    speaker_id: str,
    fallback_text: str = DEFAULT_TTS_REPAIR_FALLBACK,
    allow_generic_fallback: bool = False,
) -> str:
    clean = ensure_edge_tts_terminal_punctuation(normalize_edge_tts_text(text, preserve_pauses=True))
    if not clean:
        fallback = ensure_edge_tts_terminal_punctuation(sanitize_edge_tts_text(fallback_text))
        if allow_generic_fallback and fallback and not contains_cjk(fallback):
            return fallback
        raise RuntimeError(f"TTS text for {speaker_id} is empty after cleanup.")
    if contains_cjk(clean):
        repaired = ensure_edge_tts_terminal_punctuation(_CJK_RE.sub(" ", clean))
        repaired = sanitize_edge_tts_text(repaired)
        repaired = ensure_edge_tts_terminal_punctuation(repaired)
        min_useful_chars = max(12, int(len(clean) * 0.55))
        if repaired and not contains_cjk(repaired) and len(repaired) >= min_useful_chars:
            return repaired
        fallback = ensure_edge_tts_terminal_punctuation(sanitize_edge_tts_text(fallback_text))
        if allow_generic_fallback and fallback and not contains_cjk(fallback):
            return fallback
        raise RuntimeError(
            f"TTS text for {speaker_id} still contains source-language CJK characters after repair; translation must be fixed before render."
        )
    return clean
