from __future__ import annotations

import os
import shutil
import json
import re
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QFileDialog,
    QMessageBox,
    QFrame
)
from gui.utils import ensure_dir, repair_mojibake_text


class WindowCloneVoiceMixin:
    def _build_clone_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(10)

        clone_card = QFrame()
        clone_card.setObjectName("SurfaceCard")
        clone_inner_layout = QVBoxLayout(clone_card)
        clone_inner_layout.setContentsMargins(20, 20, 20, 20)
        clone_inner_layout.setSpacing(14)

        # Title
        title_label = QLabel("CLONE GIỌNG NÓI TIẾNG VIỆT (OMNIVOICE-TTS CLONING)")
        title_label.setObjectName("SectionTitle")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        clone_inner_layout.addWidget(title_label)

        # Grid form
        grid = QGridLayout()
        grid.setSpacing(12)

        # 1. Tên giọng nói
        grid.addWidget(self._field_label("Tên giọng clone:"), 0, 0)
        self.clone_name_edit = QLineEdit()
        self.clone_name_edit.setPlaceholderText("Ví dụ: my_vietnamese_voice")
        self.clone_name_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(15, 23, 42, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                color: #ffffff;
                padding: 8px 12px;
            }
        """)
        grid.addWidget(self.clone_name_edit, 0, 1)

        # 2. File âm thanh mẫu
        grid.addWidget(self._field_label("File mẫu (.wav):"), 1, 0)
        wav_row = QHBoxLayout()
        self.clone_wav_path_edit = QLineEdit()
        self.clone_wav_path_edit.setReadOnly(True)
        self.clone_wav_path_edit.setPlaceholderText("Chọn tệp âm thanh gốc dài 3-10 giây...")
        self.clone_wav_path_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(15, 23, 42, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                color: #ffffff;
                padding: 8px 12px;
            }
        """)
        choose_wav_btn = self._make_button("Chọn", "ghost")
        choose_wav_btn.setMinimumHeight(36)
        choose_wav_btn.clicked.connect(self.choose_reference_wav_file)
        wav_row.addWidget(self.clone_wav_path_edit, 1)
        wav_row.addWidget(choose_wav_btn)
        grid.addLayout(wav_row, 1, 1)

        # 3. Văn bản của file mẫu (Reference Text)
        grid.addWidget(self._field_label("Văn bản tệp mẫu:"), 2, 0)
        self.clone_ref_text_edit = QLineEdit()
        self.clone_ref_text_edit.setPlaceholderText("Nhập nội dung tương ứng của tệp âm thanh mẫu (khuyên dùng để tăng độ chính xác)...")
        self.clone_ref_text_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(15, 23, 42, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                color: #ffffff;
                padding: 8px 12px;
            }
        """)
        grid.addWidget(self.clone_ref_text_edit, 2, 1)

        # 4. Câu kiểm thử (Test Text)
        grid.addWidget(self._field_label("Câu kiểm thử:"), 3, 0)
        self.clone_test_text_edit = QPlainTextEdit()
        self.clone_test_text_edit.setPlainText(
            "Trong khoảnh khắc thành phố vừa thức dậy, những âm thanh quen thuộc như tiếng chim hót, "
            "tiếng gió lùa hòa vào nhau, tạo nên một bản nhạc khiến tôi muốn chậm lại, lắng nghe và mỉm cười."
        )
        self.clone_test_text_edit.setStyleSheet("""
            QPlainTextEdit {
                background: rgba(15, 23, 42, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                color: #ffffff;
                padding: 8px 12px;
            }
        """)
        self.clone_test_text_edit.setMaximumHeight(80)
        grid.addWidget(self.clone_test_text_edit, 3, 1)

        clone_inner_layout.addLayout(grid)

        # Actions row
        actions = QHBoxLayout()
        actions.setSpacing(12)

        self.clone_test_btn = self._make_button("Nghe thử", "ghost")
        self.clone_test_btn.setMinimumHeight(40)
        self.clone_test_btn.clicked.connect(self.on_test_clone_voice_clicked)
        
        self.clone_save_btn = self._make_button("Lưu giọng đọc", "success")
        self.clone_save_btn.setMinimumHeight(40)
        self.clone_save_btn.clicked.connect(self.on_save_clone_voice_clicked)

        actions.addWidget(self.clone_test_btn, 1)
        actions.addWidget(self.clone_save_btn, 1)
        clone_inner_layout.addLayout(actions)

        # Status area
        self.clone_status_label = QLabel("Chuẩn bị file .wav và bấm Nghe thử để kiểm tra.")
        self.clone_status_label.setObjectName("SectionHint")
        self.clone_status_label.setWordWrap(True)
        self.clone_status_label.setStyleSheet("color: #94a3b8; font-style: italic;")
        clone_inner_layout.addWidget(self.clone_status_label)

        clone_inner_layout.addStretch(1)
        page_layout.addWidget(clone_card)
        return page

    def choose_reference_wav_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file âm thanh mẫu (.wav)",
            "",
            "Audio files (*.wav)"
        )
        if not file_path:
            return

        # Check WAV duration
        duration = 0.0
        err_msg = None
        try:
            import wave
            with wave.open(file_path, "rb") as f:
                frames = f.getnframes()
                rate = f.getframerate()
                duration = frames / float(rate)
        except Exception as e:
            try:
                import soundfile as sf
                info = sf.info(file_path)
                duration = info.duration
            except Exception as e2:
                err_msg = f"Không thể đọc thông tin tệp âm thanh (.wav): {e2}"

        if err_msg:
            QMessageBox.warning(
                self,
                "Lỗi đọc file",
                f"Đã xảy ra lỗi khi phân tích tệp âm thanh:\n{err_msg}\n\nVui lòng đảm bảo đây là tệp WAV chuẩn PCM."
            )
            return

        # Enforce 3 to 10 seconds limit for OmniVoice reference
        MIN_DURATION = 3.0
        MAX_DURATION = 10.0

        if duration < MIN_DURATION:
            QMessageBox.warning(
                self,
                "Thời lượng không hợp lệ",
                f"Tệp âm thanh quá ngắn ({duration:.2f} giây)!\n\n"
                f"Vui lòng chọn tệp .wav có độ dài từ {MIN_DURATION} đến {MAX_DURATION} giây để đảm bảo mô hình AI clone giọng đọc được chính xác."
            )
            return
        elif duration > MAX_DURATION:
            QMessageBox.warning(
                self,
                "Thời lượng không hợp lệ",
                f"Tệp âm thanh quá dài ({duration:.2f} giây)!\n\n"
                f"Vui lòng chọn tệp .wav có độ dài từ {MIN_DURATION} đến {MAX_DURATION} giây để tránh lỗi và tối ưu độ chính xác."
            )
            return

        self.clone_wav_path_edit.setText(file_path)
        self.clone_status_label.setText(
            f"Đã chọn tệp: {os.path.basename(file_path)} ({duration:.2f} giây). Sẵn sàng để Nghe thử hoặc Lưu."
        )


    def on_test_clone_voice_clicked(self) -> None:
        ref_path = self.clone_wav_path_edit.text().strip()
        test_text = self.clone_test_text_edit.toPlainText().strip()
        ref_text = self.clone_ref_text_edit.text().strip()

        if not ref_path or not os.path.exists(ref_path):
            QMessageBox.warning(self, "Thiếu tệp tin", "Vui lòng chọn tệp âm thanh mẫu (.wav) trước khi nghe thử.")
            return
        if not test_text:
            QMessageBox.warning(self, "Thiếu văn bản", "Vui lòng nhập văn bản kiểm thử.")
            return

        self.clone_status_label.setText("Đang khởi tạo mô hình OmniVoice và tổng hợp giọng clone...")
        self.clone_test_btn.setEnabled(False)
        self.clone_save_btn.setEnabled(False)

        # Chạy logic test lồng tiếng ngầm qua CLI của CapCutMate
        from gui.config import PIPELINE_PATH, PIPELINE_PYTHON, ROOT, is_frozen
        preview_dir = ensure_dir(ROOT / "temp" / "dub_studio" / "voice_preview")
        result_path = preview_dir / "clone_preview_status.json"

        # Cấu hình file JSON tạm cho preview
        temp_voices_file = ROOT / "config" / "custom_omnivoice_voices.json"
        
        # Backup tệp cấu hình cũ (nếu có)
        backup_data = None
        if temp_voices_file.exists():
            try:
                backup_data = json.loads(temp_voices_file.read_text(encoding="utf-8"))
            except Exception: pass

        # Ghi đè cấu hình tạm thời chứa ID '__temp_clone__'
        temp_data = dict(backup_data or {})
        temp_data["omnivoice:__temp_clone__"] = {
            "filename": os.path.basename(ref_path),
            "ref_text": ref_text,
            "label": "Clone • Temp"
        }
        
        try:
            ref_target_dir = ensure_dir(ROOT / "config" / "voices" / "omnivoice")
            shutil.copy2(ref_path, ref_target_dir / os.path.basename(ref_path))
            temp_voices_file.write_text(json.dumps(temp_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            self.clone_status_label.setText(f"Lỗi chuẩn bị tệp: {e}")
            self.clone_test_btn.setEnabled(True)
            self.clone_save_btn.setEnabled(True)
            return

        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        process.setProcessEnvironment(env)
        process.setProgram(str(PIPELINE_PYTHON))
        
        args = []
        if not is_frozen:
            args.extend(["-u", str(PIPELINE_PATH)])
        else:
            args.extend(["pipeline"])
            
        args.extend([
            "preview-voice",
            "--voice", "omnivoice:__temp_clone__",
            "--text", test_text,
            "--speaker-id", "__temp_clone__",
            "--output-json", str(result_path)
        ])
        
        process.setArguments(args)
        process.setWorkingDirectory(str(ROOT))
        
        def on_finished(code: int):
            self.clone_test_btn.setEnabled(True)
            self.clone_save_btn.setEnabled(True)
            
            # Khôi phục tệp cấu hình gốc sau khi chạy xong
            if backup_data is not None:
                temp_voices_file.write_text(json.dumps(backup_data, ensure_ascii=False, indent=2), encoding="utf-8")
            elif temp_voices_file.exists():
                try: temp_voices_file.unlink()
                except Exception: pass

            if code != 0 or not result_path.exists():
                self.clone_status_label.setText("Tổng hợp giọng clone thất bại.")
                QMessageBox.warning(self, "Lỗi tổng hợp", "Không thể tạo file nghe thử. Hãy đảm bảo tệp .wav đúng định dạng và mô hình không bị lỗi.")
                return

            try:
                payload = json.loads(result_path.read_text(encoding="utf-8-sig"))
                audio_path = payload.get("outputPath")
                if audio_path and os.path.exists(audio_path):
                    self.clone_status_label.setText("Đang phát âm thanh clone...")
                    self._play_voice_preview_audio(audio_path, "Giọng clone của bạn", self.clone_status_label)
                else:
                    self.clone_status_label.setText("Không tìm thấy file audio output.")
            except Exception as e:
                self.clone_status_label.setText(f"Lỗi đọc kết quả: {e}")

        process.finished.connect(on_finished)
        process.start()
        QTimer.singleShot(180000, process.kill)

    def on_save_clone_voice_clicked(self) -> None:
        name = self.clone_name_edit.text().strip()
        ref_path = self.clone_wav_path_edit.text().strip()
        ref_text = self.clone_ref_text_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập tên giọng clone.")
            return
        if not ref_path or not os.path.exists(ref_path):
            QMessageBox.warning(self, "Thiếu tệp tin", "Vui lòng chọn tệp âm thanh mẫu (.wav) trước khi lưu.")
            return

        # Tạo tên an toàn (chỉ giữ chữ cái và số)
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "", name.replace(" ", "_").lower())
        if not safe_name:
            QMessageBox.warning(self, "Tên không hợp lệ", "Tên giọng nói chứa ký tự không được hỗ trợ. Vui lòng chỉ dùng chữ cái, chữ số và dấu gạch dưới.")
            return

        from gui.config import ROOT
        dest_dir = ensure_dir(ROOT / "config" / "voices" / "omnivoice")
        dest_filename = f"{safe_name}.wav"
        dest_path = dest_dir / dest_filename

        try:
            shutil.copy2(ref_path, dest_path)
        except Exception as e:
            QMessageBox.warning(self, "Lỗi sao chép", f"Không thể lưu file âm thanh mẫu: {e}")
            return

        config_file = ROOT / "config" / "custom_omnivoice_voices.json"
        data = {}
        if config_file.exists():
            try:
                data = json.loads(config_file.read_text(encoding="utf-8"))
            except Exception: pass

        voice_id = f"omnivoice:{safe_name}"
        data[voice_id] = {
            "filename": dest_filename,
            "ref_text": ref_text,
            "label": f"Clone • {name} (OmniVoice)"
        }

        try:
            config_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(self, "Lỗi ghi cấu hình", f"Không thể lưu cấu hình giọng clone: {e}")
            return

        # Cập nhật runtime variables của CLI và GUI để hoạt động tức thì mà không cần restart
        from tools.dub_studio.config import CUSTOM_OMNIVOICE_VOICES as cli_custom_voices
        from gui.config import SHORT_VOICE_LABELS as gui_short_labels, VOICE_LABELS as gui_labels, VOICE_OPTIONS as gui_options, INTRO_TTS_OPTIONS as gui_intro_options
        
        cli_custom_voices[voice_id] = data[voice_id]
        
        label_text = f"Clone • {name}"
        gui_short_labels[voice_id] = label_text
        gui_labels[voice_id] = f"OmniVoice • {label_text}"
        
        if all(voice_id != opt[0] for opt in gui_options):
            gui_options.append((voice_id, f"OmniVoice • {label_text}"))
            gui_intro_options.append((voice_id, f"OmniVoice • {label_text}"))

        self.clone_status_label.setText(f"Đã lưu thành công giọng clone: {name}!")
        self.refresh_voice_options_in_comboboxes()
        QMessageBox.information(self, "Thành công", f"Đã lưu thành công giọng đọc '{name}'. Bạn có thể chọn giọng này cho các nhân vật ở trang chính.")

    def refresh_voice_options_in_comboboxes(self) -> None:
        from gui.config import VOICE_OPTIONS
        for speaker_id, combo in getattr(self, "voice_combo_map", {}).items():
            current_value = self._resolve_voice_combo_value(combo)
            combo.blockSignals(True)
            combo.clear()
            for value, text in self._voice_options_for_speaker({"speakerId": speaker_id, "voicePreset": current_value}):
                combo.addItem(text, value)
            self._set_combo_value(combo, current_value)
            combo.blockSignals(False)

        for combo_name in ("main_intro_voice_combo", "intro_voice_combo", "default_voice_combo"):
            combo = getattr(self, combo_name, None)
            if combo is not None:
                current_value = self._resolve_voice_combo_value(combo)
                combo.blockSignals(True)
                combo.clear()
                for value, text in VOICE_OPTIONS:
                    combo.addItem(text, value)
                self._set_combo_value(combo, current_value)
                combo.blockSignals(False)
