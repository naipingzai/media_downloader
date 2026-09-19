"""TUI 关于页面。"""
from rich.text import Text
from textual.screen import Screen
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.widgets import Footer, Header, Label, Link

from shared.core import __VERSION__, PROJECT_NAME, REPOSITORY, LICENCE, MASTER
from shared.translation import _

__all__ = ["AboutScreen"]


class AboutScreen(Screen):
    """关于页面 —— 展示项目信息。"""

    BINDINGS = [
        Binding(key="escape", action="back", description=_("返回")),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Label(Text(PROJECT_NAME, style=MASTER)),
            Link(
                Text(REPOSITORY, style=MASTER),
                url=REPOSITORY,
            ),
            Label(Text(_("开源协议: ") + LICENCE, style=MASTER)),
        )
        yield Footer()
