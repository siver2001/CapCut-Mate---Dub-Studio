from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from .text import cjk_ratio, normalize_text


def translate_via_google(
    text: str,
    source_lang: str = "auto",
    target_lang: str = "vi",
) -> str:
    query = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": source_lang,
            "tl": target_lang,
            "dt": "t",
            "q": text,
        }
    )
    url = f"https://translate.googleapis.com/translate_a/single?{query}"
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    parts = [part[0] for part in payload[0] if part and part[0]]
    return normalize_text("".join(parts))


def translate_lines(lines: list[str]) -> list[str]:
    translated: list[str] = []
    for index, line in enumerate(lines, start=1):
        text = normalize_text(line)
        if not text:
            translated.append("")
            continue

        candidates = [("auto", "vi"), ("zh-CN", "vi"), ("zh-TW", "vi")]
        last_error: Exception | None = None
        translated_text = ""
        for source_lang, target_lang in candidates:
            for attempt in range(3):
                try:
                    translated_text = translate_via_google(text, source_lang, target_lang)
                    if translated_text and cjk_ratio(translated_text) < max(cjk_ratio(text) - 0.2, 0.2):
                        break
                except Exception as exc:  # pragma: no cover
                    last_error = exc
                    time.sleep(1.5 * (attempt + 1))
            if translated_text and cjk_ratio(translated_text) < max(cjk_ratio(text) - 0.2, 0.2):
                break

        if not translated_text:
            raise RuntimeError(f"Translation failed at line {index}: {text}") from last_error
        translated.append(translated_text)
    return translated
