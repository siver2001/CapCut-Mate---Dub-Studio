from __future__ import annotations

from pathlib import Path

try:
    import config
except Exception:  # pragma: no cover
    config = None

try:  # Optional UI enhancement packages.
    import qtawesome as qta
except Exception:  # pragma: no cover
    qta = None

try:
    from superqt import QLabeledSlider
except Exception:  # pragma: no cover
    QLabeledSlider = None


ROOT = Path(__file__).resolve().parent.parent
PIPELINE_PATH = ROOT / "tools" / "dub_studio_pipeline.py"
PIPELINE_PYTHON = (
    ROOT / ".venv" / "Scripts" / "python.exe"
    if (ROOT / ".venv" / "Scripts" / "python.exe").exists()
    else Path(__import__("sys").executable)
)
TEMP_DUB_DIR = ROOT / "temp" / "dub_studio"
DEFAULT_OUTPUT_DIR = ROOT / "output"

LANGUAGE_OPTIONS = [
    ("auto", "Tự động nhận diện"),
    ("en", "Tiếng Anh"),
    ("zh", "Tiếng Trung"),
    ("ko", "Tiếng Hàn"),
    ("ja", "Tiếng Nhật"),
]

TARGET_LANGUAGE_OPTIONS = [
    ("vi", "Tiếng Việt"),
    ("en", "Tiếng Anh"),
    ("zh", "Tiếng Trung"),
    ("ko", "Tiếng Hàn"),
    ("ja", "Tiếng Nhật"),
]

EDGE_VOICE_OPTIONS = [
    ("edge:male", "EdgeTTS • Nam Nam Minh"),
    ("edge:female", "EdgeTTS • Nữ Hoài My"),
]

VIENEU_PRESET_OPTIONS = [
    ("vieneu:ngoc", "VieNeu-TTS • Bích Ngọc (Nữ - Miền Bắc)"),
    ("vieneu:tuyen", "VieNeu-TTS • Phạm Tuyên (Nam - Miền Bắc)"),
    ("vieneu:doan", "VieNeu-TTS • Thục Đoan (Nữ - Miền Nam)"),
    ("vieneu:vinh", "VieNeu-TTS • Xuân Vĩnh (Nam - Miền Nam)"),
]

VIENEU_CLONE_OPTIONS = [
    ("vieneu:clone", "VieNeu-TTS • Clone từ mẫu speaker"),
]

VOICE_OPTIONS = [*EDGE_VOICE_OPTIONS, *VIENEU_PRESET_OPTIONS]
INTRO_TTS_OPTIONS = [*EDGE_VOICE_OPTIONS, *VIENEU_PRESET_OPTIONS]
VOICE_LABELS = {value: label for value, label in VOICE_OPTIONS}
VOICE_LABELS.update({value: label for value, label in VIENEU_CLONE_OPTIONS})

INTRO_VOICE_PRESETS = {
    "female_soft": {
        "voice": "vi-VN-HoaiMyNeural",
        "label": "Nữ nhẹ nhàng",
        "rateDeltaPercent": -4,
    },
    "female_story": {
        "voice": "vi-VN-HoaiMyNeural",
        "label": "Nữ kể chuyện",
        "rateDeltaPercent": 0,
    },
    "female_bright": {
        "voice": "vi-VN-HoaiMyNeural",
        "label": "Nữ tươi sáng",
        "rateDeltaPercent": 6,
    },
    "female_urgent": {
        "voice": "vi-VN-HoaiMyNeural",
        "label": "Nữ dồn nhịp",
        "rateDeltaPercent": 12,
    },
    "male_calm": {
        "voice": "vi-VN-NamMinhNeural",
        "label": "Nam trầm chậm",
        "rateDeltaPercent": -4,
    },
    "male_story": {
        "voice": "vi-VN-NamMinhNeural",
        "label": "Nam kể chuyện",
        "rateDeltaPercent": 0,
    },
    "male_strong": {
        "voice": "vi-VN-NamMinhNeural",
        "label": "Nam dứt khoát",
        "rateDeltaPercent": 6,
    },
    "male_fast": {
        "voice": "vi-VN-NamMinhNeural",
        "label": "Nam nhịp nhanh",
        "rateDeltaPercent": 12,
    },
}

INTRO_VOICE_OPTIONS = [
    (key, preset["label"]) for key, preset in INTRO_VOICE_PRESETS.items()
]

FONT_OPTIONS = [
    {
        "value": "arial-bold",
        "label": "Arial Bold",
        "cssFontFamily": "Arial",
        "fontFamilyName": "Arial",
        "assFontName": "Arial",
        "draftFontKey": "Poppins_Bold",
    },
    {
        "value": "verdana",
        "label": "Verdana",
        "cssFontFamily": "Verdana",
        "fontFamilyName": "Verdana",
        "assFontName": "Verdana",
        "draftFontKey": "WorkSans_Regular",
    },
    {
        "value": "trebuchet",
        "label": "Trebuchet",
        "cssFontFamily": "Trebuchet MS",
        "fontFamilyName": "Trebuchet MS",
        "assFontName": "Trebuchet MS",
        "draftFontKey": "Poppins_Regular",
    },
    {
        "value": "georgia",
        "label": "Georgia",
        "cssFontFamily": "Georgia",
        "fontFamilyName": "Georgia",
        "assFontName": "Georgia",
        "draftFontKey": "SourceHanSerifCN_Regular",
    },
    {
        "value": "impact",
        "label": "Impact",
        "cssFontFamily": "Impact",
        "fontFamilyName": "Impact",
        "assFontName": "Impact",
        "draftFontKey": "Anton",
    },
]

CLEANUP_OPTIONS = [
    ("localized_blur", "Làm mờ vùng phụ đề cũ"),
    ("localized_mask", "Phủ mềm vùng phụ đề cũ"),
    ("none", "Giữ nguyên phụ đề gốc"),
]

SUBTITLE_VISIBILITY_OPTIONS = [("on", "Có vietsub"), ("off", "Không vietsub")]

SUBTITLE_POSITION_OPTIONS = [
    ("bottom", "Phía dưới"),
    ("middle", "Chính giữa"),
    ("top", "Phía trên"),
]

WATERMARK_POSITION_OPTIONS = [
    ("top-left", "Góc trên trái"),
    ("top-right", "Góc trên phải"),
    ("bottom-left", "Góc dưới trái"),
    ("bottom-right", "Góc dưới phải"),
]

SPEAKER_DETECTION_OPTIONS = [
    ("narrator", "Giọng chung 1 người (mặc định)"),
    ("dialogue", "Hội thoại nhiều người (thủ công)"),
]

TIMING_MODE_OPTIONS = [
    ("balanced_natural", "Tự nhiên cân bằng"),
    ("ultra_tight", "Timing siêu khít"),
]

UI_THEME_OPTIONS = [
    ("cinema", "Cinema"),
    ("news", "News"),
    ("drama", "Drama"),
    ("meme", "Meme"),
    ("pastel", "Pastel"),
]

VIDEO_CODEC_OPTIONS = [
    ("gpu_preferred", "GPU tăng tốc (mặc định)"),
    ("cpu_stable", "CPU ổn định"),
]

TRANSLATE_PROVIDER_OPTIONS = [
    ("auto", "Tự động (ưu tiên Ollama → llama.cpp)"),
    ("ollama", "Ollama (local API, Gemma 4 E2B)"),
    ("llama.cpp", "llama.cpp (local CLI, Gemma 4 E2B)"),
]

DEFAULT_VOICES = [
    "edge:male",
    "edge:male",
    "edge:male",
    "edge:male",
]

SPEAKER_COLORS = ["#FFB703", "#56CFE1", "#EF476F", "#90BE6D"]
FONT_COLOR_SWATCHES = ["#ffd200", "#ffffff", "#8ef9f3", "#ff9f1c", "#ffcad4", "#a7f3d0"]
STROKE_COLOR_SWATCHES = [
    "#000000",
    "#1e293b",
    "#312e81",
    "#7f1d1d",
    "#14532d",
    "#334155",
]
MOJIBAKE_MARKERS = ("Ã", "Â", "Ä", "Æ", "áº", "á»", "â€", "Ã")

UI_THEME_PRESETS = {
    "cinema": {
        "fontFamily": "impact",
        "fontColor": "#ffd200",
        "strokeColor": "#000000",
        "strokeWidth": 3,
        "cleanupMode": "localized_blur",
        "positionPreset": "bottom",
    },
    "news": {
        "fontFamily": "arial-bold",
        "fontColor": "#ffffff",
        "strokeColor": "#0f172a",
        "strokeWidth": 2,
        "cleanupMode": "localized_mask",
        "positionPreset": "bottom",
    },
    "drama": {
        "fontFamily": "georgia",
        "fontColor": "#ffcad4",
        "strokeColor": "#312e81",
        "strokeWidth": 2,
        "cleanupMode": "localized_blur",
        "positionPreset": "middle",
    },
    "meme": {
        "fontFamily": "impact",
        "fontColor": "#ffffff",
        "strokeColor": "#000000",
        "strokeWidth": 4,
        "cleanupMode": "localized_mask",
        "positionPreset": "top",
    },
    "pastel": {
        "fontFamily": "trebuchet",
        "fontColor": "#8ef9f3",
        "strokeColor": "#334155",
        "strokeWidth": 2,
        "cleanupMode": "localized_blur",
        "positionPreset": "bottom",
    },
}
