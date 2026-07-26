from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tools.backtest_translation_quality_ab import judge_outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--ai-mode",
        choices=("local", "cloud"),
        default="local",
    )
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    legacy = report["legacy"]
    adaptive = report["adaptive"]
    source_segments = legacy["segments"]
    os.environ["DUB_AI_MODE"] = args.ai_mode
    judge, usage = judge_outputs(
        source_segments,
        legacy,
        adaptive,
        args.ai_mode,
    )
    result = {"judge": judge, "judgeUsage": usage}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
