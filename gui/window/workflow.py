from __future__ import annotations

import copy
import importlib
import shutil
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices
try:
    from PyQt6.QtMultimedia import QMediaPlayer
except Exception:  # pragma: no cover
    QMediaPlayer = None

from PyQt6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QLineEdit,
    QMessageBox,
    QTableWidgetItem,
)

from gui.config import DEFAULT_OUTPUT_DIR, ROOT, VOICE_LABELS, VOICE_OPTIONS
from gui.utils import (
    default_settings,
    ensure_dir,
    find_font_option,
    normalize_preview_text,
    repair_mojibake_text,
    resolve_intro_voice_preset,
)
from tools.dub_studio.subtitle_utils import compose_srt_from_timeline, parse_srt_to_timeline


class WindowWorkflowMixin:
    @staticmethod
    def _format_render_preview_time(ms: int) -> str:
        total_seconds = max(0, int(ms // 1000))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _set_render_preview_time_labels(
        self, position_ms: int, duration_ms: int | None = None
    ) -> None:
        total_ms = (
            self._render_preview_duration_ms
            if duration_ms is None
            else max(0, int(duration_ms))
        )
        if hasattr(self, "render_preview_position_label"):
            self.render_preview_position_label.setText(
                self._format_render_preview_time(max(0, int(position_ms)))
            )
        if hasattr(self, "render_preview_duration_label"):
            self.render_preview_duration_label.setText(
                self._format_render_preview_time(total_ms)
            )

    def _reset_render_preview_timeline(self, *, clear_duration: bool = True) -> None:
        if clear_duration:
            self._render_preview_duration_ms = 0
        self._render_preview_scrubbing = False
        max_duration = self._render_preview_duration_ms if not clear_duration else 0
        if hasattr(self, "render_preview_seek_slider"):
            self.render_preview_seek_slider.blockSignals(True)
            self.render_preview_seek_slider.setRange(0, max_duration)
            self.render_preview_seek_slider.setValue(0)
            self.render_preview_seek_slider.blockSignals(False)
        self._set_render_preview_time_labels(0, self._render_preview_duration_ms)

    def choose_video(self) -> None:
        if self.controller.has_running_job():
            QMessageBox.warning(
                self,
                "Đang xử lý",
                "Hãy đợi tác vụ hiện tại hoàn tất hoặc dừng nó trước khi đổi video.",
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn video nguồn", "", "Video (*.mp4 *.mov *.mkv *.avi *.m4v *.webm)"
        )
        if not path:
            return
        self.input_path_edit.setText(path)
        self.job_id = None
        self.analysis = None
        self.effective_analysis = None
        self.job_status = None
        self.last_output_path = ""
        self.last_exported_output_path = ""
        self.stop_render_preview(clear_source=True)
        self.refresh_all()

    def choose_directory(self, target_edit: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Chọn thư mục", target_edit.text() or str(ROOT)
        )
        if selected:
            if target_edit is self.output_dir_edit:
                self.sync_output_directory_inputs(selected)
            else:
                target_edit.setText(selected)
            self.on_basic_settings_changed()

    def choose_output_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục xuất video sau render",
            self.output_folder_quick_edit.text().strip()
            or self.output_dir_edit.text().strip()
            or str(ROOT),
        )
        if selected:
            self.sync_output_directory_inputs(selected)
            self.on_basic_settings_changed()

    def on_output_directory_quick_changed(self) -> None:
        selected = self.output_folder_quick_edit.text().strip()
        self.sync_output_directory_inputs(selected)
        self.on_basic_settings_changed()

    def sync_output_directory_inputs(self, selected: str) -> None:
        value = selected.strip()
        self.output_folder_quick_edit.blockSignals(True)
        self.output_dir_edit.blockSignals(True)
        self.output_folder_quick_edit.setText(value)
        self.output_dir_edit.setText(value)
        self.output_folder_quick_edit.blockSignals(False)
        self.output_dir_edit.blockSignals(False)

    def choose_watermark_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh watermark", "", "Image (*.png *.jpg *.jpeg)"
        )
        if not path:
            return
        self.watermark_path_edit.setText(path)
        self.settings.setdefault("watermark", {})["path"] = path
        self.on_basic_settings_changed()

    def _ensure_directory(self, raw_path: str, fallback: Path) -> Path:
        candidate = Path(raw_path.strip()) if raw_path.strip() else fallback
        ensure_dir(candidate)
        return candidate

    def _current_render_preview_path(self) -> str:
        render_result = (
            ((self.job_status or {}).get("renderResult") or {})
            if self.job_status
            else {}
        )
        return str(
            render_result.get("previewVideoPath")
            or render_result.get("outputVideoPath")
            or self.last_output_path
            or ""
        ).strip()

    @staticmethod
    def _has_dependency(module_name: str) -> bool:
        return importlib.util.find_spec(module_name) is not None

    def _validate_analysis_input(self) -> Path:
        input_path = Path(self.input_path_edit.text().strip())
        if not str(input_path):
            raise RuntimeError("Hãy chọn video trước khi phân tích.")
        if not input_path.exists():
            raise RuntimeError(f"Không tìm thấy file video: {input_path}")
        if not input_path.is_file():
            raise RuntimeError("Đường dẫn video không hợp lệ.")
        return input_path

    def _prepare_render_options(self) -> dict[str, Any]:
        if not self._has_dependency("edge_tts"):
            raise RuntimeError(
                "Thiếu thư viện `edge_tts`, nên app chưa thể tạo giọng đọc.\n\n"
                "Cài bằng lệnh:\n"
                "python -m pip install edge-tts"
            )
        options = self.current_render_options()
        output_targets = options.get("outputTargets") or {}
        if not any(bool(value) for value in output_targets.values()):
            raise RuntimeError("Hãy bật ít nhất một định dạng output trước khi render.")
        output_dir = Path(
            str(options.get("outputDirectory") or "").strip() or str(DEFAULT_OUTPUT_DIR)
        )
        options["outputDirectory"] = str(output_dir)
        self.settings["outputDirectory"] = str(output_dir)
        self.sync_output_directory_inputs(str(output_dir))
        if output_targets.get("draft"):
            draft_root = self._ensure_directory(
                str(options.get("draftRoot") or ""), output_dir / "draft"
            )
            options["draftRoot"] = str(draft_root)
            self.settings["draftRoot"] = str(draft_root)
            self.draft_dir_edit.setText(str(draft_root))
        elif not str(options.get("draftRoot") or "").strip():
            options["draftRoot"] = str(output_dir / "draft")
        return options

    def start_analysis(self) -> None:
        try:
            input_path = self._validate_analysis_input()
            self.job_id = self.controller.analyze_video(
                str(input_path),
                {"targetLanguage": self.settings.get("targetLanguage", "vi")},
            )
            self.job_status = self.controller.get_job_status(self.job_id)
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "Phân tích thất bại", str(exc))

    def start_render(self) -> None:
        if not self.job_id or not self.analysis:
            QMessageBox.warning(
                self, "Thiếu dữ liệu phân tích", "Cần phân tích video trước khi render."
            )
            return
        try:
            self.read_settings_from_widgets()
            self._push_analysis_overrides()
            self.stop_render_preview(clear_source=True)
            self.last_exported_output_path = ""
            self.controller.render_video(self.job_id, self._prepare_render_options())
        except Exception as exc:
            QMessageBox.critical(self, "Render thất bại", str(exc))

    def preview_rendered_video(self) -> None:
        preview_path = self._current_render_preview_path()
        if not preview_path:
            QMessageBox.information(
                self,
                "Chưa có video render",
                "Hãy render video trước khi xem preview.",
            )
            return
        if self.render_preview_player is None or self.render_video_widget is None:
            QMessageBox.warning(
                self,
                "Không thể preview",
                "Qt Multimedia Video chưa sẵn sàng nên app chưa thể phát video trực tiếp trong giao diện.",
            )
            return
        video_path = Path(preview_path)
        if not video_path.exists():
            QMessageBox.information(
                self,
                "Không tìm thấy video",
                f"Không thấy file video render tại:\n{video_path}",
            )
            return
        self.last_output_path = str(video_path)
        if hasattr(self, "main_tabs") and hasattr(self, "preview_page"):
            self.main_tabs.setCurrentWidget(self.preview_page)
        self.render_preview_player.stop()
        self.render_preview_player.setSource(QUrl.fromLocalFile(str(video_path)))
        self.render_preview_player.play()
        if hasattr(self, "render_preview_status_label"):
            self.render_preview_status_label.setText(
                repair_mojibake_text(
                    f"Đang phát video render nội bộ: {video_path.name}"
                )
            )

    def pause_render_preview(self) -> None:
        if self.render_preview_player is None:
            return
        playback_state = getattr(self.render_preview_player, "playbackState", None)
        if callable(playback_state):
            current_state = playback_state()
            if current_state == QMediaPlayer.PlaybackState.PausedState:
                self.render_preview_player.play()
                preview_path = (
                    Path(self._current_render_preview_path()).name or "video render"
                )
                if hasattr(self, "render_preview_status_label"):
                    self.render_preview_status_label.setText(
                        repair_mojibake_text(
                            f"Đang phát tiếp preview: {preview_path}"
                        )
                    )
                return
        self.render_preview_player.pause()
        preview_path = Path(self._current_render_preview_path()).name or "video render"
        if hasattr(self, "render_preview_status_label"):
            self.render_preview_status_label.setText(
                repair_mojibake_text(f"Đã tạm dừng preview: {preview_path}")
            )

    def stop_render_preview(self, *, clear_source: bool = False) -> None:
        if self.render_preview_player is not None:
            self.render_preview_player.stop()
            if clear_source:
                self.render_preview_player.setSource(QUrl())
        self._reset_render_preview_timeline(clear_duration=clear_source)
        if clear_source and hasattr(self, "render_preview_status_label"):
            self.render_preview_status_label.setText(
                "Chưa có video render để xem trước."
            )
        elif hasattr(self, "render_preview_status_label"):
            preview_path = Path(self._current_render_preview_path()).name or "video render"
            self.render_preview_status_label.setText(
                repair_mojibake_text(f"Đã dừng preview: {preview_path}")
            )

    def _on_render_preview_duration_changed(self, duration: int) -> None:
        self._render_preview_duration_ms = max(0, int(duration))
        if hasattr(self, "render_preview_seek_slider"):
            self.render_preview_seek_slider.blockSignals(True)
            self.render_preview_seek_slider.setRange(0, self._render_preview_duration_ms)
            if not self._render_preview_scrubbing:
                self.render_preview_seek_slider.setValue(
                    min(
                        self.render_preview_seek_slider.value(),
                        self._render_preview_duration_ms,
                    )
                )
            self.render_preview_seek_slider.blockSignals(False)
        self._set_render_preview_time_labels(
            self.render_preview_seek_slider.value()
            if hasattr(self, "render_preview_seek_slider")
            else 0,
            self._render_preview_duration_ms,
        )

    def _on_render_preview_position_changed(self, position: int) -> None:
        safe_position = max(0, int(position))
        if hasattr(self, "render_preview_seek_slider") and not self._render_preview_scrubbing:
            self.render_preview_seek_slider.blockSignals(True)
            self.render_preview_seek_slider.setValue(safe_position)
            self.render_preview_seek_slider.blockSignals(False)
        if not self._render_preview_scrubbing:
            self._set_render_preview_time_labels(
                safe_position, self._render_preview_duration_ms
            )

    def on_render_preview_slider_pressed(self) -> None:
        self._render_preview_scrubbing = True

    def on_render_preview_slider_moved(self, value: int) -> None:
        self._set_render_preview_time_labels(value, self._render_preview_duration_ms)

    def on_render_preview_slider_released(self) -> None:
        self._render_preview_scrubbing = False
        if (
            self.render_preview_player is not None
            and hasattr(self, "render_preview_seek_slider")
        ):
            target_position = int(self.render_preview_seek_slider.value())
            self.render_preview_player.setPosition(target_position)
            self._set_render_preview_time_labels(
                target_position, self._render_preview_duration_ms
            )

    def export_rendered_video_file(self) -> None:
        preview_path = self._current_render_preview_path()
        if not preview_path:
            QMessageBox.information(
                self,
                "Chưa có video render",
                "Hãy render video trước khi xuất file.",
            )
            return
        source_path = Path(preview_path)
        if not source_path.exists():
            QMessageBox.information(
                self,
                "Không tìm thấy video",
                f"Không thấy file video render tại:\n{source_path}",
            )
            return
        default_dir = Path(
            self.output_dir_edit.text().strip() or str(DEFAULT_OUTPUT_DIR)
        )
        default_dir.mkdir(parents=True, exist_ok=True)
        default_name = source_path.name or "dubstudio_render.mp4"
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất file video",
            str(default_dir / default_name),
            "Video (*.mp4 *.mov *.mkv *.avi *.m4v *.webm)",
        )
        if not target_path:
            return
        destination = Path(target_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        self.last_exported_output_path = str(destination)
        self.sync_output_directory_inputs(str(destination.parent))
        self.settings["outputDirectory"] = str(destination.parent)
        self.refresh_all()
        QMessageBox.information(
            self,
            "Xuất file hoàn tất",
            f"Đã xuất video ra file:\n{destination}",
        )

    def open_output(self) -> None:
        target = self.last_output_path or self.output_dir_edit.text().strip()
        if not target:
            QMessageBox.information(self, "Chưa có output", "Chưa có output để mở.")
            return
        path = Path(target)
        open_target = path.parent if path.is_file() else path
        if not open_target.exists() and path.parent.exists():
            open_target = path.parent
        if not open_target.exists():
            QMessageBox.information(
                self, "Không tìm thấy output", f"Đường dẫn chưa tồn tại:\n{open_target}"
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(open_target))):
            QMessageBox.warning(
                self, "Không thể mở", f"Không thể mở đường dẫn:\n{open_target}"
            )

    def open_configured_output_directory(self) -> None:
        target = self.output_dir_edit.text().strip()
        if not target:
            QMessageBox.information(
                self, "Thiếu thư mục output", "Bạn chưa đặt thư mục output."
            )
            return
        output_dir = Path(target)
        if not output_dir.exists():
            QMessageBox.information(
                self, "Chưa có thư mục output", f"Thư mục chưa tồn tại:\n{output_dir}"
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_dir))):
            QMessageBox.warning(
                self, "Không thể mở", f"Không thể mở thư mục:\n{output_dir}"
            )

    def _current_subtitle_timeline(self) -> list[dict[str, Any]]:
        analysis = self.effective_analysis or self.analysis or {}
        return copy.deepcopy(analysis.get("subtitleTimeline") or [])

    def _set_subtitle_timeline(
        self, timeline: list[dict[str, Any]], *, source: str
    ) -> None:
        if not self.job_id or not self.analysis:
            return
        try:
            self.effective_analysis = self.controller.update_analysis_config(
                self.job_id,
                {
                    "subtitleTimeline": copy.deepcopy(timeline),
                    "subtitleSrt": compose_srt_from_timeline(timeline),
                    "subtitleTimelineSource": source,
                },
            )
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "Cập nhật subtitle thất bại", str(exc))

    def import_subtitle_srt(self) -> None:
        if not self.job_id or not self.analysis:
            QMessageBox.information(
                self,
                "Chưa có phân tích",
                "Hãy phân tích video trước khi import subtitle.",
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import subtitle SRT", "", "Subtitle (*.srt)"
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            content = Path(path).read_text(encoding="utf-8")
        timeline = parse_srt_to_timeline(
            content,
            fallback_segments=(self.effective_analysis or self.analysis or {}).get(
                "segments"
            )
            or [],
        )
        if not timeline:
            QMessageBox.warning(
                self,
                "Import thất bại",
                "File SRT không có block subtitle hợp lệ.",
            )
            return
        self._set_subtitle_timeline(timeline, source="imported")

    def export_subtitle_srt(self) -> None:
        timeline = self._current_subtitle_timeline()
        if not timeline:
            QMessageBox.information(
                self,
                "Chưa có subtitle",
                "Không có subtitle nào để export.",
            )
            return
        default_name = "subtitle_current.srt"
        input_path = (
            Path(self.input_path_edit.text().strip())
            if self.input_path_edit.text().strip()
            else None
        )
        if input_path is not None:
            default_name = f"{input_path.stem}.srt"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export subtitle SRT",
            str(Path(self.output_dir_edit.text().strip() or str(ROOT)) / default_name),
            "Subtitle (*.srt)",
        )
        if not path:
            return
        Path(path).write_text(
            compose_srt_from_timeline(timeline), encoding="utf-8-sig"
        )

    def rebuild_subtitle_table(self) -> None:
        if not hasattr(self, "subtitle_table"):
            return
        timeline = self._current_subtitle_timeline()
        self._subtitle_table_syncing = True
        self.subtitle_table.blockSignals(True)
        self.subtitle_table.setRowCount(len(timeline))
        for row, item in enumerate(timeline):
            start_ms = int(item.get("startMs") or 0)
            end_ms = int(item.get("endMs") or 0)
            start_text = f"{start_ms / 1000:.2f}s"
            end_text = f"{end_ms / 1000:.2f}s"
            for column, value, editable in [
                (0, start_text, False),
                (1, end_text, False),
                (2, repair_mojibake_text(item.get("text") or ""), True),
            ]:
                cell = QTableWidgetItem(value)
                if not editable:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.subtitle_table.setItem(row, column, cell)
        self.subtitle_table.blockSignals(False)
        self._subtitle_table_syncing = False

    def on_subtitle_table_item_changed(self, item: QTableWidgetItem) -> None:
        if getattr(self, "_subtitle_table_syncing", False):
            return
        if item.column() != 2:
            return
        timeline = self._current_subtitle_timeline()
        if item.row() >= len(timeline):
            return
        timeline[item.row()]["text"] = normalize_preview_text(item.text())
        self._set_subtitle_timeline(timeline, source="edited")

    def on_analysis_ready(self, job_id: str, analysis: dict[str, Any]) -> None:
        self.job_id = job_id
        self.analysis = copy.deepcopy(self.controller.jobs[job_id]["analysis"])
        self.effective_analysis = analysis
        self.hydrate_settings_from_analysis(analysis)
        self.rebuild_voice_mapping_ui()
        self.refresh_all()

    def on_render_ready(self, job_id: str, payload: dict[str, Any]) -> None:
        self.last_output_path = (
            payload.get("previewVideoPath")
            or payload.get("outputVideoPath")
            or payload.get("draftPath")
            or ""
        )
        self.last_exported_output_path = ""
        self.stop_render_preview(clear_source=True)
        self.job_status = self.controller.get_job_status(job_id)
        self.refresh_all()
        QMessageBox.information(
            self,
            "Render hoàn tất",
            "Đã render xong. Bạn có thể bấm Xem video để preview ngay trong app hoặc bấm Xuất file khi muốn lưu ra ngoài.",
        )

    def on_status_changed(self, job_id: str, payload: dict[str, Any]) -> None:
        if self.job_id == job_id:
            self.job_status = payload
            self.refresh_status_only()

    def on_job_failed(self, job_id: str, message: str) -> None:
        if self.job_id == job_id:
            self.stop_render_preview()
            QMessageBox.critical(self, "Lỗi pipeline", repair_mojibake_text(message))

    def _handle_render_preview_error(self, _error, error_string: str) -> None:
        message = repair_mojibake_text(
            error_string or "Không thể phát video preview trong giao diện."
        )
        if hasattr(self, "render_preview_status_label"):
            self.render_preview_status_label.setText("Phát video thất bại")
        QMessageBox.warning(self, "Không thể xem preview", message)

    def on_font_size_changed(self, value: int) -> None:
        self.settings["subtitlePreset"]["fontSize"] = int(value)
        self.font_size_value.setText(f"{value}px")
        self.refresh_preview()

    def on_blur_changed(self, value: int) -> None:
        self.settings["subtitlePreset"]["cleanupBlurStrength"] = int(value)
        self.blur_value.setText(f"{value}px")
        self.refresh_preview()

    def on_bottom_offset_changed(self, value: int) -> None:
        self.settings["subtitlePreset"]["bottomOffset"] = int(value)
        self.bottom_offset_value.setText(f"{value}px")
        self.refresh_preview()

    def on_watermark_size_changed(self, value: int) -> None:
        safe_value = max(5, min(50, int(value)))
        self.settings.setdefault("watermark", {})["scale"] = safe_value / 100.0
        if hasattr(self, "watermark_scale_value"):
            self.watermark_scale_value.setText(f"{safe_value}%")
        self.refresh_preview()

    def on_watermark_scale_dragged(self, scale: float) -> None:
        slider_value = max(5, min(50, int(round(float(scale) * 100))))
        self.settings.setdefault("watermark", {})["scale"] = slider_value / 100.0
        if hasattr(self, "watermark_scale_slider"):
            self.watermark_scale_slider.blockSignals(True)
            self.watermark_scale_slider.setValue(slider_value)
            self.watermark_scale_slider.blockSignals(False)
        if hasattr(self, "watermark_scale_value"):
            self.watermark_scale_value.setText(f"{slider_value}%")
        self.refresh_preview()

    def on_preview_subtitle_dragged(
        self, position_preset: str, bottom_offset: int
    ) -> None:
        self.settings["subtitlePreset"]["positionPreset"] = position_preset
        self.settings["subtitlePreset"]["bottomOffset"] = int(bottom_offset)
        self.sync_widgets_from_settings()
        self.refresh_preview()

    def apply_caption_position(self, position_preset: str) -> None:
        default_offset = {"top": 24, "middle": 0, "bottom": 54}
        self.settings["subtitlePreset"]["positionPreset"] = position_preset
        self.settings["subtitlePreset"]["bottomOffset"] = default_offset.get(
            position_preset, 54
        )
        self.sync_widgets_from_settings()
        self.refresh_preview()

    def on_cleanup_region_dragged(self, region: dict[str, int]) -> None:
        self.settings["subtitleRegion"] = {
            "x": int(region.get("x", 0)),
            "y": int(region.get("y", 0)),
            "w": int(region.get("w", 0)),
            "h": int(region.get("h", 0)),
        }
        self.sync_widgets_from_settings()
        self.refresh_preview()

    def on_cleanup_region_changed(self, region: dict[str, int]) -> None:
        self.on_cleanup_region_dragged(region)

    def on_font_changed(self) -> None:
        option = find_font_option(self.font_combo.currentData())
        self.settings["subtitlePreset"].update(
            {
                "fontFamily": option["value"],
                "fontFamilyLabel": option["label"],
                "fontFamilyName": option["fontFamilyName"],
                "cssFontFamily": option["cssFontFamily"],
                "assFontName": option["assFontName"],
                "draftFontKey": option["draftFontKey"],
            }
        )
        self.refresh_preview()

    def on_speaker_detection_changed(self) -> None:
        mode = self.speaker_detection_combo.currentData()
        self.settings["speakerDetectionMode"] = mode
        if mode == "narrator":
            self.speaker_count_spin.setValue(1)
        elif mode == "auto":
            self.speaker_count_spin.setValue(
                max(1, len((self.effective_analysis or {}).get("speakers") or []))
            )
        else:
            detected_raw = int(
                (self.analysis or {}).get("detectedSpeakerCountRaw")
                or self.speaker_count_spin.value()
                or 2
            )
            self.speaker_count_spin.setValue(max(2, detected_raw))
        self.on_basic_settings_changed()

    def on_basic_settings_changed(self) -> None:
        self.read_settings_from_widgets()
        self._push_analysis_overrides()
        self.refresh_all()

    def pick_color(self, key: str) -> None:
        current = QColor(self.settings["subtitlePreset"].get(key, "#ffffff"))
        color = QColorDialog.getColor(current, self, "Chọn màu")
        if not color.isValid():
            return
        self.settings["subtitlePreset"][key] = color.name()
        self.refresh_all()

    def _sync_voice_mapping_from_widgets(self) -> None:
        voice_mapping = copy.deepcopy(self.settings.get("voiceMapping") or {})
        for speaker_id, combo in getattr(self, "voice_combo_map", {}).items():
            if combo is None:
                continue
            voice = self._resolve_voice_combo_value(combo)
            if not str(voice or "").strip():
                continue
            voice_mapping[str(speaker_id)] = str(voice).strip()
            status_label = self.voice_status_label_map.get(str(speaker_id))
            if status_label is not None:
                status_label.setText(
                    f"Đã chọn: {self._format_voice_label(voice_mapping[str(speaker_id)])}"
                )
        self.settings["voiceMapping"] = voice_mapping

    def read_settings_from_widgets(self) -> None:
        self.settings["sourceLanguage"] = str(self.source_language_combo.currentData())
        self.settings["targetLanguage"] = str(self.target_language_combo.currentData())
        self.settings["speakerDetectionMode"] = str(
            self.speaker_detection_combo.currentData()
        )
        self.settings["speakerCount"] = int(self.speaker_count_spin.value())
        self.settings["timingMode"] = str(self.timing_mode_combo.currentData())
        self.settings["videoCodecMode"] = str(
            self.video_codec_combo.currentData() or "gpu_preferred"
        )
        self.settings["uiThemePreset"] = str(
            self.ui_theme_combo.currentData() or "cinema"
        )
        self.settings["sourceSubtitleCleanupMode"] = str(
            self.cleanup_combo.currentData()
        )
        self.settings["subtitlePreset"]["enabled"] = (
            self.subtitle_enabled_combo.currentData() == "on"
        )
        self.settings["subtitlePreset"]["positionPreset"] = str(
            self.subtitle_position_combo.currentData()
        )
        self.settings["subtitlePreset"]["strokeWidth"] = int(
            self.stroke_width_spin.value()
        )
        self.settings["subtitlePreset"]["maxWordsPerChunk"] = int(
            self.max_words_spin.value()
        )
        self.settings["introHook"]["enabled"] = self.intro_enabled_check.isChecked()
        self.settings["introHook"]["clipDurationMs"] = int(
            round(self.intro_duration_spin.value() * 1000)
        )
        intro_voice_value = self._resolve_voice_combo_value(self.intro_voice_combo) or "edge:male"
        if str(intro_voice_value) == "vieneu:clone":
            intro_voice_value = "edge:male"
        intro_preset = resolve_intro_voice_preset(intro_voice_value)
        self.settings["introHook"]["voicePresetKey"] = intro_preset["key"]
        self.settings["introHook"]["voice"] = str(intro_preset["voice"])
        self.settings["introHook"]["voiceRateDeltaPercent"] = int(
            intro_preset["rateDeltaPercent"]
        )
        self.settings["introHook"]["useBackgroundAudio"] = (
            self.intro_background_check.isChecked()
        )
        self.settings["introHook"]["backgroundVolume"] = float(
            self.intro_background_volume_spin.value()
        )
        self.settings["keepOriginalAudio"] = self.keep_original_audio_check.isChecked()
        self.settings["outputTargets"]["mp4"] = self.output_mp4_check.isChecked()
        self.settings["outputTargets"]["draft"] = self.output_draft_check.isChecked()
        self.settings["outputDirectory"] = self.output_dir_edit.text().strip()
        self.settings["draftRoot"] = self.draft_dir_edit.text().strip()
        self.settings["subtitleRegion"] = {
            "x": int(self.region_x_spin.value()),
            "y": int(self.region_y_spin.value()),
            "w": int(self.region_w_spin.value()),
            "h": int(self.region_h_spin.value()),
        }
        self.settings.setdefault("watermark", {})["enabled"] = self.watermark_enabled_check.isChecked()
        self.settings["watermark"]["path"] = self.watermark_path_edit.text()
        self.settings["watermark"]["position"] = str(self.watermark_position_combo.currentData())
        self.settings["watermark"]["scale"] = float(self.watermark_scale_slider.value()) / 100.0
        self._sync_voice_mapping_from_widgets()
        self.on_font_changed()

    def current_analysis_overrides(self) -> dict[str, Any]:
        return {
            "sourceLanguage": ""
            if self.settings["sourceLanguage"] == "auto"
            else self.settings["sourceLanguage"],
            "targetLanguage": self.settings["targetLanguage"],
            "speakerDetectionMode": self.settings["speakerDetectionMode"],
            "speakerCount": int(self.settings["speakerCount"]),
            "voiceMapping": copy.deepcopy(self.settings["voiceMapping"]),
            "subtitleRegion": copy.deepcopy(self.settings["subtitleRegion"]),
        }

    def current_render_options(self) -> dict[str, Any]:
        effective_source_language = (
            (self.effective_analysis or self.analysis or {}).get("sourceLanguage")
            if self.settings["sourceLanguage"] == "auto"
            else self.settings["sourceLanguage"]
        )
        return {
            "sourceLanguage": effective_source_language or "",
            "targetLanguage": self.settings["targetLanguage"],
            "speakerDetectionMode": self.settings["speakerDetectionMode"],
            "voiceMapping": copy.deepcopy(self.settings["voiceMapping"]),
            "introHook": copy.deepcopy(self.settings["introHook"]),
            "subtitlePreset": copy.deepcopy(self.settings["subtitlePreset"]),
            "subtitleRegion": copy.deepcopy(self.settings["subtitleRegion"]),
            "sourceSubtitleCleanupMode": self.settings["sourceSubtitleCleanupMode"],
            "outputTargets": copy.deepcopy(self.settings["outputTargets"]),
            "timingMode": self.settings["timingMode"],
            "videoCodecMode": self.settings.get("videoCodecMode", "gpu_preferred"),
            "keepOriginalAudio": self.settings["keepOriginalAudio"],
            "draftRoot": self.settings["draftRoot"],
            "outputDirectory": self.settings["outputDirectory"],
            "watermarkEnabled": self.settings.get("watermark", {}).get("enabled", False),
            "watermarkPath": self.settings.get("watermark", {}).get("path", ""),
            "watermarkPosition": self.settings.get("watermark", {}).get("position", "top-right"),
            "watermarkScale": self.settings.get("watermark", {}).get("scale", 0.15),
        }

    def _push_analysis_overrides(self, *, rebuild_voice_ui: bool = True) -> None:
        if not self.job_id or not self.analysis:
            return
        try:
            self.effective_analysis = self.controller.update_analysis_config(
                self.job_id, self.current_analysis_overrides()
            )
            if rebuild_voice_ui:
                self.rebuild_voice_mapping_ui()
        except Exception:
            self.effective_analysis = copy.deepcopy(self.analysis)

    def hydrate_settings_from_analysis(self, analysis: dict[str, Any]) -> None:
        merged = default_settings()
        render_defaults = analysis.get("renderDefaults") or {}
        merged["sourceLanguage"] = (
            self.settings.get("sourceLanguage") or merged["sourceLanguage"]
        )
        merged["targetLanguage"] = analysis.get(
            "targetLanguage", self.settings.get("targetLanguage") or "vi"
        )
        merged["speakerDetectionMode"] = render_defaults.get(
            "speakerDetectionMode", merged["speakerDetectionMode"]
        )
        merged["speakerCount"] = len(analysis.get("speakers") or []) or 1
        merged["voiceMapping"] = {
            speaker.get("speakerId"): speaker.get("voicePreset")
            for speaker in analysis.get("speakers", [])
        }
        merged["introHook"].update(render_defaults.get("introHook") or {})
        merged["subtitlePreset"].update(render_defaults.get("subtitlePreset") or {})
        merged["subtitleRegion"].update(analysis.get("subtitleRegion") or {})
        merged["sourceSubtitleCleanupMode"] = render_defaults.get(
            "sourceSubtitleCleanupMode", merged["sourceSubtitleCleanupMode"]
        )
        merged["outputTargets"].update(render_defaults.get("outputTargets") or {})
        merged["timingMode"] = render_defaults.get("timingMode", merged["timingMode"])
        merged["videoCodecMode"] = self.settings.get(
            "videoCodecMode",
            render_defaults.get("videoCodecMode", merged["videoCodecMode"]),
        )
        merged["uiThemePreset"] = self.settings.get(
            "uiThemePreset", merged["uiThemePreset"]
        )
        merged["keepOriginalAudio"] = bool(
            render_defaults.get("keepOriginalAudio", merged["keepOriginalAudio"])
        )
        merged["draftRoot"] = render_defaults.get("draftRoot") or merged["draftRoot"]
        merged["outputDirectory"] = (
            render_defaults.get("outputDirectory") or merged["outputDirectory"]
        )
        intro_preset_key = str(
            (merged.get("introHook") or {}).get("voicePresetKey") or ""
        )
        if not intro_preset_key:
            intro_voice = str((merged.get("introHook") or {}).get("voice") or "")
            if intro_voice.endswith("Neural") and intro_voice not in {
                "vi-VN-HoaiMyNeural",
                "vi-VN-NamMinhNeural",
            }:
                intro_preset_key = intro_voice
            else:
                intro_preset_key = (
                    "female_story" if intro_voice == "vi-VN-HoaiMyNeural" else "male_story"
                )
        intro_preset = resolve_intro_voice_preset(intro_preset_key)
        merged["introHook"]["voicePresetKey"] = intro_preset["key"]
        merged["introHook"]["voice"] = intro_preset["voice"]
        merged["introHook"]["voiceRateDeltaPercent"] = int(
            (merged["introHook"] or {}).get(
                "voiceRateDeltaPercent", intro_preset["rateDeltaPercent"]
            )
        )
        merged.setdefault("watermark", {})
        merged["watermark"]["enabled"] = render_defaults.get("watermarkEnabled", merged["watermark"].get("enabled", False))
        merged["watermark"]["path"] = render_defaults.get("watermarkPath", merged["watermark"].get("path", ""))
        merged["watermark"]["position"] = render_defaults.get("watermarkPosition", merged["watermark"].get("position", "top-right"))
        merged["watermark"]["scale"] = render_defaults.get("watermarkScale", merged["watermark"].get("scale", 0.15))
        self.settings = merged
        self.sync_widgets_from_settings()

    def sync_widgets_from_settings(self) -> None:
        widgets = [
            self.source_language_combo,
            self.target_language_combo,
            self.speaker_detection_combo,
            self.speaker_count_spin,
            self.timing_mode_combo,
            self.video_codec_combo,
            self.ui_theme_combo,
            self.cleanup_combo,
            self.subtitle_enabled_combo,
            self.subtitle_position_combo,
            self.font_combo,
            self.stroke_width_spin,
            self.max_words_spin,
            self.intro_enabled_check,
            self.intro_duration_spin,
            self.intro_voice_combo,
            self.intro_background_check,
            self.intro_background_volume_spin,
            self.keep_original_audio_check,
            self.output_mp4_check,
            self.output_draft_check,
            self.output_dir_edit,
            self.draft_dir_edit,
            self.region_x_spin,
            self.region_y_spin,
            self.region_w_spin,
            self.region_h_spin,
            self.font_size_slider,
            self.blur_slider,
            self.bottom_offset_slider,
            self.watermark_enabled_check,
            self.watermark_path_edit,
            self.watermark_position_combo,
            self.watermark_scale_slider,
        ]
        for widget in widgets:
            widget.blockSignals(True)
        self._set_combo_value(
            self.source_language_combo, self.settings["sourceLanguage"]
        )
        self._set_combo_value(
            self.target_language_combo, self.settings["targetLanguage"]
        )
        self._set_combo_value(
            self.speaker_detection_combo, self.settings["speakerDetectionMode"]
        )
        self.speaker_count_spin.setValue(int(self.settings["speakerCount"]))
        self._set_combo_value(self.timing_mode_combo, self.settings["timingMode"])
        self._set_combo_value(
            self.video_codec_combo, self.settings.get("videoCodecMode", "gpu_preferred")
        )
        self._set_combo_value(
            self.ui_theme_combo, self.settings.get("uiThemePreset", "cinema")
        )
        self._set_combo_value(
            self.cleanup_combo, self.settings["sourceSubtitleCleanupMode"]
        )
        self._set_combo_value(
            self.subtitle_enabled_combo,
            "on" if self.settings["subtitlePreset"]["enabled"] else "off",
        )
        self._set_combo_value(
            self.subtitle_position_combo,
            self.settings["subtitlePreset"]["positionPreset"],
        )
        self._set_combo_value(
            self.font_combo, self.settings["subtitlePreset"]["fontFamily"]
        )
        self.stroke_width_spin.setValue(
            int(self.settings["subtitlePreset"]["strokeWidth"])
        )
        self.max_words_spin.setValue(
            int(self.settings["subtitlePreset"]["maxWordsPerChunk"])
        )
        self.intro_enabled_check.setChecked(bool(self.settings["introHook"]["enabled"]))
        self.intro_duration_spin.setValue(
            float(self.settings["introHook"]["clipDurationMs"]) / 1000.0
        )
        intro_voice_key = str(
            self.settings["introHook"].get("voicePresetKey")
            or self.settings["introHook"].get("voice")
            or VOICE_OPTIONS[0][0]
        )
        if intro_voice_key == "vieneu:clone":
            intro_voice_key = "edge:male"
        if self.intro_voice_combo.findData(intro_voice_key) >= 0:
            self._set_combo_value(self.intro_voice_combo, intro_voice_key)
        else:
            self.intro_voice_combo.setEditText(intro_voice_key)
        self.intro_background_check.setChecked(
            bool(self.settings["introHook"]["useBackgroundAudio"])
        )
        self.intro_background_volume_spin.setValue(
            float(self.settings["introHook"]["backgroundVolume"])
        )
        self.keep_original_audio_check.setChecked(
            bool(self.settings["keepOriginalAudio"])
        )
        self.output_mp4_check.setChecked(bool(self.settings["outputTargets"]["mp4"]))
        self.output_draft_check.setChecked(
            bool(self.settings["outputTargets"]["draft"])
        )
        self.output_dir_edit.setText(self.settings["outputDirectory"])
        self.output_folder_quick_edit.setText(self.settings["outputDirectory"])
        self.draft_dir_edit.setText(self.settings["draftRoot"])
        self.region_x_spin.setValue(int(self.settings["subtitleRegion"]["x"]))
        self.region_y_spin.setValue(int(self.settings["subtitleRegion"]["y"]))
        self.region_w_spin.setValue(int(self.settings["subtitleRegion"]["w"]))
        self.region_h_spin.setValue(int(self.settings["subtitleRegion"]["h"]))
        self.font_size_slider.setValue(int(self.settings["subtitlePreset"]["fontSize"]))
        self.blur_slider.setValue(
            int(self.settings["subtitlePreset"]["cleanupBlurStrength"])
        )
        self.bottom_offset_slider.setValue(
            int(self.settings["subtitlePreset"]["bottomOffset"])
        )
        watermark = self.settings.setdefault("watermark", {})
        self.watermark_enabled_check.setChecked(bool(watermark.get("enabled", False)))
        self.watermark_path_edit.setText(watermark.get("path", ""))
        self._set_combo_value(self.watermark_position_combo, watermark.get("position", "top-right"))
        self.watermark_scale_slider.setValue(int(watermark.get("scale", 0.15) * 100))
        for widget in widgets:
            widget.blockSignals(False)
        self.font_size_value.setText(f"{self.settings['subtitlePreset']['fontSize']}px")
        self.blur_value.setText(
            f"{self.settings['subtitlePreset']['cleanupBlurStrength']}px"
        )
        self.bottom_offset_value.setText(
            f"{self.settings['subtitlePreset']['bottomOffset']}px"
        )
        if hasattr(self, "watermark_scale_value"):
            self.watermark_scale_value.setText(
                f"{int(round(float(watermark.get('scale', 0.15)) * 100))}%"
            )



