from gui.config import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_VOICES,
    FONT_OPTIONS,
    INTRO_VOICE_PRESETS,
    MOJIBAKE_MARKERS,
    Path,
    ROOT,
    SPEAKER_COLORS,
    TEMP_DUB_DIR,
    VOICE_LABELS,
)
from typing import Any
import copy
import re
from PyQt6.QtWidgets import QApplication
import os
import json
from gui import config


def repair_mojibake_text(value: str | None) -> str:
    text = str(value or "")
    repaired = text
    suspicious_markers = (*MOJIBAKE_MARKERS, "Ã", "Æ", "Ä", "Å", "á»", "áº")
    for _ in range(3):
        if repaired.isascii():
            break
        if not any(marker in repaired for marker in suspicious_markers):
            break
        candidate = repaired
        for encoding in ("latin1", "cp1252"):
            try:
                candidate = repaired.encode(encoding).decode("utf-8")
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
            
    return repaired



APP_STYLESHEET = """
QMainWindow, QWidget#AppRoot {
    background: #07111f;
    color: #e8eefc;
    font-family: "Segoe UI", "Arial";
    font-size: 13px;
}
QScrollArea {
    border: none;
    background: transparent;
}
QFrame#HeroCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #102443, stop:0.5 #0f766e, stop:1 #0ea5e9);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 12px;
}
QFrame#SurfaceCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0d1b31, stop:0.55 #0d1829, stop:1 #091321);
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 20px;
}
QFrame#StatCard {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
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
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(7, 18, 34, 0.96), stop:1 rgba(12, 28, 49, 0.96));
    border: 1px solid rgba(56, 189, 248, 0.24);
    border-radius: 12px;
    color: #f8fafc;
    padding: 8px 10px;
    selection-background-color: #38bdf8;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {
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
    selection-background-color: #38bdf8;
    selection-color: #07111f;
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
    background: #38bdf8;
    color: #07111f;
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_intro_voice_preset(preset_key: str | None) -> dict[str, Any]:
    if preset_key and preset_key in INTRO_VOICE_PRESETS:
        preset = INTRO_VOICE_PRESETS[preset_key]
        voice = str(preset.get("voice") or "").strip()
        normalized_voice = (
            "edge:female"
            if voice == "vi-VN-HoaiMyNeural"
            else "edge:male"
            if voice == "vi-VN-NamMinhNeural"
            else voice
        )
        return {
            "key": normalized_voice or preset_key,
            "voice": normalized_voice or voice,
            "label": preset.get("label") or normalized_voice or voice,
            "rateDeltaPercent": int(preset.get("rateDeltaPercent") or 0),
        }
    custom_voice = str(preset_key or "").strip()
    if custom_voice in {"vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"}:
        custom_voice = (
            "edge:female" if custom_voice == "vi-VN-HoaiMyNeural" else "edge:male"
        )
    if custom_voice and (
        custom_voice in VOICE_LABELS or custom_voice.endswith("Neural")
    ):
        return {
            "key": custom_voice,
            "voice": custom_voice,
            "label": custom_voice,
            "rateDeltaPercent": 0,
        }
    fallback_key = "male_story"
    return {"key": fallback_key, **INTRO_VOICE_PRESETS[fallback_key]}


def default_settings() -> dict[str, Any]:
    return {
        "sourceLanguage": "auto",
        "targetLanguage": "vi",
        "speakerDetectionMode": "auto",
        "speakerCount": 1,
        "voiceMapping": {},
        "introHook": {
            "enabled": True,
            "clipDurationMs": 10000,
            "voice": "edge:male",
            "voicePresetKey": "edge:male",
            "voiceRateDeltaPercent": 0,
            "useBackgroundAudio": True,
            "backgroundVolume": 0.08,
        },
        "subtitlePreset": {
            "enabled": True,
            "positionPreset": "bottom",
            "fontSize": 28,
            "fontFamily": "arial-bold",
            "fontFamilyLabel": "Arial Bold",
            "fontFamilyName": "Arial",
            "cssFontFamily": "Arial",
            "assFontName": "Arial",
            "draftFontKey": "Poppins_Bold",
            "fontColor": "#ffd200",
            "strokeColor": "#000000",
            "strokeWidth": 2,
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
        "watermark": {
            "enabled": False,
            "path": "",
            "position": "top-right",
            "scale": 0.15,
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
    compact_message = " ".join(str(message or "").split()).strip()
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
        or "auto"
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
    if detection_mode == "narrator":
        speaker_count = 1
    elif detection_mode == "dialogue":
        speaker_count = requested_speaker_count
    elif base.get("voiceLayout") == "single_voice":
        speaker_count = 1
    else:
        speaker_count = detected_speaker_count
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
