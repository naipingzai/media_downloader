"""TUI — 纯总线调用，零业务逻辑。"""
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static, RichLog, Select
from shared.core import PROJECT_NAME, REPOSITORY, VOLUME, GENERAL, MASTER, PROMPT, WARNING, ERROR, INFO
from shared.core.ops import PlatformBus
from shared.core.cookies import CookieManager
from shared.translation import _
from shared.core.config import ConfigManager, AppConfig
from platforms import load_all_platforms

STEP_STYLE = "b bold cyan"


class IndexScreen(Screen):
    CSS = """
        Screen { layout: vertical; }
        #ctrl { height: 1fr; overflow-y: auto; }
        #lg { height: 10; min-height: 6; }
        Button { margin: 0 0 1 0; }
        Input { margin: 0 0 1 0; }
        Select { margin: 0 0 1 0; }
    """
    BINDINGS = [Binding(key="q", action="quit", description="退出")]

    def __init__(self):
        super().__init__()
        self.cm = CookieManager()
        self.current_platform = ""
        self.current_feature = ""
        self.need_url = True

    def _step(self, text: str) -> Text:
        return Text(f"  {text}", style=STEP_STYLE)

    def compose(self) -> ComposeResult:
        load_all_platforms()
        yield Header()
        with Container(id="ctrl"):
            yield Static(Text(PROJECT_NAME, style="b bold yellow"))
            yield Static(Text(_("项目地址: ") + REPOSITORY, style=MASTER))
            yield Static(self._step(_("第一步: 选择平台")))
            yield Select(
                [(pid, pid) for pid in PlatformBus.list_platforms()],
                prompt=_("请选择平台"), id="plat")
            yield Static(Text(""), id="s2t")
            yield Input(placeholder=_("粘贴 Cookie 字符串"), id="ci")
            yield Button(_("保存 Cookie"), id="sc", variant="success")
            yield Static(Text(""), id="s3t")
            yield Select([], id="fn", prompt=_("选择功能"))
            yield Static(Text(""), id="s4t")
            yield Input(placeholder=_("粘贴链接/关键词"), id="ur")
            yield Static(Text(""), id="s5t")
            yield Select(
                [("直接存储", "flat"), ("按作者分目录", "by_author"),
                 ("按日期分目录", "by_date"), ("按类型分目录", "by_type")],
                prompt=_("存储模式"), id="sm")
            yield Button(_("执行"), id="go", variant="success")
        yield RichLog(id="lg", markup=True, wrap=True)
        yield Footer()

    def on_mount(self):
        self.title = PROJECT_NAME
        self.log_w = self.query_one("#lg", RichLog)
        self.fn_w = self.query_one("#fn", Select)
        for w in ["#s2t", "#ci", "#sc", "#s3t", "#fn", "#s5t", "#sm", "#s4t", "#ur", "#go"]:
            try: self.query_one(w).display = False
            except Exception: pass
        self._log(PROJECT_NAME + " 已就绪", MASTER)

    @on(Select.Changed, "#plat")
    def on_plat(self, event):
        if event.value is Select.BLANK: return
        self.current_platform = str(event.value)
        ops = PlatformBus.get_ops(self.current_platform)
        cookie = self.cm.get(self.current_platform)
        self._log(_("已选择平台: {p}").format(p=ops.display_name), INFO)
        if ops.cookie_hint:
            ci = f"已设置 ({len(cookie)}字符)" if cookie else "未设置"
            s2 = Text()
            s2.append("  ", style=STEP_STYLE); s2.append(_("第二步: Cookie 管理"), style=STEP_STYLE)
            s2.append(f"\n  {ops.cookie_hint}  {_('当前状态: ')}{ci}")
            self.query_one("#s2t", Static).update(s2)
            self.query_one("#s2t").display = True
            self.query_one("#ci").display = True
            self.query_one("#sc").display = True
        else:
            self.query_one("#s2t").display = False
            self.query_one("#ci").display = False
            self.query_one("#sc").display = False
        features = PlatformBus.get_features(self.current_platform)
        self.fn_w.set_options([(f.name, f.id) for f in features])
        s3 = Text()
        s3.append("  ", style=STEP_STYLE)
        step_label = _("第三步: 选择功能") if ops.cookie_hint else _("第二步: 选择功能")
        s3.append(step_label + f" ({len(features)}个)", style=STEP_STYLE)
        self.query_one("#s3t", Static).update(s3)
        self.query_one("#s3t").display = True
        self.fn_w.display = True
        self.query_one("#s4t").display = False
        self.query_one("#ur").display = False
        self.query_one("#go").display = False

    @on(Button.Pressed, "#sc")
    def save_cookie(self):
        text = self.query_one("#ci").value.strip()
        if not text: self._log(_("请输入 Cookie"), WARNING); return
        if not self.current_platform: self._log(_("请先选择平台"), WARNING); return
        self.cm.set(self.current_platform, text)
        ops = PlatformBus.get_ops(self.current_platform)
        cookie = self.cm.get(self.current_platform)
        s2 = Text()
        s2.append("  ", style=STEP_STYLE); s2.append(_("第二步: Cookie 管理"), style=STEP_STYLE)
        s2.append(f"\n  {ops.cookie_hint}  {_('当前状态: ')}已设置 ({len(cookie)}字符)")
        self.query_one("#s2t", Static).update(s2)
        self._log(_("Cookie 已保存"), INFO)
        self.query_one("#ci").value = ""

    @on(Select.Changed, "#fn")
    def on_func(self, event):
        if event.value is Select.BLANK: return
        self.current_feature = str(event.value)
        features = PlatformBus.get_features(self.current_platform)
        meta = next((f for f in features if f.id == self.current_feature), None)
        self.need_url = meta.need_url if meta else True
        if self.need_url:
            s4 = Text()
            s4.append("  ", style=STEP_STYLE)
            step_label = _("第四步: 输入链接") if PlatformBus.get_ops(self.current_platform).cookie_hint else _("第三步: 输入链接")
            s4.append(step_label, style=STEP_STYLE)
            self.query_one("#s4t", Static).update(s4)
            self.query_one("#s4t").display = True
            self.query_one("#ur").display = True
        else:
            self.query_one("#s4t").display = False
            self.query_one("#ur").display = False
        self.query_one("#go").display = True
        s5 = Text()
        s5.append("  ", style=STEP_STYLE)
        storage_label = _("第五步: 存储模式") if PlatformBus.get_ops(self.current_platform).cookie_hint else _("第三步: 存储模式")
        s5.append(storage_label, style=STEP_STYLE)
        self.query_one("#s5t", Static).update(s5)
        self.query_one("#s5t").display = True
        self.query_one("#sm").display = True

    @on(Select.Changed, "#sm")
    def on_storage(self, event):
        if event.value is Select.BLANK: return
        config = ConfigManager.load()
        config.storage_mode = str(event.value)
        ConfigManager.save(config)
        self._log(_("存储模式已切换为: {m}").format(m=event.value), INFO)

    @on(Button.Pressed, "#go")
    async def on_execute(self):
        if not self.current_platform:
            self._log(_("请先选择平台"), WARNING); return
        if not self.current_feature:
            self._log(_("请选择功能"), WARNING); return
        url = self.query_one("#ur").value.strip() if self.need_url else ""
        if self.need_url and not url:
            self._log(_("请输入链接/关键词"), WARNING); return
        cookie = self.cm.get(self.current_platform)
        save_dir = VOLUME / self.current_platform
        save_dir.mkdir(parents=True, exist_ok=True)
        self._log(_("开始执行..."), INFO)
        result = await PlatformBus.run(self.current_platform, self.current_feature, url, cookie, save_dir)
        for line in result.log:
            self._log(line, INFO if result.success else WARNING)
        if not result.log:
            self._log(result.message, INFO if result.success else WARNING)

    def _log(self, msg, style=GENERAL):
        self.log_w.write(Text(msg, style=style), scroll_end=True)

    async def action_quit(self):
        await self.app.action_quit()
