from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QProcess, QProcessEnvironment, QTimer, QUrl, Qt, QSize
from PyQt6.QtGui import QDesktopServices, QPixmap, QPainter, QPainterPath, QColor, QFont
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QLineEdit

from gui.config import PIPELINE_PATH, PIPELINE_PYTHON, ROOT, VOICE_LABELS, VOICE_OPTIONS, is_frozen
from gui.utils import decode_process_bytes, ensure_dir, repair_mojibake_text
from .helpers import SafeComboBox


VOICE_PREVIEW_TEXT = "Trong khoảnh khắc thành phố vừa thức dậy, những âm thanh quen thuộc như tiếng chim hót, tiếng gió lùa hòa vào nhau, tạo nên một bản nhạc khiến tôi muốn chậm lại, lắng nghe và mỉm cười."


def get_circular_pixmap(image_path: str, size: int = 48) -> QPixmap:
    pixmap = QPixmap(image_path)
    if pixmap.isNull():
        return QPixmap()
    
    scaled = pixmap.scaled(
        QSize(size, size),
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation
    )
    
    out_pixmap = QPixmap(size, size)
    out_pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(out_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    
    x = (size - scaled.width()) // 2
    y = (size - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()
    
    return out_pixmap


class WindowVoiceMixin:
    def rebuild_voice_mapping_ui(self) -> None:
        while self.voice_layout.count():
            child = self.voice_layout.takeAt(0)
            widget = child.widget()
            if widget:
                widget.deleteLater()
        self.voice_combo_map = {}
        self.voice_name_edit_map = {}
        self.voice_test_button_map = {}
        self.voice_status_label_map = {}
        speakers = (self.effective_analysis or {}).get("speakers") or []
        if hasattr(self, "voice_overview_label"):
            if speakers:
                self.voice_overview_label.setText(
                    f"Đã nhận diện {len(speakers)} speaker. Chọn một giọng preset rồi bấm Nghe thử để kiểm tra trước khi render."
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
        
        from gui.config import TEMP_DUB_DIR
        for speaker in speakers:
            row = QFrame()
            row.setObjectName("StatCard")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(16, 14, 16, 14)
            row_layout.setSpacing(10)
            
            top_row = QHBoxLayout()
            top_row.setSpacing(12)
            
            # --- Avatar (Face Thumbnail or Initials Circle) ---
            avatar_label = QLabel()
            avatar_size = 44
            avatar_label.setFixedSize(avatar_size, avatar_size)
            avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            face_thumb_rel = speaker.get("faceThumbnail")
            face_thumb_path = TEMP_DUB_DIR / face_thumb_rel if face_thumb_rel else None
            
            if face_thumb_path and face_thumb_path.exists():
                circ_pix = get_circular_pixmap(str(face_thumb_path), avatar_size)
                if not circ_pix.isNull():
                    avatar_label.setPixmap(circ_pix)
                else:
                    face_thumb_path = None
                    
            if not face_thumb_path or not face_thumb_path.exists():
                # Colored circle placeholder
                placeholder = QPixmap(avatar_size, avatar_size)
                placeholder.fill(Qt.GlobalColor.transparent)
                painter = QPainter(placeholder)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                
                color_hex = speaker.get("colorTag") or "#56CFE1"
                painter.setBrush(QColor(color_hex))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(0, 0, avatar_size, avatar_size)
                
                painter.setPen(QColor("#0f172a"))
                font = QFont("Arial", 11, QFont.Weight.Bold)
                painter.setFont(font)
                display_name = speaker.get("displayName") or speaker.get("speakerId") or "S"
                if "speaker_" in display_name.lower():
                    try:
                        num = display_name.split("_")[1]
                        initial = f"S{num}"
                    except Exception:
                        initial = "S"
                else:
                    initial = display_name[0].upper()
                painter.drawText(placeholder.rect(), Qt.AlignmentFlag.AlignCenter, initial)
                painter.end()
                avatar_label.setPixmap(placeholder)
                
            badge = QLabel("Main" if speaker.get("isPrimary") else "Speaker")
            badge.setObjectName("MetricChip")
            
            # --- Editable Speaker Name QLineEdit ---
            custom_name = self.settings.setdefault("displayNameMapping", {}).get(speaker["speakerId"])
            
            if custom_name:
                name_text = custom_name
            elif speaker.get("memoryName"):
                name_text = speaker["memoryName"]
            else:
                name_text = ""
                
            name_edit = QLineEdit(name_text)
            if speaker.get("memoryName"):
                name_edit.setPlaceholderText(f"Người quen: {speaker['memoryName']}")
            else:
                raw_display = speaker.get("displayName") or speaker["speakerId"]
                if "Người quen: " in raw_display:
                    raw_display = raw_display.replace("Người quen: ", "", 1)
                name_edit.setPlaceholderText(raw_display)
                
            name_edit.setStyleSheet("""
                QLineEdit {
                    background: rgba(15, 23, 42, 0.4);
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    border-radius: 8px;
                    font-weight: 700;
                    color: #ffffff;
                    font-size: 13px;
                    padding: 6px 10px;
                    min-width: 150px;
                }
                QLineEdit:hover {
                    background: rgba(15, 23, 42, 0.7);
                    border: 1px solid rgba(56, 189, 248, 0.45);
                }
                QLineEdit:focus {
                    background: #0f172a;
                    border: 1px solid #38bdf8;
                    color: #ffffff;
                }
            """)
            
            name_edit.editingFinished.connect(
                lambda speaker_id=speaker["speakerId"], edit=name_edit: (
                    self.on_speaker_name_changed(speaker_id, edit.text())
                )
            )
            
            # --- Voice Combo Box & Preview button ---
            combo = SafeComboBox()
            for value, text in self._voice_options_for_speaker(speaker):
                combo.addItem(text, value)
            selected_voice = (
                self.settings["voiceMapping"].get(speaker["speakerId"])
                or speaker.get("voicePreset")
                or VOICE_OPTIONS[0][0]
            )
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
            
            # --- Status and Speaker Info Sub-Labels ---
            status_label = QLabel(
                f"Đề xuất: {self._format_voice_label(selected_voice)}"
            )
            status_label.setObjectName("SectionHint")
            
            # Build detailed label (Pyannote stats + detected age/gender)
            detail_text = f"{int(speaker.get('segmentCount') or 0)} câu • {float(speaker.get('totalDurationMs') or 0) / 1000:.1f}s"
            if speaker.get("gender") and speaker.get("age"):
                gender_lbl = "Nam" if speaker.get("gender") == "M" else "Nữ"
                detail_text += f" • Nhận diện: {gender_lbl}, ~{speaker.get('age')} tuổi"
                
            detail_label = QLabel(detail_text)
            detail_label.setObjectName("SectionHint")
            
            top_row.addWidget(avatar_label)
            top_row.addWidget(badge)
            top_row.addWidget(name_edit)
            top_row.addStretch(1)
            top_row.addWidget(combo, 1)
            top_row.addWidget(test_btn)
            
            row_layout.addLayout(top_row)
            row_layout.addWidget(detail_label)
            row_layout.addWidget(status_label)
            
            self.voice_combo_map[speaker["speakerId"]] = combo
            self.voice_name_edit_map[speaker["speakerId"]] = name_edit
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
        self.save_speaker_to_memory(speaker_id)

    def on_speaker_name_changed(self, speaker_id: str, new_name: str) -> None:
        new_name = new_name.strip()
        if not new_name:
            self.settings.setdefault("displayNameMapping", {}).pop(speaker_id, None)
        else:
            self.settings.setdefault("displayNameMapping", {})[speaker_id] = new_name
            
        self._push_analysis_overrides(rebuild_voice_ui=False)
        self.refresh_status_only()
        self.save_speaker_to_memory(speaker_id)

    def save_speaker_to_memory(self, speaker_id: str) -> None:
        analysis = self.effective_analysis or self.analysis or {}
        speakers = analysis.get("speakers") or []
        speaker = next((item for item in speakers if item.get("speakerId") == speaker_id), None)
        if not speaker:
            return
            
        embedding = speaker.get("embedding")
        if not embedding:
            return
            
        custom_name = self.settings.setdefault("displayNameMapping", {}).get(speaker_id)
        name = (custom_name or speaker.get("memoryName") or speaker_id).strip()
        if not name:
            name = speaker_id
            
        combo = self.voice_combo_map.get(speaker_id)
        voice = (self._resolve_voice_combo_value(combo) if combo else speaker.get("voicePreset") or "edge:female").strip()
        
        gender = speaker.get("gender") or "F"
        age = speaker.get("age") or 25
        
        from tools.speaker_identifier.memory_manager import add_or_update_speaker
        add_or_update_speaker(
            name=name,
            embedding=embedding,
            gender=gender,
            age=age,
            voice=voice
        )

    def _voice_options_for_speaker(self, speaker: dict[str, Any]) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        recommended = str(speaker.get("voicePreset") or "")
        if recommended:
            options.append(
                (recommended, f"{self._format_voice_label(recommended)} (đề xuất)")
            )
        for value, text in VOICE_OPTIONS:
            label = repair_mojibake_text(text)
            if value == recommended:
                label = f"{label} (đề xuất)"
            options.append((value, label))
        if recommended and all(recommended != value for value, _ in options):
            options.append((recommended, self._format_voice_label(recommended)))
        return options

    def _speaker_preview_text(self, speaker_id: str, display_name: str) -> str:
        return VOICE_PREVIEW_TEXT

    def on_test_default_voice_clicked(self) -> None:
        combo = getattr(self, "default_voice_combo", None)
        if combo is None:
            return
        selected_voice = str(self._resolve_voice_combo_value(combo) or "").strip()
        if not selected_voice:
            return
        self.settings["defaultVoice"] = selected_voice
        self.voice_status_label_map["__default__"] = getattr(
            self, "default_voice_status_label", None
        )
        self.on_test_voice_clicked("__default__", voice_override=selected_voice)

    def on_test_intro_voice_clicked(self) -> None:
        combo = getattr(self, "intro_voice_combo", None)
        if combo is None:
            return
        selected_voice = str(self._resolve_voice_combo_value(combo) or "").strip()
        if not selected_voice:
            return
        self.voice_status_label_map["__intro__"] = getattr(
            self, "intro_voice_status_label", None
        )
        self.on_test_voice_clicked("__intro__", voice_override=selected_voice)

    def on_test_voice_clicked(
        self, speaker_id: str, *, voice_override: str | None = None
    ) -> None:
        combo = self.voice_combo_map.get(speaker_id)
        if combo is None and voice_override is None:
            return
        analysis = self.effective_analysis or self.analysis or {}
        speakers = analysis.get("speakers") or []
        speaker = next(
            (item for item in speakers if item.get("speakerId") == speaker_id),
            {},
        )
        selected_voice = str(
            voice_override or (self._resolve_voice_combo_value(combo) if combo is not None else "")
        ).strip()
        if not selected_voice:
            return
        if selected_voice.startswith(("omnivoice:", "valtec:")):
            provider_label = "Valtec-TTS" if selected_voice.startswith("valtec:") else "OmniVoice-TTS"
            status_message = (
                f"Đang nghe thử {self._format_voice_label(selected_voice)}. "
                f"{provider_label} local sẽ phát bằng preset đã chọn."
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
                self.voice_preview_process.readyReadStandardOutput.disconnect(self._drain_voice_preview_output)
            except Exception: pass
            try:
                self.voice_preview_process.readyReadStandardError.disconnect(self._drain_voice_preview_output)
            except Exception: pass
            try:
                self.voice_preview_process.finished.disconnect(self._handle_voice_preview_finished)
            except Exception: pass
            try:
                self.voice_preview_process.kill()
            except Exception: pass

        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        process.setProcessEnvironment(env)
        process.setProgram(str(PIPELINE_PYTHON))
        if is_frozen:
            process.setArguments(["pipeline", "preview-voice", "--voice", selected_voice, "--text", preview_text, "--speaker-id", speaker_id, "--job-id", str(self.job_id or ""), "--output-json", str(result_path)])
        else:
            process.setArguments(["-u", str(PIPELINE_PATH), "preview-voice", "--voice", selected_voice, "--text", preview_text, "--speaker-id", speaker_id, "--job-id", str(self.job_id or ""), "--output-json", str(result_path)])
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
        self._voice_preview_timed_out = False
        self._set_voice_test_buttons_enabled(False)
        status_label = self.voice_status_label_map.get(speaker_id)
        if status_label is not None and not selected_voice.startswith(("omnivoice:", "valtec:")):
            status_label.setText("Đang tạo mẫu nghe thử...")
        process.start()
        QTimer.singleShot(120000, lambda p=process: self._timeout_voice_preview_process(p))

    def _timeout_voice_preview_process(self, process: QProcess) -> None:
        if self.voice_preview_process is not process:
            return
        if process.state() == QProcess.ProcessState.NotRunning:
            return
        self._voice_preview_timed_out = True
        try:
            process.kill()
        except Exception:
            pass

    def _set_voice_test_buttons_enabled(self, enabled: bool) -> None:
        for button in self.voice_test_button_map.values():
            button.setEnabled(enabled)
        intro_button = getattr(self, "intro_voice_test_btn", None)
        if intro_button is not None:
            intro_button.setEnabled(enabled)
        default_button = getattr(self, "default_voice_test_btn", None)
        if default_button is not None:
            default_button.setEnabled(enabled)

    def _drain_voice_preview_output(self) -> None:
        process = self.voice_preview_process
        if process is None:
            return
        self._voice_preview_stdout += decode_process_bytes(
            bytes(process.readAllStandardOutput())
        )
        self._voice_preview_stderr += decode_process_bytes(
            bytes(process.readAllStandardError())
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
            
        if self._play_voice_preview_with_windows_mci(audio_file):
            return

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

    def _close_voice_preview_mci_alias(self) -> None:
        alias = str(getattr(self, "_voice_preview_mci_alias", "") or "")
        if not alias or os.name != "nt":
            return
        try:
            import ctypes

            ctypes.windll.winmm.mciSendStringW(f"close {alias}", None, 0, None)
        except Exception:
            pass
        self._voice_preview_mci_alias = ""

    def _play_voice_preview_with_windows_mci(self, audio_file: Path) -> bool:
        if os.name != "nt" or audio_file.suffix.lower() not in {".mp3", ".wav"}:
            return False
        try:
            import ctypes

            self._close_voice_preview_mci_alias()
            alias = f"voice_preview_{id(self)}"
            path = str(audio_file.resolve()).replace('"', "")
            send = ctypes.windll.winmm.mciSendStringW
            error_buffer = ctypes.create_unicode_buffer(256)

            result = send(f'open "{path}" alias {alias}', error_buffer, len(error_buffer), None)
            if result != 0:
                return False
            result = send(f"play {alias}", error_buffer, len(error_buffer), None)
            if result != 0:
                send(f"close {alias}", None, 0, None)
                return False
            self._voice_preview_mci_alias = alias
            return True
        except Exception:
            return False

    def _handle_voice_player_error(self, _error, error_string: str) -> None:
        message = repair_mojibake_text(error_string or "Khong the phat audio nghe thu.")
        speaker_id = self._voice_preview_active_speaker_id
        status_label = self.voice_status_label_map.get(speaker_id)
        if status_label is not None:
            status_label.setText("Phat audio that bai")
        QMessageBox.warning(self, "Khong the nghe thu", message)
