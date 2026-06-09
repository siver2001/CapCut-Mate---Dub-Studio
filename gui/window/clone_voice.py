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
    QFrame,
    QComboBox,
    QProgressBar
)
from gui.utils import ensure_dir, repair_mojibake_text, decode_process_bytes


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
        self.clone_ref_text_edit = QPlainTextEdit()
        self.clone_ref_text_edit.setPlaceholderText("Nhập nội dung tương ứng của tệp âm thanh mẫu (khuyên dùng để tăng độ chính xác, bỏ trống để tự nghe tự phân tích)...")
        self.clone_ref_text_edit.setStyleSheet("""
            QPlainTextEdit {
                background: rgba(15, 23, 42, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                color: #ffffff;
                padding: 8px 12px;
            }
        """)
        self.clone_ref_text_edit.setMaximumHeight(60)
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

        # 5. Thiết bị chạy (Device)
        grid.addWidget(self._field_label("Thiết bị chạy OmniVoice:"), 4, 0)
        self.clone_device_combo = QComboBox()
        self.clone_device_combo.addItem("Auto (Tự động - Ưu tiên GPU)", "auto")
        self.clone_device_combo.addItem("GPU (NVIDIA CUDA)", "cuda")
        self.clone_device_combo.addItem("CPU (Ổn định)", "cpu")
        self.clone_device_combo.setStyleSheet("""
            QComboBox {
                background: rgba(15, 23, 42, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                color: #ffffff;
                padding: 8px 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #0f172a;
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.15);
            }
        """)
        
        # Load initial device setting
        init_device = os.environ.get("DUB_OMNIVOICE_DEVICE", "auto").lower()
        idx = self.clone_device_combo.findData(init_device)
        if idx >= 0:
            self.clone_device_combo.setCurrentIndex(idx)
        self.clone_device_combo.currentIndexChanged.connect(self.on_clone_device_changed)
        grid.addWidget(self.clone_device_combo, 4, 1)

        clone_inner_layout.addLayout(grid)

        # Actions row
        actions = QHBoxLayout()
        actions.setSpacing(12)

        self.clone_save_btn = self._make_button("Lưu giọng", "success")
        self.clone_save_btn.setMinimumHeight(40)
        self.clone_save_btn.clicked.connect(self.on_save_clone_voice_clicked)

        self.clone_test_btn = self._make_button("Clone giọng", "ghost")
        self.clone_test_btn.setMinimumHeight(40)
        self.clone_test_btn.clicked.connect(self.on_test_clone_voice_clicked)
        
        self.clone_replay_btn = self._make_button("Nghe thử", "ghost")
        self.clone_replay_btn.setMinimumHeight(40)
        self.clone_replay_btn.clicked.connect(self.on_replay_clone_voice_clicked)
        self.clone_replay_btn.setEnabled(False)  # Only enabled after a preview is generated

        actions.addWidget(self.clone_save_btn, 1)
        actions.addWidget(self.clone_test_btn, 1)
        actions.addWidget(self.clone_replay_btn, 1)
        clone_inner_layout.addLayout(actions)

        # Progress bar
        self.clone_progress_bar = QProgressBar()
        self.clone_progress_bar.setRange(0, 100)
        self.clone_progress_bar.setValue(0)
        self.clone_progress_bar.setTextVisible(False)
        self.clone_progress_bar.setVisible(False)
        clone_inner_layout.addWidget(self.clone_progress_bar)

        # Status area
        self.clone_status_label = QLabel("Chuẩn bị file .wav, nhập tên và bấm 'Clone giọng' để nghe thử, sau đó bấm 'Lưu giọng' nếu ưng ý.")
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

    def on_clone_device_changed(self) -> None:
        device_val = self.clone_device_combo.currentData()
        self._save_omnivoice_device_setting(device_val)
        self.clone_status_label.setText(f"Đã chuyển thiết bị OmniVoice sang: {self.clone_device_combo.currentText()}")

    def _save_omnivoice_device_setting(self, device_val: str) -> None:
        from gui.config import ROOT
        env_file = ROOT / ".env"
        
        # Update current os.environ at runtime
        os.environ["DUB_OMNIVOICE_DEVICE"] = device_val
        
        lines = []
        if env_file.exists():
            try:
                lines = env_file.read_text(encoding="utf-8-sig").splitlines()
            except Exception:
                pass
                
        updated = False
        new_lines = []
        for raw_line in lines:
            line_stripped = raw_line.strip()
            if line_stripped and not line_stripped.startswith("#") and "=" in line_stripped:
                k, v = line_stripped.split("=", 1)
                k = k.strip()
                if k == "DUB_OMNIVOICE_DEVICE":
                    new_lines.append(f"DUB_OMNIVOICE_DEVICE={device_val}")
                    updated = True
                else:
                    new_lines.append(raw_line)
            else:
                new_lines.append(raw_line)
                
        if not updated:
            new_lines.append(f"DUB_OMNIVOICE_DEVICE={device_val}")
            
        try:
            env_file.write_text("\n".join(new_lines), encoding="utf-8")
        except Exception:
            pass

    def on_test_clone_voice_clicked(self) -> None:
        name = self.clone_name_edit.text().strip()
        ref_path = self.clone_wav_path_edit.text().strip()
        test_text = self.clone_test_text_edit.toPlainText().strip()
        ref_text = self.clone_ref_text_edit.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập tên giọng clone.")
            return
        if not ref_path or not os.path.exists(ref_path):
            QMessageBox.warning(self, "Thiếu tệp tin", "Vui lòng chọn tệp âm thanh mẫu (.wav) trước khi clone giọng.")
            return
        if not test_text:
            QMessageBox.warning(self, "Thiếu văn bản", "Vui lòng nhập văn bản kiểm thử.")
            return

        from gui.config import ROOT
        
        # 1. Prepare temp directory and copy wav file
        dest_dir = ensure_dir(ROOT / "config" / "voices" / "omnivoice")
        temp_wav_filename = "__temp_clone__.wav"
        temp_wav_path = dest_dir / temp_wav_filename
        
        try:
            shutil.copy2(ref_path, temp_wav_path)
        except Exception as e:
            QMessageBox.warning(self, "Lỗi sao chép", f"Không thể chuẩn bị file âm thanh mẫu nghe thử: {e}")
            return

        # 2. Write temp voice config to custom_omnivoice_voices.json so subprocess can resolve it
        config_file = ROOT / "config" / "custom_omnivoice_voices.json"
        data = {}
        if config_file.exists():
            try:
                data = json.loads(config_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        
        voice_id = "omnivoice:__temp_clone__"
        safe_name = "__temp_clone__"
        
        data[voice_id] = {
            "filename": temp_wav_filename,
            "ref_text": ref_text,
            "label": "Clone • Temp"
        }
        
        try:
            config_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(self, "Lỗi ghi cấu hình", f"Không thể tạo cấu hình nghe thử tạm thời: {e}")
            return
            
        # Update current GUI memory state
        from tools.dub_studio.config import CUSTOM_OMNIVOICE_VOICES as cli_custom_voices
        cli_custom_voices[voice_id] = data[voice_id]

        self.clone_status_label.setText("Đang khởi tạo mô hình OmniVoice và tổng hợp giọng clone...")
        self.clone_test_btn.setEnabled(False)
        self.clone_save_btn.setEnabled(False)
        self.clone_replay_btn.setEnabled(False)

        # Run pipeline preview-voice
        from gui.config import PIPELINE_PATH, PIPELINE_PYTHON, is_frozen
        preview_dir = ensure_dir(ROOT / "temp" / "dub_studio" / "voice_preview")
        result_path = preview_dir / "clone_preview_status.json"

        process = QProcess(self)
        process.stdout_data = []
        process.stderr_data = []
        
        def read_stdout():
            process.stdout_data.append(process.readAllStandardOutput().data())
        def read_stderr():
            process.stderr_data.append(process.readAllStandardError().data())
            
        process.readyReadStandardOutput.connect(read_stdout)
        process.readyReadStandardError.connect(read_stderr)
        
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUNBUFFERED", "1")
        
        # Pass device setting from combo
        device_val = self.clone_device_combo.currentData()
        env.insert("DUB_OMNIVOICE_DEVICE", device_val)
        
        process.setProcessEnvironment(env)
        process.setProgram(str(PIPELINE_PYTHON))
        
        args = []
        if not is_frozen:
            args.extend(["-u", str(PIPELINE_PATH)])
        else:
            args.extend(["pipeline"])
            
        args.extend([
            "preview-voice",
            "--voice", voice_id,
            "--text", test_text,
            "--speaker-id", safe_name,
            "--output-json", str(result_path)
        ])
        
        process.setArguments(args)
        process.setWorkingDirectory(str(ROOT))
        
        def on_finished(code: int):
            self.clone_progress_bar.setVisible(False)
            self.clone_progress_bar.setRange(0, 100)
            self.clone_test_btn.setEnabled(True)
            self.clone_save_btn.setEnabled(True)
            
            stdout_str = decode_process_bytes(b"".join(process.stdout_data))
            stderr_str = decode_process_bytes(b"".join(process.stderr_data))
            
            if code != 0 or not result_path.exists():
                self.clone_status_label.setText("Tổng hợp giọng clone thất bại.")
                try:
                    error_log_path = preview_dir / "clone_error.log"
                    error_log_path.write_text(
                        f"Exit Code: {code}\n"
                        f"--- STDERR ---\n{stderr_str}\n"
                        f"--- STDOUT ---\n{stdout_str}\n",
                        encoding="utf-8"
                    )
                except Exception:
                    pass
                
                err_msg = stderr_str.strip() or stdout_str.strip() or "Không nhận dạng được lỗi (quá thời gian hoặc tiến trình bị tắt đột ngột)."
                detailed_msg = f"Không thể thực hiện clone giọng. Hãy đảm bảo tệp .wav đúng định dạng và mô hình không bị lỗi.\n\nChi tiết lỗi:\n{err_msg}"
                QMessageBox.warning(self, "Lỗi tổng hợp", repair_mojibake_text(detailed_msg))
                return

            try:
                payload = json.loads(result_path.read_text(encoding="utf-8-sig"))
                audio_path = payload.get("outputPath")
                
                if audio_path and os.path.exists(audio_path):
                    self._last_clone_preview_path = audio_path
                    self.clone_replay_btn.setEnabled(True)
                    self.clone_status_label.setText("Đang phát âm thanh clone...")
                    self._play_voice_preview_audio(audio_path, f"Giọng clone {name}", self.clone_status_label)
                else:
                    self.clone_status_label.setText("Không tìm thấy file audio output.")
            except Exception as e:
                self.clone_status_label.setText(f"Lỗi đọc kết quả: {e}")

        process.finished.connect(on_finished)
        self.clone_progress_bar.setRange(0, 0)
        self.clone_progress_bar.setVisible(True)
        process.start()
        QTimer.singleShot(180000, process.kill)

    def on_replay_clone_voice_clicked(self) -> None:
        audio_path = getattr(self, "_last_clone_preview_path", None)
        if audio_path and os.path.exists(audio_path):
            self.clone_status_label.setText("Đang phát âm thanh nghe thử...")
            self._play_voice_preview_audio(audio_path, "Giọng clone phát lại", self.clone_status_label)
        else:
            self.clone_status_label.setText("Không tìm thấy file âm thanh nghe thử.")
            self.clone_replay_btn.setEnabled(False)

    def on_save_clone_voice_clicked(self) -> None:
        name = self.clone_name_edit.text().strip()
        ref_path = self.clone_wav_path_edit.text().strip()
        ref_text = self.clone_ref_text_edit.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập tên giọng clone.")
            return
        if not ref_path or not os.path.exists(ref_path):
            QMessageBox.warning(self, "Thiếu tệp tin", "Vui lòng chọn tệp âm thanh mẫu (.wav) trước khi lưu.")
            return

        if not ref_text:
            self.clone_status_label.setText("Đang tự động phân tích và nhận diện văn bản từ tệp mẫu...")
            self.clone_test_btn.setEnabled(False)
            self.clone_save_btn.setEnabled(False)
            self.clone_replay_btn.setEnabled(False)
            
            from gui.config import PIPELINE_PATH, PIPELINE_PYTHON, ROOT, is_frozen
            preview_dir = ensure_dir(ROOT / "temp" / "dub_studio" / "voice_preview")
            transcribe_result_path = preview_dir / "transcribe_result.json"
            if transcribe_result_path.exists():
                try: transcribe_result_path.unlink()
                except Exception: pass

            process = QProcess(self)
            process.stdout_data = []
            process.stderr_data = []
            
            def read_stdout():
                process.stdout_data.append(process.readAllStandardOutput().data())
            def read_stderr():
                process.stderr_data.append(process.readAllStandardError().data())
                
            process.readyReadStandardOutput.connect(read_stdout)
            process.readyReadStandardError.connect(read_stderr)
            
            env = QProcessEnvironment.systemEnvironment()
            env.insert("PYTHONIOENCODING", "utf-8")
            env.insert("PYTHONUNBUFFERED", "1")
            process.setProcessEnvironment(env)
            process.setProgram(str(PIPELINE_PYTHON))
            
            args = []
            if not is_frozen:
                args.extend(["-u", str(PIPELINE_PATH)])
            else:
                args.extend(["pipeline"])
                
            args.extend([
                "transcribe-audio",
                "--audio", ref_path,
                "--output-json", str(transcribe_result_path)
            ])
            
            process.setArguments(args)
            process.setWorkingDirectory(str(ROOT))
            
            def on_transcribe_finished(code: int):
                self.clone_progress_bar.setVisible(False)
                self.clone_progress_bar.setRange(0, 100)
                self.clone_test_btn.setEnabled(True)
                self.clone_save_btn.setEnabled(True)
                if getattr(self, "_last_clone_preview_path", None) and os.path.exists(self._last_clone_preview_path):
                    self.clone_replay_btn.setEnabled(True)
                
                stdout_str = decode_process_bytes(b"".join(process.stdout_data))
                stderr_str = decode_process_bytes(b"".join(process.stderr_data))
                
                transcribed_text = ""
                if code == 0 and transcribe_result_path.exists():
                    try:
                        payload = json.loads(transcribe_result_path.read_text(encoding="utf-8-sig"))
                        transcribed_text = payload.get("text", "").strip()
                    except Exception as e:
                        self.clone_status_label.setText(f"Lỗi đọc kết quả phân tích: {e}")
                
                if not transcribed_text:
                    self.clone_status_label.setText("Không thể tự động nhận dạng văn bản mẫu.")
                    try:
                        error_log_path = preview_dir / "transcribe_error.log"
                        error_log_path.write_text(
                            f"Exit Code: {code}\n"
                            f"--- STDERR ---\n{stderr_str}\n"
                            f"--- STDOUT ---\n{stdout_str}\n",
                            encoding="utf-8"
                        )
                    except Exception:
                        pass
                    err_msg = stderr_str.strip() or stdout_str.strip() or "Không nhận dạng được lỗi (quá thời gian hoặc tiến trình bị tắt đột ngột)."
                    QMessageBox.warning(self, "Lỗi nhận dạng", f"Không thể tự động nhận dạng văn bản mẫu.\n\nChi tiết lỗi:\n{err_msg}")
                    return
                else:
                    self.clone_ref_text_edit.setPlainText(transcribed_text)
                    self.clone_status_label.setText("Đã tự động nhận diện văn bản mẫu thành công!")
                
                self._proceed_save_clone_voice(name, ref_path, transcribed_text)

            process.finished.connect(on_transcribe_finished)
            self.clone_progress_bar.setRange(0, 0)
            self.clone_progress_bar.setVisible(True)
            process.start()
            QTimer.singleShot(180000, process.kill)
            return

        self._proceed_save_clone_voice(name, ref_path, ref_text)

    def _proceed_save_clone_voice(self, name: str, ref_path: str, ref_text: str) -> None:
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

        # Clean up temporary clone voice if it exists
        temp_voice_id = "omnivoice:__temp_clone__"
        data.pop(temp_voice_id, None)
        
        temp_wav_path = dest_dir / "__temp_clone__.wav"
        if temp_wav_path.exists():
            try:
                temp_wav_path.unlink()
            except Exception:
                pass

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
        
        cli_custom_voices.pop(temp_voice_id, None)
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
