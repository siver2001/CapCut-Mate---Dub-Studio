from __future__ import annotations

import re
import textwrap


def normalize_text(text: str) -> str:
    cleaned = " ".join(text.replace("\n", " ").split())
    return cleaned.strip()


def wrap_vietnamese_text(text: str, width: int = 30, max_lines: int = 3) -> str:
    if not text:
        return text
    wrapped = textwrap.wrap(text, width=width, break_long_words=False)
    while len(wrapped) > max_lines:
        wrapped[-2] = f"{wrapped[-2]} {wrapped[-1]}"
        wrapped.pop()
    return "\n".join(wrapped)


def cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    cjk_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    return cjk_chars / max(len(text), 1)


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


def split_display_text(text: str, max_words: int = 5, max_chars: int = 22) -> list[str]:
    clean_text = normalize_text(text)
    if not clean_text:
        return []

    chunks: list[str] = []
    clauses = [
        part.strip()
        for part in re.findall(r"[^,;:.!?]+(?:[,;:.!?]+)?", clean_text)
        if part.strip()
    ]
    for clause in clauses:
        if len(clause) <= max_chars:
            chunks.append(clause)
            continue
        chunks.extend(split_long_clause(clause, max_words=max_words, max_chars=max_chars))
    return chunks


def clean_tts_text(text: str) -> str:
    cleaned = text.replace("\u200b", " ").replace("\ufeff", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()
