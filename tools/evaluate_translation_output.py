from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from tools.dub_studio.cli_parts.runtime import (
    get_ai_usage_stats,
    reset_ai_usage_stats,
    reset_cloud_ai_circuit_breaker,
    run_ollama_prompt,
)
from tools.dub_studio.quality import audit_translation_segments


SCORE_NAMES = (
    "semanticFidelity",
    "crossSegmentCoherence",
    "terminologyConsistency",
    "naturalVietnamese",
    "dubbingTiming",
    "overall",
)


def _score_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(SCORE_NAMES),
        "properties": {
            name: {"type": "number", "minimum": 0, "maximum": 10}
            for name in SCORE_NAMES
        },
    }


def evaluate(
    segments: list[dict[str, Any]],
    *,
    source_language: str,
    ai_mode: str,
    semantic_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = []
    for index, item in enumerate(segments, start=1):
        rows.append(
            {
                "sourceId": str(item.get("id") or f"segment_{index}"),
                "sourceText": str(item.get("sourceText") or ""),
                "translation": str(
                    item.get("finalText") or item.get("translatedText") or ""
                ),
                "durationMs": max(
                    int(item.get("endMs") or 0) - int(item.get("startMs") or 0),
                    0,
                ),
            }
        )
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["scores", "materialErrors", "verdict", "summary"],
        "properties": {
            "scores": _score_schema(),
            "materialErrors": {
                "type": "array",
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "sourceId",
                        "category",
                        "severity",
                        "explanation",
                    ],
                    "properties": {
                        "sourceId": {"type": "string"},
                        "category": {"type": "string", "maxLength": 80},
                        "severity": {
                            "type": "string",
                            "enum": ["minor", "major", "critical"],
                        },
                        "explanation": {"type": "string", "maxLength": 320},
                    },
                },
            },
            "verdict": {
                "type": "string",
                "enum": ["excellent", "good", "needs_revision", "reject"],
            },
            "summary": {"type": "string", "maxLength": 600},
        },
    }
    prompt = (
        "You are an independent senior Vietnamese audiovisual translation QA editor. "
        f"The source language is {source_language}. Evaluate the actual Vietnamese output, "
        "not whether software execution succeeded.\n"
        "Check every source against its translation and the adjacent segments. Penalize "
        "missing or invented facts, wrong entities, actions, relationships, negation, "
        "uncertainty, numbers or units; inconsistent names/pronouns/terms; broken narrative "
        "connections; unnatural Vietnamese; and wording that cannot be spoken naturally "
        "within durationMs. Wording differences alone are not errors. Segment boundaries are "
        "timing markers, not sentence boundaries. First compare CONTINUOUS_SOURCE with "
        "CONTINUOUS_TRANSLATION as whole passages. A fact is missing only if it is absent from "
        "the whole translated passage, not merely moved to an adjacent segment. Do not report "
        "a truncated clause at a segment edge as an error when the next segment completes it. "
        "Never list sentence-boundary completion itself as a material error. Treat uncertainTerms "
        "and high-confidence glossary entries as the resolved meaning of corrupted ASR; do not "
        "reinterpret those corrupted characters literally or swap their associated entities. "
        "Then use rows only to assess chronology, local alignment, and timing. Score every "
        "Treat high-confidence entries in REFERENCE_CONTRACT as already verified; do not "
        "reclassify their canonicalEnglish or vietnameseTerm as hallucinations. Judge whether "
        "the output uses them consistently. Score every category from 0 to 10; use 8.5 for "
        "eight-and-a-half, never 0.85. List at most 12 distinct material errors "
        "and keep each explanation under 45 words. Return JSON only.\n\n"
        f"CONTINUOUS_SOURCE:\n{' '.join(row['sourceText'] for row in rows)}\n\n"
        f"CONTINUOUS_TRANSLATION:\n{' '.join(row['translation'] for row in rows)}\n\n"
        f"REFERENCE_CONTRACT:\n{json.dumps(semantic_context or {}, ensure_ascii=False)}\n\n"
        f"TIMED_ROWS:\n{json.dumps(rows, ensure_ascii=False)}"
    )
    os.environ["DUB_AI_MODE"] = ai_mode
    reset_cloud_ai_circuit_breaker()
    reset_ai_usage_stats()
    hard_gate = audit_translation_segments(
        segments,
        source_language=source_language,
    )
    try:
        judged = json.loads(
            run_ollama_prompt(
                prompt,
                max_tokens=4096,
                temperature=0.0,
                timeout=180,
                json_schema=schema,
            )
        )
    except Exception as exc:
        return {
            "accepted": False,
            "judge": None,
            "judgeError": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
            "hardGate": hard_gate,
            "judgeUsage": get_ai_usage_stats(),
            "segmentCount": len(segments),
        }
    scores = judged.get("scores") or {}
    material_errors = judged.get("materialErrors") or []
    # The local semantic judge is advisory: it can mistranslate noisy ASR and
    # occasionally emit duplicate/contradictory findings. Production acceptance
    # therefore uses its category scores together with deterministic source-leak,
    # timing and semantic-contract gates, rather than one ungrounded severity label.
    accepted = bool(
        not hard_gate.get("criticalCount")
        and not hard_gate.get("warningCount")
        and float(scores.get("semanticFidelity") or 0) >= 8.0
        and float(scores.get("crossSegmentCoherence") or 0) >= 7.5
        and float(scores.get("terminologyConsistency") or 0) >= 8.0
        and float(scores.get("naturalVietnamese") or 0) >= 8.0
        and float(scores.get("dubbingTiming") or 0) >= 7.0
        and float(scores.get("overall") or 0) >= 9.0
    )
    return {
        "accepted": accepted,
        "judge": judged,
        "judgeMaterialErrorsAdvisory": True,
        "hardGate": hard_gate,
        "judgeUsage": get_ai_usage_stats(),
        "segmentCount": len(segments),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    parser.add_argument("--source-language", default="zh")
    parser.add_argument("--ai-mode", choices=("cloud", "local"), default="local")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.result.read_text(encoding="utf-8"))
    segments = payload.get("segments") or []
    report = evaluate(
        segments,
        source_language=args.source_language,
        ai_mode=args.ai_mode,
        semantic_context=None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["accepted"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
