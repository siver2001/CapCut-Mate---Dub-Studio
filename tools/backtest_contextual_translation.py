from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from tools.dub_studio.cli_parts.translation import translate_segments
from tools.dub_studio.cli_parts.render import _split_segments_into_sentences
from tools.dub_studio.quality import audit_translation_segments


def main() -> int:
    parser = argparse.ArgumentParser(description="Live contextual translation backtest on an existing analysis.")
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    collapsed: list[dict] = []
    for item in analysis.get("segments") or []:
        source_text = str(item.get("sourceText") or "").strip()
        if collapsed and collapsed[-1]["text"] == source_text:
            collapsed[-1]["endMs"] = max(collapsed[-1]["endMs"], int(item.get("endMs") or 0))
            continue
        collapsed.append({
            "text": source_text,
            "startMs": int(item.get("startMs") or 0),
            "endMs": int(item.get("endMs") or 0),
            "speakerId": str(item.get("speakerId") or "speaker_1"),
        })
    selected = copy.deepcopy(
        _split_segments_into_sentences(collapsed)[: max(args.limit, 1)]
    )
    for index, item in enumerate(selected, start=1):
        item["id"] = str(item.get("sourceSegmentId") or f"backtest_{index:04d}")
        item.pop("translatedText", None)
        item.pop("machineTranslatedText", None)
        item.pop("faithfulTranslation", None)
        item.pop("spokenAdaptation", None)
        item.pop("finalText", None)
        item.pop("translationPromptVersion", None)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    translated = translate_segments(
        selected,
        str(analysis.get("sourceLanguage") or "auto"),
        args.output_dir / "translated.json",
        target_language=str(analysis.get("targetLanguage") or "vi"),
        phase="backtest",
        localization_mode="literal",
    )
    report = audit_translation_segments(
        translated,
        source_language=str(analysis.get("sourceLanguage") or "auto"),
    )
    payload = {"report": report, "segments": translated}
    (args.output_dir / "result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
