"""
VideoPreviewWidget — plays source video with synchronized subtitle + sticker overlay.

Layers:
  1. QVideoWidget (bottom) — video frames
  2. _OverlayWidget (transparent, top) — paints subtitle text and sticker,
     synchronized to the QMediaPlayer positionChanged signal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QRectF, QEvent, QUrl, QSizeF, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPainter, QPixmap, QPen, QFont, QColor
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QPushButton,
    QSlider,
    QStackedLayout,
)

from gui.utils import ensure_qt_readable_sticker_preview, find_font_option, repair_mojibake_text
from tools.dub_studio.font_cache import preload_font

_loaded_fonts: set[str] = set()


def _fix_black_color(color: QColor) -> QColor:
    """If color is too dark (near black), return white instead for visibility."""
    if color.red() < 30 and color.green() < 30 and color.blue() < 30:
        return QColor("#ffffff")
    return color


class _SubtitleOverlay(QWidget):
    """Transparent widget that paints subtitle text + sticker at the correct position."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAutoFillBackground(False)
        self._subtitle_data: dict[str, Any] = {}
        self._sticker_pixmap: QPixmap | None = None
        self._sticker_opts: dict[str, Any] = {}

    def update_overlay(
        self,
        subtitle_data: dict[str, Any],
        sticker_opts: dict[str, Any],
        sticker_pixmap: QPixmap | None,
    ) -> None:
        self._subtitle_data = subtitle_data
        self._sticker_opts = sticker_opts
        self._sticker_pixmap = sticker_pixmap
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_sticker(painter)
        self._paint_subtitle(painter)
        painter.end()

    def _paint_sticker(self, painter: QPainter) -> None:
        sticker_opts = self._sticker_opts
        sticker_id = str(sticker_opts.get("stickerId") or "")
        if not sticker_id:
            return
        pixmap = self._sticker_pixmap
        if pixmap is None or pixmap.isNull():
            self._paint_sticker_placeholder(painter)
            return
        scale = float(sticker_opts.get("scale", 1.0))
        base_w = self.width() // 4
        sw = max(20, int(base_w * scale))
        sw = min(sw, int(self.width() * 0.5))
        sticker_pm = pixmap.scaledToWidth(sw, Qt.TransformationMode.SmoothTransformation)
        transform_x = max(-1.0, min(float(sticker_opts.get("transform_x", 0.0)), 1.0))
        transform_y = max(-1.0, min(float(sticker_opts.get("transform_y", -0.3)), 1.0))
        sx = (self.width() - sticker_pm.width()) * ((transform_x + 1.0) * 0.5)
        sy = (self.height() - sticker_pm.height()) * ((transform_y + 1.0) * 0.5)
        sx = max(0.0, min(sx, max(self.width() - sticker_pm.width(), 0)))
        sy = max(0.0, min(sy, max(self.height() - sticker_pm.height(), 0)))
        painter.drawPixmap(int(sx), int(sy), sticker_pm)
        border_rect = QRectF(sx, sy, sticker_pm.width(), sticker_pm.height())
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1, Qt.PenStyle.DashLine))
        painter.drawRect(border_rect)

    def _paint_sticker_placeholder(self, painter: QPainter) -> None:
        sticker_opts = self._sticker_opts
        sticker_id = str(sticker_opts.get("stickerId") or "")
        if not sticker_id:
            return
        label = "[Sticker Animated]" if int(sticker_opts.get("sticker_type", 1)) == 2 else "[Sticker]"
        painter.setFont(QFont("Segoe UI", 10))
        metrics = painter.fontMetrics()
        rect_width = min(max(metrics.horizontalAdvance(label) + 28, 130), max(self.width() - 32, 80))
        rect_height = metrics.height() + 16
        transform_x = max(-1.0, min(float(sticker_opts.get("transform_x", 0.0)), 1.0))
        transform_y = max(-1.0, min(float(sticker_opts.get("transform_y", -0.3)), 1.0))
        left = (self.width() - rect_width) * ((transform_x + 1.0) * 0.5)
        top = (self.height() - rect_height) * ((transform_y + 1.0) * 0.5)
        rect = QRectF(left, top, rect_width, rect_height)
        painter.setPen(QPen(QColor(255, 255, 255, 110), 1, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(8, 15, 29, 180))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), label)

    def _paint_subtitle(self, painter: QPainter) -> None:
        subtitle_preset = self._subtitle_data.get("subtitlePreset") or {}
        if not subtitle_preset.get("enabled", True):
            return
        current_text = self._subtitle_data.get("current_text") or ""
        if not current_text:
            current_text = self._subtitle_data.get("preview_text") or ""
        if not current_text:
            return

        font_option = find_font_option(
            str(subtitle_preset.get("fontFamily") or "arial-bold")
        )
        font_family = str(
            subtitle_preset.get("fontFamilyName")
            or font_option["fontFamilyName"]
        )
        if font_family not in _loaded_fonts:
            if preload_font(font_family):
                _loaded_fonts.add(font_family)
        base_font = QFont(font_family)
        base_font.setPixelSize(max(int(subtitle_preset.get("fontSize", 14)), 8))
        base_font.setBold(True)
        painter.setFont(base_font)
        metrics = painter.fontMetrics()
        max_words = int(subtitle_preset.get("maxWordsPerChunk", 5))
        preview_lines = self._build_preview_lines(current_text, max_words)
        content_height = metrics.boundingRect("Ag").height()
        line_gap = max(int(content_height * 0.3), 4)
        box_enabled = bool(subtitle_preset.get("boxEnabled", False))
        box_layout_mode = str(subtitle_preset.get("boxLayoutMode", "line") or "line").strip().lower()
        box_padding_x = max(int(subtitle_preset.get("boxPaddingX", 24)), 0)
        box_padding_y = max(int(subtitle_preset.get("boxPaddingY", 12)), 0)
        box_radius = max(int(subtitle_preset.get("boxRadius", 16)), 0)
        box_border_width = max(int(subtitle_preset.get("boxBorderWidth", 2)), 0)
        box_fill_opacity = max(min(float(subtitle_preset.get("boxFillOpacity", 0.86)), 1.0), 0.0)
        box_border_opacity = max(min(float(subtitle_preset.get("boxBorderOpacity", 1.0)), 1.0), 0.0)
        max_text_width = self.width() * 0.76
        text_width = min(
            metrics.horizontalAdvance((current_text or " ").replace("\n", " ")),
            max_text_width,
        )
        caption_height = content_height * len(preview_lines) + line_gap * max(len(preview_lines) - 1, 0)
        caption_width = max(text_width + box_padding_x * 2, self.width() * 0.22)
        caption_height_total = caption_height + box_padding_y * 2
        if box_enabled and box_layout_mode == "line" and len(preview_lines) > 1:
            caption_height_total = (
                len(preview_lines) * (content_height + box_padding_y * 2)
                + max(line_gap - 1, 3) * (len(preview_lines) - 1)
            )
        if not box_enabled:
            caption_width += 20
            caption_height_total += 12
        caption_width = min(caption_width, self.width() * 0.84)
        caption_left = self.width() / 2 - caption_width * 0.5
        placement, offset = self._resolve_placement(
            str(subtitle_preset.get("positionPreset") or "bottom"),
            int(subtitle_preset.get("bottomOffset", 54)),
        )
        if placement == "top":
            caption_top = offset
        elif placement == "middle":
            caption_top = self.height() / 2 - caption_height_total * 0.5
        else:
            caption_top = self.height() - caption_height_total - offset
        caption_rect = QRectF(caption_left, caption_top, caption_width, caption_height_total)
        caption_rects = [caption_rect]
        if box_enabled:
            box_fill = QColor(str(subtitle_preset.get("boxFillColor", "#77b8ee")))
            box_fill.setAlphaF(box_fill_opacity)
            box_border = QColor(str(subtitle_preset.get("boxBorderColor", "#3b82f6")))
            box_border.setAlphaF(box_border_opacity)
            if box_border_width > 0:
                painter.setPen(QPen(box_border, float(box_border_width)))
            else:
                painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(box_fill)
            if box_layout_mode == "line" and len(preview_lines) > 1:
                line_rects: list[QRectF] = []
                current_top = caption_top
                min_width = self.width() * 0.24
                for line in preview_lines:
                    line_text_width = min(metrics.horizontalAdvance(line or " "), max_text_width)
                    line_box_width = min(max(line_text_width + box_padding_x * 2, min_width), self.width() * 0.84)
                    line_box_height = content_height + box_padding_y * 2
                    line_left = self.width() / 2 - line_box_width * 0.5
                    line_rect = QRectF(line_left, current_top, line_box_width, line_box_height)
                    line_rects.append(line_rect)
                    current_top += line_box_height + max(line_gap - 1, 3)
                caption_rects = line_rects or [caption_rect]
            for rect in caption_rects:
                painter.drawRoundedRect(rect, box_radius, box_radius)
        stroke_width = max(int(round(float(subtitle_preset.get("strokeWidth", 2)))), 0)
        text_flags = int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap)
        if stroke_width > 0:
            stroke_color = QColor(str(subtitle_preset.get("strokeColor", "#000000")))
            painter.setPen(stroke_color)
            for dx in range(-stroke_width, stroke_width + 1):
                for dy in range(-stroke_width, stroke_width + 1):
                    if dx == 0 and dy == 0:
                        continue
                    if abs(dx) + abs(dy) > stroke_width + 1:
                        continue
                    for i, line in enumerate(preview_lines):
                        line_y = caption_rect.top() + box_padding_y + i * (content_height + line_gap)
                        painter.drawText(
                            int(caption_rect.left()),
                            int(line_y),
                            int(caption_rect.width()),
                            int(content_height + 2),
                            text_flags,
                            line,
                        )
        painter.setPen(_fix_black_color(QColor(str(subtitle_preset.get("fontColor", "#ffd200")))))
        for i, line in enumerate(preview_lines):
            line_y = caption_rect.top() + box_padding_y + i * (content_height + line_gap)
            painter.drawText(
                int(caption_rect.left()),
                int(line_y),
                int(caption_rect.width()),
                int(content_height + 2),
                text_flags,
                line,
            )

    @staticmethod
    def _build_preview_lines(text: str, max_words_per_line: int) -> list[str]:
        clean = repair_mojibake_text(text or "")
        if not clean:
            return []
        words = clean.split()
        safe_limit = max(2, int(max_words_per_line or 5))
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            current.append(word)
            if len(current) >= safe_limit:
                lines.append(" ".join(current))
                current = []
            if len(lines) >= 2:
                break
        if current and len(lines) < 2:
            lines.append(" ".join(current))
        if not lines:
            lines = [clean]
        return lines[:2]

    @staticmethod
    def _resolve_placement(position: str, offset: int) -> tuple[str, int]:
        return position, offset


class VideoPreviewWidget(QWidget):
    """
    Combines QVideoWidget + subtitle/sticker overlay + playback controls.

    Call `load_video(path)` to load a source video, then `play()`.
    Call `update_state(subtitle_data, sticker_opts)` to refresh overlays.
    """

    play_toggled = pyqtSignal(bool)  # True = playing, False = paused

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(320)

        # --- Media player ---
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(1.0)
        self._player.setAudioOutput(self._audio)

        # --- Layout ---
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # --- Video surface + overlay ---
        self._video_surface = QWidget(self)
        self._video_surface.setMinimumHeight(260)
        self._video_surface.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._video_surface.installEventFilter(self)
        self._surface_stack = QStackedLayout(self._video_surface)
        self._surface_stack.setContentsMargins(0, 0, 0, 0)
        self._surface_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)

        self._scene = QGraphicsScene(self._video_surface)
        self._video_item = QGraphicsVideoItem()
        self._video_item.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self._scene.addItem(self._video_item)
        self._video_view = QGraphicsView(self._scene, self._video_surface)
        self._video_view.setFrameShape(QFrame.Shape.NoFrame)
        self._video_view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._video_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._video_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._video_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_view.setStyleSheet("background: #000000; border: none;")
        self._video_view.installEventFilter(self)
        self._video_view.viewport().installEventFilter(self)
        self._player.setVideoOutput(self._video_item)

        self._overlay = _SubtitleOverlay(self._video_surface)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._surface_stack.addWidget(self._video_view)
        self._surface_stack.addWidget(self._overlay)
        self._layout.addWidget(self._video_surface, 1)

        # --- Controls ---
        self._controls_widget = QWidget(self)
        controls_layout = QVBoxLayout(self._controls_widget)
        controls_layout.setContentsMargins(4, 2, 4, 2)
        controls_layout.setSpacing(4)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(5)

        self._restart_btn = QPushButton("Từ đầu")
        self._restart_btn.clicked.connect(self._on_restart)

        self._seek_back_btn = QPushButton("-10s")
        self._seek_back_btn.clicked.connect(lambda: self.seek_relative(-10000))

        self._play_btn = QPushButton("Phát")
        self._play_btn.clicked.connect(self._on_play_clicked)

        self._seek_forward_btn = QPushButton("+10s")
        self._seek_forward_btn.clicked.connect(lambda: self.seek_relative(10000))

        self._stop_btn = QPushButton("Dừng")
        self._stop_btn.clicked.connect(self._on_stop_clicked)

        self._fullscreen_btn = QPushButton("Phóng To")
        self._fullscreen_btn.setToolTip("Phóng to màn hình. Nhấn Esc, F11 hoặc double-click video để thoát.")
        self._fullscreen_btn.clicked.connect(self.toggle_fullscreen)

        for button in (
            self._restart_btn,
            self._seek_back_btn,
            self._play_btn,
            self._seek_forward_btn,
            self._stop_btn,
            self._fullscreen_btn,
        ):
            button.setMaximumWidth(78)
            button_row.addWidget(button)
        button_row.addStretch(1)
        controls_layout.addLayout(button_row)

        seek_row = QHBoxLayout()
        seek_row.setContentsMargins(0, 0, 0, 0)
        seek_row.setSpacing(6)
        self._position_label = QLabel("00:00")
        self._position_label.setMinimumWidth(48)
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.setEnabled(False)
        self._seek_slider.sliderMoved.connect(self._on_seek_slider_moved)
        self._seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self._seek_slider.sliderReleased.connect(self._on_seek_released)

        self._duration_label = QLabel("00:00")
        self._duration_label.setMinimumWidth(48)
        seek_row.addWidget(self._position_label)
        seek_row.addWidget(self._seek_slider, 1)
        seek_row.addWidget(self._duration_label)
        controls_layout.addLayout(seek_row)

        audio_row = QHBoxLayout()
        audio_row.setContentsMargins(0, 0, 0, 0)
        audio_row.setSpacing(5)
        self._mute_btn = QPushButton("Tắt tiếng")
        self._mute_btn.setMaximumWidth(84)
        self._mute_btn.clicked.connect(self.toggle_mute)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(100)
        self._volume_slider.setMaximumWidth(180)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        self._volume_label = QLabel("100%")
        self._volume_label.setMinimumWidth(42)

        self._speed_combo = QComboBox()
        for value, label in [
            (0.75, "0.75x"),
            (1.0, "1x"),
            (1.25, "1.25x"),
            (1.5, "1.5x"),
            (2.0, "2x"),
        ]:
            self._speed_combo.addItem(label, value)
        self._speed_combo.setCurrentIndex(1)
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)

        audio_row.addWidget(self._mute_btn)
        audio_row.addWidget(QLabel("Âm"))
        audio_row.addWidget(self._volume_slider)
        audio_row.addWidget(self._volume_label)
        audio_row.addSpacing(6)
        audio_row.addWidget(QLabel("Tốc độ"))
        audio_row.addWidget(self._speed_combo)
        audio_row.addStretch(1)
        controls_layout.addLayout(audio_row)

        self._layout.addWidget(self._controls_widget, 0)

        # --- State ---
        self._subtitle_timeline: list[dict[str, Any]] = []
        self._subtitle_preset: dict[str, Any] = {}
        self._sticker_opts: dict[str, Any] = {}
        self._sticker_pixmap: QPixmap | None = None
        self._sticker_cache_key = ""
        self._current_text = ""
        self._preview_text = ""
        self._duration_ms = 0
        self._seeking = False
        self._muted = False
        self._volume = 100
        self._playback_rate = 1.0
        self._pause_after_load = False

        # --- Signals ---
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._fit_video_scene()

    def load_video(self, path: str | Path) -> bool:
        """Load a video file for preview. Returns True if successful."""
        video_path = Path(path).resolve()
        if not video_path.exists():
            return False
        self._player.stop()
        self._pause_after_load = True
        self._player.setSource(QUrl.fromLocalFile(str(video_path)))
        self._player.setPosition(0)
        self._player.pause()
        QTimer.singleShot(0, self._ensure_loaded_video_stays_paused)
        self._current_text = ""
        self._apply_audio_state()
        self._apply_playback_rate()
        self._set_time_labels(0, 0)
        self._update_control_labels()
        self._update_overlay()
        return True

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()
        self._set_time_labels(self._player.position(), self._duration_ms)
        self._update_control_labels()

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def seek_relative(self, delta_ms: int) -> None:
        current = max(0, int(self._player.position()))
        upper = self._duration_ms if self._duration_ms > 0 else current + abs(int(delta_ms))
        target = max(0, min(current + int(delta_ms), upper))
        self._player.setPosition(target)
        self._set_time_labels(target, self._duration_ms)

    def toggle_mute(self) -> None:
        self._muted = not self._muted
        self._apply_audio_state()

    def toggle_fullscreen(self) -> None:
        if self._is_fullscreen():
            self.exit_fullscreen()
            return
        self._video_surface.showFullScreen()
        self._video_surface.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._update_control_labels()

    def exit_fullscreen(self) -> None:
        if self._is_fullscreen():
            self._video_surface.showNormal()
        self._update_control_labels()

    def update_state(
        self,
        subtitle_data: dict[str, Any],
        sticker_opts: dict[str, Any],
    ) -> None:
        """
        Update the overlay with new subtitle and sticker settings.
        Called whenever settings change so the preview reflects live edits.
        """
        self._subtitle_preset = subtitle_data.get("subtitlePreset") or {}
        self._subtitle_timeline = subtitle_data.get("subtitleTimeline") or []
        self._preview_text = str(
            subtitle_data.get("preview_text")
            or subtitle_data.get("current_text")
            or ""
        )
        self._sticker_opts = sticker_opts or {}
        self._load_sticker_pixmap()
        self._update_overlay()

    def _load_sticker_pixmap(self) -> None:
        opts = self._sticker_opts
        sticker_id = str(opts.get("stickerId") or "")
        if not sticker_id:
            self._sticker_pixmap = None
            self._sticker_cache_key = ""
            return
        image_url = str(opts.get("image_url") or "").strip()
        if not image_url:
            self._sticker_pixmap = None
            self._sticker_cache_key = ""
            return
        cache_key = "|".join(
            [
                sticker_id,
                image_url,
                str(opts.get("sticker_type") or ""),
            ]
        )
        if cache_key == self._sticker_cache_key and self._sticker_pixmap is not None:
            return
        self._sticker_pixmap = None
        try:
            cached = ensure_qt_readable_sticker_preview(opts)
            if cached is None:
                return
            img = QImage(str(cached))
            if not img.isNull():
                self._sticker_pixmap = QPixmap.fromImage(img)
                self._sticker_cache_key = cache_key
        except Exception:
            pass

    def _find_subtitle_at_position(self, position_ms: int) -> str:
        for segment in self._subtitle_timeline:
            start = int(segment.get("startMs", 0))
            end = int(segment.get("endMs", 0))
            if start <= position_ms <= end:
                return str(segment.get("text") or "")
        return ""

    def _on_position_changed(self, position: int) -> None:
        if not self._seeking:
            self._seek_slider.blockSignals(True)
            self._seek_slider.setValue(position)
            self._seek_slider.blockSignals(False)
            self._set_time_labels(position, self._duration_ms)
            self._current_text = self._find_subtitle_at_position(position)
            self._update_overlay()

    def _on_duration_changed(self, duration: int) -> None:
        self._duration_ms = max(0, int(duration))
        self._seek_slider.blockSignals(True)
        self._seek_slider.setRange(0, self._duration_ms)
        self._seek_slider.setEnabled(self._duration_ms > 0)
        self._seek_slider.blockSignals(False)
        self._set_time_labels(self._player.position(), self._duration_ms)

    def _on_playback_state_changed(self, _state) -> None:
        playing = self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        if self._pause_after_load and playing:
            self._ensure_loaded_video_stays_paused()
            playing = False
        self._update_control_labels()
        self.play_toggled.emit(playing)

    def _ensure_loaded_video_stays_paused(self) -> None:
        if not self._pause_after_load:
            return
        self._player.pause()
        self._player.setPosition(0)
        self._pause_after_load = False
        self._current_text = ""
        self._set_time_labels(0, self._duration_ms)
        self._update_overlay()
        self._update_control_labels()

    def _on_play_clicked(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            if self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self._player.setPosition(0)
            self._player.play()

    def _on_restart(self) -> None:
        self._player.setPosition(0)
        self._player.play()

    def _on_stop_clicked(self) -> None:
        self._player.stop()
        self._set_time_labels(self._player.position(), self._duration_ms)
        self._update_control_labels()

    def _on_seek_pressed(self) -> None:
        self._seeking = True

    def _on_seek_slider_moved(self, value: int) -> None:
        self._set_time_labels(value, self._duration_ms)
        self._current_text = self._find_subtitle_at_position(value)
        self._update_overlay()

    def _on_seek_released(self) -> None:
        self._seeking = False
        self._player.setPosition(int(self._seek_slider.value()))

    def _on_volume_changed(self, value: int) -> None:
        self._volume = max(0, min(int(value), 100))
        if self._volume > 0 and self._muted:
            self._muted = False
        self._apply_audio_state()

    def _on_speed_changed(self) -> None:
        try:
            self._playback_rate = float(self._speed_combo.currentData() or 1.0)
        except Exception:
            self._playback_rate = 1.0
        self._apply_playback_rate()

    def _apply_audio_state(self) -> None:
        self._audio.setVolume(max(0.0, min(float(self._volume) / 100.0, 1.0)))
        try:
            self._audio.setMuted(self._muted)
        except Exception:
            pass
        self._update_control_labels()

    def _apply_playback_rate(self) -> None:
        self._playback_rate = max(0.25, min(float(self._playback_rate), 3.0))
        self._player.setPlaybackRate(self._playback_rate)

    def _is_fullscreen(self) -> bool:
        return bool(getattr(self._video_surface, "isFullScreen", lambda: False)())

    def _set_time_labels(self, position_ms: int, duration_ms: int) -> None:
        self._position_label.setText(self._format_time(position_ms))
        self._duration_label.setText(self._format_time(duration_ms))

    def _update_control_labels(self) -> None:
        playing = self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self._play_btn.setText("Tạm dừng" if playing else "Phát")
        self._mute_btn.setText("Bật tiếng" if self._muted else "Tắt tiếng")
        self._volume_label.setText(f"{self._volume}%")
        self._fullscreen_btn.setText("Thu nhỏ" if self._is_fullscreen() else "Phóng To")

    def _update_overlay(self) -> None:
        self._overlay.update_overlay(
            {
                "subtitlePreset": self._subtitle_preset,
                "subtitleTimeline": self._subtitle_timeline,
                "current_text": self._current_text,
                "preview_text": self._preview_text,
            },
            self._sticker_opts,
            self._sticker_pixmap,
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_video_scene()
        self._overlay.resize(self._video_surface.size())

    def _fit_video_scene(self) -> None:
        width = max(1, self._video_surface.width())
        height = max(1, self._video_surface.height())
        self._scene.setSceneRect(0, 0, width, height)
        self._video_item.setPos(0, 0)
        self._video_item.setSize(QSizeF(width, height))

    def eventFilter(self, watched, event) -> bool:
        watch_targets = {self._video_surface}
        video_view = getattr(self, "_video_view", None)
        if video_view is not None:
            watch_targets.add(video_view)
            watch_targets.add(video_view.viewport())
        if watched in watch_targets:
            event_type = event.type()
            if event_type == QEvent.Type.MouseButtonDblClick:
                self.toggle_fullscreen()
                return True
            if event_type == QEvent.Type.KeyPress and event.key() in {
                Qt.Key.Key_Escape,
                Qt.Key.Key_F11,
            }:
                if self._is_fullscreen():
                    self.exit_fullscreen()
                    return True
        return super().eventFilter(watched, event)

    @staticmethod
    def _format_time(ms: int) -> str:
        total_seconds = max(0, int(ms // 1000))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
