import os
import sys
import shutil
import urllib.request
import zipfile
import tempfile
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QProgressDialog
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class UpdateThread(QThread):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, is_frozen: bool, root_path: Path):
        super().__init__()
        self.is_frozen = is_frozen
        self.root_path = root_path

    def run(self):
        # 1. Try to update via Git if running from source (has .git directory)
        if (self.root_path / ".git").exists():
            try:
                self.progress_signal.emit(20, "Phát hiện thư mục git. Đang fetch từ GitHub...")
                # Run git fetch
                fetch_res = subprocess.run(
                    ["git", "fetch", "origin"],
                    cwd=str(self.root_path),
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if fetch_res.returncode != 0:
                    raise RuntimeError(fetch_res.stderr or fetch_res.stdout)

                self.progress_signal.emit(60, "Đang pull mã nguồn mới nhất từ GitHub...")
                # Run git pull
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
                # If git fails (e.g. because of local changes conflict), we log it and try zip
                self.progress_signal.emit(35, f"Git pull thất bại ({str(git_err).strip()}). Đang thử cách tải Zip...")

        # 2. Traditional ZIP download method
        try:
            self.progress_signal.emit(40, "Đang kiểm tra kết nối tới server...")
            zip_url = "https://github.com/siver2001/CapCut-Mate---Dub-Studio/archive/refs/heads/main.zip"
            
            with tempfile.TemporaryDirectory(dir=str(self.root_path)) as tmp_dir:
                tmp_zip = Path(tmp_dir) / "main.zip"
                
                self.progress_signal.emit(50, "Đang tải gói cập nhật mới nhất từ GitHub...")
                try:
                    urllib.request.urlretrieve(zip_url, str(tmp_zip))
                except urllib.error.HTTPError as http_err:
                    if http_err.code == 404:
                        raise RuntimeError(
                            "HTTP Error 404: Not Found.\n"
                            "Kho lưu trữ GitHub hiện tại là riêng tư (private).\n"
                            "Vui lòng cài đặt Git và cấu hình quyền để cập nhật ứng dụng tự động."
                        ) from http_err
                    raise
                
                self.progress_signal.emit(70, "Đang trích xuất dữ liệu cập nhật...")
                extract_path = Path(tmp_dir) / "extracted"
                extract_path.mkdir(exist_ok=True)
                
                with zipfile.ZipFile(tmp_zip, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                
                extracted_folders = [p for p in extract_path.iterdir() if p.is_dir()]
                if not extracted_folders:
                    self.finished_signal.emit(False, "Không tìm thấy nội dung cập nhật sau khi giải nén.")
                    return
                
                update_src = extracted_folders[0]
                
                self.progress_signal.emit(85, "Đang cài đặt các thay đổi...")
                
                skip_dirs = {"temp", "output", "config", ".git", "__pycache__", ".github", ".gemini"}
                
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
        "Bạn có muốn kiểm tra và tải xuống phiên bản mới nhất từ GitHub không?\nQuá trình này sẽ không ảnh hưởng đến dữ liệu models hoặc cache đã tải trước đó.",
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
            QMessageBox.information(parent_widget, "Thành công", msg)
        else:
            QMessageBox.warning(parent_widget, "Lỗi cập nhật", msg)

    thread.progress_signal.connect(on_progress)
    thread.finished_signal.connect(on_finished)
    
    # Run the thread
    thread.start()
    # Keep reference to avoid garbage collection
    parent_widget._update_thread = thread
