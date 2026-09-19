"""MediaDownloader 统一入口。

用法:
    python main.py              # 默认启动 GUI (PySide6)
    python main.py tui          # 启动 TUI (Textual)
    python main.py web          # 启动 Web UI (FastAPI + Uvicorn)
    python main.py api          # 启动纯 Web API (FastAPI)
    python main.py cli ...      # 使用 CLI 模式
"""
from asyncio import run
from asyncio.exceptions import CancelledError
from contextlib import suppress
from sys import argv, path
from pathlib import Path

# 确保项目根目录在 Python 路径中
_root = str(Path(__file__).resolve().parent)
if _root not in path:
    path.insert(0, _root)


async def start_tui():
    from ui.tui import MediaDownloaderTUI

    app = MediaDownloaderTUI()
    await app.run_async()


async def start_web(host: str = "0.0.0.0", port: int = 5555):
    from uvicorn import Config, Server
    from ui.web import create_web_app

    app = create_web_app()
    config = Config(app, host=host, port=port, log_level="info")
    server = Server(config)
    await server.serve()


def start_cli():
    import sys
    # 移除 "cli" 模式标记，让 click 只接收实际参数
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    from ui.cli import cli

    cli()


def start_gui():
    from ui.gui import launch

    launch()


def main():
    with suppress(KeyboardInterrupt, CancelledError):
        if len(argv) <= 1:
            # 默认模式: GUI
            start_gui()
        else:
            mode = argv[1].lower()
            match mode:
                case "tui":
                    run(start_tui())
                case "web" | "webui":
                    host = argv[2] if len(argv) > 2 else "0.0.0.0"
                    port = int(argv[3]) if len(argv) > 3 else 5555
                    run(start_web(host, port))
                case "api":
                    host = argv[2] if len(argv) > 2 else "0.0.0.0"
                    port = int(argv[3]) if len(argv) > 3 else 5555
                    run(start_web(host, port))
                case "cli" | _:
                    start_cli()


if __name__ == "__main__":
    main()
