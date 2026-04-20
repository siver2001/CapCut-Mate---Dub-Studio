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
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
