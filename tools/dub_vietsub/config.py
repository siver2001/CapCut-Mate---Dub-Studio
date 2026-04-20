from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMP_DIR = ROOT / "temp" / "dub_vietsub"
MODEL_PATH = ROOT / "temp" / "models" / "ggml-small.bin"
DEFAULT_VOICES = ["vi-VN-NamMinhNeural", "vi-VN-HoaiMyNeural"]
