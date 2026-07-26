from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any

from tools.dub_studio.cli_parts.render import _split_segments_into_sentences
from tools.dub_studio.cli_parts.runtime import (
    get_ai_usage_stats,
    reset_ai_usage_stats,
    reset_cloud_ai_circuit_breaker,
    run_ollama_prompt,
)
from tools.dub_studio.cli_parts.translation import translate_segments
from tools.dub_studio.quality import audit_translation_segments


def prepare_segments(analysis: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    collapsed: list[dict[str, Any]] = []
    for item in analysis.get("segments") or []:
        source = str(item.get("sourceText") or "").strip()
        if not source:
            continue
        if (
            collapsed
            and collapsed[-1]["text"] == source
            and collapsed[-1]["speakerId"]
            == str(item.get("speakerId") or "speaker_1")
        ):
            collapsed[-1]["endMs"] = max(
                collapsed[-1]["endMs"],
                int(item.get("endMs") or 0),
            )
            continue
        collapsed.append(
            {
                "text": source,
                "startMs": int(item.get("startMs") or 0),
                "endMs": int(item.get("endMs") or 0),
                "speakerId": str(item.get("speakerId") or "speaker_1"),
            }
        )
    selected = _split_segments_into_sentences(collapsed)[: max(limit, 1)]
    for index, item in enumerate(selected, start=1):
        item["id"] = f"quality_{index:04d}"
        item["sourceSegmentId"] = item["id"]
    return selected


def run_variant(
    *,
    mode: str,
    source_segments: list[dict[str, Any]],
    source_language: str,
    target_language: str,
    output_dir: Path,
    ai_mode: str,
) -> dict[str, Any]:
    segments = copy.deepcopy(source_segments)
    variant_dir = output_dir / mode
    variant_dir.mkdir(parents=True, exist_ok=True)
    os.environ["DUB_TRANSLATION_OPTIMIZATION"] = mode
    os.environ["DUB_AI_MODE"] = ai_mode
    os.environ["DUB_TRANSLATE_PROVIDER"] = "ollama"
    reset_cloud_ai_circuit_breaker()
    reset_ai_usage_stats()
    translated = translate_segments(
        segments,
        source_language,
        variant_dir / "translated.json",
        target_language=target_language,
        phase=f"backtest_{mode}",
        localization_mode="literal",
    )
    usage = get_ai_usage_stats()
    try:
        semantic_context = json.loads(
            (variant_dir / "translation_context.json").read_text(encoding="utf-8")
        ).get("context") or {}
    except Exception:
        semantic_context = {}
    quality = audit_translation_segments(
        translated,
        source_language=source_language,
    )
    reviewed = sum(
        bool((item.get("translationRisk") or {}).get("reviewed"))
        for item in translated
    )
    providers = sorted(
        {
            str(item.get("translationProvider") or "unknown")
            for item in translated
            if item.get("sourceText")
        }
    )
    return {
        "mode": mode,
        "usage": usage,
        "reviewedSegmentCount": reviewed,
        "segmentCount": len(translated),
        "qualityGate": quality,
        "translationProviders": providers,
        "semanticContext": semantic_context,
        "validForQualityComparison": bool(translated)
        and not ({"fallback", "ai_unreviewed"} & set(providers))
        and not quality.get("criticalCount")
        and not quality.get("warningCount"),
        "segments": translated,
    }


def judge_outputs(
    source_segments: list[dict[str, Any]],
    legacy: dict[str, Any],
    adaptive: dict[str, Any],
    ai_mode: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    rows = []
    for source, old, new in zip(
        source_segments,
        legacy["segments"],
        adaptive["segments"],
    ):
        rows.append(
            {
                "sourceId": source["id"],
                "sourceText": source["sourceText"],
                "legacy": old.get("finalText") or old.get("translatedText") or "",
                "adaptive": new.get("finalText") or new.get("translatedText") or "",
                "durationMs": int(source.get("endMs", 0))
                - int(source.get("startMs", 0)),
            }
        )
    prompt = (
        "You are an impartial senior Vietnamese audiovisual translation evaluator. "
        "Blindly compare LEGACY and ADAPTIVE translations against every source segment.\n"
        "Score each system from 0 to 10 for: semanticFidelity, crossSegmentCoherence, "
        "terminologyConsistency, naturalVietnamese, dubbingTiming, and overall.\n"
        "Penalize invented facts, missing subjects/actions/negation/uncertainty, wrong numbers, "
        "wrong relationships, inconsistent names/pronouns, source-language leakage, and text "
        "that cannot be spoken in the allotted duration. Do not reward verbosity or style when "
        "meaning changes. A difference in wording alone is not an error. Source segments may "
        "split one sentence mid-phrase, so judge combined meaning across immediate neighbors. "
        "Score from 0 to 10; use 8.5 for eight-and-a-half, never 0.85.\n"
        "List every material error with sourceId, system, category and concise explanation. "
        "Choose preferredSystem as legacy, adaptive, or tie. Return JSON only.\n\n"
        f"DATA:\n{json.dumps(rows, ensure_ascii=False)}"
    )
    score_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "semanticFidelity",
            "crossSegmentCoherence",
            "terminologyConsistency",
            "naturalVietnamese",
            "dubbingTiming",
            "overall",
        ],
        "properties": {
            name: {"type": "number", "minimum": 0, "maximum": 10}
            for name in (
                "semanticFidelity",
                "crossSegmentCoherence",
                "terminologyConsistency",
                "naturalVietnamese",
                "dubbingTiming",
                "overall",
            )
        },
    }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "preferredSystem",
            "legacyScores",
            "adaptiveScores",
            "materialErrors",
            "summary",
        ],
        "properties": {
            "preferredSystem": {
                "type": "string",
                "enum": ["legacy", "adaptive", "tie"],
            },
            "legacyScores": score_schema,
            "adaptiveScores": score_schema,
            "materialErrors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["sourceId", "system", "category", "explanation"],
                    "properties": {
                        "sourceId": {"type": "string"},
                        "system": {
                            "type": "string",
                            "enum": ["legacy", "adaptive", "both"],
                        },
                        "category": {"type": "string"},
                        "explanation": {"type": "string"},
                    },
                },
            },
            "summary": {"type": "string"},
        },
    }
    reset_cloud_ai_circuit_breaker()
    reset_ai_usage_stats()
    os.environ["DUB_AI_MODE"] = ai_mode
    judged = json.loads(
        run_ollama_prompt(
            prompt,
            max_tokens=3200,
            temperature=0.0,
            timeout=120,
            json_schema=schema,
        )
    )
    return judged, get_ai_usage_stats()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--ai-mode",
        choices=("cloud", "local"),
        default="cloud",
        help="Provider used for translation and the blind quality judge.",
    )
    parser.add_argument(
        "--judge-ai-mode",
        choices=("cloud", "local"),
        help="Optional independent judge provider; defaults to --ai-mode.",
    )
    parser.add_argument(
        "--baseline-report",
        type=Path,
        help="Reuse the legacy result from an earlier valid A/B report.",
    )
    args = parser.parse_args()

    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    source_language = str(analysis.get("sourceLanguage") or "auto")
    target_language = str(analysis.get("targetLanguage") or "vi")
    source_segments = prepare_segments(analysis, args.limit)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.baseline_report:
        baseline_payload = json.loads(
            args.baseline_report.read_text(encoding="utf-8")
        )
        legacy = baseline_payload["legacy"]
    else:
        legacy = run_variant(
            mode="legacy",
            source_segments=source_segments,
            source_language=source_language,
            target_language=target_language,
            output_dir=args.output_dir,
            ai_mode=args.ai_mode,
        )
    adaptive = run_variant(
        mode="adaptive",
        source_segments=source_segments,
        source_language=source_language,
        target_language=target_language,
        output_dir=args.output_dir,
        ai_mode=args.ai_mode,
    )
    judge: dict[str, Any] | None = None
    judge_usage: dict[str, int] = {}
    judge_error: dict[str, str] | None = None
    comparison_valid = bool(
        legacy["validForQualityComparison"]
        and adaptive["validForQualityComparison"]
    )
    if comparison_valid:
        try:
            judge_ai_mode = args.judge_ai_mode or args.ai_mode
            judge, judge_usage = judge_outputs(
                source_segments,
                legacy,
                adaptive,
                judge_ai_mode,
            )
        except Exception as exc:
            judge_error = {
                "type": type(exc).__name__,
                "code": str(getattr(exc, "code", "") or ""),
                "message": str(exc),
            }
    else:
        judge_error = {
            "type": "InvalidComparison",
            "code": "fallback_or_quality_gate_failure",
            "message": (
                "Không chấm A/B vì ít nhất một biến thể dùng bản dịch fallback "
                "hoặc không vượt quality gate."
            ),
        }

    token_savings: float | None = None
    request_savings: float | None = None
    if comparison_valid:
        old_total = max(int(legacy["usage"].get("totalTokens") or 0), 1)
        new_total = int(adaptive["usage"].get("totalTokens") or 0)
        token_savings = round((1 - new_total / old_total) * 100, 2)
        request_savings = round(
            (
                1
                - int(adaptive["usage"].get("requests") or 0)
                / max(int(legacy["usage"].get("requests") or 0), 1)
            )
            * 100,
            2,
        )
    comparison = {
        "tokenSavingsPercent": token_savings,
        "requestSavingsPercent": request_savings,
        "legacy": legacy,
        "adaptive": adaptive,
        "comparisonValid": comparison_valid and judge is not None,
        "judge": judge,
        "judgeError": judge_error,
        "judgeUsage": judge_usage,
    }
    output_path = args.output_dir / "quality_ab_report.json"
    output_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "tokenSavingsPercent": comparison["tokenSavingsPercent"],
                "requestSavingsPercent": comparison["requestSavingsPercent"],
                "legacyUsage": legacy["usage"],
                "adaptiveUsage": adaptive["usage"],
                "legacyReviewed": legacy["reviewedSegmentCount"],
                "adaptiveReviewed": adaptive["reviewedSegmentCount"],
                "judge": judge,
                "judgeError": judge_error,
                "report": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not comparison["comparisonValid"]:
        return 4
    adaptive_score = float(judge["adaptiveScores"]["overall"])
    legacy_score = float(judge["legacyScores"]["overall"])
    return 0 if adaptive_score >= legacy_score - 0.25 else 3


if __name__ == "__main__":
    raise SystemExit(main())
