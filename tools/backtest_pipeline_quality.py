from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.dub_studio.quality import audit_timeline, audit_translation_segments


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    segments = [dict(item) for item in analysis.get("segments") or []]
    source_language = str(analysis.get("sourceLanguage") or "auto")
    translation = audit_translation_segments(segments, source_language=source_language)
    timeline = audit_timeline(
        segments,
        video_duration_ms=int((analysis.get("videoMeta") or {}).get("durationMs") or 0),
    )

    source_ids = [str(item.get("sourceSegmentId") or item.get("id") or "") for item in segments]
    source_texts = [str(item.get("sourceText") or "").strip() for item in segments]
    repeated_source_groups = [
        {"count": count, "preview": text[:100]}
        for text, count in Counter(source_texts).most_common()
        if text and count >= 3
    ]
    missing_source_ids = sum(1 for value in source_ids if not value)
    unique_source_ratio = round(len(set(source_texts)) / max(len(source_texts), 1), 4)
    canonical_mapping = {
        "status": "blocked" if missing_source_ids else (
            "warning" if unique_source_ratio < 0.5 else "pass"
        ),
        "missingSourceIdCount": missing_source_ids,
        "uniqueSourceTextRatio": unique_source_ratio,
        "repeatedSourceGroups": repeated_source_groups[:12],
    }
    statuses = [translation["status"], timeline["status"], canonical_mapping["status"]]
    status = "blocked" if "blocked" in statuses else ("warning" if "warning" in statuses else "pass")
    return {
        "status": status,
        "segmentCount": len(segments),
        "translation": translation,
        "timeline": timeline,
        "canonicalMapping": canonical_mapping,
    }


def evaluate_manifest(manifest_path: Path, *, video_duration_ms: int) -> dict[str, Any]:
    rows = _load(manifest_path)
    segments = [
        {"startMs": row.get("start_ms", 0), "endMs": row.get("end_ms", 0)}
        for row in rows
    ]
    return audit_timeline(segments, video_duration_ms=video_duration_ms)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest semantic and timeline quality gates.")
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    analysis = _load(args.analysis)
    report = evaluate_analysis(analysis)
    if args.manifest and args.manifest.exists():
        report["renderedTimeline"] = evaluate_manifest(
            args.manifest,
            video_duration_ms=int((analysis.get("videoMeta") or {}).get("durationMs") or 0),
        )
        if report["renderedTimeline"]["status"] == "blocked":
            report["status"] = "blocked"

    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized)
    return 0 if report["status"] == "pass" else (1 if report["status"] == "warning" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
