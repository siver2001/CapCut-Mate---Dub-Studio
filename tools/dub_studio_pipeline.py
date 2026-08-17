from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
os.environ["HF_HOME"] = str(ROOT / "hf_cache")
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

try:
    from tools.dub_studio.cli import *  # type: ignore # noqa: F401,F403
    from tools.dub_studio.cli import main
except Exception:
    from dub_studio.cli import *  # type: ignore # noqa: F401,F403
    from dub_studio.cli import main


def setup_quiet_excepthook() -> None:
    def custom_excepthook(exc_type, exc_value, exc_traceback):
        import traceback
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        err_msg = str(exc_value) or str(exc_type)
        try:
            import json
            print(f"ERROR::{json.dumps({'message': err_msg})}", flush=True)
            print(f"Pipeline failed: {err_msg}", file=sys.stderr, flush=True)
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)
        except Exception:
            pass
        os._exit(1)
    sys.excepthook = custom_excepthook


if __name__ == "__main__":
    setup_quiet_excepthook()
    try:
        ret = main()
        os._exit(ret if isinstance(ret, int) else 0)
    except Exception as exc:  # pragma: no cover
        import json
        err_msg = str(exc)
        try:
            print(f"ERROR::{json.dumps({'message': err_msg})}", flush=True)
            print(f"Pipeline failed: {err_msg}", file=sys.stderr, flush=True)
        except (BrokenPipeError, OSError):
            pass
        os._exit(1)

