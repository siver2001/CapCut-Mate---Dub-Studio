import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import QTimer, Qt
from gui.utils import apply_app_theme
from gui.main_window import DubStudioWindow


class ShortcutPromptDialog(QDialog):
    def __init__(self, parent=None, logo_path: str = None):
        super().__init__(parent)
        self.setWindowTitle("Thiết lập lối tắt")
        self.setFixedSize(420, 240)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Header / Icon + Title layout
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        self.logo_label = QLabel()
        if logo_path and os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)
        else:
            self.logo_label.setText("🚀")
            self.logo_label.setStyleSheet("font-size: 32px;")
        header_layout.addWidget(self.logo_label)
        
        title_label = QLabel("Tạo lối tắt ứng dụng")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #f8fafc;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Message description
        msg_label = QLabel("Bạn có muốn tạo biểu tượng lối tắt (Desktop Shortcut) để truy cập nhanh CapCut-Mate Dub Studio từ màn hình máy tính không?")
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet("font-size: 13px; line-height: 1.5; color: #cbd5e1;")
        layout.addWidget(msg_label)
        
        layout.addStretch()
        
        # Buttons layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()
        
        self.no_btn = QPushButton("Để sau")
        self.no_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.no_btn.setFixedSize(100, 36)
        self.no_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #f1f5f9;
                border: 1px solid #475569;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #475569;
                border-color: #64748b;
            }
            QPushButton:pressed {
                background-color: #1e293b;
            }
        """)
        
        self.yes_btn = QPushButton("Đồng ý và Tạo")
        self.yes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.yes_btn.setFixedSize(140, 36)
        self.yes_btn.setStyleSheet("""
            QPushButton {
                background-color: #db2777;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #ec4899;
            }
            QPushButton:pressed {
                background-color: #be185d;
            }
        """)
        
        btn_layout.addWidget(self.no_btn)
        btn_layout.addWidget(self.yes_btn)
        layout.addLayout(btn_layout)
        
        self.yes_btn.clicked.connect(self.accept)
        self.no_btn.clicked.connect(self.reject)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                border: 1px solid #1e293b;
            }
        """)




def run_self_test() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication([])
    apply_app_theme(app)
    window = DubStudioWindow()
    window.show()
    QTimer.singleShot(120, app.quit)
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ứng dụng desktop PyQt6 cho Dub Studio."
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Khởi động giao diện ở chế độ offscreen rồi thoát nhanh.",
    )
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
        
    if os.name == 'nt':
        import ctypes
        myappid = 'capcutmate.dubstudio.desktop.1.0.0'
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except AttributeError:
            pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_app_theme(app)
    
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")
    if os.path.exists(logo_path):
        app.setWindowIcon(QIcon(logo_path))
    window = DubStudioWindow()
    window.show()

    # ---------------------------------------------------------
    # Ask to create Desktop Shortcut on first launch (Windows only)
    # ---------------------------------------------------------
    if os.name == 'nt':
        marker = ROOT / "config" / "shortcut_setup.done"
        if not marker.exists():
            from PyQt6.QtWidgets import QMessageBox
            # Ensure the config folder exists
            (ROOT / "config").mkdir(parents=True, exist_ok=True)
            
            # Create high-quality icon.ico from logo.png if it doesn't exist
            icon_path = ROOT / "assets" / "icon.ico"
            if not icon_path.exists() and os.path.exists(logo_path):
                try:
                    from PIL import Image
                    img = Image.open(logo_path)
                    img.save(icon_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
                except Exception:
                    pass

            dialog = ShortcutPromptDialog(window, logo_path)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                try:
                    import subprocess
                    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
                    target = os.path.abspath(sys.executable)
                    w_dir = os.path.dirname(target)
                    icon = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icon.ico"))
                    shortcut_path = os.path.join(desktop, "CapCutMate.lnk")
                    
                    ps_cmd = (
                        f'$ws = New-Object -ComObject WScript.Shell; '
                        f'$s = $ws.CreateShortcut("{shortcut_path}"); '
                        f'$s.TargetPath = "{target}"; '
                        f'$s.WorkingDirectory = "{w_dir}"; '
                        f'$s.IconLocation = "{icon}"; '
                        f'$s.Save()'
                    )
                    
                    creationflags = 0
                    if sys.platform == "win32":
                        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                        
                    subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, creationflags=creationflags)
                except Exception:
                    pass
            # Mark as done so it doesn't pop up again
            try:
                marker.write_text("done", encoding="utf-8")
            except Exception:
                pass

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
