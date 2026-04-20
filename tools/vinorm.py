from __future__ import annotations

import re


def TTSnorm(
    text: str,
    punc: bool = False,
    unknown: bool = True,
    lower: bool = True,
    rule: bool = False,
) -> str:
    del punc, unknown, rule
    normalized = str(text or "").strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if lower:
        normalized = normalized.lower()
    return normalized
