from __future__ import annotations

import json
import time

from PyQt6.QtCore import QProcess, QProcessEnvironment
from PyQt6.QtWidgets import QMessageBox

from gui.config import PIPELINE_PATH, PIPELINE_PYTHON, ROOT, UI_THEME_OPTIONS
from gui.utils import (
    decode_process_bytes,
    find_font_option,
    normalize_preview_text,
    repair_mojibake_text,
)


class WindowRefreshMixin:
    def _maybe_repair_widget_texts(self, *, force: bool = False) -> None:
        now = time.monotonic()
        last_run = float(getattr(self, "_last_widget_repair_at", 0.0) or 0.0)
        if not force and (now - last_run) < 2.5:
            return
        self._last_widget_repair_at = now
        self._repair_widget_texts()

    @staticmethod
    def _subtitle_timeline_signature(timeline: list[dict]) -> tuple:
        return tuple(
            (
                int(item.get("startMs", 0) or 0),
                int(item.get("endMs", 0) or 0),
                str(item.get("text") or ""),
                str(item.get("voice") or item.get("voicePreset") or item.get("voiceOverride") or ""),
            )
            for item in (timeline or [])
        )

    def _sync_settings_lock_state(self, running: bool) -> None:
        widget_names = [
            "source_language_combo",
            "target_language_combo",
            "speaker_detection_combo",
            "speaker_count_spin",
            "timing_mode_combo",
            "video_codec_combo",
            "ui_theme_combo",
            "cleanup_combo",
            "subtitle_enabled_combo",
            "subtitle_position_combo",
            "font_group_combo",
            "font_combo",
            "font_size_spin",
            "font_color_btn",
            "stroke_color_btn",
            "subtitle_box_check",
            "box_style_combo",
            "box_layout_combo",
            "box_radius_spin",
            "box_border_width_spin",
            "box_fill_opacity_spin",
            "box_fill_color_btn",
            "box_border_color_btn",
            "stroke_width_spin",
            "max_words_spin",
            "intro_enabled_check",
            "intro_duration_spin",
            "intro_voice_combo",
            "default_voice_combo",
            "default_voice_test_btn",
            "intro_background_check",
            "intro_background_volume_spin",
            "keep_original_audio_check",
            "background_music_enabled_check",
            "background_music_path_edit",
            "background_music_choose_btn",
            "background_music_volume_spin",
            "output_mp4_check",
            "output_draft_check",
            "output_dir_edit",
            "draft_dir_edit",
            "output_folder_quick_edit",
            "region_x_spin",
            "region_y_spin",
            "region_w_spin",
            "region_h_spin",
            "font_size_slider",
            "blur_slider",
            "bottom_offset_slider",
            "preview_canvas",
            "subtitle_table",
            "batch_table",
            "batch_output_dir_edit",
        ]
        for name in widget_names:
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setEnabled(not running)
        for combo in getattr(self, "voice_combo_map", {}).values():
            if combo is not None:
                combo.setEnabled(not running)
        for button in getattr(self, "voice_test_button_map", {}).values():
            if button is not None:
                button.setEnabled(not running)

    def compute_preview_text(self) -> str:
        best_candidate = ""
        for item in (self.effective_analysis or self.analysis or {}).get(
            "subtitleTimeline", []
        )[:18]:
            candidate = normalize_preview_text(item.get("text"))
            if 18 <= len(candidate) <= 120 and len(candidate) > len(best_candidate):
                best_candidate = candidate
        for segment in (self.effective_analysis or self.analysis or {}).get(
            "segments", []
        )[:18]:
            candidate = normalize_preview_text(
                segment.get("translatedText") or segment.get("sourceText")
            )
            if 18 <= len(candidate) <= 120 and len(candidate) > len(best_candidate):
                best_candidate = candidate
        if best_candidate:
            return repair_mojibake_text(best_candidate)
        return "Đây là preview subtitle để xem màu chữ, cỡ chữ, cách xuống dòng và kiểu box trên video."

    def refresh_preview(self) -> None:
        analysis = self.preview_media_analysis or self.effective_analysis or self.analysis
        text = self.compute_preview_text()
        preview_canvas = getattr(self, "preview_canvas", None)
        if preview_canvas is not None:
            preview_canvas.update_state(analysis, self.settings, text)
        video_preview = getattr(self, "_video_preview_widget", None)
        if video_preview is not None:
            video_preview.update_state(
                {
                    "subtitlePreset": self.settings.get("subtitlePreset") or {},
                    "subtitleTimeline": (analysis or {}).get("subtitleTimeline") or [],
                    "preview_text": text,
                },
                self.settings.get("stickerOptions") or {},
            )

    def refresh_style_preview_card(self) -> None:
        subtitle_preset = self.settings.get("subtitlePreset") or {}
        text = self.compute_preview_text()
        font_option = find_font_option(str(subtitle_preset.get("fontFamily") or "arial-bold"))
        font_family = str(
            subtitle_preset.get("fontFamilyName") or font_option["fontFamilyName"]
        )
        font_size = max(13, min(int(subtitle_preset.get("fontSize", 14)), 28))
        font_color = str(subtitle_preset.get("fontColor") or "#ffffff")
        box_enabled = bool(subtitle_preset.get("boxEnabled", False))
        background = (
            str(subtitle_preset.get("boxFillColor") or "#111827")
            if box_enabled
            else "rgba(255,255,255,0.06)"
        )
        border_color = (
            str(subtitle_preset.get("boxBorderColor") or "#334155")
            if box_enabled
            else "rgba(255,255,255,0.12)"
        )
        border_width = int(subtitle_preset.get("boxBorderWidth", 1)) if box_enabled else 1
        radius = max(6, min(int(subtitle_preset.get("boxRadius", 12)), 28))
        label_style = (
            f'font-family: "{font_family}"; font-size: {font_size}px; '
            f"font-weight: 800; color: {font_color}; background: {background}; "
            f"border: {border_width}px solid {border_color}; "
            f"border-radius: {radius}px; padding: 10px 12px;"
        )
        compact_text = self._compact_preview_text(text, 80)
        for attr_name in ("preview_style_label", "_preview_style_label_full"):
            label = getattr(self, attr_name, None)
            if label is not None:
                label.setText(compact_text)
                label.setStyleSheet(label_style)
        sticker_options = self.settings.get("stickerOptions") or {}
        sticker_label = str(sticker_options.get("stickerName") or "Không sticker")
        if not str(sticker_options.get("stickerId") or "").strip():
            sticker_label = "Không sticker"
        meta_text = (
            f"{font_option['label']} | "
            f"Box: {'bật' if box_enabled else 'tắt'} | "
            f"Sticker: {sticker_label}"
        )
        for attr_name in ("preview_style_meta", "_preview_style_meta_full"):
            meta_label = getattr(self, attr_name, None)
            if meta_label is not None:
                meta_label.setText(repair_mojibake_text(meta_text))

    @staticmethod
    def _compact_preview_text(text: str, limit: int) -> str:
        clean = repair_mojibake_text(normalize_preview_text(text))
        if len(clean) <= limit:
            return clean
        return clean[: max(0, limit - 3)].rstrip() + "..."

    def refresh_status_only(self) -> None:
        status = self.job_status or {}
        self._set_chip_display_text(
            self.phase_label,
            f"Trạng thái: {str(status.get('phase') or 'idle')}",
            max_width=220,
        )
        self._set_chip_display_text(
            self.step_label,
            f"Bước: {str(status.get('step') or 'chờ')}",
            max_width=280,
        )
        progress = int(round(float(status.get("progress") or 0) * 100))
        self.progress_bar.setValue(progress)
        visible_logs = (status.get("logs") or [])[-8:]
        log_text = "\\n".join(
            repair_mojibake_text(
                f"[{item.get('level', 'info')}] {item.get('message', '')}"
            )
            for item in visible_logs
        )
        if self.log_box.toPlainText() != log_text:
            self.log_box.setPlainText(log_text)
        self._maybe_repair_widget_texts()
        self._sync_action_buttons()

    def _sync_action_buttons(self) -> None:
        if not hasattr(self, "analyze_btn"):
            return
        running = self.controller.has_running_job()
        has_render_preview = bool(getattr(self, "last_output_path", "").strip())
        preview_available = bool(
            getattr(self, "render_preview_player", None) is not None
            and getattr(self, "render_video_widget", None) is not None
        )
        self._sync_settings_lock_state(running)
        self.analyze_btn.setEnabled(not running)
        self.render_btn.setEnabled(not running and bool(self.analysis))
        self.cancel_btn.setEnabled(running)
        if hasattr(self, "preview_video_btn"):
            self.preview_video_btn.setEnabled(
                not running and has_render_preview and preview_available
            )
        if hasattr(self, "export_file_btn"):
            self.export_file_btn.setEnabled(not running and has_render_preview)
        if hasattr(self, "pause_preview_btn"):
            self.pause_preview_btn.setEnabled(
                not running and has_render_preview and preview_available
            )
        if hasattr(self, "restart_preview_btn"):
            self.restart_preview_btn.setEnabled(
                not running and has_render_preview and preview_available
            )
        if hasattr(self, "seek_back_preview_btn"):
            self.seek_back_preview_btn.setEnabled(
                not running and has_render_preview and preview_available
            )
        if hasattr(self, "seek_forward_preview_btn"):
            self.seek_forward_preview_btn.setEnabled(
                not running and has_render_preview and preview_available
            )
        if hasattr(self, "stop_preview_btn"):
            self.stop_preview_btn.setEnabled(
                not running and has_render_preview and preview_available
            )
        if hasattr(self, "fullscreen_preview_btn"):
            self.fullscreen_preview_btn.setEnabled(
                not running and has_render_preview and preview_available
            )
        if hasattr(self, "render_preview_seek_slider"):
            self.render_preview_seek_slider.setEnabled(
                not running and has_render_preview and preview_available
            )
        if hasattr(self, "mute_preview_btn"):
            self.mute_preview_btn.setEnabled(
                not running and has_render_preview and preview_available
            )
        if hasattr(self, "render_preview_volume_slider"):
            self.render_preview_volume_slider.setEnabled(
                not running and has_render_preview and preview_available
            )
        if hasattr(self, "render_preview_speed_combo"):
            self.render_preview_speed_combo.setEnabled(
                not running and has_render_preview and preview_available
            )
        if hasattr(self, "import_srt_btn"):
            self.import_srt_btn.setEnabled(not running and bool(self.analysis))
        if hasattr(self, "export_srt_btn"):
            self.export_srt_btn.setEnabled(
                not running
                and bool((self.effective_analysis or self.analysis or {}).get("subtitleTimeline"))
            )

    def refresh_all(self) -> None:
        analysis = self.effective_analysis or self.analysis or {}
        self.refresh_preview()
        if hasattr(self, "refresh_style_preview_card"):
            self.refresh_style_preview_card()
        self.refresh_status_only()
        voice_layout = analysis.get("voiceLayout")
        if hasattr(self, "summary_labels"):
            self.summary_labels["sourceLanguage"].setText(
                str(analysis.get("sourceLanguage") or "--")
            )
            self.summary_labels["speakers"].setText(
                str(len(analysis.get("speakers") or []))
            )
            self.summary_labels["voiceLayout"].setText(
                repair_mojibake_text(
                    "Giọng chung"
                    if voice_layout == "single_voice"
                    else "Nhiều nhân vật"
                    if voice_layout == "multi_character"
                    else "--"
                )
            )
            self.summary_labels["cleanupMode"].setText(
                str((analysis.get("subtitleRegion") or {}).get("cleanupMode") or "--")
            )
        warning_box = getattr(self, "warning_box", None)
        if warning_box is not None:
            warning_text = "\\n".join(
                repair_mojibake_text(item)
                for item in (analysis.get("warnings") or [])
            )
            if warning_box.toPlainText() != warning_text:
                warning_box.setPlainText(warning_text)
        subtitle_timeline = analysis.get("subtitleTimeline") or []
        timeline_lines = []
        for item in subtitle_timeline[:12]:
            timeline_lines.append(
                repair_mojibake_text(
                    f"{item.get('startMs', 0) / 1000:.1f}s | {item.get('speakerId') or '--'} | {normalize_preview_text(item.get('text'))}"
                )
            )
        timeline_box = getattr(self, "timeline_box", None)
        if timeline_box is not None:
            timeline_text = "\\n".join(timeline_lines)
            if timeline_box.toPlainText() != timeline_text:
                timeline_box.setPlainText(timeline_text)
        if hasattr(self, "subtitle_editor_status"):
            source_label = str(analysis.get("subtitleTimelineSource") or "ai_generated")
            pretty_source = {
                "ai_generated": "AI tạo",
                "edited": "Đã sửa tay",
                "imported": "SRT import",
            }.get(source_label, source_label)
            status_text = (
                f"{len(subtitle_timeline)} dong subtitle dang hoat dong • Nguon: {pretty_source}"
            )
            repaired_status = repair_mojibake_text(status_text)
            if self.subtitle_editor_status.text() != repaired_status:
                self.subtitle_editor_status.setText(repaired_status)
        if hasattr(self, "rebuild_subtitle_table"):
            timeline_signature = self._subtitle_timeline_signature(subtitle_timeline)
            if getattr(self, "_last_subtitle_table_signature", None) != timeline_signature:
                self.rebuild_subtitle_table()
                self._last_subtitle_table_signature = timeline_signature
        self._set_chip_display_text(
            self.mode_chip,
            "Audio: Giọng chung"
            if voice_layout == "single_voice"
            else "Audio: Hội thoại nhiều người"
            if voice_layout == "multi_character"
            else "Chờ phân tích",
            max_width=220,
        )
        self._set_chip_display_text(
            self.subtitle_chip,
            "Vietsub: Bật"
            if self.settings["subtitlePreset"].get("enabled", True)
            else "Vietsub: Tắt",
            max_width=150,
        )
        self._set_chip_display_text(
            self.timing_chip,
            "Timing: Siêu khít"
            if self.settings.get("timingMode") == "ultra_tight"
            else "Timing: Tự nhiên",
            max_width=170,
        )
        preset_label = dict(UI_THEME_OPTIONS).get(
            self.settings.get("uiThemePreset", "cinema"), "Cinema"
        )
        if hasattr(self, "sidebar_status_chip"):
            self._set_chip_display_text(
                self.sidebar_status_chip,
                f"Preset: {preset_label}",
                max_width=180,
            )
        latest_output_path = self.last_output_path or ""
        output_directory = (
            self.output_dir_edit.text().strip()
            or self.settings.get("outputDirectory", "")
        )
        if hasattr(self, "render_preview_status_label"):
            preview_available = bool(
                getattr(self, "render_preview_player", None) is not None
                and getattr(self, "render_video_widget", None) is not None
            )
            if latest_output_path and preview_available:
                latest_name = latest_output_path.replace("\\", "/").rsplit("/", 1)[-1]
                self.render_preview_status_label.setText(
                    repair_mojibake_text(
                        f"Video render nội bộ đã sẵn sàng: {latest_name}. Bấm Xem video để phát trực tiếp trong app."
                    )
                )
            elif latest_output_path:
                self.render_preview_status_label.setText(
                    "Video render nội bộ đã sẵn sàng nhưng môi trường hiện tại chưa bật được Qt Multimedia Video để phát trực tiếp trong app."
                )
            else:
                self.render_preview_status_label.setText(
                    "Chưa có video render để xem trước."
                )
        if hasattr(self, "output_export_status_label"):
            if getattr(self, "last_exported_output_path", "").strip():
                exported_name = self.last_exported_output_path.replace("\\", "/").rsplit("/", 1)[-1]
                self.output_export_status_label.setText(
                    repair_mojibake_text(
                        f"Đã xuất file gần nhất: {exported_name}. Bạn vẫn có thể preview lại video nội bộ hoặc xuất sang vị trí khác."
                    )
                )
            elif latest_output_path:
                self.output_export_status_label.setText(
                    "Video render nội bộ đã sẵn sàng. App sẽ tự lưu file ra thư mục output đã chọn sau khi render xong."
                )
            else:
                self.output_export_status_label.setText(
                    "Video render nội bộ sẽ sẵn sàng để preview sau khi render hoàn tất."
                )
        self.output_result_edit.setText(latest_output_path)
        self.output_result_edit.setToolTip(latest_output_path)
        self.output_result_edit.setCursorPosition(0)
        self.output_folder_quick_edit.setText(output_directory)
        self.output_folder_quick_edit.setToolTip(output_directory)
        self.output_folder_quick_edit.setCursorPosition(0)
        if hasattr(self, "_apply_render_preview_audio_state"):
            self._apply_render_preview_audio_state()
        if hasattr(self, "_apply_render_preview_playback_rate"):
            self._apply_render_preview_playback_rate()
        if hasattr(self, "_update_render_preview_button_labels"):
            self._update_render_preview_button_labels()
        self._update_color_button_styles()
        self._configure_responsive_widgets()
        self._maybe_repair_widget_texts(force=True)

    def _append_install_log(self, message: str) -> None:
        existing = self.log_box.toPlainText().splitlines()
        existing.append(repair_mojibake_text(message))
        self.log_box.setPlainText("\n".join(existing[-300:]))
        scroll_bar = self.log_box.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def _update_install_progress(
        self, *, phase: str, step: str, progress: float, message: str
    ) -> None:
        percent = int(round(max(0.0, min(progress, 1.0)) * 100))
        self._set_chip_display_text(
            self.phase_label,
            f"Trạng thái: {phase}",
            max_width=220,
        )
        self._set_chip_display_text(
            self.step_label,
            f"Bước: {step}",
            max_width=280,
        )
        self.progress_bar.setValue(percent)
        
        self._append_install_log(message)

    def _drain_install_output(self, stream: str) -> None:
        process = self.install_process
        if process is None:
            return
        if stream == "stdout":
            chunk = decode_process_bytes(bytes(process.readAllStandardOutput()))
            self._install_stdout_buffer += chunk
            buffer = self._install_stdout_buffer
        else:
            chunk = decode_process_bytes(bytes(process.readAllStandardError()))
            self._install_stderr_buffer += chunk
            buffer = self._install_stderr_buffer
        lines = buffer.splitlines(keepends=False)
        if buffer and not buffer.endswith(("\n", "\r")):
            remainder = lines.pop() if lines else buffer
        else:
            remainder = ""
        if stream == "stdout":
            self._install_stdout_buffer = remainder
        else:
            self._install_stderr_buffer = remainder
        for line in lines:
            self._handle_install_line(line.strip(), stream)

    def _handle_install_line(self, line: str, stream: str) -> None:
        if not line:
            return
        if stream == "stdout" and line.startswith("PROGRESS::"):
            try:
                payload = json.loads(line.split("PROGRESS::", 1)[1])
            except json.JSONDecodeError:
                self._append_install_log(line)
                return
            self._update_install_progress(
                phase=str(payload.get("phase") or "prepare"),
                step=str(payload.get("step") or "prepare"),
                progress=float(payload.get("progress") or 0.0),
                message=str(payload.get("message") or "Dang chuan bi moi truong..."),
            )
            return
        if stream == "stdout" and line.startswith("ERROR::"):
            try:
                payload = json.loads(line.split("ERROR::", 1)[1])
                self._append_install_log(str(payload.get("message") or line))
            except json.JSONDecodeError:
                self._append_install_log(line)
            return
        if stream == "stdout" and line.startswith("RESULT::"):
            self._append_install_log("Moi truong da san sang.")
            return
        self._append_install_log(line)

    def _handle_install_finished(self, code: int) -> None:
        self._drain_install_output("stdout")
        self._drain_install_output("stderr")
        if self.install_process is not None:
            self.install_process.deleteLater()
        self.install_process = None
        self._install_stdout_buffer = ""
        self._install_stderr_buffer = ""
        self.install_env_btn.setEnabled(True)
        self.install_env_btn.setText("Chuẩn bị model")
        if code == 0:
            QMessageBox.information(
                self,
                "Chuẩn bị hoàn tất",
                "Môi trường đã sẵn sàng. Khi phân tích hoặc render, chương trình cũng sẽ tự tải phần còn thiếu nếu cần.",
            )
        else:
            QMessageBox.warning(
                self,
                "Chuẩn bị chưa hoàn tất",
                "Có lỗi khi chuẩn bị môi trường. Xem log trong app để biết chi tiết.",
            )

    def _start_install_environment_process(self) -> None:
        if self.install_process is not None and (
            self.install_process.state() != QProcess.ProcessState.NotRunning
        ):
            QMessageBox.information(
                self,
                "Đang chuẩn bị",
                "Tiến trình chuẩn bị môi trường vẫn đang chạy.",
            )
            return
        self.install_env_btn.setEnabled(False)
        self.install_env_btn.setText("Đang chuẩn bị...")
        self._append_install_log("Bắt đầu kiểm tra thư viện và model...")
        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        process.setProcessEnvironment(env)
        process.setProgram(str(PIPELINE_PYTHON))
        process.setArguments(["-u", str(PIPELINE_PATH), "prepare", "--target", "all"])
        process.setWorkingDirectory(str(ROOT))
        process.readyReadStandardOutput.connect(
            lambda: self._drain_install_output("stdout")
        )
        process.readyReadStandardError.connect(
            lambda: self._drain_install_output("stderr")
        )
        process.finished.connect(
            lambda code, _status: self._handle_install_finished(code)
        )
        self.install_process = process
        self._install_stdout_buffer = ""
        self._install_stderr_buffer = ""
        process.start()

    def install_environment(self) -> None:
        self._start_install_environment_process()
