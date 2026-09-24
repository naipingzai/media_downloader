"""PySide6 GUI 启动器。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _find_check_icon() -> Path | None:
    """查找 checkbox 对勾图标 (兼容 PyInstaller 冻结)。"""
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "static" / "checkbox_check.svg")
        candidates.append(Path(sys.argv[0]).resolve().parent
                          / "static" / "checkbox_check.svg")
    else:
        candidates.append(ROOT / "static" / "checkbox_check.svg")
    for p in candidates:
        if p.is_file():
            return p
    return None


def _apply_font(app, font_size: int):
    """全局字体设置 (字号由配置决定)。"""
    from PySide6.QtGui import QFont
    font = QFont()
    font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
                      "Noto Sans CJK SC", "WenQuanYi Micro Hei",
                      "Source Han Sans CN"])
    font.setPixelSize(max(10, int(font_size)))
    app.setFont(font)


def launch():
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("请安装 PySide6: pip install PySide6")
        return
    app = QApplication(sys.argv)
    app.setApplicationName("MediaDownloader")
    # 加载配置 → 应用字号
    from shared.core.config import ConfigManager
    cfg = ConfigManager.load()
    _apply_font(app, cfg.font_size)

    icon = _find_check_icon()
    icon_url = icon.as_posix() if icon else ""
    from .resources import theme as _theme
    _theme.set_check_icon_url(icon_url)
    _theme.apply_theme(app, "dark")

    from .main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
