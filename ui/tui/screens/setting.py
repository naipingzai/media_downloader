"""TUI 设置页面 —— Cookie / 代理 / 下载路径 / 文件命名 / 高级选项。"""
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Select

from shared.core import PROJECT_NAME, IMPERSONATE
from shared.translation import _

__all__ = ["SettingScreen"]


class SettingScreen(Screen):
    BINDINGS = [
        Binding(key="Q", action="quit", description=_("退出程序")),
        Binding(key="B", action="back", description=_("返回首页")),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Label(_("作品文件保存根路径"), classes="params"),
            Input(placeholder=_("留空则使用程序根路径"), id="work_path", valid_empty=True),
            Label(_("作品文件储存文件夹名称"), classes="params"),
            Input("Download", id="folder_name"),
            Label(_("作品文件名称格式"), classes="params"),
            Input("create_time type nickname desc", id="name_format", valid_empty=True),
            Label(_("浏览器模拟目标"), classes="params"),
            Input(IMPERSONATE, id="impersonate", valid_empty=True),
            Label(_("Cookie (无需登录，部分功能需要)"), classes="params"),
            Input(placeholder=_("粘贴 Cookie 字符串"), id="cookie", valid_empty=True),
            Label(_("网络代理"), classes="params"),
            Input(placeholder=_("不使用代理"), id="proxy", valid_empty=True),
            Label(_("请求超时 (秒)"), classes="params"),
            Input("10", id="timeout", type="integer"),
            Label(_("下载分块大小 (字节)"), classes="params"),
            Input("2097152", id="chunk", type="integer"),
            Label(_("请求失败重试次数"), classes="params"),
            Input("5", id="max_retry", type="integer"),
            Label(_("数据储存格式"), classes="params"),
            Select(
                [(_("不保存"), ""), ("CSV", "csv"), ("XLSX", "xlsx"),
                 ("SQLite", "sql"), ("JSON", "json")],
                id="storage_format",
            ),
            Checkbox(_("文件夹归档模式"), id="folder_mode"),
            Checkbox(_("下载作品封面"), id="download_cover"),
            Checkbox(_("下载背景音乐"), id="download_music"),
            Label(_("界面语言"), classes="params"),
            Select(
                [("简体中文", "zh_CN"), ("English", "en_US")],
                value="zh_CN", id="language",
            ),
            Button(_("保存配置"), id="save"),
            Button(_("放弃更改"), id="abandon"),
        )
        yield Footer()

    def on_mount(self):
        self.title = _("程序设置")

    @on(Button.Pressed, "#save")
    def save_settings(self):
        data = {
            "work_path": self.query_one("#work_path").value,
            "folder_name": self.query_one("#folder_name").value,
            "name_format": self.query_one("#name_format").value,
            "impersonate": self.query_one("#impersonate").value,
            "cookie": self.query_one("#cookie").value,
            "proxy": self.query_one("#proxy").value or None,
            "timeout": int(self.query_one("#timeout").value or 10),
            "chunk": int(self.query_one("#chunk").value or 2097152),
            "max_retry": int(self.query_one("#max_retry").value or 5),
            "storage_format": self.query_one("#storage_format").value,
            "folder_mode": self.query_one("#folder_mode").value,
            "download_cover": self.query_one("#download_cover").value,
            "download_music": self.query_one("#download_music").value,
            "language": self.query_one("#language").value,
        }
        self.app.notify(_("配置已保存"))
        self.dismiss(data)

    @on(Button.Pressed, "#abandon")
    def abandon(self):
        self.dismiss(None)

    async def action_back(self):
        await self.app.action_back()

    async def action_quit(self):
        await self.app.action_quit()
