"""MediaDownloader TUI (Textual) — 与 GUI 设计同步的终端界面。"""
from .app import TuiApp


def launch():
    """启动 TUI。"""
    TuiApp().run()


__all__ = ["launch", "TuiApp"]
