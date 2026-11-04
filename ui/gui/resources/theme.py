"""主题管理 —— 暗色 / 亮色切换与全局字号缩放。

工作方式:
1. QPalette (Qt 原生控件)
2. 动态加载 styles_dark.qss / styles_light.qss
3. QSS 中使用 `{{FS_*}}` 字号占位符; 主题加载时按当前设置生成 pt 值

说明: Qt Style Sheets 不支持 CSS 的 `em` 单位, 因此不能直接在 QSS 中
使用相对字号。本模块在字号变化后重新生成 QSS, 保证 12~20 的界面字号设置
对标题、按钮、输入框和所有组件都真实生效。
"""
from __future__ import annotations

from pathlib import Path
import sys
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication


RES = Path(__file__).resolve().parent

MIN_FONT_SIZE = 12
MAX_FONT_SIZE = 20

# 占位符 → 相对基准字号的倍率
_FONT_RATIOS = {
    "{{FS_TINY}}": 0.80,
    "{{FS_XS}}": 0.86,
    "{{FS_SM}}": 0.93,
    "{{FS_MD}}": 1.00,
    "{{FS_LG}}": 1.08,
    "{{FS_XL}}": 1.15,
    "{{FS_TITLE}}": 1.30,
}


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


def _clamp_font_size(value: int | float) -> int:
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        value = 14
    return max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, value))


def _base_point_size(font_size: int) -> int:
    """配置值 12~20 映射为 9~16pt, 与启动器原有 DPI 行为一致。"""
    return max(9, min(16, round(_clamp_font_size(font_size) * 0.75)))


def _font_tokens(font_size: int) -> dict[str, str]:
    base = _base_point_size(font_size)
    tokens: dict[str, str] = {}
    for token, ratio in _FONT_RATIOS.items():
        value = round(base * ratio * 10) / 10
        tokens[token] = f"{value:g}pt"
    return tokens


def _infer_font_size(app: QApplication) -> int:
    value = app.property("ui_font_size")
    if value is not None:
        try:
            return _clamp_font_size(int(value))
        except (TypeError, ValueError):
            pass
    point = app.font().pointSize()
    if point > 0:
        return _clamp_font_size(round(point / 0.75))
    pixel = app.font().pixelSize()
    if pixel > 0:
        return _clamp_font_size(round(pixel / 0.75))
    return 14


# 全局共享: checkbox 对勾图标路径 (launcher 设置, theme.apply 时替换占位符)
_check_icon_url: str = ""


def set_check_icon_url(url: str):
    global _check_icon_url
    _check_icon_url = url or ""


def apply_theme(app: QApplication, theme: str = "dark",
                check_icon_url: str | None = None,
                font_size: int | None = None):
    """切换主题; theme = 'dark' | 'light'。

    font_size 为设置页中的 12~20 字号值。为空时沿用应用当前字号。
    """
    theme = "dark" if theme != "light" else "light"
    app.setProperty("theme", theme)

    if font_size is None:
        font_size = _infer_font_size(app)
    else:
        font_size = _clamp_font_size(font_size)
    app.setProperty("ui_font_size", font_size)

    # 保持当前字体家族, 仅更新 point size
    font = QFont(app.font())
    font.setPointSize(_base_point_size(font_size))
    app.setFont(font)
    app.setPalette(PALETTES[theme]())

    if check_icon_url is not None:
        set_check_icon_url(check_icon_url)
    qss_path = _resolve_style_path(THEME_FILES[theme])
    if qss_path and qss_path.is_file():
        qss = qss_path.read_text(encoding="utf-8")
        for token, value in _font_tokens(font_size).items():
            qss = qss.replace(token, value)
        if _check_icon_url:
            qss = qss.replace("{{CHECK_ICON}}", _check_icon_url)
        else:
            qss = qss.replace('image: url("{{CHECK_ICON}}");', "")
        app.setStyleSheet(qss)
    else:
        app.setStyleSheet("")


def apply_font_size(app: QApplication, font_size: int):
    """实时应用全局字号并重新生成当前主题 QSS。"""
    apply_theme(app, current_theme(app), font_size=_clamp_font_size(font_size))


def current_theme(app: QApplication) -> str:
    return app.property("theme") or "dark"


def toggle_theme(app: QApplication) -> str:
    """切换主题, 返回新主题。"""
    new = "light" if current_theme(app) == "dark" else "dark"
    apply_theme(app, new)
    return new
