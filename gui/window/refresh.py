from __future__ import annotations

import json

from PyQt6.QtCore import QProcess, QProcessEnvironment
from PyQt6.QtWidgets import QMessageBox

from gui.config import PIPELINE_PATH, PIPELINE_PYTHON, ROOT, UI_THEME_OPTIONS
from gui.utils import normalize_preview_text, repair_mojibake_text


class WindowRefreshMixin:
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
            "font_combo",
            "font_color_btn",
            "stroke_color_btn",
            "stroke_width_spin",
            "max_words_spin",
            "intro_enabled_check",
            "intro_duration_spin",
            "intro_voice_combo",
            "intro_background_check",
            "intro_background_volume_spin",
            "keep_original_audio_check",
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
        for item in (self.effective_analysis or self.analysis or {}).get(
            "subtitleTimeline", []
        ):
            candidate = normalize_preview_text(item.get("text"))
            if len(candidate) >= 8:
                return repair_mojibake_text(candidate)
        for segment in (self.effective_analysis or self.analysis or {}).get(
            "segments", []
        ):
            candidate = normalize_preview_text(
                segment.get("translatedText") or segment.get("sourceText")
            )
            if len(candidate) >= 8:
                return repair_mojibake_text(candidate)
        return "Xem trước vietsub mới ngay trên khung video"

    def refresh_preview(self) -> None:
        self.preview_canvas.update_state(
            self.preview_media_analysis or self.effective_analysis or self.analysis,
            self.settings,
            self.compute_preview_text(),
        )

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
        self._repair_widget_texts()
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
        self.refresh_status_only()
        self.summary_labels["sourceLanguage"].setText(
            str(analysis.get("sourceLanguage") or "--")
        )
        self.summary_labels["speakers"].setText(
            str(len(analysis.get("speakers") or []))
        )
        voice_layout = analysis.get("voiceLayout")
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
            warning_box.setPlainText(
                "\\n".join(
                    repair_mojibake_text(item)
                    for item in (analysis.get("warnings") or [])
                )
            )
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
            timeline_box.setPlainText("\\n".join(timeline_lines))
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
            self.subtitle_editor_status.setText(repair_mojibake_text(status_text))
        if hasattr(self, "rebuild_subtitle_table"):
            self.rebuild_subtitle_table()
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
                    "Video render đã sẵn sàng trong hệ thống. Chỉ khi bấm Xuất file thì app mới ghi video ra thư mục bạn chọn."
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
        self._repair_widget_texts()

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
            chunk = bytes(process.readAllStandardOutput()).decode(
                "utf-8", errors="ignore"
            )
            self._install_stdout_buffer += chunk
            buffer = self._install_stdout_buffer
        else:
            chunk = bytes(process.readAllStandardError()).decode(
                "utf-8", errors="ignore"
            )
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
        return
        import threading
        import subprocess

        def run_install():
            self.controller.status_changed.emit("render", "system", 0.0, "Đang kiểm tra và cài đặt Ollama...")
            try:
                # 1. Install Ollama via winget
                install_cmd = "winget install Ollama.Ollama --accept-source-agreements --accept-package-agreements --silent"
                subprocess.run(install_cmd, shell=True, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
                
                self.controller.status_changed.emit("render", "system", 0.4, "Đang tải model gemma4:e4b (Khoảng 2.5GB - Vui lòng đợi trong ít phút)...")
                
                # 2. Pull the model (Ollama runs automatically after installation)
                pull_cmd = "ollama pull gemma4:e4b"
                pull_process = subprocess.run(pull_cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
                if pull_process.returncode == 0:
                    self.controller.status_changed.emit("render", "system", 1.0, "Cài đặt thành công! Hệ thống đã sẵn sàng với gemma4:e4b.")
                else:
                    self.controller.status_changed.emit("render", "system", 0.0, f"Lỗi kéo model. Mở Ollama lên và gõ lệnh 'ollama pull gemma4:e4b'. Chi tiết lỗi: {pull_process.stderr[:150]}")
            except Exception as e:
                self.controller.status_changed.emit("render", "system", 0.0, f"Lỗi: {e}")

        self.install_env_btn.setEnabled(False)
        self.install_env_btn.setText("Đang cài đặt...")
        def reset_btn():
            self.install_env_btn.setEnabled(True)
            self.install_env_btn.setText("Cài Ollama & Gemma4")
        self.controller.status_changed.connect(lambda p, s, pr, m: reset_btn() if pr == 1.0 or (pr == 0.0 and s == "system") else None)
        
        threading.Thread(target=run_install, daemon=True).start()



