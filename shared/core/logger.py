"""统一日志体系 —— 全工程共用。

用法:
    from shared.core.logger import get_logger
    log = get_logger(__name__)
    log.info("...")

特性:
- 控制台输出 (开发/TUI 场景可见)
- 文件输出 (Volume/logs/, 打包后用户可排查问题)
- GUI 可通过 attach_handler 把日志行转发到界面日志面板
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

__all__ = ["get_logger", "attach_gui_handler", "LOG_FILE"]

from .constants import VOLUME

LOG_DIR = VOLUME / "logs"
LOG_FILE = LOG_DIR / "mediadownloader.log"

_FMT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATEFMT = "%m-%d %H:%M:%S"

_configured = False


def _setup() -> None:
    """初始化根 logger (仅一次)。"""
    global _configured
    if _configured:
        return
    root = logging.getLogger("mediadownloader")
    root.setLevel(logging.INFO)
    fmt = logging.Formatter(_FMT, datefmt=_DATEFMT)

    # 控制台
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    root.addHandler(console)

    # 文件 (失败则跳过, 不影响运行)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3,
            encoding="utf-8")
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:
        pass

    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """获取命名 logger, 自动挂接到工程根 logger。"""
    _setup()
    if name.startswith("mediadownloader"):
        return logging.getLogger(name)
    return logging.getLogger(f"mediadownloader.{name}")


def attach_gui_handler(callback) -> None:
    """把日志转发到 GUI (callback: str -> None)。

    GUI 日志面板调用此方法后, 全工程 logger 输出同时进入界面。
    """
    _setup()

    class _Bridge(logging.Handler):
        def emit(self, record: logging.LogRecord):
            try:
                callback(self.format(record))
            except Exception:
                pass

    bridge = _Bridge()
    bridge.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger("mediadownloader").addHandler(bridge)
