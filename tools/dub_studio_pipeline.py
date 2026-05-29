from __future__ import annotations

import os
import sys
from pathlib import Path

# Force HuggingFace cache to project local workspace directory
ROOT = Path(__file__).resolve().parent.parent
os.environ["HF_HOME"] = str(ROOT / "temp" / ".cache")
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

try:
    from tools.dub_studio.cli import *  # type: ignore # noqa: F401,F403
    from tools.dub_studio.cli import main
except Exception:
    from dub_studio.cli import *  # type: ignore # noqa: F401,F403
    from dub_studio.cli import main


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        try:
            print(f"Pipeline failed: {exc}", file=sys.stderr)
        except (BrokenPipeError, OSError):
            pass
        raise
