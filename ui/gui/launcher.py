"""PySide6 GUI 启动器。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def launch():
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("请安装 PySide6: pip install PySide6")
        return

    app = QApplication(sys.argv)
    app.setApplicationName("MediaDownloader")

    from .resources.theme import apply_theme
    apply_theme(app, dark=True)

    from shared.core.i18n import load_lang
    load_lang()

    style_path = ROOT / "ui" / "gui" / "resources" / "styles.qss"
    if style_path.is_file():
        app.setStyleSheet(style_path.read_text(encoding="utf-8"))

    from .main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
