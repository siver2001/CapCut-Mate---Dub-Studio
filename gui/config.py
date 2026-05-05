from __future__ import annotations

import sys
import json
from pathlib import Path

try:  # Optional UI enhancement packages.
    import qtawesome as qta
except Exception:  # pragma: no cover
    qta = None

try:
    from superqt import QLabeledSlider
except Exception:  # pragma: no cover
    QLabeledSlider = None

is_frozen = getattr(sys, 'frozen', False)
if is_frozen:
    ROOT = Path(sys.executable).parent
    MEI_ROOT = Path(getattr(sys, '_MEIPASS', str(ROOT)))
    PIPELINE_PYTHON = Path(sys.executable)
else:
    ROOT = Path(__file__).resolve().parent.parent
    MEI_ROOT = ROOT
    import platform
    if platform.system() == "Windows":
        pythonw_cand = Path(sys.executable).parent / "pythonw.exe"
        PIPELINE_PYTHON = pythonw_cand if pythonw_cand.exists() else Path(sys.executable)
    else:
        PIPELINE_PYTHON = Path(sys.executable)

PIPELINE_PATH = ROOT / "tools" / "dub_studio_pipeline.py"


TEMP_DUB_DIR = ROOT / "temp" / "dub_studio"
DEFAULT_OUTPUT_DIR = ROOT / "output"

def _load_text_effect_options():
    try:
        data = json.loads((ROOT / "config" / "huazi.json").read_text(encoding="utf-8"))
        options = [("none", "Không (Sử dụng Box cơ bản)")]
        for item in data.get("materials", []):
            if item.get("id") and item.get("name"):
                options.append((item["id"], item["name"]))
        return options
    except Exception:
        return [("none", "Không (Sử dụng Box cơ bản)")]

TEXT_EFFECT_OPTIONS = _load_text_effect_options()

def _format_text_effect_label_v2(item: dict[str, object]) -> str:
    raw_label = str(
        item.get("title") or item.get("name") or item.get("label") or ""
    ).strip()
    if not raw_label:
        return ""
    return f"{raw_label} {'[VIP]' if item.get('is_vip') else '[Free]'}"


def _load_text_effect_options_v2():
    fallback = [("none", "Khong (Dung box co ban)")]
    try:
        raw = (ROOT / "config" / "huazi.json").read_text(encoding="utf-8-sig")
        data = json.loads(raw)
        if isinstance(data, dict):
            materials = data.get("materials", [])
        elif isinstance(data, list):
            materials = data
        else:
            materials = []
        options: list[tuple[str, str]] = list(fallback)
        seen_ids = {"none"}
        for item in materials:
            if not isinstance(item, dict):
                continue
            effect_id = str(item.get("id") or "").strip()
            label = _format_text_effect_label_v2(item)
            if not effect_id or not label or effect_id in seen_ids:
                continue
            options.append((effect_id, label))
            seen_ids.add(effect_id)
        return options if len(options) > 1 else fallback
    except Exception:
        return fallback


TEXT_EFFECT_OPTIONS = _load_text_effect_options_v2()


def _load_sticker_options():
    fallback = [("none", "Không dùng sticker")]
    try:
        raw = (ROOT / "config" / "sticker.json").read_text(encoding="utf-8-sig")
        data = json.loads(raw)
        if not isinstance(data, list):
            return fallback
        options: list[tuple[str, str]] = list(fallback)
        seen_ids = {"none"}
        for item in data:
            if not isinstance(item, dict):
                continue
            sticker_id = str(item.get("sticker_id") or "").strip()
            title = str(item.get("title") or "").strip()
            if not sticker_id or not title or sticker_id in seen_ids:
                continue
            # sticker_type: 1=static image, 2=animated (GIF)
            sticker_type = int(item.get("sticker_type", 1))
            is_animated = "[Animated]" if sticker_type == 2 else ""
            options.append((sticker_id, f"{title} {is_animated}".strip()))
            seen_ids.add(sticker_id)
        return options if len(options) > 1 else fallback
    except Exception:
        return fallback


STICKER_OPTIONS = _load_sticker_options()


_STICKER_MAP: dict[str, dict] = {}


def _load_sticker_map() -> dict[str, dict]:
    try:
        raw = (ROOT / "config" / "sticker.json").read_text(encoding="utf-8-sig")
        data = json.loads(raw)
        if not isinstance(data, list):
            return {}
        return {str(item.get("sticker_id", "")): item for item in data if isinstance(item, dict)}
    except Exception:
        return {}


def get_sticker_by_id(sticker_id: str) -> dict:
    if not _STICKER_MAP:
        _STICKER_MAP.update(_load_sticker_map())
    return _STICKER_MAP.get(sticker_id, {})


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
    ("edge:male", "Nam Minh"),
    ("edge:female", "Hoài My"),
]

VIENEU_PRESET_OPTIONS = [
    ("vieneu:ngoc", "Bích Ngọc"),
    ("vieneu:tuyen", "Phạm Tuyên"),
    ("vieneu:doan", "Thục Đoan"),
]

VALTEC_PRESET_OPTIONS = [
    ("valtec:nf", "Nữ miền Bắc"),
    ("valtec:sf", "Nữ miền Nam"),
    ("valtec:nm1", "Nam miền Bắc"),
    ("valtec:sm", "Nam miền Nam"),
    ("valtec:nm2", "Nam miền Bắc 2"),
]

VALTEC_REFERENCE_OPTIONS = [
    ("valtec:thu_ha", "Thu Hà"),
    ("valtec:minh_duc", "Minh Đức"),
    ("valtec:thanh_tam", "Thanh Tâm"),
    ("valtec:quang_huy", "Quang Huy"),
    ("valtec:ngoc_anh", "Ngọc Ánh"),
    ("valtec:hoang_nam", "Hoàng Nam"),
]

CUSTOM_VALTEC_VOICES_FILE = ROOT / "config" / "custom_valtec_voices.json"
if CUSTOM_VALTEC_VOICES_FILE.exists():
    try:
        import json
        custom_data = json.loads(CUSTOM_VALTEC_VOICES_FILE.read_text(encoding="utf-8"))
        for k, v in custom_data.items():
            VALTEC_REFERENCE_OPTIONS.append((k, v.get("label", k).replace("Valtec-TTS • ", "")))
    except Exception:
        pass

VALTEC_ZEROSHOT_CODE_PATH = MEI_ROOT / "tools" / "valtec_repo" / "valtec_tts" / "zeroshot.py"
VALTEC_ZEROSHOT_AVAILABLE = VALTEC_ZEROSHOT_CODE_PATH.exists()
if not VALTEC_ZEROSHOT_AVAILABLE:
    VALTEC_REFERENCE_OPTIONS = []

VOICE_OPTIONS = [
    *VALTEC_PRESET_OPTIONS,
    *VALTEC_REFERENCE_OPTIONS,
    *VIENEU_PRESET_OPTIONS,
    *EDGE_VOICE_OPTIONS,
]

INTRO_TTS_OPTIONS = [
    *VALTEC_PRESET_OPTIONS,
    *VALTEC_REFERENCE_OPTIONS,
    *VIENEU_PRESET_OPTIONS,
    *EDGE_VOICE_OPTIONS,
]

SHORT_VOICE_LABELS = {
    "valtec:nf": "Nữ miền Bắc",
    "valtec:sf": "Nữ miền Nam",
    "valtec:nm1": "Nam miền Bắc",
    "valtec:sm": "Nam miền Nam",
    "valtec:nm2": "Nam miền Bắc 2",
    "valtec:thu_ha": "Thu Hà",
    "valtec:minh_duc": "Minh Đức",
    "valtec:thanh_tam": "Thanh Tâm",
    "valtec:quang_huy": "Quang Huy",
    "valtec:ngoc_anh": "Ngọc Ánh",
    "valtec:hoang_nam": "Hoàng Nam",
    "vieneu:ngoc": "Bích Ngọc",
    "vieneu:tuyen": "Phạm Tuyên",
    "vieneu:doan": "Thục Đoan",
    "edge:male": "Nam Minh",
    "edge:female": "Hoài My",
}

VOICE_LABELS = {value: label for value, label in VOICE_OPTIONS}

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

def _font_option(
    value: str,
    label: str,
    css_font_family: str,
    font_family_name: str,
    ass_font_name: str,
    draft_font_key: str,
    group: str,
    preview_text: str,
) -> dict[str, str]:
    return {
        "value": value,
        "label": label,
        "cssFontFamily": css_font_family,
        "fontFamilyName": font_family_name,
        "assFontName": ass_font_name,
        "draftFontKey": draft_font_key,
        "group": group,
        "previewText": preview_text,
    }


FONT_GROUP_OPTIONS = [
    ("all", "Tat ca phong cach"),
    ("headline", "Headline / hook"),
    ("clean", "Clean / modern"),
    ("serif", "Serif / editorial"),
    ("handwriting", "Handwriting / soft"),
    ("fun", "Fun / cute / creator"),
    ("cinematic", "Cinematic / luxury"),
]


FONT_OPTIONS = [
    _font_option("arial-bold", "Arial Bold", "Arial", "Arial", "Arial", "Poppins_Bold", "clean", "Ban tin cap nhat hom nay"),
    _font_option("impact", "Impact", "Impact", "Impact", "Impact", "Anton", "headline", "Cuon qua roi!"),
    _font_option("poppins-bold", "Poppins Bold", "Poppins", "Poppins", "Poppins", "Poppins_Bold", "clean", "Noi dung dang len xu huong"),
    _font_option("poppins-regular", "Poppins Regular", "Poppins", "Poppins", "Poppins", "Poppins_Regular", "clean", "Vlog hom nay co gi vui"),
    _font_option("montserrat-black", "Montserrat Black", "Montserrat", "Montserrat", "Montserrat", "Montserrat_Black", "headline", "Flash sale toi nay"),
    _font_option("inter-semibold", "Inter SemiBold", "Inter", "Inter", "Inter", "Inter_SemiBold", "clean", "Ban tin nhanh 60 giay"),
    _font_option("anton", "Anton", "Anton", "Anton", "Anton", "Anton", "headline", "Can xem ngay"),
    _font_option("staatliches", "Staatliches", "Staatliches", "Staatliches", "Staatliches", "Staatliches_Regular", "headline", "Neon night edit"),
    _font_option("bungee", "Bungee", "Bungee", "Bungee", "Bungee", "Bungee_Regular", "fun", "Karaoke bung no"),
    _font_option("kanit-regular", "Kanit Regular", "Kanit", "Kanit", "Kanit", "Kanit_Regular", "clean", "Vlog di cafe cuoi tuan"),
    _font_option("kanit-italic", "Kanit ExtraBold Italic", "Kanit", "Kanit", "Kanit", "Kanit_ExtraBoldItalic", "headline", "Drama dang toi"),
    _font_option("nunito", "Nunito", "Nunito", "Nunito", "Nunito", "Nunito", "fun", "De thuong that su"),
    _font_option("rubik", "Rubik", "Rubik", "Rubik", "Rubik", "Rubik", "clean", "Talk show moi len song"),
    _font_option("work-sans", "Work Sans", "Work Sans", "Work Sans", "Work Sans", "WorkSans_Regular", "clean", "Mot ngay lam viec hieu qua"),
    _font_option("source-sans-pro", "Source Sans Pro", "Source Sans Pro", "Source Sans Pro", "Source Sans Pro", "SourceSansPro_Regular", "clean", "Tong hop thong tin can biet"),
    _font_option("source-han-sans-bold", "Source Han Sans Bold", "Source Han Sans CN", "Source Han Sans CN", "Source Han Sans CN", "SourceHanSansCN_Bold", "headline", "Subtitle dam net"),
    _font_option("source-han-serif", "Source Han Serif SemiBold", "Source Han Serif CN", "Source Han Serif CN", "Source Han Serif CN", "SourceHanSerifCN_SemiBold", "serif", "Thuoc phim co dien"),
    _font_option("playfair-sc", "Playfair Display SC", "Playfair Display", "Playfair Display", "Playfair Display", "Playfair_Display_SC_Re", "cinematic", "Luxury frame"),
    _font_option("lora", "Lora", "Lora", "Lora", "Lora", "Lora_Regular", "serif", "Mot cau chuyen dep"),
    _font_option("georgia", "Georgia", "Georgia", "Georgia", "Georgia", "SourceHanSerifCN_Regular", "serif", "Phong cach editorial"),
    _font_option("caveat-bold", "Caveat Bold", "Caveat", "Caveat", "Caveat", "Caveat_Bold", "handwriting", "Ghi chu nhanh"),
    _font_option("great-vibes", "Great Vibes", "Great Vibes", "Great Vibes", "Great Vibes", "Great_Vibes_Regular", "handwriting", "Soft story"),
    _font_option("alex-brush", "Alex Brush", "Alex Brush", "Alex Brush", "Alex Brush", "AlexBrush", "handwriting", "Letter from the heart"),
    _font_option("marker", "Marker", "Marker", "Marker", "Marker", "Marker", "fun", "Highlight nay"),
    _font_option("jellee-bold", "Jellee Bold", "Jellee", "Jellee", "Jellee", "Jellee_Bold", "fun", "Cute creator style"),
    _font_option("bevan", "Bevan", "Bevan", "Bevan", "Bevan", "Bevan_Regular", "cinematic", "Retro poster"),
    _font_option("koulen", "Koulen", "Koulen", "Koulen", "Koulen", "Koulen_Regular", "headline", "Anime battle"),
    _font_option("luxury", "Luxury", "Times New Roman", "Luxury", "Luxury", "Luxury", "cinematic", "Signature premium"),
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
    ("auto", "Tự động (Ưu tiên Ollama → llama.cpp)"),
    ("ollama", "Ollama (Local API, Gemma 4 E2B)"),
    ("llama.cpp", "llama.cpp (Local CLI, Gemma 4 E2B)"),
]

SUBTITLE_STYLE_OPTIONS = [
    ("classic", "Cổ điển (Dòng đơn/đôi)"),
    ("karaoke", "Karaoke (Chạy từng từ)"),
    ("highlight", "Nhấn mạnh (Tô đậm từ nói)"),
]

SUBTITLE_ANIMATION_OPTIONS = [
    ("none", "Không hiệu ứng"),
    ("fade_in", "Mờ dần (Fade In)"),
    ("bounce", "Nhảy chữ (Bounce)"),
    ("slide_up", "Trượt lên (Slide Up)"),
    ("typewriter", "Đánh máy (Typewriter)"),
]

LOCALIZATION_MODE_OPTIONS = [
    ("literal", "Dịch sát nghĩa"),
    ("creative", "Viết lại sáng tạo (Creative Rewrite)"),
    ("vietnamese_slang", "Phong cách Gen Z / Slang Việt"),
]

VOICE_LABELS = {value: label for value, label in VOICE_OPTIONS}

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

def _font_option(
    value: str,
    label: str,
    css_font_family: str,
    font_family_name: str,
    ass_font_name: str,
    draft_font_key: str,
    group: str,
    preview_text: str,
) -> dict[str, str]:
    return {
        "value": value,
        "label": label,
        "cssFontFamily": css_font_family,
        "fontFamilyName": font_family_name,
        "assFontName": ass_font_name,
        "draftFontKey": draft_font_key,
        "group": group,
        "previewText": preview_text,
    }


FONT_GROUP_OPTIONS = [
    ("all", "Tat ca phong cach"),
    ("headline", "Headline / hook"),
    ("clean", "Clean / modern"),
    ("serif", "Serif / editorial"),
    ("handwriting", "Handwriting / soft"),
    ("fun", "Fun / cute / creator"),
    ("cinematic", "Cinematic / luxury"),
]


FONT_OPTIONS = [
    _font_option("arial-bold", "Arial Bold", "Arial", "Arial", "Arial", "Poppins_Bold", "clean", "Ban tin cap nhat hom nay"),
    _font_option("impact", "Impact", "Impact", "Impact", "Impact", "Anton", "headline", "Cuon qua roi!"),
    _font_option("poppins-bold", "Poppins Bold", "Poppins", "Poppins", "Poppins", "Poppins_Bold", "clean", "Noi dung dang len xu huong"),
    _font_option("poppins-regular", "Poppins Regular", "Poppins", "Poppins", "Poppins", "Poppins_Regular", "clean", "Vlog hom nay co gi vui"),
    _font_option("montserrat-black", "Montserrat Black", "Montserrat", "Montserrat", "Montserrat", "Montserrat_Black", "headline", "Flash sale toi nay"),
    _font_option("inter-semibold", "Inter SemiBold", "Inter", "Inter", "Inter", "Inter_SemiBold", "clean", "Ban tin nhanh 60 giay"),
    _font_option("anton", "Anton", "Anton", "Anton", "Anton", "Anton", "headline", "Can xem ngay"),
    _font_option("staatliches", "Staatliches", "Staatliches", "Staatliches", "Staatliches", "Staatliches_Regular", "headline", "Neon night edit"),
    _font_option("bungee", "Bungee", "Bungee", "Bungee", "Bungee", "Bungee_Regular", "fun", "Karaoke bung no"),
    _font_option("kanit-regular", "Kanit Regular", "Kanit", "Kanit", "Kanit", "Kanit_Regular", "clean", "Vlog di cafe cuoi tuan"),
    _font_option("kanit-italic", "Kanit ExtraBold Italic", "Kanit", "Kanit", "Kanit", "Kanit_ExtraBoldItalic", "headline", "Drama dang toi"),
    _font_option("nunito", "Nunito", "Nunito", "Nunito", "Nunito", "Nunito", "fun", "De thuong that su"),
    _font_option("rubik", "Rubik", "Rubik", "Rubik", "Rubik", "Rubik", "clean", "Talk show moi len song"),
    _font_option("work-sans", "Work Sans", "Work Sans", "Work Sans", "Work Sans", "WorkSans_Regular", "clean", "Mot ngay lam viec hieu qua"),
    _font_option("source-sans-pro", "Source Sans Pro", "Source Sans Pro", "Source Sans Pro", "Source Sans Pro", "SourceSansPro_Regular", "clean", "Tong hop thong tin can biet"),
    _font_option("source-han-sans-bold", "Source Han Sans Bold", "Source Han Sans CN", "Source Han Sans CN", "Source Han Sans CN", "SourceHanSansCN_Bold", "headline", "Subtitle dam net"),
    _font_option("source-han-serif", "Source Han Serif SemiBold", "Source Han Serif CN", "Source Han Serif CN", "Source Han Serif CN", "SourceHanSerifCN_SemiBold", "serif", "Thuoc phim co dien"),
    _font_option("playfair-sc", "Playfair Display SC", "Playfair Display", "Playfair Display", "Playfair Display", "Playfair_Display_SC_Re", "cinematic", "Luxury frame"),
    _font_option("lora", "Lora", "Lora", "Lora", "Lora", "Lora_Regular", "serif", "Mot cau chuyen dep"),
    _font_option("georgia", "Georgia", "Georgia", "Georgia", "Georgia", "SourceHanSerifCN_Regular", "serif", "Phong cach editorial"),
    _font_option("caveat-bold", "Caveat Bold", "Caveat", "Caveat", "Caveat", "Caveat_Bold", "handwriting", "Ghi chu nhanh"),
    _font_option("great-vibes", "Great Vibes", "Great Vibes", "Great Vibes", "Great Vibes", "Great_Vibes_Regular", "handwriting", "Soft story"),
    _font_option("alex-brush", "Alex Brush", "Alex Brush", "Alex Brush", "Alex Brush", "AlexBrush", "handwriting", "Letter from the heart"),
    _font_option("marker", "Marker", "Marker", "Marker", "Marker", "Marker", "fun", "Highlight nay"),
    _font_option("jellee-bold", "Jellee Bold", "Jellee", "Jellee", "Jellee", "Jellee_Bold", "fun", "Cute creator style"),
    _font_option("bevan", "Bevan", "Bevan", "Bevan", "Bevan", "Bevan_Regular", "cinematic", "Retro poster"),
    _font_option("koulen", "Koulen", "Koulen", "Koulen", "Koulen", "Koulen_Regular", "headline", "Anime battle"),
    _font_option("luxury", "Luxury", "Times New Roman", "Luxury", "Luxury", "Luxury", "cinematic", "Signature premium"),
]


CLEANUP_OPTIONS = [
    ("localized_blur", "Làm mờ vùng phụ đề cũ"),
    ("localized_mask", "Phủ mềm vùng phụ đề cũ"),
    ("pixelate", "Che bằng hiệu ứng Pixel (Mosaic)"),
    ("custom_box", "Che bằng hộp trắng (Màu tùy chỉnh)"),
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
    ("auto", "Tự động (Ưu tiên Ollama → llama.cpp)"),
    ("ollama", "Ollama (Local API, Gemma 4 E2B)"),
    ("llama.cpp", "llama.cpp (Local CLI, Gemma 4 E2B)"),
]

SUBTITLE_STYLE_OPTIONS = [
    ("classic", "Cổ điển (Dòng đơn/đôi)"),
    ("karaoke", "Karaoke (Chạy từng từ)"),
    ("highlight", "Nhấn mạnh (Tô đậm từ nói)"),
]

SUBTITLE_ANIMATION_OPTIONS = [
    ("none", "Không hiệu ứng"),
    ("fade_in", "Mờ dần (Fade In)"),
    ("bounce", "Nhảy chữ (Bounce)"),
    ("slide_up", "Trượt lên (Slide Up)"),
    ("typewriter", "Đánh máy (Typewriter)"),
]

LOCALIZATION_MODE_OPTIONS = [
    ("literal", "Dịch sát nghĩa"),
    ("creative", "Viết lại sáng tạo (Creative Rewrite)"),
    ("vietnamese_slang", "Phong cách Gen Z / Slang Việt"),
]

VOICE_OPTIONS = [
    *VALTEC_PRESET_OPTIONS,
    *VALTEC_REFERENCE_OPTIONS,
    *VIENEU_PRESET_OPTIONS,
    *EDGE_VOICE_OPTIONS,
]
INTRO_TTS_OPTIONS = list(VOICE_OPTIONS)
VOICE_LABELS = {value: label for value, label in VOICE_OPTIONS}

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

_EXTRA_BOX_STYLE_OPTIONS = [
    ("cyber_blue", "Cyber blue"),
    ("warm_cream", "Warm cream"),
    ("noir_caption", "Noir caption"),
    ("sakura_card", "Sakura card"),
    ("mint_tag", "Mint tag"),
    ("lava_bar", "Lava bar"),
    ("sky_round", "Sky round"),
    ("emerald_tape", "Emerald tape"),
    ("comic_pop", "Comic pop"),
    ("luxury_plate", "Luxury plate"),
    ("frosted_banner", "Frosted banner"),
    ("obsidian_capsule", "Obsidian capsule"),
]

_EXTRA_BOX_STYLE_PRESETS = {
    "cyber_blue": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#082f49",
        "boxFillOpacity": 0.92,
        "boxBorderColor": "#38bdf8",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 18,
        "boxPaddingX": 26,
        "boxPaddingY": 14,
    },
    "warm_cream": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#fef3c7",
        "boxFillOpacity": 0.96,
        "boxBorderColor": "#f59e0b",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 18,
        "boxPaddingX": 24,
        "boxPaddingY": 12,
    },
    "noir_caption": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#09090b",
        "boxFillOpacity": 0.94,
        "boxBorderColor": "#52525b",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 1,
        "boxRadius": 12,
        "boxPaddingX": 24,
        "boxPaddingY": 12,
    },
    "sakura_card": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#fbcfe8",
        "boxFillOpacity": 0.95,
        "boxBorderColor": "#ec4899",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 24,
        "boxPaddingX": 28,
        "boxPaddingY": 14,
    },
    "mint_tag": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#d1fae5",
        "boxFillOpacity": 0.96,
        "boxBorderColor": "#10b981",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 16,
        "boxPaddingX": 24,
        "boxPaddingY": 11,
    },
    "lava_bar": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#7c2d12",
        "boxFillOpacity": 0.93,
        "boxBorderColor": "#fb923c",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 3,
        "boxRadius": 10,
        "boxPaddingX": 24,
        "boxPaddingY": 12,
    },
    "sky_round": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#e0f2fe",
        "boxFillOpacity": 0.94,
        "boxBorderColor": "#0ea5e9",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 28,
        "boxPaddingX": 30,
        "boxPaddingY": 14,
    },
    "emerald_tape": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#14532d",
        "boxFillOpacity": 0.9,
        "boxBorderColor": "#4ade80",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 8,
        "boxPaddingX": 28,
        "boxPaddingY": 12,
    },
    "comic_pop": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#fef08a",
        "boxFillOpacity": 0.96,
        "boxBorderColor": "#111827",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 3,
        "boxRadius": 18,
        "boxPaddingX": 28,
        "boxPaddingY": 14,
    },
    "luxury_plate": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#1c1917",
        "boxFillOpacity": 0.92,
        "boxBorderColor": "#fbbf24",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 16,
        "boxPaddingX": 28,
        "boxPaddingY": 12,
    },
    "frosted_banner": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#f8fafc",
        "boxFillOpacity": 0.34,
        "boxBorderColor": "#cbd5e1",
        "boxBorderOpacity": 0.95,
        "boxBorderWidth": 2,
        "boxRadius": 22,
        "boxPaddingX": 30,
        "boxPaddingY": 14,
    },
    "obsidian_capsule": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#111827",
        "boxFillOpacity": 0.94,
        "boxBorderColor": "#94a3b8",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 30,
        "boxPaddingX": 32,
        "boxPaddingY": 14,
    },
}

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

BOX_FILL_COLOR_SWATCHES = [
    "#0f172a",
    "#111827",
    "#1d4ed8",
    "#0f766e",
    "#7c3aed",
    "#f59e0b",
    "#77b8ee",
]

BOX_BORDER_COLOR_SWATCHES = [
    "#334155",
    "#475569",
    "#3b82f6",
    "#14b8a6",
    "#8b5cf6",
    "#facc15",
    "#ffffff",
]

BOX_LAYOUT_OPTIONS = [
    ("line", "Moi dong mot box"),
    ("unified", "Mot box chung"),
]

BOX_STYLE_OPTIONS = [
    ("custom", "Tuy chinh"),
    ("soft_blue", "Xanh mem"),
    ("midnight", "Dem toi"),
    ("teal_glow", "Teal glow"),
    ("headline", "Nhan vang"),
]

BOX_STYLE_PRESETS = {
    "soft_blue": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#77b8ee",
        "boxFillOpacity": 0.86,
        "boxBorderColor": "#3b82f6",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 16,
        "boxPaddingX": 24,
        "boxPaddingY": 12,
    },
    "midnight": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#0f172a",
        "boxFillOpacity": 0.9,
        "boxBorderColor": "#475569",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 20,
        "boxPaddingX": 28,
        "boxPaddingY": 14,
    },
    "teal_glow": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#0f766e",
        "boxFillOpacity": 0.82,
        "boxBorderColor": "#5eead4",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 18,
        "boxPaddingX": 24,
        "boxPaddingY": 12,
    },
    "headline": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#111827",
        "boxFillOpacity": 0.88,
        "boxBorderColor": "#facc15",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 3,
        "boxRadius": 14,
        "boxPaddingX": 26,
        "boxPaddingY": 12,
    },
}

UI_THEME_OPTIONS = [
    ("cinema", "Cinema"),
    ("news", "News"),
    ("tiktok_energy", "TikTok Energy"),
    ("vlog_daily", "Vlog Daily"),
    ("anime_glow", "Anime Glow"),
    ("luxury_brand", "Luxury Brand"),
    ("drama", "Drama"),
    ("meme", "Meme"),
    ("pastel", "Pastel"),
    ("golden_reel", "Golden Reel"),
    ("glass_promo", "Glass Promo"),
    ("karaoke_pop", "Karaoke Pop"),
    ("retro_poster", "Retro Poster"),
    ("clean_minimal", "Clean Minimal"),
    ("night_neon", "Night Neon"),
    ("soft_story", "Soft Story"),
]

BOX_FILL_COLOR_SWATCHES = [
    "#0f172a",
    "#111827",
    "#1d4ed8",
    "#0f766e",
    "#7c3aed",
    "#f59e0b",
    "#77b8ee",
    "#18181b",
    "#ffffff",
    "#fef3c7",
    "#fecdd3",
    "#cffafe",
]

BOX_BORDER_COLOR_SWATCHES = [
    "#334155",
    "#475569",
    "#3b82f6",
    "#14b8a6",
    "#8b5cf6",
    "#facc15",
    "#ffffff",
    "#fb7185",
    "#22c55e",
    "#38bdf8",
]

BOX_STYLE_OPTIONS = [
    ("custom", "Tuy chinh"),
    ("soft_blue", "Xanh mem"),
    ("midnight", "Dem toi"),
    ("teal_glow", "Teal glow"),
    ("headline", "Headline"),
    ("glass_panel", "Glass panel"),
    ("pill_white", "Pill trang"),
    ("retro_orange", "Retro cam"),
    ("neon_magenta", "Neon hong"),
    ("cute_bubble", "Cute bubble"),
]

BOX_STYLE_PRESETS = {
    "soft_blue": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#77b8ee",
        "boxFillOpacity": 0.86,
        "boxBorderColor": "#3b82f6",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 16,
        "boxPaddingX": 24,
        "boxPaddingY": 12,
    },
    "midnight": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#0f172a",
        "boxFillOpacity": 0.9,
        "boxBorderColor": "#475569",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 20,
        "boxPaddingX": 28,
        "boxPaddingY": 14,
    },
    "teal_glow": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#0f766e",
        "boxFillOpacity": 0.82,
        "boxBorderColor": "#5eead4",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 18,
        "boxPaddingX": 24,
        "boxPaddingY": 12,
    },
    "headline": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#111827",
        "boxFillOpacity": 0.88,
        "boxBorderColor": "#facc15",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 3,
        "boxRadius": 14,
        "boxPaddingX": 26,
        "boxPaddingY": 12,
    },
    "glass_panel": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#ffffff",
        "boxFillOpacity": 0.28,
        "boxBorderColor": "#e2e8f0",
        "boxBorderOpacity": 0.9,
        "boxBorderWidth": 2,
        "boxRadius": 24,
        "boxPaddingX": 30,
        "boxPaddingY": 16,
    },
    "pill_white": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#ffffff",
        "boxFillOpacity": 0.95,
        "boxBorderColor": "#e5e7eb",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 1,
        "boxRadius": 999,
        "boxPaddingX": 30,
        "boxPaddingY": 14,
    },
    "retro_orange": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#f97316",
        "boxFillOpacity": 0.92,
        "boxBorderColor": "#7c2d12",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 3,
        "boxRadius": 10,
        "boxPaddingX": 24,
        "boxPaddingY": 12,
    },
    "neon_magenta": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#4a044e",
        "boxFillOpacity": 0.88,
        "boxBorderColor": "#f0abfc",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 3,
        "boxRadius": 18,
        "boxPaddingX": 26,
        "boxPaddingY": 14,
    },
    "cute_bubble": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#fecdd3",
        "boxFillOpacity": 0.95,
        "boxBorderColor": "#fb7185",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 26,
        "boxPaddingX": 28,
        "boxPaddingY": 14,
    },
}

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
        "fontFamily": "inter-semibold",
        "fontColor": "#ffffff",
        "strokeColor": "#0f172a",
        "strokeWidth": 2,
        "cleanupMode": "localized_mask",
        "positionPreset": "bottom",
        "boxEnabled": True,
        "boxStylePreset": "glass_panel",
    },
    "tiktok_energy": {
        "fontFamily": "montserrat-black",
        "fontColor": "#fef08a",
        "strokeColor": "#111827",
        "strokeWidth": 3,
        "cleanupMode": "localized_mask",
        "positionPreset": "middle",
        "boxEnabled": True,
        "boxStylePreset": "pill_white",
    },
    "vlog_daily": {
        "fontFamily": "kanit-regular",
        "fontColor": "#ffffff",
        "strokeColor": "#0f172a",
        "strokeWidth": 2,
        "cleanupMode": "localized_blur",
        "positionPreset": "bottom",
        "boxEnabled": True,
        "boxStylePreset": "soft_blue",
    },
    "anime_glow": {
        "fontFamily": "koulen",
        "fontColor": "#ffffff",
        "strokeColor": "#1e1b4b",
        "strokeWidth": 3,
        "cleanupMode": "localized_mask",
        "positionPreset": "top",
        "boxEnabled": True,
        "boxStylePreset": "neon_magenta",
    },
    "luxury_brand": {
        "fontFamily": "playfair-sc",
        "fontColor": "#fef3c7",
        "strokeColor": "#78350f",
        "strokeWidth": 2,
        "cleanupMode": "localized_blur",
        "positionPreset": "bottom",
        "boxEnabled": True,
        "boxStylePreset": "headline",
    },
    "drama": {
        "fontFamily": "playfair-sc",
        "fontColor": "#ffcad4",
        "strokeColor": "#312e81",
        "strokeWidth": 2,
        "cleanupMode": "localized_blur",
        "positionPreset": "middle",
    },
    "meme": {
        "fontFamily": "anton",
        "fontColor": "#ffffff",
        "strokeColor": "#000000",
        "strokeWidth": 4,
        "cleanupMode": "localized_mask",
        "positionPreset": "top",
    },
    "pastel": {
        "fontFamily": "nunito",
        "fontColor": "#8ef9f3",
        "strokeColor": "#334155",
        "strokeWidth": 2,
        "cleanupMode": "localized_blur",
        "positionPreset": "bottom",
        "boxEnabled": True,
        "boxStylePreset": "cute_bubble",
    },
    "golden_reel": {
        "fontFamily": "playfair-sc",
        "fontColor": "#fef08a",
        "strokeColor": "#78350f",
        "strokeWidth": 3,
        "cleanupMode": "localized_blur",
        "positionPreset": "bottom",
        "boxEnabled": True,
        "boxStylePreset": "headline",
    },
    "glass_promo": {
        "fontFamily": "montserrat-black",
        "fontColor": "#ffffff",
        "strokeColor": "#0f172a",
        "strokeWidth": 1,
        "cleanupMode": "localized_mask",
        "positionPreset": "middle",
        "boxEnabled": True,
        "boxStylePreset": "glass_panel",
    },
    "karaoke_pop": {
        "fontFamily": "bungee",
        "fontColor": "#fef08a",
        "strokeColor": "#1f2937",
        "strokeWidth": 3,
        "cleanupMode": "localized_mask",
        "positionPreset": "bottom",
        "boxEnabled": True,
        "boxStylePreset": "pill_white",
    },
    "retro_poster": {
        "fontFamily": "bevan",
        "fontColor": "#fde68a",
        "strokeColor": "#7c2d12",
        "strokeWidth": 3,
        "cleanupMode": "localized_blur",
        "positionPreset": "middle",
        "boxEnabled": True,
        "boxStylePreset": "retro_orange",
    },
    "clean_minimal": {
        "fontFamily": "inter-semibold",
        "fontColor": "#ffffff",
        "strokeColor": "#111827",
        "strokeWidth": 1,
        "cleanupMode": "localized_mask",
        "positionPreset": "bottom",
        "boxEnabled": True,
        "boxStylePreset": "pill_white",
    },
    "night_neon": {
        "fontFamily": "staatliches",
        "fontColor": "#67e8f9",
        "strokeColor": "#111827",
        "strokeWidth": 3,
        "cleanupMode": "localized_mask",
        "positionPreset": "top",
        "boxEnabled": True,
        "boxStylePreset": "neon_magenta",
    },
    "soft_story": {
        "fontFamily": "great-vibes",
        "fontColor": "#fff7ed",
        "strokeColor": "#7c2d12",
        "strokeWidth": 2,
        "cleanupMode": "localized_blur",
        "positionPreset": "bottom",
        "boxEnabled": True,
        "boxStylePreset": "soft_blue",
    },
}

CAPCUT_BOX_STYLE_OPTIONS = [
    ("cc_clean_caption", "CapCut clean caption"),
    ("cc_viral_yellow", "CapCut viral yellow"),
    ("cc_creator_black", "Creator black pill"),
    ("cc_karaoke_blue", "Karaoke blue"),
    ("cc_comment_card", "Comment card"),
    ("cc_breaking_news", "Breaking news bar"),
    ("cc_comic_burst", "Comic burst"),
    ("cc_neon_lime", "Neon lime"),
    ("cc_glass_dark", "Glass dark"),
    ("cc_soft_shadow", "Soft shadow card"),
    ("cc_minimal_white", "Minimal white chip"),
    ("cc_red_alert", "Red alert tag"),
    ("cc_podcast_lower", "Podcast lower third"),
    ("cc_gaming_plate", "Gaming plate"),
    ("cc_story_note", "Story note"),
    ("cc_lux_gold", "Luxury gold"),
    ("cc_candy_pop", "Candy pop"),
    ("cc_no_box", "Khong box - text vien"),
]

CAPCUT_BOX_STYLE_PRESETS = {
    "cc_clean_caption": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#111827",
        "boxFillOpacity": 0.88,
        "boxBorderColor": "#374151",
        "boxBorderOpacity": 0.95,
        "boxBorderWidth": 1,
        "boxRadius": 14,
        "boxPaddingX": 24,
        "boxPaddingY": 11,
        "fontColor": "#ffffff",
        "strokeColor": "#000000",
        "strokeWidth": 1,
    },
    "cc_viral_yellow": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#facc15",
        "boxFillOpacity": 0.96,
        "boxBorderColor": "#111827",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 3,
        "boxRadius": 16,
        "boxPaddingX": 28,
        "boxPaddingY": 13,
        "fontColor": "#111827",
        "strokeColor": "#ffffff",
        "strokeWidth": 1,
    },
    "cc_creator_black": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#050505",
        "boxFillOpacity": 0.92,
        "boxBorderColor": "#ffffff",
        "boxBorderOpacity": 0.88,
        "boxBorderWidth": 2,
        "boxRadius": 999,
        "boxPaddingX": 34,
        "boxPaddingY": 13,
        "fontColor": "#ffffff",
        "strokeColor": "#000000",
        "strokeWidth": 0,
    },
    "cc_karaoke_blue": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#1d4ed8",
        "boxFillOpacity": 0.9,
        "boxBorderColor": "#bae6fd",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 3,
        "boxRadius": 18,
        "boxPaddingX": 30,
        "boxPaddingY": 14,
        "fontColor": "#fef08a",
        "strokeColor": "#0f172a",
        "strokeWidth": 2,
    },
    "cc_comment_card": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#f8fafc",
        "boxFillOpacity": 0.94,
        "boxBorderColor": "#cbd5e1",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 1,
        "boxRadius": 20,
        "boxPaddingX": 30,
        "boxPaddingY": 16,
        "fontColor": "#0f172a",
        "strokeColor": "#ffffff",
        "strokeWidth": 0,
    },
    "cc_breaking_news": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#b91c1c",
        "boxFillOpacity": 0.94,
        "boxBorderColor": "#fef2f2",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 6,
        "boxPaddingX": 28,
        "boxPaddingY": 12,
        "fontColor": "#ffffff",
        "strokeColor": "#450a0a",
        "strokeWidth": 2,
    },
    "cc_comic_burst": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#fef08a",
        "boxFillOpacity": 0.98,
        "boxBorderColor": "#111827",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 4,
        "boxRadius": 18,
        "boxPaddingX": 32,
        "boxPaddingY": 15,
        "fontColor": "#ef4444",
        "strokeColor": "#111827",
        "strokeWidth": 2,
    },
    "cc_neon_lime": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#052e16",
        "boxFillOpacity": 0.9,
        "boxBorderColor": "#a3e635",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 3,
        "boxRadius": 22,
        "boxPaddingX": 28,
        "boxPaddingY": 14,
        "fontColor": "#ecfccb",
        "strokeColor": "#000000",
        "strokeWidth": 2,
    },
    "cc_glass_dark": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#0f172a",
        "boxFillOpacity": 0.46,
        "boxBorderColor": "#e2e8f0",
        "boxBorderOpacity": 0.74,
        "boxBorderWidth": 2,
        "boxRadius": 24,
        "boxPaddingX": 34,
        "boxPaddingY": 16,
        "fontColor": "#ffffff",
        "strokeColor": "#020617",
        "strokeWidth": 2,
    },
    "cc_soft_shadow": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#e0f2fe",
        "boxFillOpacity": 0.92,
        "boxBorderColor": "#38bdf8",
        "boxBorderOpacity": 0.95,
        "boxBorderWidth": 2,
        "boxRadius": 18,
        "boxPaddingX": 30,
        "boxPaddingY": 15,
        "fontColor": "#0c4a6e",
        "strokeColor": "#ffffff",
        "strokeWidth": 1,
    },
    "cc_minimal_white": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#ffffff",
        "boxFillOpacity": 0.96,
        "boxBorderColor": "#e5e7eb",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 1,
        "boxRadius": 999,
        "boxPaddingX": 32,
        "boxPaddingY": 12,
        "fontColor": "#111827",
        "strokeColor": "#ffffff",
        "strokeWidth": 0,
    },
    "cc_red_alert": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#991b1b",
        "boxFillOpacity": 0.92,
        "boxBorderColor": "#fecaca",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 3,
        "boxRadius": 12,
        "boxPaddingX": 26,
        "boxPaddingY": 12,
        "fontColor": "#ffffff",
        "strokeColor": "#450a0a",
        "strokeWidth": 2,
    },
    "cc_podcast_lower": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#1e1b4b",
        "boxFillOpacity": 0.9,
        "boxBorderColor": "#818cf8",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 10,
        "boxPaddingX": 34,
        "boxPaddingY": 13,
        "fontColor": "#ffffff",
        "strokeColor": "#000000",
        "strokeWidth": 1,
    },
    "cc_gaming_plate": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#18181b",
        "boxFillOpacity": 0.94,
        "boxBorderColor": "#22d3ee",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 3,
        "boxRadius": 8,
        "boxPaddingX": 30,
        "boxPaddingY": 14,
        "fontColor": "#fef08a",
        "strokeColor": "#000000",
        "strokeWidth": 2,
    },
    "cc_story_note": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#fef3c7",
        "boxFillOpacity": 0.94,
        "boxBorderColor": "#d97706",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 14,
        "boxPaddingX": 26,
        "boxPaddingY": 12,
        "fontColor": "#78350f",
        "strokeColor": "#ffffff",
        "strokeWidth": 1,
    },
    "cc_lux_gold": {
        "boxEnabled": True,
        "boxLayoutMode": "unified",
        "boxFillColor": "#1c1917",
        "boxFillOpacity": 0.92,
        "boxBorderColor": "#fbbf24",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 2,
        "boxRadius": 18,
        "boxPaddingX": 34,
        "boxPaddingY": 14,
        "fontColor": "#fef3c7",
        "strokeColor": "#000000",
        "strokeWidth": 1,
    },
    "cc_candy_pop": {
        "boxEnabled": True,
        "boxLayoutMode": "line",
        "boxFillColor": "#fbcfe8",
        "boxFillOpacity": 0.95,
        "boxBorderColor": "#38bdf8",
        "boxBorderOpacity": 1.0,
        "boxBorderWidth": 3,
        "boxRadius": 24,
        "boxPaddingX": 30,
        "boxPaddingY": 14,
        "fontColor": "#831843",
        "strokeColor": "#ffffff",
        "strokeWidth": 1,
    },
    "cc_no_box": {
        "boxEnabled": False,
        "boxStylePreset": "cc_no_box",
        "fontColor": "#ffffff",
        "strokeColor": "#000000",
        "strokeWidth": 3,
    },
}

BOX_STYLE_OPTIONS = (
    BOX_STYLE_OPTIONS + _EXTRA_BOX_STYLE_OPTIONS + CAPCUT_BOX_STYLE_OPTIONS
)
BOX_STYLE_PRESETS = {
    **BOX_STYLE_PRESETS,
    **_EXTRA_BOX_STYLE_PRESETS,
    **CAPCUT_BOX_STYLE_PRESETS,
}
