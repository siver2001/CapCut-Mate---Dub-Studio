from gui.config import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_VOICES,
    FONT_OPTIONS,
    MOJIBAKE_MARKERS,
    Path,
    ROOT,
    SPEAKER_COLORS,
    TEMP_DUB_DIR,
    VOICE_LABELS,
)
from typing import Any
import copy
import hashlib
import re
import os
import json
from PyQt6.QtWidgets import QApplication
from gui import config


_CP1252_BYTE_BY_CHAR = {
    "\u20ac": 0x80,
    "\u201a": 0x82,
    "\u0192": 0x83,
    "\u201e": 0x84,
    "\u2026": 0x85,
    "\u2020": 0x86,
    "\u2021": 0x87,
    "\u02c6": 0x88,
    "\u2030": 0x89,
    "\u0160": 0x8A,
    "\u2039": 0x8B,
    "\u0152": 0x8C,
    "\u017d": 0x8E,
    "\u2018": 0x91,
    "\u2019": 0x92,
    "\u201c": 0x93,
    "\u201d": 0x94,
    "\u2022": 0x95,
    "\u2013": 0x96,
    "\u2014": 0x97,
    "\u02dc": 0x98,
    "\u2122": 0x99,
    "\u0161": 0x9A,
    "\u203a": 0x9B,
    "\u0153": 0x9C,
    "\u017e": 0x9E,
    "\u0178": 0x9F,
}


def _encode_mojibake_bytes(text: str) -> bytes:
    data = bytearray()
    for char in text:
        codepoint = ord(char)
        if codepoint <= 0xFF:
            data.append(codepoint)
        elif char in _CP1252_BYTE_BY_CHAR:
            data.append(_CP1252_BYTE_BY_CHAR[char])
        else:
            raise UnicodeEncodeError("mojibake", char, 0, 1, "not a mojibake byte")
    return bytes(data)


def repair_mojibake_text(value: str | None) -> str:
    text = str(value or "")
    repaired = text
    suspicious_markers = (
        *MOJIBAKE_MARKERS,
        "Ã",
        "Â",
        "Ä",
        "Æ",
        "áº",
        "á»",
        "â€",
    )
    for _ in range(3):
        if repaired.isascii():
            break
        if not any(marker in repaired for marker in suspicious_markers):
            break
        candidate = repaired
        for repairer in (
            lambda value: _encode_mojibake_bytes(value).decode("utf-8"),
            lambda value: value.encode("latin1").decode("utf-8"),
            lambda value: value.encode("cp1252").decode("utf-8"),
        ):
            try:
                candidate = repairer(repaired)
                break
            except Exception:
                candidate = repaired
        if candidate == repaired:
            break
        repaired = candidate
        
    # Manual replacements for unaccented logs or common unmapped mojibake
    replacements = {
        "Dang doc thong tin video": "Đang đọc thông tin video",
        "Dang nhan dien loi noi": "Đang nhận diện lời nói",
        "Dang nhan dien ngon ngu": "Đang nhận diện ngôn ngữ",
        "Dang uoc luong so nguoi noi": "Đang ước lượng số người nói",
        "Phan tich xong": "Phân tích xong",
        "Dang chuan bi du lieu render": "Đang chuẩn bị dữ liệu render",
        "Dang tao long tieng": "Đang tạo lồng tiếng",
        "Dang ghep audio": "Đang ghép audio",
        "Dang xuat MP4": "Đang xuất MP4",
        "Dang tao intro hook tu dong": "Đang tạo intro hook tự động",
        "Dang tao draft CapCut": "Đang tạo draft CapCut",
        "Render hoan tat": "Render hoàn tất",
        "Dang kiem tra thu vien va model cho phan tich": "Đang kiểm tra thư viện và model cho phân tích",
        "Dang kiem tra thu vien va model cho render": "Đang kiểm tra thư viện và model cho render",
        "Dang xac nhan ngon ngu nguon": "Đang xác nhận ngôn ngữ nguồn",
        "Dang gom nhom nguoi noi": "Đang gom nhóm người nói",
        "Dang tach mau giong tung nhan vat": "Đang tách mẫu giọng từng nhân vật",
        "Dang tao audio nghe thu giong doc": "Đang tạo audio nghe thử giọng đọc",
        "Moi truong da san sang": "Môi trường đã sẵn sàng",
    }
    
    # Try exact match first
    if repaired in replacements:
        return replacements[repaired]
        
    # Then try partial replacements for lines containing these strings (like logs with levels)
    for unaccented, accented in replacements.items():
        if unaccented in repaired:
            repaired = repaired.replace(unaccented, accented)

    # Automatically add diacritics for common Vietnamese words if the text looks like unaccented Vietnamese
    repaired = restore_vietnamese_diacritics(repaired)
            
    return repaired


def restore_vietnamese_diacritics(text: str) -> str:
    """Heuristic to add diacritics to common unaccented Vietnamese words."""
    if not text or not any(c.isalpha() for c in text):
        return text
    
    # Only attempt if there are few existing diacritics (likely unaccented)
    accented_chars = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
    if sum(1 for c in text.lower() if c in accented_chars) > len(text) * 0.15:
        return text

    # Common unaccented -> accented mapping
    mapping = {
        "tieng": "tiếng", "viet": "việt", "chao": "chào", "ban": "bạn", "toi": "tôi",
        "dang": "đang", "lam": "làm", "duoc": "được", "nay": "này", "cai": "cái",
        "cua": "của", "co": "có", "khong": "không", "biet": "biết", "nguoi": "người",
        "nhieu": "nhiều", "tot": "tốt", "dep": "đẹp", "moi": "mới", "di": "đi",
        "ve": "về", "an": "ăn", "uong": "uống", "ngu": "ngủ", "noi": "nói",
        "thay": "thấy", "nghi": "nghĩ", "muon": "muốn", "can": "cần", "phai": "phải",
        "nen": "nên", "roi": "rồi", "va": "và", "voi": "với", "nhu": "như",
        "the": "thế", "la": "là", "mot": "một", "bon": "bốn", "sau": "sáu",
        "bay": "bảy", "tam": "tám", "chin": "chín", "muoi": "mười",
        "khi": "khi", "nhung": "nhưng", "ma": "mà", "de": "để", "den": "đến",
        "tu": "từ", "vao": "vào", "ra": "ra", "len": "lên", "xuong": "xuống",
        "trong": "trong", "ngoai": "ngoài", "tren": "trên", "duoi": "dưới",
        "truoc": "trước", "giua": "giữa", "canh": "cạnh", "gan": "gần", "xa": "xa",
        "rat": "rất", "qua": "quá", "cung": "cũng", "chi": "chỉ", "se": "sẽ", "da": "đã",
        "tung": "từng", "vua": "vừa", "sap": "sắp", "chung": "chúng", "no": "nó",
        "minh": "mình", "cau": "cậu", "anh": "anh", "chi": "chị", "em": "em",
        "ong": "ông", "ba": "bà", "co": "cô", "chu": "chú", "bac": "bác",
        "goc": "góc", "kieu": "kiểu", "phan": "phân", "tich": "tích", "am": "âm",
        "luong": "lượng", "toc": "tốc", "do": "độ", "nhan": "nhân", "vat": "vật",
        "dau": "đầu", "nhap": "nhập", "xuat": "xuất", "phu": "phụ", "de": "đề",
        "mau": "màu", "chu": "chữ", "vien": "viền", "nen": "nền", "tri": "trí",
        "gia": "giá", "tri": "trị", "he": "hệ", "thong": "thống", "ca": "cả",
        "chon": "chọn", "anh": "ảnh", "kich": "kích", "thuoc": "thước", "nhanh": "nhanh",
    }
    
    # Split by non-word characters to preserve them
    parts = re.split(r'(\W+)', text)
    result = []
    for part in parts:
        lowered = part.lower()
        if lowered in mapping:
            accented = mapping[lowered]
            if part.isupper():
                result.append(accented.upper())
            elif part[0].isupper():
                result.append(accented[0].upper() + accented[1:])
            else:
                result.append(accented)
        else:
            result.append(part)
            
    return "".join(result)


def decode_process_bytes(data: bytes) -> str:
    if not data:
        return ""
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "cp1252", "latin1"):
        try:
            return repair_mojibake_text(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    return repair_mojibake_text(data.decode("utf-8", errors="replace"))



APP_STYLESHEET = """
QMainWindow, QWidget#AppRoot, QScrollArea QWidget {
    background: #07111f;
    color: #e8eefc;
    font-family: "Segoe UI", "Arial";
    font-size: 13px;
}
QLabel, QCheckBox, QRadioButton, QGroupBox {
    color: #e8eefc;
}
QScrollArea {
    border: none;
    background: transparent;
}
QFrame#HeroCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #102443, stop:0.5 #0f766e, stop:1 #0ea5e9);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 12px;
    color: white;
}
QFrame#SurfaceCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0d1b31, stop:0.55 #0d1829, stop:1 #091321);
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 20px;
    color: #e8eefc;
}
QFrame#StatCard {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    color: #e8eefc;
}
QLabel#HeroEyebrow {
    color: rgba(255,255,255,0.78);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.4px;
    text-transform: uppercase;
}
QLabel#HeroTitle {
    color: white;
    font-size: 20px;
    font-weight: 700;
}
QLabel#HeroSubtitle {
    color: rgba(255,255,255,0.86);
    font-size: 13px;
    line-height: 1.45em;
}
QLabel#SectionTitle {
    color: #f8fbff;
    font-size: 18px;
    font-weight: 750;
}
QLabel#SectionHint {
    color: #94a3b8;
    font-size: 11px;
}
QLabel#StatTitle {
    color: #93c5fd;
    font-size: 11px;
    font-weight: 600;
}
QLabel#StatValue {
    color: #ffffff; font-weight: 700; text-align: center;
    font-size: 18px;
    font-weight: 700;
}
QLabel#MetricChip {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 999px;
    color: #e2e8f0;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#FieldLabel {
    color: #cbd5e1;
    font-size: 11px;
    font-weight: 700;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTableWidget, QHeaderView {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(7, 18, 34, 0.96), stop:1 rgba(12, 28, 49, 0.96));
    border: 1px solid rgba(56, 189, 248, 0.24);
    border-radius: 12px;
    color: #f8fafc;
    padding: 8px 10px;
    selection-background-color: #38bdf8;
}
QHeaderView::section {
    background: #0f1f35;
    color: #f8fafc;
    padding: 8px 6px;
    min-height: 34px;
    border: 1px solid rgba(56, 189, 248, 0.24);
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus, QTableWidget:focus {
    border: 1px solid #38bdf8;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QPlainTextEdit:hover {
    border: 1px solid rgba(103, 232, 249, 0.45);
}
QComboBox {
    min-height: 34px;
    padding-right: 28px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(13, 27, 49, 0.98), stop:0.55 rgba(16, 55, 77, 0.96), stop:1 rgba(12, 39, 64, 0.98));
}
QComboBox::drop-down {
    border: none;
    width: 24px;
    background: rgba(14, 165, 233, 0.16);
    border-top-right-radius: 11px;
    border-bottom-right-radius: 11px;
}
QComboBox:on {
    border: 1px solid rgba(34, 211, 238, 0.7);
}
QComboBox QAbstractItemView {
    background: #0f1f35;
    color: #f8fafc;
    border: 1px solid rgba(96, 165, 250, 0.35);
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    outline: 0;
    padding: 6px;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 6px 10px;
    color: #f8fafc;
    background: transparent;
}
QComboBox QAbstractItemView::item:selected {
    background: #2563eb;
    color: #ffffff;
}
QComboBox QAbstractItemView::item:hover {
    background: rgba(56, 189, 248, 0.22);
    color: #ffffff; font-weight: 700; text-align: center;
}
QSlider::groove:horizontal {
    height: 8px;
    border-radius: 4px;
    background: rgba(255,255,255,0.12);
}
QSlider::handle:horizontal {
    width: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: #22d3ee;
    border: 2px solid #ffffff;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(18, 34, 59, 0.95), stop:1 rgba(22, 44, 71, 0.95));
    border: 1px solid rgba(125, 211, 252, 0.16);
    border-radius: 12px;
    color: #f1f5f9;
    font-weight: 700;
    font-size: 12px;
    padding: 6px 10px;
    min-height: 30px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(15, 112, 136, 0.95), stop:1 rgba(37, 99, 235, 0.95));
    border: 1px solid rgba(186, 230, 253, 0.42);
    color: white;
}
QPushButton:pressed {
    background: rgba(12, 26, 45, 0.92);
    border: 1px solid rgba(103, 232, 249, 0.35);
}
QPushButton[variant="primary"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #06b6d4, stop:1 #2563eb);
    border: 1px solid rgba(186, 230, 253, 0.24);
}
QPushButton[variant="primary"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22d3ee, stop:1 #3b82f6);
    border: 1px solid rgba(255,255,255,0.34);
}
QPushButton[variant="success"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #14b8a6, stop:1 #16a34a);
    border: 1px solid rgba(220, 252, 231, 0.22);
}
QPushButton[variant="success"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2dd4bf, stop:1 #22c55e);
    border: 1px solid rgba(255,255,255,0.34);
}
QPushButton[variant="ghost"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(21, 34, 53, 0.88), stop:1 rgba(15, 38, 52, 0.88));
    border: 1px solid rgba(148, 163, 184, 0.14);
}
QPushButton[variant="ghost"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(14, 116, 144, 0.82), stop:1 rgba(14, 165, 233, 0.82));
    border: 1px solid rgba(186, 230, 253, 0.3);
}
QPushButton:disabled, QComboBox:disabled, QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: rgba(226, 232, 240, 0.52);
    border: 1px solid rgba(148, 163, 184, 0.10);
    background: rgba(15, 23, 42, 0.55);
}
QPushButton#ColorButton {
    text-align: left;
    padding-left: 14px;
}
QCheckBox {
    color: #e2e8f0;
    spacing: 10px;
    font-weight: 600;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.28);
    background: rgba(15, 23, 42, 0.85);
}
QCheckBox::indicator:checked {
    background: #60a5fa;
    border: 1px solid #60a5fa;
}
QProgressBar {
    border: none;
    border-radius: 12px;
    background: rgba(255,255,255,0.08);
    min-height: 24px;
    color: #ffffff; font-weight: 700; text-align: center;
}
QProgressBar::chunk {
    border-radius: 12px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22d3ee, stop:1 #a855f7);
}
QScrollBar:vertical {
    background: transparent;
    width: 12px;
}
QScrollBar::handle:vertical {
    background: rgba(255,255,255,0.18);
    border-radius: 6px;
    min-height: 26px;
}
QTabWidget::pane {
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 14px;
    background: rgba(11, 23, 41, 0.7);
    margin-top: 8px;
}
QTabBar::tab {
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(96, 165, 250, 0.16);
    color: #cbd5e1;
    padding: 8px 16px;
    border-top-left-radius: 11px;
    border-top-right-radius: 11px;
    margin-right: 6px;
    font-weight: 700;
}
QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0ea5e9, stop:1 #8b5cf6);
    color: white;
    border-color: #ffffff; font-weight: 700; text-align: center;
}
QTabBar::tab:hover {
    color: white;
}
"""


def apply_app_theme(app: QApplication) -> None:
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return
    if os.environ.get("CAPCUT_ENABLE_QT_MATERIAL") != "1":
        return
    try:
        from qt_material import apply_stylesheet as apply_qt_material_stylesheet
        import qt_material.resources.generate as qt_material_generate
    except Exception:
        return
    theme_cache = ROOT / ".qt_material_cache"
    ensure_dir(theme_cache)
    qt_material_generate.RESOURCES_PATH = str(theme_cache)
    try:
        apply_qt_material_stylesheet(
            app,
            theme="dark_pink.xml",
            invert_secondary=True,
            extra={
                "density_scale": "-1",
                "font_family": "Segoe UI",
            },
        )
    except Exception:
        return


def safe_qta_icon(name: str, color: str = "white"):
    return None


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_cache_name(value: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return compact.strip("._")[:80]


def ensure_sticker_preview_cache(sticker_options: dict[str, Any]) -> Path | None:
    """Return a local image path for the selected sticker, downloading it if needed."""
    options = sticker_options or {}
    image_url = str(options.get("image_url") or options.get("url") or "").strip()
    sticker_id = str(options.get("stickerId") or options.get("sticker_id") or "").strip()
    if not image_url:
        return None


def ensure_qt_readable_sticker_preview(sticker_options: dict[str, Any]) -> Path | None:
    """Return a sticker image path that QImage can read, converting with ffmpeg if needed."""
    source = ensure_sticker_preview_cache(sticker_options)
    if source is None:
        return None
    try:
        from PyQt6.QtGui import QImage

        if not QImage(str(source)).isNull():
            return source
        converted = source.with_name(f"{source.stem}_preview.png")
        if converted.exists() and converted.stat().st_size > 0:
            if not QImage(str(converted)).isNull():
                return converted
        import subprocess

        subprocess.run(
            ["ffmpeg", "-y", "-i", str(source), "-frames:v", "1", str(converted)],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=False,
        )
        if converted.exists() and converted.stat().st_size > 0:
            if not QImage(str(converted)).isNull():
                return converted
    except Exception:
        pass
    return source

    local_candidate = Path(image_url).expanduser()
    if local_candidate.exists() and local_candidate.is_file():
        return local_candidate

    cache_dir = ensure_dir(ROOT / "temp" / "dub_studio" / "sticker_cache")
    cache_name = _safe_cache_name(sticker_id)
    if not cache_name:
        cache_name = hashlib.sha1(image_url.encode("utf-8", errors="ignore")).hexdigest()[:16]
    sticker_type = int(options.get("sticker_type") or options.get("stickerType") or 1)
    preferred_ext = "gif" if sticker_type == 2 else "png"
    candidates = [
        cache_dir / f"{cache_name}.{preferred_ext}",
        cache_dir / f"{cache_name}.png",
        cache_dir / f"{cache_name}.gif",
        cache_dir / f"{cache_name}.webp",
        cache_dir / f"{cache_name}.img",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate

    failed_marker = cache_dir / f"{cache_name}.failed"
    try:
        import time

        if failed_marker.exists() and time.time() - failed_marker.stat().st_mtime < 300:
            return None
    except Exception:
        pass

    target = candidates[0]
    temp_target = target.with_suffix(target.suffix + ".tmp")
    try:
        import urllib.request

        request = urllib.request.Request(
            image_url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            data = response.read()
        if not data:
            return None
        temp_target.write_bytes(data)
        os.replace(temp_target, target)
        if failed_marker.exists():
            failed_marker.unlink(missing_ok=True)
        return target
    except Exception as exc:
        try:
            failed_marker.write_text(str(exc)[:240], encoding="utf-8")
            if temp_target.exists():
                temp_target.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_intro_voice_preset(preset_key: str | None) -> dict[str, Any]:
    voice = str(preset_key or "").strip()
    if voice in {"vi-VN-HoaiMyNeural"}:
        voice = "edge:female"
    elif voice in {"vi-VN-NamMinhNeural"}:
        voice = "edge:male"
    if not voice:
        voice = str(DEFAULT_VOICES[0] if DEFAULT_VOICES else "edge:male")
    return {
        "key": voice,
        "voice": voice,
        "label": voice,
        "rateDeltaPercent": 0,
    }


def preferred_default_voice() -> str:
    return str(DEFAULT_VOICES[0] if DEFAULT_VOICES else "edge:male")


def default_settings() -> dict[str, Any]:
    default_voice = str(DEFAULT_VOICES[0] if DEFAULT_VOICES else "edge:male")
    return {
        "sourceLanguage": "auto",
        "targetLanguage": "vi",
        "speakerDetectionMode": "narrator",
        "speakerCount": 1,
        "defaultVoice": default_voice,
        "voiceMapping": {},
        "introHook": {
            "enabled": True,
            "clipDurationMs": 15000,
            "voice": default_voice,
            "voicePresetKey": default_voice,
            "voiceRateDeltaPercent": 0,
            "useBackgroundAudio": True,
            "backgroundVolume": 0.08,
        },
        "subtitlePreset": {
            "enabled": True,
            "positionPreset": "bottom",
            "fontSize": 14,
            "fontFamily": "arial-bold",
            "fontFamilyLabel": "Arial Bold",
            "fontFamilyName": "Arial",
            "cssFontFamily": "Arial",
            "assFontName": "Arial",
            "draftFontKey": "Poppins_Bold",
            "fontGroup": "all",
            "fontColor": "#ffd200",
            "strokeColor": "#000000",
            "strokeWidth": 2,
            "boxEnabled": False,
            "boxStylePreset": "custom",
            "textEffect": "none",
            "boxLayoutMode": "line",
            "boxFillColor": "#77b8ee",
            "boxFillOpacity": 0.86,
            "boxBorderColor": "#3b82f6",
            "boxBorderOpacity": 1.0,
            "boxBorderWidth": 2,
            "boxRadius": 16,
            "boxPaddingX": 24,
            "boxPaddingY": 12,
            "bottomOffset": 54,
            "cleanupBlurStrength": 14,
            "maxWordsPerChunk": 5,
            "maxCharsPerChunk": 22,
            "punctuationAwareSplit": True,
        },
        "subtitleRegion": {"x": 0, "y": 0, "w": 0, "h": 0},
        "sourceSubtitleCleanupMode": "localized_blur",
        "outputTargets": {"mp4": True, "draft": False},
        "timingMode": "balanced_natural",
        "videoCodecMode": "gpu_preferred",
        "uiThemePreset": "cinema",
        "audioMixMode": "preserve_background",
        "keepOriginalAudio": True,
        "backgroundMusic": {
            "enabled": False,
            "path": "",
            "volume": 0.12,
        },
        "watermark": {
            "enabled": False,
            "path": "",
            "position": "top-right",
            "scale": 0.15,
        },
        "stickerOptions": {
            "stickerId": "",
            "sticker_id": "",
            "stickerName": "",
            "image_url": "",
            "sticker_type": 1,
            "scale": 1.0,
            "transform_x": 0.0,
            "transform_y": -0.3,
        },
        "draftRoot": str(getattr(config, "DRAFT_DIR", "") or ""),
        "outputDirectory": str(DEFAULT_OUTPUT_DIR),
    }


def find_font_option(value: str) -> dict[str, Any]:
    for option in FONT_OPTIONS:
        if option["value"] == value:
            return option
    return FONT_OPTIONS[0]


def normalize_preview_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


def resolve_preview_caption_placement(
    position_preset: str, bottom_offset: int
) -> tuple[str, float]:
    safe_offset = max(min(int(bottom_offset), 240), 0)
    if position_preset == "top":
        return "top", 32 + safe_offset * 0.35
    if position_preset == "middle":
        return "middle", 0
    return "bottom", max(safe_offset, 12) * 0.7


def get_job_dir(job_id: str) -> Path:
    return TEMP_DUB_DIR / job_id


def get_analysis_path(job_id: str) -> Path:
    return get_job_dir(job_id) / "analysis.json"


def get_render_options_path(job_id: str) -> Path:
    return get_job_dir(job_id) / "render-options.json"


def get_render_result_path(job_id: str) -> Path:
    return get_job_dir(job_id) / "render-result.json"


def create_base_job(job_id: str, input_path: str) -> dict[str, Any]:
    return {
        "jobId": job_id,
        "inputPath": input_path,
        "status": "idle",
        "phase": "idle",
        "step": "idle",
        "progress": 0.0,
        "logs": [],
        "warnings": [],
        "analysis": None,
        "overrides": {},
        "renderResult": None,
        "process": None,
        "stdoutBuffer": "",
        "stderrBuffer": "",
        "lastError": None,
        "cancelRequested": False,
    }


def append_job_log(job: dict[str, Any], message: str, level: str = "info") -> None:
    compact_message = " ".join(repair_mojibake_text(str(message or "")).split()).strip()
    if not compact_message:
        return
    if len(compact_message) > 220:
        compact_message = compact_message[:217].rstrip() + "..."
    logs = job.setdefault("logs", [])
    if logs and logs[-1].get("level") == level and logs[-1].get("message") == compact_message:
        return
    logs.append({"level": level, "message": compact_message})
    if len(logs) > 40:
        del logs[:-40]


FFMPEG_PROGRESS_RE = re.compile(r"^frame=\s*\d+")
FFMPEG_INFO_PREFIXES = (
    "ffmpeg version",
    "built with",
    "configuration:",
    "libav",
    "input #",
    "output #",
    "stream mapping:",
    "metadata:",
    "duration:",
    "press [q] to stop",
)


def classify_process_log_line(line: str, stream: str) -> str:
    if stream != "stderr":
        return "info"
    compact = " ".join(line.split())
    lowered = compact.lower()
    if FFMPEG_PROGRESS_RE.match(compact) and "fps=" in compact and "size=" in compact:
        return "info"
    if lowered.startswith(FFMPEG_INFO_PREFIXES):
        return "info"
    if "warning" in lowered:
        return "warn"
    return "error"


def should_capture_process_log_line(line: str, stream: str) -> bool:
    compact = " ".join(str(line or "").split()).strip()
    if not compact:
        return False
    lowered = compact.lower()
    if stream == "stderr":
        if FFMPEG_PROGRESS_RE.match(compact) and "fps=" in compact and "size=" in compact:
            return False
        if lowered.startswith(FFMPEG_INFO_PREFIXES):
            return False
    if lowered in {"[info] processing", "processing"}:
        return False
    return True


def build_speakers(
    count: int,
    voice_mapping: dict[str, str] | None = None,
    base_speakers: list[dict[str, Any]] | None = None,
    main_speaker_id: str = "speaker_1",
) -> list[dict[str, Any]]:
    voice_mapping = voice_mapping or {}
    base_speakers = base_speakers or []
    speaker_meta = {speaker.get("speakerId"): speaker for speaker in base_speakers}
    speakers: list[dict[str, Any]] = []
    for index in range(max(count, 1)):
        speaker_id = f"speaker_{index + 1}"
        meta = speaker_meta.get(speaker_id, {})
        speakers.append(
            {
                "speakerId": speaker_id,
                "displayName": meta.get(
                    "displayName",
                    "Nhân vật chính"
                    if speaker_id == main_speaker_id
                    else f"Nhân vật {index + 1}",
                ),
                "estimatedGender": meta.get("estimatedGender", "unknown"),
                "voicePreset": voice_mapping.get(speaker_id)
                or DEFAULT_VOICES[index % len(DEFAULT_VOICES)],
                "voiceLabel": meta.get("voiceLabel")
                or VOICE_LABELS.get(
                    voice_mapping.get(speaker_id)
                    or meta.get("voicePreset")
                    or DEFAULT_VOICES[index % len(DEFAULT_VOICES)],
                    voice_mapping.get(speaker_id)
                    or meta.get("voicePreset")
                    or DEFAULT_VOICES[index % len(DEFAULT_VOICES)],
                ),
                "colorTag": SPEAKER_COLORS[index % len(SPEAKER_COLORS)],
                "isPrimary": speaker_id == main_speaker_id
                or meta.get("isPrimary") is True,
                "segmentCount": int(meta.get("segmentCount", 0)),
                "totalDurationMs": int(meta.get("totalDurationMs", 0)),
                "samplePath": meta.get("samplePath", ""),
                "voiceCloneReady": bool(meta.get("voiceCloneReady")),
            }
        )
    return speakers


def reconcile_segments_to_speaker_count(
    segments: list[dict[str, Any]],
    speaker_count: int,
    main_speaker_id: str = "speaker_1",
) -> list[dict[str, Any]]:
    allowed = {f"speaker_{index + 1}" for index in range(max(speaker_count, 1))}
    fallback = main_speaker_id if main_speaker_id in allowed else "speaker_1"
    normalized: list[dict[str, Any]] = []
    for segment in segments:
        updated = dict(segment)
        updated["speakerId"] = (
            segment.get("speakerId")
            if segment.get("speakerId") in allowed
            else fallback
        )
        normalized.append(updated)
    return normalized


def build_effective_analysis(job: dict[str, Any] | None) -> dict[str, Any] | None:
    if not job or not job.get("analysis"):
        return None
    base = copy.deepcopy(job["analysis"])
    overrides = job.get("overrides") or {}
    if not base.get("videoMeta"):
        return None
    if overrides.get("sourceLanguage") and overrides.get("sourceLanguage") != "auto":
        base["sourceLanguage"] = overrides["sourceLanguage"]
    if overrides.get("targetLanguage"):
        base["targetLanguage"] = overrides["targetLanguage"]
    if overrides.get("subtitleRegion"):
        base["subtitleRegion"] = {
            **(base.get("subtitleRegion") or {}),
            **overrides["subtitleRegion"],
        }
    if overrides.get("subtitleTimeline") is not None:
        base["subtitleTimeline"] = copy.deepcopy(overrides.get("subtitleTimeline") or [])
    if overrides.get("subtitleSrt") is not None:
        base["subtitleSrt"] = overrides.get("subtitleSrt") or ""
    if overrides.get("subtitleTimelineSource"):
        base["subtitleTimelineSource"] = overrides["subtitleTimelineSource"]
    detection_mode = (
        overrides.get("speakerDetectionMode")
        or base.get("renderDefaults", {}).get("speakerDetectionMode")
        or "narrator"
    )
    detected_speaker_count = max(
        1,
        min(
            int(
                base.get("detectedSpeakerCountRaw")
                or len(base.get("speakers") or [])
                or 1
            ),
            4,
        ),
    )
    requested_speaker_count = max(
        1, min(int(overrides.get("speakerCount") or detected_speaker_count or 1), 4)
    )
    if detection_mode == "dialogue":
        speaker_count = requested_speaker_count
    else:
        speaker_count = 1
    raw_main_speaker_id = base.get("mainSpeakerId") or "speaker_1"
    try:
        main_index = int(str(raw_main_speaker_id).replace("speaker_", ""))
    except Exception:
        main_index = 1
    main_speaker_id = (
        raw_main_speaker_id if 1 <= main_index <= speaker_count else "speaker_1"
    )
    voice_mapping = {
        **{
            speaker.get("speakerId"): speaker.get("voicePreset")
            for speaker in base.get("speakers", [])
        },
        **(overrides.get("voiceMapping") or {}),
    }
    base["speakers"] = build_speakers(
        speaker_count,
        voice_mapping=voice_mapping,
        base_speakers=base.get("speakers") or [],
        main_speaker_id=main_speaker_id,
    )
    base["segments"] = reconcile_segments_to_speaker_count(
        base.get("segments") or [], speaker_count, main_speaker_id=main_speaker_id
    )
    base["renderDefaults"] = {
        **(base.get("renderDefaults") or {}),
        "voiceMapping": voice_mapping,
        "speakerDetectionMode": detection_mode,
        "targetLanguage": base.get("targetLanguage", "vi"),
    }
    return base
