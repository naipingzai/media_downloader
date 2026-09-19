"""TUI 剪贴板监听页面 —— 自动检测链接并下载。"""
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, RichLog

from shared.core import PROJECT_NAME, INFO, GENERAL
from shared.translation import _

__all__ = ["MonitorScreen"]


class MonitorScreen(Screen):
    """剪贴板监听模式：自动检测剪贴板中的链接并下载。"""

    BINDINGS = [
        Binding(key="Q", action="quit", description=_("退出程序")),
        Binding(key="C", action="close", description=_("关闭监听")),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(
            Text(_("已启动监听剪贴板模式"), style=INFO), classes="prompt",
        )
        yield RichLog(id="monitor-log", markup=True, wrap=True)
        yield Button(_("退出监听剪贴板模式"), id="close")
        yield Footer()

    @on(Button.Pressed, "#close")
    async def close_button(self):
        await self.action_close()

    def on_mount(self):
        self.title = PROJECT_NAME

    async def action_close(self):
        await self.app.action_back()

    async def action_quit(self):
        await self.action_close()
        await self.app.action_quit()
