"""MediaDownloader 入口。"""
from contextlib import suppress
from sys import argv, path
from pathlib import Path

_root = str(Path(__file__).resolve().parent)
if _root not in path:
    path.insert(0, _root)


def main():
    with suppress(KeyboardInterrupt):
        from ui.gui import launch
        launch()


if __name__ == "__main__":
    main()
