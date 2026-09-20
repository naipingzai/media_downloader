"""PySide6 GUI 启动器。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def launch():
    print("[DEBUG] launch() called")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("请安装 PySide6: pip install PySide6")
        return

    print("[DEBUG] Creating QApplication")
    app = QApplication(sys.argv)
    app.setApplicationName("MediaDownloader")

    from .resources.theme import apply_theme
    apply_theme(app, dark=True)

    style_path = ROOT / "ui" / "gui" / "resources" / "styles.qss"
    if style_path.is_file():
        app.setStyleSheet(style_path.read_text(encoding="utf-8"))
        print("[DEBUG] Styles loaded")

    print("[DEBUG] Importing MainWindow")
    from .main_window import MainWindow
    print("[DEBUG] Creating MainWindow")
    window = MainWindow()
    print(f"[DEBUG] MainWindow created, id={id(window)}, parent={window.parent()}")
    print(f"[DEBUG] Window count before show: {len(app.topLevelWidgets())}")
    window.show()
    print(f"[DEBUG] Window count after show: {len(app.topLevelWidgets())}")
    for i, w in enumerate(app.topLevelWidgets()):
        print(f"  Widget {i}: {w.__class__.__name__} id={id(w)} visible={w.isVisible()}")
    print("[DEBUG] Entering app.exec()")
    sys.exit(app.exec())
