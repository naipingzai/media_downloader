"""主题管理 —— 暗色 / 亮色 切换。

通过:
1. QPalette (Qt 原生控件)
2. 动态加载 styles_dark.qss / styles_light.qss
3. setProperty("theme", "dark"|"light") 让子 widget 在 paintEvent 中自取

子 widget 使用 palette 时, theme="dark" 背景 #1e293b, theme="light" 背景 #ffffff。
"""
from __future__ import annotations
from pathlib import Path
import sys
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


RES = Path(__file__).resolve().parent


def _palette_dark() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor(15, 23, 42))           # #0f172a
    p.setColor(QPalette.WindowText, QColor(226, 232, 240))     # #e2e8f0
    p.setColor(QPalette.Base, QColor(30, 41, 59))              # #1e293b
    p.setColor(QPalette.AlternateBase, QColor(15, 23, 42))
    p.setColor(QPalette.Text, QColor(226, 232, 240))
    p.setColor(QPalette.Button, QColor(51, 65, 85))            # #334155
    p.setColor(QPalette.ButtonText, QColor(226, 232, 240))
    p.setColor(QPalette.Highlight, QColor(56, 189, 248))       # #38bdf8
    p.setColor(QPalette.HighlightedText, QColor(15, 23, 42))
    return p


def _palette_light() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor(248, 250, 252))         # #f8fafc
    p.setColor(QPalette.WindowText, QColor(15, 23, 42))        # #0f172a
    p.setColor(QPalette.Base, QColor(255, 255, 255))           # #ffffff
    p.setColor(QPalette.AlternateBase, QColor(248, 250, 252))
    p.setColor(QPalette.Text, QColor(15, 23, 42))
    p.setColor(QPalette.Button, QColor(226, 232, 240))         # #e2e8f0
    p.setColor(QPalette.ButtonText, QColor(15, 23, 42))
    p.setColor(QPalette.Highlight, QColor(59, 130, 246))       # #3b82f6
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    return p


PALETTES = {"dark": _palette_dark, "light": _palette_light}
THEME_FILES = {"dark": "styles_dark.qss", "light": "styles_light.qss"}


def _resolve_style_path(name: str) -> Path | None:
    """查找 QSS 文件, 兼容 PyInstaller 冻结。"""
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "ui" / "gui" / "resources" / name)
        candidates.append(Path(sys.argv[0]).resolve().parent / "ui" / "gui" / "resources" / name)
    candidates.append(RES / name)
    for p in candidates:
        if p.is_file():
            return p
    return None


# 全局共享: checkbox 对勾图标路径 (launcher 设置, theme.apply 时替换占位符)
_check_icon_url: str = ""


def set_check_icon_url(url: str):
    global _check_icon_url
    _check_icon_url = url or ""


def apply_theme(app: QApplication, theme: str = "dark", check_icon_url: str | None = None):
    """切换主题; theme = 'dark' | 'light'."""
    theme = "dark" if theme != "light" else "light"
    app.setProperty("theme", theme)
    app.setPalette(PALETTES[theme]())
    if check_icon_url is not None:
        set_check_icon_url(check_icon_url)
    qss_path = _resolve_style_path(THEME_FILES[theme])
    if qss_path and qss_path.is_file():
        qss = qss_path.read_text(encoding="utf-8")
        if _check_icon_url:
            qss = qss.replace("{{CHECK_ICON}}", _check_icon_url)
        else:
            qss = qss.replace('image: url("{{CHECK_ICON}}");', "")
        app.setStyleSheet(qss)
    else:
        app.setStyleSheet("")


def current_theme(app: QApplication) -> str:
    return app.property("theme") or "dark"


def toggle_theme(app: QApplication) -> str:
    """切换主题, 返回新主题。"""
    new = "light" if current_theme(app) == "dark" else "dark"
    apply_theme(app, new)
    return new
