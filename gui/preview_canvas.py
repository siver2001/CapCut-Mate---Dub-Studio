from gui.utils import (
    Any,
    copy,
    default_settings,
    find_font_option,
    repair_mojibake_text,
    resolve_preview_caption_placement,
)
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QImage, QPixmap, QPen, QFont, QPainterPath


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
        self._cleanup_rect = QRectF()
        self._cleanup_handle_rect = QRectF()
        self._watermark_rect = QRectF()
        self._watermark_handle_rect = QRectF()
        self._dragging_caption = False
        self._dragging_cleanup = False
        self._resizing_cleanup = False
        self._resizing_watermark = False
        self._drag_offset_y = 0.0
        self._cleanup_drag_offset = (0.0, 0.0)

    def update_state(
        self,
        analysis: dict[str, Any] | None,
        settings: dict[str, Any],
        preview_text: str,
    ) -> None:
        self.analysis = analysis
        self.settings = copy.deepcopy(settings)
        self.preview_text = preview_text
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#091221"))

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

        video_meta = self.analysis.get("videoMeta") or {}
        width = max(int(video_meta.get("width") or 1), 1)
        height = max(int(video_meta.get("height") or 1), 1)
        region = self.settings.get("subtitleRegion") or {}

        def map_rect(x: int, y: int, w: int, h: int) -> QRectF:
            return QRectF(
                target.left() + (x / width) * target.width(),
                target.top() + (y / height) * target.height(),
                max((w / width) * target.width(), 1.0),
                max((h / height) * target.height(), 1.0),
            )

        preview_rect = map_rect(
            region.get("x", 0),
            region.get("y", 0),
            region.get("w", 0),
            region.get("h", 0),
        )
        self._cleanup_rect = QRectF(preview_rect)
        self._cleanup_handle_rect = QRectF(
            preview_rect.right() - 8, preview_rect.bottom() - 8, 10, 10
        )

        cleanup_mode = self.settings.get("sourceSubtitleCleanupMode", "none")
        if cleanup_mode != "none":
            fill = QColor(0, 0, 0, 105 if cleanup_mode == "localized_mask" else 55)
            painter.fillRect(preview_rect, fill)
            painter.setPen(QPen(QColor("#facc15"), 2))
            painter.drawRoundedRect(preview_rect, 10, 10)
            painter.fillRect(self._cleanup_handle_rect, QColor("#facc15"))
        painter.setPen(QPen(QColor(255, 255, 255, 180), 1, Qt.PenStyle.DashLine))
        painter.drawRoundedRect(preview_rect, 10, 10)

        subtitle_preset = self.settings.get("subtitlePreset") or {}
        if subtitle_preset.get("enabled", True):
            font_option = find_font_option(
                str(subtitle_preset.get("fontFamily") or "arial-bold")
            )
            base_font = QFont(
                str(
                    subtitle_preset.get("fontFamilyName")
                    or font_option["fontFamilyName"]
                ),
                max(int(subtitle_preset.get("fontSize", 28) * 0.55), 12),
            )
            base_font.setBold(True)
            placement, offset = resolve_preview_caption_placement(
                str(subtitle_preset.get("positionPreset") or "bottom"),
                int(subtitle_preset.get("bottomOffset", 54)),
            )
            painter.setFont(base_font)
            metrics_height = painter.fontMetrics().boundingRect("Ag").height()
            text_rect = QRectF(
                target.left() + target.width() * 0.08,
                target.top(),
                target.width() * 0.84,
                target.height(),
            )
            if placement == "top":
                text_rect.moveTop(target.top() + offset)
                text_rect.setHeight(metrics_height * 2.8)
            elif placement == "middle":
                text_rect.setHeight(metrics_height * 3.0)
                text_rect.moveTop(target.center().y() - text_rect.height() * 0.5)
            else:
                text_rect.setHeight(metrics_height * 2.8)
                text_rect.moveTop(target.bottom() - text_rect.height() - offset)
            self._caption_rect = QRectF(text_rect)
            path = QPainterPath()
            path.addText(
                text_rect.left() + 6,
                text_rect.top() + metrics_height + 4,
                base_font,
                repair_mojibake_text(self.preview_text or "Xem trước vietsub mới"),
            )
            stroke_width = max(float(subtitle_preset.get("strokeWidth", 2)), 0.0) * 1.3
            painter.setPen(
                QPen(
                    QColor(str(subtitle_preset.get("strokeColor", "#000000"))),
                    stroke_width,
                )
            )
            painter.drawPath(path)
            painter.fillPath(
                path, QColor(str(subtitle_preset.get("fontColor", "#ffd200")))
            )
            painter.setPen(QPen(QColor(255, 255, 255, 110), 1, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(text_rect.adjusted(-8, -6, 8, 8), 12, 12)
            painter.setPen(QColor("#e2e8f0"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(
                text_rect.adjusted(0, -24, 0, -4),
                Qt.AlignmentFlag.AlignCenter,
                "Kéo phụ đề để đổi vị trí",
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
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._cleanup_handle_rect.contains(event.position())
        ):
            self._resizing_cleanup = True
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._cleanup_rect.contains(
            event.position()
        ):
            self._dragging_cleanup = True
            self._cleanup_drag_offset = (
                float(event.position().x() - self._cleanup_rect.left()),
                float(event.position().y() - self._cleanup_rect.top()),
            )
            self.setCursor(Qt.CursorShape.SizeAllCursor)
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
        if self._dragging_cleanup and self._target_rect.height() > 0:
            left = float(event.position().x() - self._cleanup_drag_offset[0])
            top = float(event.position().y() - self._cleanup_drag_offset[1])
            self.cleanup_region_changed.emit(self._resolve_cleanup_move(left, top))
            event.accept()
            return
        if self._resizing_cleanup and self._target_rect.height() > 0:
            self.cleanup_region_changed.emit(
                self._resolve_cleanup_resize(
                    float(event.position().x()), float(event.position().y())
                )
            )
            event.accept()
            return

        if self._caption_rect.contains(event.position()):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif self._watermark_handle_rect.contains(event.position()):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif self._cleanup_handle_rect.contains(event.position()):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif self._cleanup_rect.contains(event.position()):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
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
        if self._dragging_cleanup or self._resizing_cleanup:
            self._dragging_cleanup = False
            self._resizing_cleanup = False
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

    def _resolve_cleanup_move(self, left: float, top: float) -> dict[str, int]:
        target = self._target_rect
        rect = self._cleanup_rect
        bounded_left = max(
            float(target.left()), min(left, float(target.right() - rect.width()))
        )
        bounded_top = max(
            float(target.top()), min(top, float(target.bottom() - rect.height()))
        )
        return self._cleanup_rect_to_region(
            QRectF(bounded_left, bounded_top, rect.width(), rect.height())
        )

    def _resolve_cleanup_resize(self, right: float, bottom: float) -> dict[str, int]:
        rect = self._cleanup_rect
        target = self._target_rect
        bounded_right = max(rect.left() + 36.0, min(right, float(target.right())))
        bounded_bottom = max(rect.top() + 28.0, min(bottom, float(target.bottom())))
        return self._cleanup_rect_to_region(
            QRectF(
                rect.left(),
                rect.top(),
                bounded_right - rect.left(),
                bounded_bottom - rect.top(),
            )
        )

    def _cleanup_rect_to_region(self, rect: QRectF) -> dict[str, int]:
        if not self.analysis or not self.analysis.get("videoMeta"):
            return {"x": 0, "y": 0, "w": 0, "h": 0}
        target = self._target_rect
        video_meta = self.analysis.get("videoMeta") or {}
        width = max(int(video_meta.get("width") or 1), 1)
        height = max(int(video_meta.get("height") or 1), 1)
        return {
            "x": max(
                0, int(round((rect.left() - target.left()) / target.width() * width))
            ),
            "y": max(
                0, int(round((rect.top() - target.top()) / target.height() * height))
            ),
            "w": max(1, int(round(rect.width() / target.width() * width))),
            "h": max(1, int(round(rect.height() / target.height() * height))),
        }
