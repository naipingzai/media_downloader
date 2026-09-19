"""TUI 下载记录管理页面。"""
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, HorizontalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label

from shared.translation import _

__all__ = ["RecordScreen"]


class RecordScreen(ModalScreen):
    """下载记录管理：删除已下载作品的记录 ID。"""

    BINDINGS = [
        Binding(key="escape", action="close", description=_("返回")),
    ]

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(_("请输入待删除的作品链接或作品 ID"), classes="prompt"),
            Input(
                placeholder=_("支持输入作品 ID 或链接，多个用空格分隔"),
                id="id-input",
            ),
            HorizontalScroll(
                Button(_("删除指定记录"), id="enter"),
                Button(_("返回首页"), id="close"),
            ),
            id="record",
        )

    @on(Button.Pressed, "#enter")
    async def delete_record(self):
        text = self.query_one("#id-input").value
        self.app.notify(_("记录删除功能需连接数据库后生效: ") + text)
        self.query_one("#id-input").value = ""

    @on(Button.Pressed, "#close")
    def close_dialog(self):
        self.dismiss()
