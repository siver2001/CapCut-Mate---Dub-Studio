from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QProcess, QProcessEnvironment, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout

from gui.config import PIPELINE_PATH, PIPELINE_PYTHON, ROOT, VOICE_LABELS, VOICE_OPTIONS
from gui.utils import ensure_dir, normalize_preview_text, repair_mojibake_text


class WindowVoiceMixin:
    def rebuild_voice_mapping_ui(self) -> None:
        while self.voice_layout.count():
            child = self.voice_layout.takeAt(0)
            widget = child.widget()
            if widget:
                widget.deleteLater()
        self.voice_combo_map = {}
        self.voice_test_button_map = {}
        self.voice_status_label_map = {}
        speakers = (self.effective_analysis or {}).get("speakers") or []
        if hasattr(self, "voice_overview_label"):
            if speakers:
                clone_ready = sum(
                    1 for speaker in speakers if bool(speaker.get("voiceCloneReady"))
                )
                self.voice_overview_label.setText(
                    f"Đã nhận diện {len(speakers)} speaker. VieNeu-TTS local có 4 giọng preset và clone theo mẫu speaker, hiện sẵn sàng clone cho {clone_ready}/{len(speakers)} speaker."
                )
            else:
                self.voice_overview_label.setText(
                    "Danh sách speaker sẽ hiện sau khi phân tích video."
                )
        if not speakers:
            empty_label = QLabel("Danh sách speaker sẽ hiện sau khi phân tích video.")
            empty_label.setObjectName("SectionHint")
            empty_label.setWordWrap(True)
            self.voice_layout.addWidget(empty_label)
            return
        for speaker in speakers:
            row = QFrame()
            row.setObjectName("StatCard")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(16, 14, 16, 14)
            row_layout.setSpacing(10)
            top_row = QHBoxLayout()
            top_row.setSpacing(12)
            badge = QLabel("Main" if speaker.get("isPrimary") else "Speaker")
            badge.setObjectName("MetricChip")
            label = QLabel(f"{speaker.get('displayName', speaker.get('speakerId'))}")
            label.setStyleSheet(
                f"font-weight: 700; color: {speaker.get('colorTag') or '#f8fafc'};"
            )
            detail_label = QLabel(
                f"{int(speaker.get('segmentCount') or 0)} câu • {float(speaker.get('totalDurationMs') or 0) / 1000:.1f}s • {'Đã có mẫu để clone VieNeu-TTS' if speaker.get('voiceCloneReady') else 'Chưa có mẫu speaker để clone VieNeu-TTS'}"
            )
            detail_label.setObjectName("SectionHint")
            combo = QComboBox()
            for value, text in self._voice_options_for_speaker(speaker):
                combo.addItem(text, value)
            selected_voice = (
                self.settings["voiceMapping"].get(speaker["speakerId"])
                or speaker.get("voicePreset")
                or VOICE_OPTIONS[0][0]
            )
            original_selected_voice = str(selected_voice)
            if str(selected_voice) == "vieneu:clone":
                fallback_voice = speaker.get("voicePreset") or VOICE_OPTIONS[0][0]
                selected_voice = (
                    fallback_voice
                    if str(fallback_voice) != "vieneu:clone"
                    else VOICE_OPTIONS[0][0]
                )
            if original_selected_voice == "vieneu:clone":
                self.settings["voiceMapping"][speaker["speakerId"]] = str(selected_voice)
            combo.setEditable(True)
            if combo.findData(selected_voice) >= 0:
                self._set_combo_value(combo, selected_voice)
            else:
                combo.setEditText(str(selected_voice))
            combo.activated.connect(
                lambda _idx, speaker_id=speaker["speakerId"], c=combo: (
                    self.on_voice_mapping_changed(speaker_id, self._resolve_voice_combo_value(c))
                )
            )
            if combo.lineEdit() is not None:
                combo.lineEdit().setPlaceholderText(
                    "Chọn preset hoặc nhập Edge voice, ví dụ en-US-AvaNeural"
                )
                combo.lineEdit().returnPressed.connect(
                    lambda speaker_id=speaker["speakerId"], c=combo: (
                        self.on_voice_mapping_changed(speaker_id, self._resolve_voice_combo_value(c))
                    )
                )
            test_btn = QPushButton("Nghe thử")
            test_btn.clicked.connect(
                lambda _checked=False, speaker_id=speaker["speakerId"]: self.on_test_voice_clicked(speaker_id)
            )
            status_label = QLabel(
                f"Đề xuất: {self._format_voice_label(selected_voice)}"
            )
            status_label.setObjectName("SectionHint")
            top_row.addWidget(badge)
            top_row.addWidget(label)
            top_row.addStretch(1)
            top_row.addWidget(combo, 1)
            top_row.addWidget(test_btn)
            row_layout.addLayout(top_row)
            row_layout.addWidget(detail_label)
            row_layout.addWidget(status_label)
            self.voice_combo_map[speaker["speakerId"]] = combo
            self.voice_test_button_map[speaker["speakerId"]] = test_btn
            self.voice_status_label_map[speaker["speakerId"]] = status_label
            self.voice_layout.addWidget(row)

    def on_voice_mapping_changed(self, speaker_id: str, voice: str) -> None:
        voice = str(voice or "").strip()
        if not voice:
            return
        self.settings["voiceMapping"][speaker_id] = voice
        status_label = self.voice_status_label_map.get(speaker_id)
        if status_label is not None:
            status_label.setText(f"Đã chọn: {self._format_voice_label(voice)}")
        self._push_analysis_overrides(rebuild_voice_ui=False)
        self.refresh_status_only()

    def _voice_options_for_speaker(self, speaker: dict[str, Any]) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        clone_ready = bool(speaker.get("voiceCloneReady"))
        recommended = str(speaker.get("voicePreset") or "")
        for value, text in VOICE_OPTIONS:
            if value == "vieneu:clone" and not clone_ready:
                continue
            if value == "vieneu:clone":
                label = "VieNeu-TTS • Clone từ speaker này"
            else:
                label = repair_mojibake_text(text)
            if value == recommended:
                label = f"{label} (đề xuất)"
            options.append((value, label))
        if recommended and recommended != "vieneu:clone" and all(recommended != value for value, _ in options):
            options.append((recommended, self._format_voice_label(recommended)))
        return options

    def _speaker_preview_text(self, speaker_id: str, display_name: str) -> str:
        analysis = self.effective_analysis or self.analysis or {}
        for segment in analysis.get("segments") or []:
            if segment.get("speakerId") != speaker_id:
                continue
            candidate = normalize_preview_text(
                segment.get("spokenText") or segment.get("translatedText") or ""
            )
            if len(candidate) >= 8:
                shortened = " ".join(candidate.split()[:8]).strip()
                return repair_mojibake_text(shortened or candidate[:48])
        safe_name = repair_mojibake_text(display_name or speaker_id)
        return f"Xin chào, đây là giọng lồng tiếng của {safe_name}. Bạn thấy có tự nhiên không?"

    def on_test_voice_clicked(
        self, speaker_id: str, *, voice_override: str | None = None
    ) -> None:
        combo = self.voice_combo_map.get(speaker_id)
        if combo is None:
            return
        analysis = self.effective_analysis or self.analysis or {}
        speakers = analysis.get("speakers") or []
        speaker = next(
            (item for item in speakers if item.get("speakerId") == speaker_id),
            {},
        )
        selected_voice = str(voice_override or self._resolve_voice_combo_value(combo)).strip()
        if selected_voice.startswith("vieneu:"):
            if selected_voice == "vieneu:clone" and speaker.get("voiceCloneReady"):
                status_message = (
                    f"Đang nghe thử {self._format_voice_label(selected_voice)}. "
                    "Lần đầu VieNeu-TTS có thể mất 10-20 giây để nạp model local."
                )
            elif selected_voice == "vieneu:clone":
                status_message = "Speaker này chưa có mẫu clone VieNeu-TTS, app sẽ nghe thử bằng EdgeTTS thay thế."
            else:
                status_message = (
                    f"Đang nghe thử {self._format_voice_label(selected_voice)}. "
                    "VieNeu-TTS local sẽ phát bằng preset đã chọn."
                )
            status_label = self.voice_status_label_map.get(speaker_id)
            if status_label is not None:
                status_label.setText(repair_mojibake_text(status_message))
        preview_text = self._speaker_preview_text(
            speaker_id,
            str(speaker.get("displayName") or speaker_id),
        )
        preview_dir = ensure_dir(ROOT / "temp" / "dub_studio" / "voice_preview")
        result_path = preview_dir / f"{speaker_id}_preview.json"
        if self.voice_preview_process is not None:
            try:
                self.voice_preview_process.readyReadStandardOutput.disconnect(
                    self._drain_voice_preview_output
                )
            except Exception:
                pass
            try:
                self.voice_preview_process.readyReadStandardError.disconnect(
                    self._drain_voice_preview_output
                )
            except Exception:
                pass
            try:
                self.voice_preview_process.finished.disconnect(
                    self._handle_voice_preview_finished
                )
            except Exception:
                pass
            try:
                self.voice_preview_process.kill()
            except Exception:
                pass
        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        process.setProcessEnvironment(env)
        process.setProgram(str(PIPELINE_PYTHON))
        process.setArguments(
            [
                "-u",
                str(PIPELINE_PATH),
                "preview-voice",
                "--voice",
                selected_voice,
                "--text",
                preview_text,
                "--speaker-id",
                speaker_id,
                "--job-id",
                str(self.job_id or ""),
                "--output-json",
                str(result_path),
            ]
        )
        process.setWorkingDirectory(str(ROOT))
        process.readyReadStandardOutput.connect(self._drain_voice_preview_output)
        process.readyReadStandardError.connect(self._drain_voice_preview_output)
        process.finished.connect(self._handle_voice_preview_finished)
        self.voice_preview_process = process
        self._voice_preview_stdout = ""
        self._voice_preview_stderr = ""
        self._voice_preview_result_path = result_path
        self._voice_preview_active_speaker_id = speaker_id
        self._voice_preview_audio_path = ""
        self._set_voice_test_buttons_enabled(False)
        status_label = self.voice_status_label_map.get(speaker_id)
        if status_label is not None and not selected_voice.startswith("vieneu:"):
            status_label.setText("Đang tạo mẫu nghe thử...")
        process.start()

    def _set_voice_test_buttons_enabled(self, enabled: bool) -> None:
        for button in self.voice_test_button_map.values():
            button.setEnabled(enabled)

    def _drain_voice_preview_output(self) -> None:
        process = self.voice_preview_process
        if process is None:
            return
        self._voice_preview_stdout += bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="ignore"
        )
        self._voice_preview_stderr += bytes(process.readAllStandardError()).decode(
            "utf-8", errors="ignore"
        )

    def _handle_voice_preview_finished(self, code: int, _status) -> None:
        self._drain_voice_preview_output()
        speaker_id = self._voice_preview_active_speaker_id
        status_label = self.voice_status_label_map.get(speaker_id)
        self._set_voice_test_buttons_enabled(True)
        self.voice_preview_process = None
        if (
            code != 0
            or self._voice_preview_result_path is None
            or not self._voice_preview_result_path.exists()
        ):
            message = (
                self._voice_preview_stderr.strip()
                or self._voice_preview_stdout.strip()
                or "Không tạo được audio nghe thử."
            )
            if status_label is not None:
                status_label.setText("Nghe thử thất bại")
            QMessageBox.warning(self, "Không thể nghe thử", repair_mojibake_text(message))
            return
        try:
            payload = json.loads(
                self._voice_preview_result_path.read_text(encoding="utf-8-sig")
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Không thể nghe thử",
                f"Không đọc được file preview: {exc}",
            )
            return
        audio_path = str(payload.get("outputPath") or "")
        if not audio_path:
            QMessageBox.warning(
                self,
                "Không thể nghe thử",
                "Preview không trả về audio path.",
            )
            return
        self._play_voice_preview_audio(
            audio_path,
            self._format_voice_label(str(payload.get("voice") or "")),
            status_label,
        )

    def _play_voice_preview_audio(
        self, audio_path: str, voice_label: str, status_label: QLabel | None
    ) -> None:
        audio_file = Path(audio_path)
        if not audio_file.exists():
            if status_label is not None:
                status_label.setText("Không tìm thấy file nghe thử")
            QMessageBox.warning(
                self,
                "Không thể nghe thử",
                f"File audio không tồn tại: {audio_file}",
            )
            return
        self._voice_preview_audio_path = str(audio_file)
        if status_label is not None:
            status_label.setText(f"Đang phát: {repair_mojibake_text(voice_label)}")
        if self.voice_player is not None:
            self.voice_player.stop()
            self.voice_player.setSource(QUrl.fromLocalFile(str(audio_file)))
            self.voice_player.play()
            return
        if status_label is not None:
            status_label.setText("Đã mở bằng trình phát mặc định")
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(audio_file))):
            QMessageBox.warning(
                self,
                "Không thể nghe thử",
                f"Không mở được file audio: {audio_file}",
            )

    def _handle_voice_player_error(self, _error, error_string: str) -> None:
        message = repair_mojibake_text(error_string or "Khong the phat audio nghe thu.")
        speaker_id = self._voice_preview_active_speaker_id
        status_label = self.voice_status_label_map.get(speaker_id)
        if status_label is not None:
            status_label.setText("Phat audio that bai")
        QMessageBox.warning(self, "Khong the nghe thu", message)


