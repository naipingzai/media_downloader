"""MediaDownloader 入口。

用法:
    python main.py          # GUI 模式 (默认, PySide6)
    python main.py tui      # TUI 模式 (Textual)
"""
from contextlib import suppress
from sys import argv, path
from pathlib import Path

_root = str(Path(__file__).resolve().parent)
if _root not in path:
    path.insert(0, _root)


def launch_gui():
    from ui.gui import launch
    launch()


def launch_tui():
    from ui.tui import launch
    launch()


def main():
    mode = "gui"
    if len(argv) > 1:
        arg = argv[1].strip().lower()
        if arg in ("tui", "--tui"):
            mode = "tui"
        elif arg in ("gui", "--gui"):
            mode = "gui"
    with suppress(KeyboardInterrupt):
        if mode == "tui":
            launch_tui()
        else:
            launch_gui()


if __name__ == "__main__":
    main()
