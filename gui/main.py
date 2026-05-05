import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer
from gui.utils import apply_app_theme
from gui.main_window import DubStudioWindow




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

            ans = QMessageBox.question(
                window,
                "Tạo lối tắt Desktop",
                "Bạn có muốn tạo biểu tượng ứng dụng trên màn hình Desktop để truy cập nhanh không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if ans == QMessageBox.StandardButton.Yes:
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
