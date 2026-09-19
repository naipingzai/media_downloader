"""统一的 Rich 彩色控制台。"""
from typing import Any, Optional, Union

from rich.console import Console
from rich.style import Style
from rich.text import Text, TextType

from .constants import GENERAL, PROMPT, INFO, WARNING, ERROR, DEBUG

__all__ = ["ColorfulConsole"]


class ColorfulConsole(Console):
    """所有平台共享的彩色控制台封装。"""

    def __init__(self, debug: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.debug_mode = debug

    def print(
        self,
        *objects: Any,
        style: Optional[Union[str, Style]] = None,
        highlight: Optional[bool] = False,
        **kwargs,
    ) -> None:
        super().print(*objects, style=style or GENERAL, highlight=highlight, **kwargs)

    def input(
        self,
        prompt: TextType = "",
        style: Optional[Union[str, Style]] = None,
        **kwargs,
    ) -> str:
        try:
            return super().input(Text(prompt, style=style or PROMPT), **kwargs)
        except EOFError as e:
            raise KeyboardInterrupt from e

    def info(self, message: str, **kwargs):
        self.print(message, style=INFO, **kwargs)

    def warning(self, message: str, **kwargs):
        self.print(message, style=WARNING, **kwargs)

    def error(self, message: str, **kwargs):
        self.print(message, style=ERROR, **kwargs)

    def debug(self, message: str, **kwargs):
        if self.debug_mode:
            self.print(message, style=DEBUG, **kwargs)
