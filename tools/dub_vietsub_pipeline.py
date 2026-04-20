from __future__ import annotations

import sys

from dub_vietsub.cli import main


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        raise
