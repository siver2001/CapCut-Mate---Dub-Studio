from __future__ import annotations

import os
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", write_through=True)
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", write_through=True)
    except Exception:
        pass

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
    CODE_ROOT = Path(getattr(sys, "_MEIPASS", ROOT)).resolve()
else:
    ROOT = Path(__file__).resolve().parents[2]
    CODE_ROOT = ROOT

for _path in (CODE_ROOT, ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def load_local_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.replace("\x00", "").strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env(ROOT / ".env")

try:
    import config  # noqa: E402
except Exception:  # pragma: no cover
    config = None


def env_value(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def env_bool(*names: str, default: bool = False) -> bool:
    for name in names:
        value = os.getenv(name)
        if value is None or not str(value).strip():
            continue
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    return default


MODEL_CANDIDATES = [
    ROOT / "temp" / "models" / "ggml-small.bin",
    ROOT / "temp" / "models" / "ggml-base.bin",
]
FFMPEG_BIN_DIR = ROOT / "tools" / "bin"
BUNDLED_FFMPEG_BIN_DIR = CODE_ROOT / "tools" / "bin"
for _ffmpeg_dir in (FFMPEG_BIN_DIR, BUNDLED_FFMPEG_BIN_DIR):
    if _ffmpeg_dir.exists():
        os.environ["PATH"] = str(_ffmpeg_dir) + os.pathsep + os.environ.get("PATH", "")

WHISPER_CPP_MODEL_REPO = env_value("DUB_WHISPER_CPP_MODEL_REPO", default="ggerganov/whisper.cpp")
WHISPER_CPP_MODEL_FILENAME = env_value("DUB_WHISPER_CPP_MODEL_FILENAME", default="ggml-small.bin")
OLLAMA_BIN = env_value("DUB_OLLAMA_BIN", default="")
OLLAMA_WINGET_ID = env_value("DUB_OLLAMA_WINGET_ID", default="Ollama.Ollama")
LLAMA_CPP_MODEL_URL = env_value("DUB_LLAMA_CPP_MODEL_URL", default="")

DUB_TRANSCRIBE_PROVIDER = env_value("DUB_TRANSCRIBE_PROVIDER", default="auto").lower()
DUB_TRANSLATE_PROVIDER = env_value("DUB_TRANSLATE_PROVIDER", default="ollama").lower()
MICROSOFT_TRANSLATOR_KEY = env_value(
    "DUB_MICROSOFT_TRANSLATOR_KEY",
    "MICROSOFT_TRANSLATOR_KEY",
    "AZURE_TRANSLATOR_KEY",
    default="",
)
MICROSOFT_TRANSLATOR_ENDPOINT = (
    env_value(
        "DUB_MICROSOFT_TRANSLATOR_ENDPOINT",
        "MICROSOFT_TRANSLATOR_ENDPOINT",
        "AZURE_TRANSLATOR_ENDPOINT",
        default="https://api.cognitive.microsofttranslator.com",
    ).rstrip("/")
    or "https://api.cognitive.microsofttranslator.com"
)
MICROSOFT_TRANSLATOR_REGION = env_value(
    "DUB_MICROSOFT_TRANSLATOR_REGION",
    "MICROSOFT_TRANSLATOR_REGION",
    "AZURE_TRANSLATOR_REGION",
    default="",
)
MICROSOFT_TRANSLATOR_TIMEOUT = max(
    int(env_value("DUB_MICROSOFT_TRANSLATOR_TIMEOUT", default="20")),
    5,
)
DUB_USE_GPU = True
DUB_USE_OMNIVOICE = env_bool("DUB_USE_OMNIVOICE", default=True)
DUB_USE_VALTEC = env_bool("DUB_USE_VALTEC", default=True)
DUB_VALTEC_PRELOAD_ZEROSHOT = env_bool("DUB_VALTEC_PRELOAD_ZEROSHOT", default=False)
DUB_TTS_ENABLE_PARALLEL = env_bool("DUB_TTS_ENABLE_PARALLEL", default=True)
DUB_TTS_ALLOW_SILENT_FALLBACK = env_bool("DUB_TTS_ALLOW_SILENT_FALLBACK", default=False)
DUB_ENABLE_ENERGY_MATCHING = False
DUB_MAX_ENERGY_GAIN_DB = float(env_value("DUB_MAX_ENERGY_GAIN_DB", default="7.0"))
DUB_SOURCE_SEPARATION_ENABLED = True
DUB_SOURCE_SEPARATION_PROVIDER = env_value("DUB_SOURCE_SEPARATION_PROVIDER", default="torchaudio").lower()
DUB_SOURCE_SEPARATION_MODEL = env_value("DUB_SOURCE_SEPARATION_MODEL", default="htdemucs")
DUB_SOURCE_SEPARATION_STEM = env_value("DUB_SOURCE_SEPARATION_STEM", default="vocals")
DUB_SOURCE_SEPARATION_TIMEOUT = max(int(env_value("DUB_SOURCE_SEPARATION_TIMEOUT", default="1800")), 120)
DUB_BACKGROUND_AUDIO_GAIN = float(env_value("DUB_BACKGROUND_AUDIO_GAIN", default="0.92"))
DUB_ORIGINAL_AUDIO_FALLBACK_GAIN = float(env_value("DUB_ORIGINAL_AUDIO_FALLBACK_GAIN", default="0.12"))
DUB_GPU_DEVICE = 0
DUB_STUDIO_DIR = ROOT / "temp" / "dub_studio"
LLAMA_CPP_BIN = env_value("DUB_LLAMA_CPP_BIN", default="")
LLAMA_CPP_MODEL = env_value("DUB_LLAMA_CPP_MODEL", default="")
LLAMA_CPP_MODEL_NAME = env_value("DUB_LLAMA_CPP_MODEL_NAME", default="gemma4-e2b") or "gemma4-e2b"
LLAMA_CPP_CTX = max(int(env_value("DUB_LLAMA_CPP_CTX", default="4096")), 1024)
LLAMA_CPP_THREADS = max(
    int(env_value("DUB_LLAMA_CPP_THREADS", default=str(max((os.cpu_count() or 8) // 2, 4)))),
    1,
)
LLAMA_CPP_N_GPU_LAYERS = int(env_value("DUB_LLAMA_CPP_N_GPU_LAYERS", default=("999" if DUB_USE_GPU else "0")))
LLAMA_CPP_TEMP = float(env_value("DUB_LLAMA_CPP_TEMP", default="0.2"))
OLLAMA_BASE_URL = env_value("DUB_OLLAMA_BASE_URL", default="http://localhost:11434").rstrip("/")
OLLAMA_MODEL = env_value("DUB_OLLAMA_MODEL", default="qwen3.5:4b")
OLLAMA_CTX = max(int(env_value("DUB_OLLAMA_CTX", default="8192")), 1024)
OLLAMA_TEMP = float(env_value("DUB_OLLAMA_TEMP", default="0.30"))
OLLAMA_TIMEOUT = int(env_value("DUB_OLLAMA_TIMEOUT", default="150"))
OLLAMA_MAX_TIMEOUT = max(int(env_value("DUB_OLLAMA_MAX_TIMEOUT", default="420")), OLLAMA_TIMEOUT)
OLLAMA_KEEP_ALIVE = env_value("DUB_OLLAMA_KEEP_ALIVE", default="5m")
OLLAMA_WARMUP = env_bool("DUB_OLLAMA_WARMUP", default=True)
OLLAMA_WARMUP_TIMEOUT = max(int(env_value("DUB_OLLAMA_WARMUP_TIMEOUT", default="120")), 15)
EDGE_TTS_TIMEOUT = max(int(env_value("DUB_EDGE_TTS_TIMEOUT", default="45")), 10)
EDGE_TTS_CONCURRENCY = max(
    int(
        env_value(
            "DUB_EDGE_TTS_CONCURRENCY",
            default="1",
        )
    ),
    1,
)
DUB_SUBTITLE_REGION_SAMPLES = 2
OMNIVOICE_TTS_CONCURRENCY = max(
    int(
        env_value(
            "DUB_OMNIVOICE_TTS_CONCURRENCY",
            default=("1" if DUB_USE_GPU else "2"),
        )
    ),
    1,
)
TTS_FIT_CACHE_ENABLED = env_bool("DUB_TTS_FIT_CACHE_ENABLED", default=True)
VIDEO_X264_PRESET = env_value("DUB_VIDEO_X264_PRESET", default="veryfast") or "veryfast"
VIDEO_X264_CRF = max(int(env_value("DUB_VIDEO_X264_CRF", default="23")), 18)
VIDEO_NVENC_PRESET = env_value("DUB_VIDEO_NVENC_PRESET", default="p4") or "p4"
VIDEO_NVENC_CQ = max(int(env_value("DUB_VIDEO_NVENC_CQ", default="23")), 18)
VIDEO_AMF_PRESET = env_value("DUB_VIDEO_AMF_PRESET", default="speed") or "speed"
VIDEO_AMF_QUALITY = env_value("DUB_VIDEO_AMF_QUALITY", default="speed") or "speed"
TRANSLATE_BATCH_SIZE = max(int(env_value("DUB_TRANSLATE_BATCH_SIZE", default="4")), 1)
TRANSLATE_FIRST_BATCH_SIZE = max(
    int(env_value("DUB_TRANSLATE_FIRST_BATCH_SIZE", default=str(min(TRANSLATE_BATCH_SIZE, 4)))),
    1,
)
OLLAMA_TOKENS_PER_ITEM = max(int(env_value("DUB_OLLAMA_TOKENS_PER_ITEM", default="256")), 96)
OLLAMA_TOKENS_MIN = max(int(env_value("DUB_OLLAMA_TOKENS_MIN", default="320")), 128)
LLAMA_CPP_TIMEOUT = max(int(env_value("DUB_LLAMA_CPP_TIMEOUT", default="180")), 30)
WHISPERX_MODEL = env_value("DUB_WHISPERX_MODEL", "WHISPERX_MODEL", default="large-v3") or "large-v3"
WHISPERX_ASR_REPO = env_value("DUB_WHISPERX_ASR_REPO", default="")
HUGGINGFACE_HUB_CACHE = Path(
    env_value("DUB_HF_CACHE_DIR", default=str(ROOT / "temp" / ".cache" / "huggingface" / "hub"))
).expanduser()
WHISPERX_BATCH_SIZE = max(
    int(env_value("DUB_WHISPERX_BATCH_SIZE", "WHISPERX_BATCH_SIZE", default=("4" if DUB_USE_GPU else "1"))),
    1,
)
WHISPERX_THREADS = max(
    int(
        env_value(
            "DUB_WHISPERX_THREADS",
            "WHISPERX_THREADS",
            default=("4" if DUB_USE_GPU else str(min(max(os.cpu_count() or 8, 4), 8))),
        )
    ),
    1,
)
WHISPERX_COMPUTE_TYPE = env_value(
    "DUB_WHISPERX_COMPUTE_TYPE",
    "WHISPERX_COMPUTE_TYPE",
    default=("float16" if DUB_USE_GPU else "int8"),
) or ("float16" if DUB_USE_GPU else "int8")
WHISPERX_DIARIZATION_MAX_SPEAKERS = max(
    int(
        env_value(
            "DUB_WHISPERX_DIARIZATION_MAX_SPEAKERS",
            "WHISPERX_DIARIZATION_MAX_SPEAKERS",
            default="4",
        )
    ),
    1,
)
WHISPERX_DIARIZATION_MODEL = env_value("DUB_WHISPERX_DIARIZATION_MODEL", default="")
EDGE_VOICE_PRESETS = {
    "edge:female": "vi-VN-HoaiMyNeural",
    "edge:male": "vi-VN-NamMinhNeural",
}
EDGE_VOICE_NAME_PATTERN = re.compile(r"^[a-z]{2,5}-[A-Z]{2,5}-.+Neural$")
# Cloning presets removed
OMNIVOICE_PRESET_VOICE_IDS = {}
VALTEC_PRESET_SPEAKER_IDS = {
    "valtec:nf": "NF",
    "valtec:sf": "SF",
    "valtec:nm1": "NM1",
    "valtec:sm": "SM",
    "valtec:nm2": "NM2",
}
VALTEC_REFERENCE_VOICES = {
    "valtec:thu_ha": {"filename": "thu_ha.wav", "label": "Valtec-TTS • Thu Hà"},
    "valtec:minh_duc": {"filename": "minh_duc.wav", "label": "Valtec-TTS • Minh Đức"},
    "valtec:thanh_tam": {"filename": "thanh_tam.wav", "label": "Valtec-TTS • Thanh Tâm"},
    "valtec:quang_huy": {"filename": "quang_huy.wav", "label": "Valtec-TTS • Quang Huy"},
    "valtec:ngoc_anh": {"filename": "ngoc_anh.wav", "label": "Valtec-TTS • Ngọc Ánh"},
    "valtec:hoang_nam": {"filename": "hoang_nam.wav", "label": "Valtec-TTS • Hoàng Nam"},
}

CUSTOM_VALTEC_VOICES_FILE = ROOT / "config" / "custom_valtec_voices.json"
if CUSTOM_VALTEC_VOICES_FILE.exists():
    try:
        import json
        custom_data = json.loads(CUSTOM_VALTEC_VOICES_FILE.read_text(encoding="utf-8"))
        for k, v in custom_data.items():
            VALTEC_REFERENCE_VOICES[k] = v
    except Exception:
        pass

OMNIVOICE_CLONE_PRESET = "omnivoice:clone"
# OmniVoice models are managed by the omnivoice library and downloaded dynamically.
OMNIVOICE_MODEL_DIR = ROOT / "temp" / "models" / "omnivoice"

CUSTOM_OMNIVOICE_VOICES_FILE = ROOT / "config" / "custom_omnivoice_voices.json"
OMNIVOICE_REFERENCE_DIR = ROOT / "config" / "voices" / "omnivoice"
CUSTOM_OMNIVOICE_VOICES = {}
if CUSTOM_OMNIVOICE_VOICES_FILE.exists():
    try:
        import json
        custom_data = json.loads(CUSTOM_OMNIVOICE_VOICES_FILE.read_text(encoding="utf-8"))
        for k, v in custom_data.items():
            CUSTOM_OMNIVOICE_VOICES[k] = v
    except Exception:
        pass

VALTEC_CLONE_PRESET = "valtec:clone"
VALTEC_REPO_URL = env_value("DUB_VALTEC_REPO_URL", default="https://github.com/tronghieuit/valtec-tts.git")
VALTEC_ZEROSHOT_REPO = env_value("DUB_VALTEC_ZEROSHOT_REPO", default="valtecAI-team/valtec-zeroshot-voice-cloning")
LOCAL_TRANSCRIBE_PROVIDERS = {"ffmpeg", "ffmpeg_whisper", "ffmpeg-whisper", "local"}
VALTEC_MODEL_DIR = ROOT / "temp" / "models" / "valtec"
VALTEC_ZEROSHOT_MODEL_DIR = VALTEC_MODEL_DIR / "models" / "zeroshot-vietnamese"
VALTEC_HASP_MODEL_DIR = VALTEC_MODEL_DIR / "models" / "hasp"
VALTEC_REFERENCE_DIR = VALTEC_MODEL_DIR / "references"
VALTEC_ZEROSHOT_CODE_PATH = CODE_ROOT / "tools" / "valtec_repo" / "valtec_tts" / "zeroshot.py"
VALTEC_ZEROSHOT_AVAILABLE = VALTEC_ZEROSHOT_CODE_PATH.exists()
if not VALTEC_ZEROSHOT_AVAILABLE:
    VALTEC_REFERENCE_VOICES = {}

DEFAULT_VOICES = (
    [
        "valtec:thanh_tam",
        "valtec:thu_ha",
        "valtec:nf",
        "valtec:nm1",
        "valtec:sf",
        "valtec:sm",
        "valtec:nm2",
    ]
    if VALTEC_ZEROSHOT_AVAILABLE
    else [
        "valtec:nf",
        "valtec:sf",
        "valtec:nm1",
        "valtec:sm",
        "valtec:nm2",
    ]
)
VOICE_LABELS = {
    "edge:female": "EdgeTTS • Nữ Hoài My",
    "edge:male": "EdgeTTS • Nam Nam Minh",
    "valtec:nf": "Valtec-TTS • NF Nu Bac",
    "valtec:sf": "Valtec-TTS • SF Nu Nam",
    "valtec:nm1": "Valtec-TTS • NM1 Nam Bac",
    "valtec:sm": "Valtec-TTS • SM Nam Nam",
    "valtec:nm2": "Valtec-TTS • NM2 Nam Bac 2",
    "valtec:thu_ha": "Valtec-TTS • Thu Hà",
    "valtec:minh_duc": "Valtec-TTS • Minh Đức",
    "valtec:thanh_tam": "Valtec-TTS • Thanh Tâm",
    "valtec:quang_huy": "Valtec-TTS • Quang Huy",
    "valtec:ngoc_anh": "Valtec-TTS • Ngọc Ánh",
    "valtec:hoang_nam": "Valtec-TTS • Hoàng Nam",
    "vi-VN-HoaiMyNeural": "EdgeTTS • Nữ Hoài My",
    "vi-VN-NamMinhNeural": "EdgeTTS • Nam Nam Minh",
}
VOICE_LABELS.update(
    {
        "valtec:nf": "Valtec-TTS • NF (Northern Female / Nữ miền Bắc)",
        "valtec:sf": "Valtec-TTS • SF (Southern Female / Nữ miền Nam)",
        "valtec:nm1": "Valtec-TTS • NM1 (Northern Male / Nam miền Bắc)",
        "valtec:sm": "Valtec-TTS • SM (Southern Male / Nam miền Nam)",
        "valtec:nm2": "Valtec-TTS • NM2 (Northern Male / Nam miền Bắc)",
    }
)
VOICE_LABELS.update({k: v.get("label", k) for k, v in CUSTOM_OMNIVOICE_VOICES.items()})
if not VALTEC_ZEROSHOT_AVAILABLE:
    for _voice_key in (
        "valtec:thu_ha",
        "valtec:minh_duc",
        "valtec:thanh_tam",
        "valtec:quang_huy",
        "valtec:ngoc_anh",
        "valtec:hoang_nam",
    ):
        VOICE_LABELS.pop(_voice_key, None)
LANGUAGE_OPTIONS = ("en", "zh", "ko", "ja")
WHISPERX_PRELOAD_ALIGN_LANGUAGES = tuple(
    language
    for language in dict.fromkeys(
        part.strip().lower()
        for part in env_value(
            "DUB_WHISPERX_PRELOAD_ALIGN_LANGUAGES",
            default="en,zh,ko,ja",
        ).split(",")
        if part.strip()
    )
    if language
)
SPEAKER_COLORS = ["#FFB703", "#56CFE1", "#EF476F", "#90BE6D"]


def whisperx_disabled() -> bool:
    return DUB_TRANSCRIBE_PROVIDER in LOCAL_TRANSCRIBE_PROVIDERS


def omnivoice_model_ready(model_dir: Path = OMNIVOICE_MODEL_DIR) -> bool:
    # OmniVoice downloads models directly from HuggingFace and manages them internally
    return True


# Cấu hình các mô hình dịch local cho 4 ngôn ngữ
DUB_MT5_EN2VI_MODEL = env_value("DUB_MT5_EN2VI_MODEL", default="Helsinki-NLP/opus-mt-en-vi")
DUB_MT5_ZH2VI_MODEL = env_value("DUB_MT5_ZH2VI_MODEL", default="Helsinki-NLP/opus-mt-zh-vi")
DUB_MT5_JA2VI_MODEL = env_value("DUB_MT5_JA2VI_MODEL", default="Helsinki-NLP/opus-mt-ja-vi")
DUB_MT5_KO2VI_MODEL = env_value("DUB_MT5_KO2VI_MODEL", default="Helsinki-NLP/opus-mt-ko-vi")

