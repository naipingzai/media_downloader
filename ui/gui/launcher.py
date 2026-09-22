"""PySide6 GUI 启动器。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _find_check_icon() -> Path | None:
    """查找 checkbox 对勾图标（兼容 PyInstaller 冻结）。"""
    candidates = []
    if getattr(sys, "frozen", False):
        # PyInstaller: 资源在 _MEIPASS/static 或可执行文件同目录 static
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "static" / "checkbox_check.svg")
        candidates.append(Path(sys.argv[0]).resolve().parent / "static" / "checkbox_check.svg")
    else:
        candidates.append(ROOT / "static" / "checkbox_check.svg")
    for p in candidates:
        if p.is_file():
            return p
    return None


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

    # 加载 QSS（dev 模式在源码目录，冻结模式在 _MEIPASS）
    style_path = None
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate = Path(meipass) / "ui" / "gui" / "resources" / "styles.qss"
            if candidate.is_file():
                style_path = candidate
    if style_path is None:
        style_path = ROOT / "ui" / "gui" / "resources" / "styles.qss"

    if style_path.is_file():
        qss = style_path.read_text(encoding="utf-8")
        # 替换 checkbox 对勾图标占位符为绝对路径
        icon = _find_check_icon()
        if icon:
            qss = qss.replace("{{CHECK_ICON}}", icon.as_posix())
        else:
            # 未找到图标时移除该行，避免显示破图
            qss = qss.replace('image: url("{{CHECK_ICON}}");', "")
        app.setStyleSheet(qss)

    from .main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
