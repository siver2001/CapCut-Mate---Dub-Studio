import os
import sys
import shutil
import urllib.request
import urllib.error
import zipfile
import tempfile
import subprocess
import json
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QApplication
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from gui.config import APP_VERSION

class UpdateThread(QThread):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, is_frozen: bool, root_path: Path):
        super().__init__()
        self.is_frozen = is_frozen
        self.root_path = root_path

    def is_newer_version(self, local: str, remote: str) -> bool:
        try:
            l_parts = [int(x) for x in local.split(".")]
            r_parts = [int(x) for x in remote.split(".")]
            # Pad with zeros if versions have different lengths
            max_len = max(len(l_parts), len(r_parts))
            l_parts += [0] * (max_len - len(l_parts))
            r_parts += [0] * (max_len - len(r_parts))
            return r_parts > l_parts
        except Exception:
            return False

    def run(self):
        # 1. Check Version First
        self.progress_signal.emit(5, "Đang kết nối máy chủ kiểm tra phiên bản...")
        remote_ver = None
        try:
            # Try to fetch version.json from main branch
            ver_url = "https://raw.githubusercontent.com/siver2001/CapCut-Mate---Dub-Studio/main/config/version.json"
            req = urllib.request.Request(ver_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode('utf-8'))
                remote_ver = data.get("version")
        except Exception as ver_err:
            self.progress_signal.emit(10, f"Không thể kiểm tra phiên bản ({str(ver_err).strip()}). Tiếp tục tiến trình...")

        if remote_ver:
            self.progress_signal.emit(15, f"Tìm thấy phiên bản trên máy chủ: {remote_ver} (Cục bộ: {APP_VERSION}). Đang tiến hành đồng bộ mã nguồn mới nhất...")
        else:
            self.progress_signal.emit(15, f"Chuẩn bị đồng bộ mã nguồn mới nhất từ GitHub...")

        # 2. Check Write Permission
        self.progress_signal.emit(20, "Kiểm tra quyền ghi vào thư mục cài đặt...")
        try:
            test_file = self.root_path / f".write_test_{os.getpid()}"
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
        except PermissionError:
            self.finished_signal.emit(
                False,
                "Không có quyền ghi vào thư mục cài đặt.\n"
                "Vui lòng tắt ứng dụng và khởi chạy lại bằng quyền Administrator (Run as Administrator) để cập nhật."
            )
            return
        except Exception as e:
            self.finished_signal.emit(False, f"Lỗi kiểm tra quyền ghi: {str(e)}")
            return

        # 3. Source update via Git (only if NOT frozen and has .git folder)
        if not self.is_frozen and (self.root_path / ".git").exists():
            try:
                self.progress_signal.emit(30, "Phát hiện thư mục git. Đang fetch từ GitHub...")
                fetch_res = subprocess.run(
                    ["git", "fetch", "origin"],
                    cwd=str(self.root_path),
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if fetch_res.returncode != 0:
                    raise RuntimeError(fetch_res.stderr or fetch_res.stdout)

                self.progress_signal.emit(70, "Đang pull mã nguồn mới nhất...")
                pull_res = subprocess.run(
                    ["git", "pull", "origin", "main"],
                    cwd=str(self.root_path),
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if pull_res.returncode != 0:
                    raise RuntimeError(pull_res.stderr or pull_res.stdout)

                self.progress_signal.emit(100, "Hoàn tất cập nhật.")
                self.finished_signal.emit(True, "Cập nhật thành công qua Git! Vui lòng khởi động lại ứng dụng.")
                return
            except Exception as git_err:
                self.progress_signal.emit(35, f"Git pull thất bại ({str(git_err).strip()}). Đang thử cách tải ZIP...")

        # 4. ZIP Update Method
        try:
            # Both frozen and non-frozen download the source repository ZIP for Hot Updates
            zip_url = "https://github.com/siver2001/CapCut-Mate---Dub-Studio/archive/refs/heads/main.zip"
            if self.is_frozen:
                self.progress_signal.emit(40, "Đang chuẩn bị tải gói cập nhật mã nguồn...")
            else:
                self.progress_signal.emit(40, "Đang chuẩn bị tải mã nguồn mới nhất...")

            with tempfile.TemporaryDirectory(dir=str(self.root_path)) as tmp_dir:
                tmp_zip = Path(tmp_dir) / "update.zip"
                
                self.progress_signal.emit(50, "Đang tải gói cập nhật từ GitHub...")
                try:
                    req = urllib.request.Request(zip_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=30) as response, open(tmp_zip, 'wb') as out_file:
                        shutil.copyfileobj(response, out_file)
                except urllib.error.HTTPError as http_err:
                    if http_err.code == 404:
                        raise RuntimeError(
                            "HTTP Error 404: Kho lưu trữ GitHub riêng tư hoặc sai đường dẫn."
                        ) from http_err
                    raise
                
                self.progress_signal.emit(70, "Đang giải nén dữ liệu cập nhật...")
                extract_path = Path(tmp_dir) / "extracted"
                extract_path.mkdir(exist_ok=True)
                
                with zipfile.ZipFile(tmp_zip, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                
                # Check for root source folder
                extracted_folders = [p for p in extract_path.iterdir() if p.is_dir()]
                if not extracted_folders:
                    self.finished_signal.emit(False, "Không tìm thấy nội dung cập nhật sau khi giải nén.")
                    return
                update_src = extracted_folders[0]

                self.progress_signal.emit(85, "Đang chuẩn bị cài đặt các thay đổi...")
                
                def should_skip_path(rel_path: Path) -> bool:
                    # Exclude temporary, dev, and output folders
                    if any(d in rel_path.parts for d in ("temp", "output", ".git", "__pycache__", ".github", ".gemini")):
                        return True
                    # Exclude user configuration files inside config folder to preserve user voices/tokens
                    if "config" in rel_path.parts:
                        if "voices" in rel_path.parts:
                            return True
                        if rel_path.name in ("custom_cloud_voices.json", "custom_omnivoice_voices.json", "shortcut_setup.done"):
                            return True
                    return False

                if self.is_frozen:
                    # For packaged EXE: We must copy files using a detached batch script after the app closes
                    # We copy the extracted folder to a persistent temp update folder so the batch script can read it
                    persistent_temp_update = self.root_path / "temp" / "update_staging"
                    if persistent_temp_update.exists():
                        shutil.rmtree(persistent_temp_update, ignore_errors=True)
                    persistent_temp_update.mkdir(parents=True, exist_ok=True)
                    
                    # Copy update_src to persistent_temp_update (excluding local user folders if they are in the zip)
                    for src_item in update_src.rglob("*"):
                        if src_item.is_file():
                            rel_path = src_item.relative_to(update_src)
                            if should_skip_path(rel_path):
                                continue
                            target_file = persistent_temp_update / rel_path
                            target_file.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src_item, target_file)

                    # Create update.bat
                    bat_path = self.root_path.parent / f"update_capcutmate_{os.getpid()}.bat"
                    bat_content = f"""@echo off
chcp 65001 > nul
echo ==================================================
echo   Dang cap nhat CapCut Mate... Vui long cho.
echo ==================================================
echo.
echo Dang cho ung dung goc dong...
taskkill /f /im CapCutMate.exe > nul 2>&1
timeout /t 3 /nobreak > nul

echo.
echo Dang sao chep cac file cap nhat...
robocopy "{persistent_temp_update}" "{self.root_path}" /E /R:3 /W:1 /XD temp output .git .github .gemini > nul

echo.
echo Dang don dep...
rd /s /q "{persistent_temp_update}"

echo.
echo Cap nhat hoan tat! Dang khoi dong lai ung dung...
start "" "{self.root_path}\\CapCutMate.exe"
del "%~f0"
"""
                    bat_path.write_text(bat_content, encoding="utf-8")
                    
                    # Run detached batch script
                    creationflags = 0
                    if os.name == 'nt':
                        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
                    
                    subprocess.Popen(
                        [str(bat_path)],
                        creationflags=creationflags,
                        shell=True
                    )
                    
                    self.progress_signal.emit(100, "Hoàn tất chuẩn bị cập nhật.")
                    self.finished_signal.emit(True, "RESTART_REQUIRED")
                else:
                    # For source code: We can copy files directly using Python
                    for src_item in update_src.rglob("*"):
                        if src_item.is_file():
                            rel_path = src_item.relative_to(update_src)
                            
                            if should_skip_path(rel_path):
                                continue
                                
                            target_file = self.root_path / rel_path
                            target_file.parent.mkdir(parents=True, exist_ok=True)
                            
                            shutil.copy2(src_item, target_file)
                    
                    self.progress_signal.emit(100, "Hoàn tất cập nhật.")
                    self.finished_signal.emit(True, "Cập nhật thành công! Vui lòng khởi động lại ứng dụng.")
                
        except Exception as e:
            self.finished_signal.emit(False, f"Có lỗi xảy ra trong quá trình cập nhật: {str(e)}")

def trigger_update(parent_widget, is_frozen: bool, root_path: Path):
    """Prompts the user for confirmation and directly downloads/installs the latest code from GitHub main branch."""
    confirm = QMessageBox.question(
        parent_widget,
        "Xác nhận cập nhật",
        "Bạn có muốn tải xuống và cập nhật mã nguồn mới nhất từ GitHub không?\nQuá trình này sẽ đồng bộ ứng dụng của bạn với bản mới nhất trên GitHub mà không ảnh hưởng đến cấu hình/dữ liệu cá nhân.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    if confirm == QMessageBox.StandardButton.Yes:
        run_download_update(parent_widget, is_frozen, root_path)


def run_download_update(parent_widget, is_frozen: bool, root_path: Path):
    """Downloads and installs the update."""
    progress = QProgressDialog("Bắt đầu tải bản cập nhật...", "Hủy", 0, 100, parent_widget)
    progress.setWindowTitle("Cập nhật ứng dụng")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setAutoClose(True)
    progress.setValue(0)
    progress.setMinimumWidth(480)
    
    progress.setStyleSheet("""
        QProgressDialog {
            background-color: #0b0f19;
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 8px;
        }
        QLabel {
            color: #f1f5f9;
            font-size: 13px;
            font-family: "Segoe UI", Arial, sans-serif;
            min-height: 36px;
        }
        QProgressBar {
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 6px;
            background-color: #1e293b;
            text-align: center;
            color: #ffffff;
            font-weight: bold;
            font-size: 11px;
            height: 22px;
        }
        QProgressBar::chunk {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #06b6d4, stop:1 #8b5cf6);
            border-radius: 5px;
        }
        QPushButton {
            background-color: rgba(239, 68, 68, 0.1);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.3);
            padding: 6px 20px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 12px;
            font-family: "Segoe UI", Arial, sans-serif;
            min-width: 80px;
            min-height: 24px;
        }
        QPushButton:hover {
            background-color: rgba(239, 68, 68, 0.2);
            border-color: #ef4444;
        }
        QPushButton:pressed {
            background-color: rgba(239, 68, 68, 0.3);
        }
    """)

    thread = UpdateThread(is_frozen, root_path)

    def on_progress(val, msg):
        progress.setLabelText(msg)
        progress.setValue(val)

    def on_finished(success, msg):
        progress.close()
        if success:
            if msg == "RESTART_REQUIRED":
                QMessageBox.information(
                    parent_widget,
                    "Cập nhật thành công",
                    "Gói cập nhật đã được chuẩn bị thành công.\nỨng dụng sẽ tự động tắt và khởi động lại sau vài giây để hoàn tất cài đặt."
                )
                QApplication.quit()
            else:
                QMessageBox.information(parent_widget, "Thành công", msg)
        else:
            QMessageBox.warning(parent_widget, "Lỗi cập nhật", msg)

    thread.progress_signal.connect(on_progress)
    thread.finished_signal.connect(on_finished)
    thread.start()
    parent_widget._update_thread = thread
