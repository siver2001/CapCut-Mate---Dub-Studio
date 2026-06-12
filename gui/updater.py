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
            if not self.is_newer_version(APP_VERSION, remote_ver):
                self.progress_signal.emit(100, "Phiên bản hiện tại đã là mới nhất.")
                self.finished_signal.emit(True, f"Phiên bản hiện tại ({APP_VERSION}) đã là mới nhất. Không cần cập nhật.")
                return
            else:
                self.progress_signal.emit(15, f"Tìm thấy phiên bản mới: {remote_ver} (Hiện tại: {APP_VERSION})")

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
            if self.is_frozen:
                # URL for packaged version (Release exe ZIP)
                zip_url = "https://github.com/siver2001/CapCut-Mate---Dub-Studio/releases/latest/download/CapCutMate.zip"
                self.progress_signal.emit(40, "Đang chuẩn bị tải bản đóng gói .exe mới nhất...")
            else:
                # URL for source code ZIP
                zip_url = "https://github.com/siver2001/CapCut-Mate---Dub-Studio/archive/refs/heads/main.zip"
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
                        if self.is_frozen:
                            raise RuntimeError(
                                "HTTP Error 404: Bản đóng gói chưa được phát hành trên GitHub Releases.\n"
                                "Vui lòng kiểm tra lại liên kết Releases của dự án."
                            ) from http_err
                        else:
                            raise RuntimeError(
                                "HTTP Error 404: Kho lưu trữ GitHub riêng tư hoặc sai đường dẫn."
                            ) from http_err
                    raise
                
                self.progress_signal.emit(70, "Đang giải nén dữ liệu cập nhật...")
                extract_path = Path(tmp_dir) / "extracted"
                extract_path.mkdir(exist_ok=True)
                
                with zipfile.ZipFile(tmp_zip, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                
                # Check for packaged executable or root source folder
                if self.is_frozen:
                    exe_candidates = list(extract_path.glob("**/CapCutMate.exe"))
                    if not exe_candidates:
                        # Fallback to check for any executable
                        exe_candidates = list(extract_path.glob("**/*.exe"))
                    
                    if not exe_candidates:
                        raise RuntimeError("Không tìm thấy file thực thi CapCutMate.exe trong gói cập nhật.")
                    
                    update_src = exe_candidates[0].parent
                else:
                    extracted_folders = [p for p in extract_path.iterdir() if p.is_dir()]
                    if not extracted_folders:
                        self.finished_signal.emit(False, "Không tìm thấy nội dung cập nhật sau khi giải nén.")
                        return
                    update_src = extracted_folders[0]

                self.progress_signal.emit(85, "Đang chuẩn bị cài đặt các thay đổi...")
                
                skip_dirs = {"temp", "output", "config", ".git", "__pycache__", ".github", ".gemini"}

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
                            if any(skip_dir in rel_path.parts for skip_dir in skip_dirs):
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
robocopy "{persistent_temp_update}" "{self.root_path}" /E /R:3 /W:1 /XD temp output config .git .github .gemini > nul

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
                        creationflags = subprocess.CREATE_NEW_CONSOLE | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                    
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
                            
                            if any(skip_dir in rel_path.parts for skip_dir in skip_dirs):
                                continue
                                
                            target_file = self.root_path / rel_path
                            target_file.parent.mkdir(parents=True, exist_ok=True)
                            
                            shutil.copy2(src_item, target_file)
                    
                    self.progress_signal.emit(100, "Hoàn tất cập nhật.")
                    self.finished_signal.emit(True, "Cập nhật thành công! Vui lòng khởi động lại ứng dụng.")
                
        except Exception as e:
            self.finished_signal.emit(False, f"Có lỗi xảy ra trong quá trình cập nhật: {str(e)}")

def trigger_update(parent_widget, is_frozen: bool, root_path: Path):
    """Checks and performs clean updates without overwriting existing data."""
    confirm = QMessageBox.question(
        parent_widget,
        "Xác nhận cập nhật",
        "Bạn có muốn kiểm tra và tải xuống phiên bản mới nhất từ GitHub không?\nQuá trình này sẽ không ảnh hưởng đến dữ liệu của bạn.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    if confirm != QMessageBox.StandardButton.Yes:
        return

    progress = QProgressDialog("Bắt đầu cập nhật...", "Hủy", 0, 100, parent_widget)
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setAutoClose(True)
    progress.setValue(0)

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
    
    # Run the thread
    thread.start()
    # Keep reference to avoid garbage collection
    parent_widget._update_thread = thread
