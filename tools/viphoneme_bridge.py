import sys
import os
import traceback

# Force UTF-8 for everything
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stdin, 'reconfigure'):
    sys.stdin.reconfigure(encoding='utf-8')

# Disable vinorm isolation to avoid hangs on Windows
os.environ["VIPHONEME_ISOLATE_VINORM"] = "0"

# Add tools folder to sys.path to force viphoneme to use our local mock vinorm instead of the broken global site-packages one
from pathlib import Path
tools_dir = str(Path(__file__).parent.resolve())
if tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)

try:
    import viphoneme
    text = sys.stdin.read().strip()
    if not text:
        sys.exit(0)
    ipa = viphoneme.vi2IPA(text)
    sys.stdout.write(ipa)
    sys.stdout.flush()
except Exception:
    # Print error to stderr for debugging
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
