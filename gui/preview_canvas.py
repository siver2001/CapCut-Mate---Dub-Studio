from gui.utils import (
    Any,
    copy,
    default_settings,
    ensure_qt_readable_sticker_preview,
    find_font_option,
    normalize_preview_text,
    repair_mojibake_text,
    resolve_preview_caption_placement,
)
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QImage, QPixmap, QPen, QFont

from tools.dub_studio.font_cache import preload_font

# Track which fonts have been loaded into Qt's font database
_loaded_fonts: set[str] = set()


def _fix_black_color(color: QColor) -> QColor:
    """If color is too dark (near black), return white instead for visibility."""
    if color.red() < 30 and color.green() < 30 and color.blue() < 30:
        return QColor("#ffffff")
    return color


class PreviewCanvas(QWidget):
    subtitle_dragged = pyqtSignal(str, int)
    cleanup_region_changed = pyqtSignal(dict)
    watermark_scale_changed = pyqtSignal(float)

    def __init__(self) -> None:
        super().__init__()
        self.analysis: dict[str, Any] | None = None
        self.settings: dict[str, Any] = default_settings()
        self.preview_text = "Xem trước vietsub mới ngay trên khung video"
        self.setMinimumHeight(320)
        self._target_rect = QRectF()
        self._caption_rect = QRectF()
        self._watermark_rect = QRectF()
        self._watermark_handle_rect = QRectF()
        self._sticker_pixmap = None
        self._sticker_cache_key = ""
        # Preload all Google Fonts in background to avoid delay on first paint
        self._preload_fonts_in_background()

    def _preload_fonts_in_background(self) -> None:
        """Load all Google Fonts in a background thread so preview is ready immediately."""
        try:
            from PyQt6.QtCore import QThread

            class FontPreloadThread(QThread):
                def run(self) -> None:
                    try:
                        from tools.dub_studio.font_cache import preload_all_fonts

                        preload_all_fonts()
                    except Exception:
                        pass

            thread = FontPreloadThread(self)
            thread.setDaemon(True)
            thread.start(QThread.Priority.LowestPriority)
        except Exception:
            pass  # Non-critical: fonts load lazily on paint anyway
        self._dragging_caption = False
        self._resizing_watermark = False
        self._drag_offset_y = 0.0

    def update_state(
        self,
        analysis: dict[str, Any] | None,
        settings: dict[str, Any],
        preview_text: str,
    ) -> None:
        self.analysis = analysis
        self.settings = copy.deepcopy(settings)
        self.preview_text = preview_text
        self._load_sticker_preview()
        self.update()

    def _load_sticker_preview(self) -> None:
        """Preload sticker image for preview rendering."""
        self._sticker_pixmap = None
        sticker_opts = self.settings.get("stickerOptions") or {}
        sticker_id = str(sticker_opts.get("stickerId") or "")
        if not sticker_id:
            self._sticker_cache_key = ""
            return
        image_url = str(sticker_opts.get("image_url") or "").strip()
        if not image_url:
            self._sticker_cache_key = ""
            return
        cache_key = "|".join(
            [
                sticker_id,
                image_url,
                str(sticker_opts.get("sticker_type") or ""),
            ]
        )
        if cache_key == self._sticker_cache_key and self._sticker_pixmap is not None:
            return
        try:
            cached = ensure_qt_readable_sticker_preview(sticker_opts)
            if cached is None:
                return
            img = QImage(str(cached))
            if not img.isNull():
                self._sticker_pixmap = QPixmap.fromImage(img)
                self._sticker_cache_key = cache_key
        except Exception:
            pass

    @staticmethod
    def _build_preview_text(text: str, max_words_per_line: int) -> str:
        clean = normalize_preview_text(text)
        if not clean:
            clean = "Đây là preview subtitle để xem cỡ chữ, màu chữ và box trên video."
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
        if len(lines) >= 2 and len(words) > sum(len(line.split()) for line in lines):
            lines[-1] = lines[-1].rstrip(" .,!?:;") + "..."
        if not lines:
            lines = [clean]
        return "\n".join(lines[:2])

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#091221"))
        pending_preview_overlay: dict[str, Any] | None = None

        if not self.analysis or not self.analysis.get("thumbnailPath"):
            painter.setPen(QColor("#cbd5e1"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Khung preview sẽ hiện tại đây sau khi phân tích video",
            )
            painter.end()
            return

        image = QImage(self.analysis["thumbnailPath"])
        if image.isNull():
            painter.setPen(QColor("#ef4444"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Không tải được thumbnail preview",
            )
            painter.end()
            return

        pixmap = QPixmap.fromImage(image)
        target = self._fit_rect(
            self.rect().adjusted(12, 12, -12, -12), pixmap.width(), pixmap.height()
        )
        self._target_rect = QRectF(target)
        painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))

        # Sticker Preview
        sticker_opts = self.settings.get("stickerOptions") or {}
        sticker_id = str(sticker_opts.get("stickerId") or "")
        if sticker_id and self._sticker_pixmap and not self._sticker_pixmap.isNull():
            scale = float(sticker_opts.get("scale", 1.0))
            base_w = target.width() // 4
            sw = max(20, int(base_w * scale))
            sw = min(sw, int(target.width() * 0.5))
            sticker_pm = self._sticker_pixmap.scaledToWidth(
                sw, Qt.TransformationMode.SmoothTransformation
            )
            # Position: upper area, center horizontally
            sx = target.center().x() - sticker_pm.width() * 0.5
            sy = target.top() + 16
            painter.drawPixmap(int(sx), int(sy), sticker_pm)
            # Subtle dashed border
            sticker_border_rect = QRectF(
                sx, sy, sticker_pm.width(), sticker_pm.height()
            )
            painter.setPen(QPen(QColor(255, 255, 255, 80), 1, Qt.PenStyle.DashLine))
            painter.drawRect(sticker_border_rect)
        elif sticker_id:
            # Sticker selected but image not cached (or is GIF) — show label
            painter.setPen(QColor(255, 200, 0, 200))
            painter.setFont(QFont("Segoe UI", 9))
            label = "[Sticker]"
            if int(sticker_opts.get("sticker_type", 1)) == 2:
                label = "[Sticker Animated]"
            tw = painter.fontMetrics().horizontalAdvance(label)
            painter.drawText(
                int(target.center().x() - tw * 0.5), int(target.top() + 30), label
            )

        subtitle_preset = self.settings.get("subtitlePreset") or {}
        if subtitle_preset.get("enabled", True):
            font_option = find_font_option(
                str(subtitle_preset.get("fontFamily") or "arial-bold")
            )
            font_family = str(
                subtitle_preset.get("fontFamilyName")
                or font_option["fontFamilyName"]
            )
            # Load font from cache if not already loaded (enables Google Fonts / custom fonts in preview)
            if font_family not in _loaded_fonts:
                if preload_font(font_family):
                    _loaded_fonts.add(font_family)
            base_font = QFont(font_family)
            base_font.setPixelSize(max(int(subtitle_preset.get("fontSize", 14)), 8))
            base_font.setBold(True)
            placement, offset = resolve_preview_caption_placement(
                str(subtitle_preset.get("positionPreset") or "bottom"),
                int(subtitle_preset.get("bottomOffset", 54)),
            )
            painter.setFont(base_font)
            metrics = painter.fontMetrics()
            metrics_height = metrics.boundingRect("Ag").height()
            preview_text = self._build_preview_text(
                repair_mojibake_text(self.preview_text or ""),
                int(subtitle_preset.get("maxWordsPerChunk", 5)),
            )
            max_text_width = target.width() * 0.76
            text_width = min(metrics.horizontalAdvance(preview_text.replace("\n", " ")), max_text_width)
            box_enabled = bool(subtitle_preset.get("boxEnabled", False))
            box_layout_mode = str(subtitle_preset.get("boxLayoutMode", "line") or "line").strip().lower()
            box_padding_x = max(int(subtitle_preset.get("boxPaddingX", 24)), 0)
            box_padding_y = max(int(subtitle_preset.get("boxPaddingY", 12)), 0)
            box_radius = max(int(subtitle_preset.get("boxRadius", 16)), 0)
            box_border_width = max(int(subtitle_preset.get("boxBorderWidth", 2)), 0)
            box_fill_opacity = max(min(float(subtitle_preset.get("boxFillOpacity", 0.86)), 1.0), 0.0)
            box_border_opacity = max(min(float(subtitle_preset.get("boxBorderOpacity", 1.0)), 1.0), 0.0)
            line_gap = max(int(metrics_height * 0.3), 4)
            preview_lines = preview_text.splitlines() or [preview_text]
            content_height = metrics_height * len(preview_lines) + line_gap * max(len(preview_lines) - 1, 0)
            caption_width = max(text_width + box_padding_x * 2, target.width() * 0.22)
            caption_height = content_height + box_padding_y * 2
            if box_enabled and box_layout_mode == "line" and len(preview_lines) > 1:
                caption_height = (
                    len(preview_lines) * (metrics_height + box_padding_y * 2)
                    + max(line_gap - 1, 3) * (len(preview_lines) - 1)
                )
            if not box_enabled:
                caption_width += 20
                caption_height += 12
            caption_width = min(caption_width, target.width() * 0.84)
            caption_left = target.center().x() - caption_width * 0.5
            if placement == "top":
                caption_top = target.top() + offset
            elif placement == "middle":
                caption_top = target.center().y() - caption_height * 0.5
            else:
                caption_top = target.bottom() - caption_height - offset
            caption_rect = QRectF(caption_left, caption_top, caption_width, caption_height)
            caption_rects = [caption_rect]
            if box_enabled:
                box_fill = QColor(str(subtitle_preset.get("boxFillColor", "#77b8ee")))
                box_fill.setAlphaF(box_fill_opacity)
                box_border = QColor(str(subtitle_preset.get("boxBorderColor", "#3b82f6")))
                box_border.setAlphaF(box_border_opacity)
                if box_layout_mode == "line" and len(preview_lines) > 1:
                    line_rects: list[QRectF] = []
                    current_top = caption_top
                    min_width = target.width() * 0.24
                    for line in preview_lines:
                        line_text_width = min(
                            metrics.horizontalAdvance(line or " "),
                            max_text_width,
                        )
                        line_box_width = min(
                            max(line_text_width + box_padding_x * 2, min_width),
                            target.width() * 0.84,
                        )
                        line_box_height = metrics_height + box_padding_y * 2
                        line_left = target.center().x() - line_box_width * 0.5
                        line_rect = QRectF(
                            line_left,
                            current_top,
                            line_box_width,
                            line_box_height,
                        )
                        line_rects.append(line_rect)
                        current_top += line_box_height + max(line_gap - 1, 3)
                    caption_rects = line_rects or [caption_rect]
                    
                # Pass 1: Filled background
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(box_fill)
                for rect in caption_rects:
                    painter.drawRoundedRect(rect, box_radius, box_radius)
                    
                # Pass 2: Border outline
                if box_border_width > 0:
                    painter.setPen(QPen(box_border, float(box_border_width), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    for rect in caption_rects:
                        painter.drawRoundedRect(rect, box_radius, box_radius)
            outline_union_rect = QRectF(caption_rects[0])
            for rect in caption_rects[1:]:
                outline_union_rect = outline_union_rect.united(rect)
            self._caption_rect = QRectF(outline_union_rect.adjusted(-8, -8, 8, 8))
            stroke_width = max(int(round(float(subtitle_preset.get("strokeWidth", 2)))), 0)
            text_rect = outline_union_rect.adjusted(
                box_padding_x,
                box_padding_y - 2,
                -box_padding_x,
                -box_padding_y + 2,
            )
            pending_preview_overlay = {
                "font": QFont(base_font),
                "textRect": QRectF(text_rect),
                "text": preview_text,
                "fontColor": _fix_black_color(QColor(str(subtitle_preset.get("fontColor", "#ffd200")))),
                "strokeColor": QColor(str(subtitle_preset.get("strokeColor", "#000000"))),
                "strokeWidth": stroke_width,
            }
            painter.setPen(QPen(QColor(255, 255, 255, 110), 1, Qt.PenStyle.DashLine))
            outline_rect = self._caption_rect
            painter.drawRoundedRect(outline_rect, 12, 12)
            hint_font = QFont("Segoe UI", 9)
            painter.setFont(hint_font)
            hint_text = "Preview subtitle - kéo để đổi vị trí"
            hint_width = painter.fontMetrics().horizontalAdvance(hint_text) + 16
            hint_rect = QRectF(
                target.left() + 10,
                target.top() + 10,
                min(hint_width, target.width() * 0.44),
                painter.fontMetrics().height() + 10,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(8, 15, 29, 185))
            painter.drawRoundedRect(hint_rect, 10, 10)
            painter.setPen(QColor("#e2e8f0"))
            painter.drawText(
                hint_rect,
                Qt.AlignmentFlag.AlignCenter,
                hint_text,
            )
        else:
            self._caption_rect = QRectF()

        # Watermark Preview
        watermark = self.settings.get("watermark", {})
        if watermark.get("enabled") and watermark.get("path"):
            wm_pm = QPixmap(watermark["path"])
            if not wm_pm.isNull():
                scale_factor = float(watermark.get("scale", 0.15))
                wm_w = max(10.0, target.width() * scale_factor)
                wm_pm_scaled = wm_pm.scaledToWidth(int(wm_w), Qt.TransformationMode.SmoothTransformation)
                
                pos = watermark.get("position", "top-right")
                margin = 10
                
                if pos == "top-left":
                    wm_x = target.left() + margin
                    wm_y = target.top() + margin
                elif pos == "top-right":
                    wm_x = target.right() - wm_pm_scaled.width() - margin
                    wm_y = target.top() + margin
                elif pos == "bottom-left":
                    wm_x = target.left() + margin
                    wm_y = target.bottom() - wm_pm_scaled.height() - margin
                else: # bottom-right
                    wm_x = target.right() - wm_pm_scaled.width() - margin
                    wm_y = target.bottom() - wm_pm_scaled.height() - margin
                
                self._watermark_rect = QRectF(wm_x, wm_y, wm_pm_scaled.width(), wm_pm_scaled.height())
                painter.drawPixmap(int(wm_x), int(wm_y), wm_pm_scaled)
                
                # Draw a subtle border around watermark and a resize handle
                painter.setPen(QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine))
                painter.drawRect(self._watermark_rect)
                
                handle_size = 10
                self._watermark_handle_rect = QRectF(
                    self._watermark_rect.right() - handle_size/2,
                    self._watermark_rect.bottom() - handle_size/2,
                    handle_size,
                    handle_size
                )
                painter.fillRect(self._watermark_handle_rect, QColor("#facc15"))
        else:
            self._watermark_rect = QRectF()
            self._watermark_handle_rect = QRectF()

        painter.end()
        if pending_preview_overlay:
            overlay = QPainter(self)
            overlay.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            overlay.setFont(pending_preview_overlay["font"])
            text_rect = pending_preview_overlay["textRect"]
            text = pending_preview_overlay["text"]
            text_flags = int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap)
            stroke_width = max(int(pending_preview_overlay["strokeWidth"]), 0)
            if stroke_width > 0:
                overlay.setPen(pending_preview_overlay["strokeColor"])
                for dx in range(-stroke_width, stroke_width + 1):
                    for dy in range(-stroke_width, stroke_width + 1):
                        if dx == 0 and dy == 0:
                            continue
                        if abs(dx) + abs(dy) > stroke_width + 1:
                            continue
                        overlay.drawText(text_rect.translated(dx, dy), text_flags, text)
            overlay.setPen(pending_preview_overlay["fontColor"])
            overlay.drawText(text_rect, text_flags, text)
            overlay.end()

    @staticmethod
    def _fit_rect(bounds: QRectF, source_width: int, source_height: int) -> QRectF:
        if source_width <= 0 or source_height <= 0:
            return QRectF(bounds)
        scale = min(bounds.width() / source_width, bounds.height() / source_height)
        width = source_width * scale
        height = source_height * scale
        left = bounds.left() + (bounds.width() - width) / 2
        top = bounds.top() + (bounds.height() - height) / 2
        return QRectF(left, top, width, height)

    def mousePressEvent(self, event) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._watermark_handle_rect.contains(event.position())
        ):
            self._resizing_watermark = True
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            event.accept()
            return
  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._caption_rect.contains(
            event.position()
        ):
            self._dragging_caption = True
            self._drag_offset_y = float(event.position().y() - self._caption_rect.top())
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._resizing_watermark and self._target_rect.width() > 0:
            new_width = float(event.position().x() - self._watermark_rect.left())
            new_scale = new_width / self._target_rect.width()
            new_scale = max(0.05, min(0.5, new_scale))
            self.watermark_scale_changed.emit(new_scale)
            event.accept()
            return
            
        if self._dragging_caption and self._target_rect.height() > 0:
            top = float(event.position().y() - self._drag_offset_y)
            placement, offset = self._resolve_drag_position(top)
            self.subtitle_dragged.emit(placement, offset)
            event.accept()
            return

        if self._caption_rect.contains(event.position()):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif self._watermark_handle_rect.contains(event.position()):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._resizing_watermark:
            self._resizing_watermark = False
            self.unsetCursor()
        if self._dragging_caption:
            self._dragging_caption = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _resolve_drag_position(self, top: float) -> tuple[str, int]:
        target = self._target_rect
        caption_height = max(self._caption_rect.height(), 48.0)
        bounded_top = max(
            float(target.top()), min(top, float(target.bottom() - caption_height))
        )
        relative_top = bounded_top - float(target.top())
        relative_center = relative_top + caption_height * 0.5
        if relative_center <= target.height() * 0.33:
            position = "top"
            offset = int(round(max(relative_top - 12.0, 0.0) / 0.35))
        elif relative_center <= target.height() * 0.66:
            position = "middle"
            offset = 0
        else:
            distance_from_bottom = max(
                float(target.bottom()) - (bounded_top + caption_height), 0.0
            )
            position = "bottom"
            offset = int(round(distance_from_bottom / 0.7))
        return position, max(0, min(offset, 240))
