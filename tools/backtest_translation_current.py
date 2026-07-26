from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.backtest_translation_quality_ab import prepare_segments, run_variant
from tools.dub_studio.config import cloud_model_name
from tools.evaluate_translation_output import evaluate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--optimization",
        choices=("legacy", "adaptive"),
        default="legacy",
    )
    parser.add_argument(
        "--judge-mode",
        choices=("local", "cloud"),
        default="local",
    )
    args = parser.parse_args()

    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    source_language = str(analysis.get("sourceLanguage") or "auto")
    target_language = str(analysis.get("targetLanguage") or "vi")
    segments = prepare_segments(analysis, args.limit)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    translation = run_variant(
        mode=args.optimization,
        source_segments=segments,
        source_language=source_language,
        target_language=target_language,
        output_dir=args.output_dir,
        ai_mode="cloud",
    )
    semantic_evaluation = None
    if translation["validForQualityComparison"]:
        semantic_evaluation = evaluate(
            translation["segments"],
            source_language=source_language,
            ai_mode=args.judge_mode,
            semantic_context=translation.get("semanticContext") or {},
        )
    report = {
        "model": cloud_model_name(),
        "optimization": args.optimization,
        "translation": translation,
        "semanticEvaluation": semantic_evaluation,
        "accepted": bool(
            semantic_evaluation and semantic_evaluation.get("accepted")
        ),
    }
    output_path = args.output_dir / "current_quality_report.json"
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "model": report["model"],
                "optimization": report["optimization"],
                "usage": translation["usage"],
                "qualityGate": translation["qualityGate"],
                "semanticEvaluation": semantic_evaluation,
                "report": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["accepted"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
