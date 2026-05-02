import sys
import os

# ---------------------------------------------------------
# PyInstaller Worker / Pipeline Entry Mode
# ---------------------------------------------------------
if len(sys.argv) > 1 and sys.argv[1] == "pipeline":
    # If called with 'pipeline' argument, act as the dub studio worker.
    # This allows the packaged .exe to call itself as the subprocess.
    sys.argv.pop(1)
    # Add root to path for imports
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    from tools.dub_studio_pipeline import main as run_pipeline
    sys.exit(run_pipeline())

from gui.main import main
if __name__ == "__main__":
    sys.exit(main())