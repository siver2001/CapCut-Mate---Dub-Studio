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

import json
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

BOX_STYLE_OPTIONS = BOX_STYLE_OPTIONS + _EXTRA_BOX_STYLE_OPTIONS
BOX_STYLE_PRESETS = {**BOX_STYLE_PRESETS, **_EXTRA_BOX_STYLE_PRESETS}
