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
        try:
            self.progress_signal.emit(10, "Đang kiểm tra kết nối tới server...")
            # For now we pull main.zip from GitHub as a universal patch since source changes are standard.
            # Repo: siver2001/CapCut-Mate---Dub-Studio
            zip_url = "https://github.com/siver2001/CapCut-Mate---Dub-Studio/archive/refs/heads/main.zip"
            
            # Using custom temporary directories within workspace
            with tempfile.TemporaryDirectory(dir=str(self.root_path)) as tmp_dir:
                tmp_zip = Path(tmp_dir) / "main.zip"
                
                self.progress_signal.emit(30, "Đang tải gói cập nhật mới nhất từ GitHub...")
                # Download with chunk tracking if possible, or simple urlretrieve
                urllib.request.urlretrieve(zip_url, str(tmp_zip))
                
                self.progress_signal.emit(60, "Đang trích xuất dữ liệu cập nhật...")
                extract_path = Path(tmp_dir) / "extracted"
                extract_path.mkdir(exist_ok=True)
                
                with zipfile.ZipFile(tmp_zip, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                
                # The GitHub ZIP contains a folder like CapCut-Mate---Dub-Studio-main
                extracted_folders = [p for p in extract_path.iterdir() if p.is_dir()]
                if not extracted_folders:
                    self.finished_signal.emit(False, "Không tìm thấy nội dung cập nhật sau khi giải nén.")
                    return
                
                update_src = extracted_folders[0]
                
                self.progress_signal.emit(80, "Đang cài đặt các thay đổi...")
                
                # Walk through update source and copy files selectively
                # We skip: temp/, output/, config/, .git/
                skip_dirs = {"temp", "output", "config", ".git", "__pycache__", ".github", ".gemini"}
                
                for src_item in update_src.rglob("*"):
                    if src_item.is_file():
                        # Compute relative path to copy to target
                        rel_path = src_item.relative_to(update_src)
                        
                        # Check if any skip directory is in the rel_path parts
                        if any(skip_dir in rel_path.parts for skip_dir in skip_dirs):
                            continue
                            
                        target_file = self.root_path / rel_path
                        # Create parent directories if they don't exist
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Overwrite target file
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
