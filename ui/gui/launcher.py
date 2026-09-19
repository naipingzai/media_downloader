"""统一 GUI —— 基于 PyWebView。"""
from pathlib import Path

from shared.core import ROOT, PROJECT_NAME

__all__ = ["launch"]

GUI_INDEX = ROOT / "ui" / "gui" / "static" / "index.html"
GUI_ICON = ROOT / "static" / "images" / "icon.png"


def launch():
    """启动 PyWebView GUI 窗口。"""
    try:
        import webview
    except ImportError:
        print("请安装 pywebview: pip install pywebview")
        return

    if not GUI_INDEX.is_file():
        print(f"GUI 入口文件不存在: {GUI_INDEX}")
        return

    from .backend import GuiBackend

    backend = GuiBackend()
    window = webview.create_window(
        PROJECT_NAME,
        str(GUI_INDEX),
        width=1280,
        height=720,
        min_size=(960, 540),
        resizable=True,
        text_select=True,
        js_api=backend,
    )
    backend._bind_window(window)

    try:
        webview.start(icon=str(GUI_ICON) if GUI_ICON.is_file() else None)
    finally:
        backend.stop()
