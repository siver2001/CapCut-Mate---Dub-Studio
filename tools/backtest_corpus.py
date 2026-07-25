from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.backtest_pipeline_quality import evaluate_analysis, evaluate_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run quality gates across a Dub Studio analysis corpus.")
    parser.add_argument("corpus", type=Path, help="Directory containing job analysis.json files.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    results = []
    candidates = sorted(args.corpus.rglob("analysis.json"))
    for analysis_path in candidates:
        try:
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            report = evaluate_analysis(analysis)
            manifest_candidates = [
                analysis_path.parent / "audio" / "dub_manifest.json",
                analysis_path.parent.parent / "audio" / "dub_manifest.json",
            ]
            manifest_path = next((path for path in manifest_candidates if path.exists()), None)
            if manifest_path:
                report["renderedTimeline"] = evaluate_manifest(
                    manifest_path,
                    video_duration_ms=int((analysis.get("videoMeta") or {}).get("durationMs") or 0),
                )
                if report["renderedTimeline"]["status"] == "blocked":
                    report["status"] = "blocked"
            results.append({"analysisPath": str(analysis_path), **report})
        except Exception as exc:
            results.append({
                "analysisPath": str(analysis_path),
                "status": "blocked",
                "error": str(exc),
            })

    counts = {
        status: sum(1 for item in results if item.get("status") == status)
        for status in ("pass", "warning", "blocked")
    }
    payload = {
        "status": "blocked" if counts["blocked"] else ("warning" if counts["warning"] else "pass"),
        "analysisCount": len(results),
        "counts": counts,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "results"}, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "pass" else (1 if payload["status"] == "warning" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
