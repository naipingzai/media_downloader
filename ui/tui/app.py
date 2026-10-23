"""TUI 主应用 v2 — 布局与功能完全同步 GUI。

v2 修复 (相对 v1):
  1. 死锁: 全部后台任务改用 Textual 原生 run_worker (事件循环内协程),
     log_line 直接写 RichLog, 不再跨线程 call_from_thread。
  2. 日志: 用 rich Text 对象着色, 不经 markup 解析, 不会误吞方括号内容。
  3. 字段: 作品渲染兼容 parse_detail 原始字段 (media_type/image_urls/cover_url)。
  4. 链接: 支持粘贴整段分享文本, 自动提取 http 链接。
"""
from __future__ import annotations

import asyncio
import re
import threading

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Static

from shared.core import (
    PROJECT_NAME, VOLUME, CookieManager, PlatformBus,
    platform_name as _pn, FFmpegManager,
)
from platforms import load_all_platforms
from .screens import (
    BatchSelectScreen, DataTableScreen, LoginScreen, SettingsScreen, UrlListScreen, _fmt_count,
)

APP_VERSION_LABEL = "TUI v1.1"

_PREFIX_STYLES = (
    ("✓", "bold green"),
    ("✔", "bold green"),
    ("✗", "bold red"),
    ("⚠", "bold yellow"),
    ("▸", "cyan"),
    ("■", "bold yellow"),
    ("[", "dim"),
)


def _style_of(msg: str) -> str:
    for prefix, style in _PREFIX_STYLES:
        if msg.startswith(prefix):
            return style
    return ""


class TuiApp(App):
    """MediaDownloader TUI — 与 GUI MainWindow 布局/功能同步。"""

    TITLE = PROJECT_NAME
    SUB_TITLE = APP_VERSION_LABEL

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("l", "open_login", "登录"),
        Binding("s", "open_settings", "设置"),
        Binding("d", "show_dir", "下载目录"),
        Binding("ctrl+p", "preview", "解析预览"),
        Binding("x", "stop_task", "停止任务"),
    ]

    CSS = """
    Screen { layout: vertical; }
    #plat-row { height: 3; padding: 0 1; background: $surface;
                border-bottom: solid $primary; }
    #plat-label { text-style: bold; color: $primary; padding: 0 1; }
    .plat-btn { margin: 0 1; min-width: 8; height: 3; }
    .plat-btn.-active { background: $primary; color: $text; text-style: bold; }
    #author-card { height: auto; border: round $panel; margin: 1 1 0 1;
                   padding: 0 1; }
    #author-title { text-style: bold; color: $accent; }
    #author-name { text-style: bold; }
    #author-stats, #author-sign { color: $text-muted; }
    #work-card { height: auto; border: round $panel; margin: 1 1 0 1;
                 padding: 0 1; }
    #work-title { text-style: bold; color: $accent; }
    #work-detail { height: auto; }
    #link-row { height: 3; padding: 1 1 0 1; }
    #link-input { width: 1fr; }
    .sec-title { text-style: bold; color: $accent; padding: 1 1 0 1; }
    #features-box { height: auto; max-height: 14; padding: 0 1 0 1; }
    .feature-btn { width: 1fr; height: 3; margin: 0 1 0 1; }
    #log-panel { height: 1fr; border: round $panel; margin: 0 1; }
    #footer-status { dock: bottom; color: $text-muted; padding: 0 1;
                     background: $surface; }
    """

    _DOWNLOAD_FEATURES = {"download", "account", "series", "collection",
                          "collection_album", "mix", "live", "tk_download",
                          "ks_download", "xhs_download"}

    def __init__(self):
        super().__init__()
        load_all_platforms()
        self._cm = CookieManager()
        self._platform = ""
        self._current_url = ""
        self._current_user: dict | None = None
        self._author_profile: dict = {}
        self._work: dict = {}       # parse_detail 原始输出 (字段最全)
        self._norm_work: dict = {}  # norm_work 归一化输出
        self._task_guard: set[str] = set()   # 正在执行的任务 guard_key
        self._stop_event = threading.Event()

    # ---------------- 布局 ----------------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        # 平台切换
        with Horizontal(id="plat-row"):
            yield Label("平台:", id="plat-label")
            for pid in PlatformBus.list_platforms():
                yield Button(_pn(pid), id=f"plat-{pid}", classes="plat-btn")
        # 作者资料 (纯文本)
        with Vertical(id="author-card"):
            yield Label("👤 作者资料", id="author-title")
            yield Label("未选择平台", id="author-name")
            yield Label("", id="author-stats")
            yield Label("", id="author-sign")
        # 作品资料 (纯文本, 不显示图片)
        with Vertical(id="work-card"):
            yield Label("📌 作品资料", id="work-title")
            yield Static("粘贴链接 → 解析预览 (Ctrl+P)", id="work-detail")
        # 链接输入
        with Horizontal(id="link-row"):
            yield Input(placeholder="粘贴作品链接/分享文本 (自动提取 http 链接)",
                        id="link-input")
            yield Button("解析 (Ctrl+P)", id="act-preview", variant="primary")
        # 功能菜单 (作品/作者/平台 三组, 全部功能)
        yield Label("📋 功能", classes="sec-title")
        yield VerticalScroll(id="features-box")
        # 日志
        yield Label("📜 执行日志", classes="sec-title")
        yield RichLog(id="log-panel", wrap=True, markup=False, highlight=False)
        yield Label("", id="footer-status")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_features()
        self._refresh_status()
        if "douyin" in PlatformBus.list_platforms():
            self.action_select_platform("douyin")

    # ---------------- 平台切换 (对应 _select_platform) ----------------
    def action_select_platform(self, pid: str) -> None:
        self._platform = pid
        for p in PlatformBus.list_platforms():
            try:
                btn = self.query_one(f"#plat-{p}", Button)
                btn.set_classes("plat-btn -active" if p == pid else "plat-btn")
            except Exception:
                pass
        self._work = {}
        self._norm_work = {}
        self._refresh_features()
        self._render_author({"nickname": f"已选择 {_pn(pid)}",
                             "signature": "正在加载当前登录用户…"})
        self._render_work({})
        self.log_line(f"[{_pn(pid)}] 平台已切换")
        self._refresh_status()
        if self._cm.get(pid):
            self._load_current_user()

    def _refresh_features(self) -> None:
        """重建功能按钮 (作品/作者/平台三组, 对应 FeaturePanel)。"""
        box = self.query_one("#features-box", VerticalScroll)
        box.remove_children()
        if not self._platform:
            return
        groups = [
            ("w", "作品操作", [
                ("图片URL列表", self._act_show_urls),
                ("获取链接", self._act_copy_link),
                ("查看评论", self._act_comments),
                ("下载封面", self._act_download_cover),
            ]),
            ("a", "作者操作", [
                ("获取作品", self._act_fetch_works),
                ("关注列表", self._act_follow_list),
                ("收藏列表", self._act_collect_list),
                ("下载头像", self._act_download_avatar),
                ("获取主页", self._act_open_home),
            ]),
        ]
        for prefix, title, actions in groups:
            box.mount(Label(title, classes="sec-title"))
            for i, (label, cb) in enumerate(actions):
                b = Button(label, id=f"{prefix}{i}", classes="feature-btn")
                b.handlers = cb  # type: ignore[attr-defined]
                box.mount(b)
        feats = PlatformBus.get_features(self._platform)
        if feats:
            box.mount(Label("平台功能", classes="sec-title"))
            for f in feats:
                b = Button(f.name, id=f"feat-{f.id}", classes="feature-btn")
                b.feature_id = f.id  # type: ignore[attr-defined]
                box.mount(b)

    def _refresh_status(self) -> None:
        """底部状态栏 (对应 _refresh_cookie_status)。"""
        parts = []
        if not self._platform:
            parts.append("未选择平台")
        else:
            cookie = self._cm.get(self._platform)
            name = _pn(self._platform)
            if cookie and cookie.strip():
                hint = self._cookie_key_hint(self._platform)
                if hint and not all(k in cookie for k in hint.split("|")):
                    parts.append(f"{name}: ⚠ Cookie 不完整 (建议含 {hint})")
                else:
                    parts.append(f"{name}: ✓ Cookie 已配置 ({len(cookie)} 字符)")
            else:
                parts.append(f"{name}: ✗ Cookie 未配置 (按 l 登录)")
        ok, _ = FFmpegManager.check_available()
        parts.append(f"FFmpeg {'✓' if ok else '✗'}")
        parts.append(f"目录: {VOLUME}")
        self.query_one("#footer-status", Label).update("  |  ".join(parts))

    @staticmethod
    def _cookie_key_hint(platform: str) -> str:
        return {
            "douyin": "ttwid|msToken|sessionid",
            "bilibili": "SESSDATA|bili_jct",
            "kuaishou": "did",
            "xiaohongshu": "web_session",
        }.get(platform, "")

    # ---------------- 事件 ----------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "act-preview":
            self.action_preview()
            return
        if bid.startswith("plat-"):
            self.action_select_platform(bid[5:])
            return
        if bid.startswith("feat-"):
            self.action_execute(bid[5:])
            return
        cb = getattr(event.button, "handlers", None)
        if cb:
            cb()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "link-input":
            self.action_preview()

    # ---------------- 日志 (v2: worker 协程内直接调用, 无跨线程) ----------------
    def log_line(self, msg: str, style: str = "") -> None:
        try:
            self.query_one("#log-panel", RichLog).write(
                Text(str(msg), style=style or _style_of(msg)))
        except Exception:
            pass

    # ---------------- 后台任务 (v2: 原生 run_worker) ----------------
    def _run_task(self, coro, on_done=None, name="task",
                  guard_key: str = "") -> None:
        """运行后台协程。guard_key 非空时, 同名任务防重复 (预览/评论等互不阻塞)。"""
        if guard_key and guard_key in self._task_guard:
            self.log_line(f"⚠ [{name}] 已在执行中, 请稍候 (x 可停止)", "yellow")
            coro.close()
            return
        if guard_key:
            self._task_guard.add(guard_key)

        async def _wrapped():
            try:
                result = await coro
            except Exception as e:
                self.log_line(f"✗ {name} 异常: {type(e).__name__}: {e}", "red")
                self.log_line(repr(e)[-200:], "dim")
                result = None
            finally:
                if guard_key:
                    self._task_guard.discard(guard_key)
            if on_done:
                try:
                    on_done(result)
                except Exception as e:
                    self.log_line(f"✗ 回调异常: {e}", "red")

        self.run_worker(_wrapped(), exclusive=False, group="task",
                        description=name)

    def action_stop_task(self) -> None:
        self._stop_event.set()
        self.log_line("■ 已请求停止录制/长任务", "yellow")

    # ---------------- 渲染 ----------------
    def _render_author(self, p: dict) -> None:
        self._author_profile = p
        self.query_one("#author-name", Label).update(
            p.get("nickname") or p.get("name") or "?")
        self.query_one("#author-stats", Label).update(
            f"粉丝 {_fmt_count(p.get('follower_count'))}"
            f" · 关注 {_fmt_count(p.get('following_count'))}"
            f" · 获赞 {_fmt_count(p.get('total_favorited'))}"
            f" · 作品 {_fmt_count(p.get('aweme_count'))}")
        self.query_one("#author-sign", Label).update(
            (p.get("signature") or "").strip() or "—")

    def _render_work(self, w: dict, norm: dict | None = None) -> None:
        self._work = w
        self._norm_work = norm or {}
        if not w:
            self.query_one("#work-detail", Static).update(
                "粘贴链接 → Ctrl+P 解析预览")
            return
        media = w.get("media_type") or ""
        lines = []
        if media == "images":
            imgs = w.get("image_urls")
            if isinstance(imgs, str) and "http" in imgs:
                n_img = 1
            elif isinstance(imgs, list):
                n_img = len(imgs)
            else:
                n_img = 0
            lines.append(f"◆ 图集 · {n_img} 张")
        else:
            lines.append("◆ 视频")
        lines.append(f"标题: {(w.get('title') or w.get('desc') or '—')[:80]}")
        lines.append(f"作者: {w.get('author_name') or '?'}")
        dur = w.get("duration") or 0
        try:
            dur = int(dur)
            if dur > 10000:
                dur //= 1000
        except (TypeError, ValueError):
            dur = 0
        if media != "images" and dur:
            lines.append(f"时长: {dur}s")
        digg, cmt, view = (_fmt_count(w.get(k)) for k in
                           ("digg_count", "comment_count", "view_count"))
        if any((digg, cmt, view)):
            lines.append(f"点赞 {digg} · 评论 {cmt} · 播放 {view}")
        url = w.get("share_url") or self._norm_work.get("share_url") or ""
        if url:
            lines.append(f"链接: {url}")
        if w.get("mix_id"):
            lines.append(f"合集: {w['mix_id']}")
        self.query_one("#work-detail", Static).update("\n".join(lines))

    def _cover_url(self) -> str:
        return (self._work.get("cover_url")
                or self._norm_work.get("cover_url") or "")

    def _adapter(self):
        from shared.core.adapter import PlatformConfig
        from platforms import get_platform
        cls = get_platform(self._platform)
        return cls(config=PlatformConfig(
            name=self._platform, display_name=self._platform,
            domains=[], cookie=self._cm.get(self._platform)))

    # ---------------- 当前用户 ----------------
    def _load_current_user(self) -> None:
        if not self._platform or not self._cm.get(self._platform):
            return
        self.log_line("▸ 获取当前登录用户...", "cyan")

        async def _do():
            a = self._adapter()
            try:
                if hasattr(a, "fetch_current_user"):
                    return await asyncio.wait_for(a.fetch_current_user(), 15)
                return None
            finally:
                await a.close()

        def _done(result):
            if not result:
                self.log_line("✗ 未获取到用户 (Cookie 可能失效, 按 l 重新登录)",
                              "red")
                return
            self.log_line(f"✓ 当前用户: {result.get('nickname', '?')}", "green")
            self._current_user = result
            self._render_author(result)

        self._run_task(_do(), _done, "当前用户", guard_key="user")

    # ---------------- 解析预览 ----------------
    def action_preview(self) -> None:
        raw = self.query_one("#link-input", Input).value.strip()
        if not raw:
            if not self._platform:
                self.log_line("⚠ 请先选择平台", "yellow")
                return
            if not self._cm.get(self._platform):
                self.log_line("⚠ 未配置 Cookie (按 l 登录)", "yellow")
                return
            self._load_current_user()
            return
        if not self._platform:
            self.log_line("⚠ 请先选择平台", "yellow")
            return
        m = re.search(r"https?://\S+", raw)
        if not m:
            self.log_line("⚠ 未找到有效链接", "yellow")
            return
        url = m.group(0)
        for junk in ("复制此链接", "打开Dou音", "，", "。", "！", ")", "）"):
            url = url.split(junk)[0]
        url = url.rstrip("/ ")
        self._current_url = url
        self.log_line(f"[{_pn(self._platform)}] 正在解析 {url[:70]}...", "cyan")

        async def _do():
            from shared.core.session import create_async_client
            from shared.flow.link import LinkExtractor
            client = create_async_client()
            try:
                links = await LinkExtractor(client).run(url, self._platform)
            finally:
                await client.close()
            if not links:
                return None
            a = self._adapter()
            try:
                raw_detail = await a.request_detail(links[0])
                return a.parse_detail(raw_detail) if raw_detail else None
            finally:
                await a.close()

        def _done(work):
            if not work:
                self.log_line("✗ 解析失败: 未获取到作品资料", "red")
                return
            from shared.core import norm_work
            norm = norm_work(work, self._platform)
            self._render_work(work, norm)
            media = work.get("media_type") or "作品"
            self.log_line(f"✓ 解析成功 [{media}]: "
                          f"{(work.get('title') or '')[:50]}", "green")

        self._run_task(_do(), _done, "解析预览", guard_key="preview")

    # ---------------- 功能执行 (对应 _on_execute + FeatureWorker) ----------------
    def action_execute(self, feature_id: str) -> None:
        if not self._platform:
            self.log_line("⚠ 请先选择平台", "yellow")
            return
        ops = PlatformBus.get_ops(self._platform)
        feat = next((f for f in (ops.features if ops else [])
                     if f.id == feature_id), None)
        if feat and feat.need_url and not self._current_url:
            self.log_line(f"⚠ [{feat.name}] 需要先粘贴链接并解析 (Ctrl+P)",
                          "yellow")
            return
        self._run_feature(feature_id, None)

    def _run_feature(self, feature_id: str,
                     selected: list[str] | None) -> None:
        cookie = self._cm.get(self._platform)
        save_dir = VOLUME / self._platform
        save_dir.mkdir(parents=True, exist_ok=True)
        self._stop_event.clear()

        async def _do():
            return await PlatformBus.run(
                self._platform, feature_id, self._current_url,
                cookie, save_dir, on_log=self.log_line,
                selected=selected, stop_event=self._stop_event)

        def _done(result):
            if result is None:
                return
            for line in result.log or []:
                self.log_line(line)
            if result.preview == "batch" and result.data:
                self._open_batch_select(result.message, result.data, feature_id)
                return
            if (result.data and feature_id in self._DOWNLOAD_FEATURES
                    and not result.preview):
                from shared.core import norm_work
                d0 = result.data[0]
                self._render_work(d0, norm_work(d0, self._platform))
            self.log_line(("✓ " if result.success else "✗ ") + result.message,
                          "green" if result.success else "red")
            for f in (result.files or [])[:5]:
                self.log_line(f"  📄 {f}", "dim")
            self._refresh_status()

        self._run_task(_do(), _done, f"功能 {feature_id}",
                       guard_key=f"feat:{feature_id}")

    def _open_batch_select(self, title: str, items: list[dict],
                           feature_id: str) -> None:
        def _cb(selected):
            if selected:
                self.log_line(f"✓ 已勾选 {len(selected)} 项, 开始下载", "green")
                self._run_feature(feature_id, selected)
        self.push_screen(BatchSelectScreen(title, items), _cb)

    # ---------------- 作者/作品 操作 ----------------
    def _act_show_urls(self) -> None:
        """图片/视频 URL 列表 — 终端不显示图片, 列出 URL 供浏览器查看。"""
        w = self._work
        if not w:
            self.log_line("⚠ 无作品 (先解析预览)", "yellow")
            return
        media = w.get("media_type") or ""
        imgs = w.get("image_urls")
        if isinstance(imgs, str) and imgs.startswith("["):
            import ast
            try:
                imgs = ast.literal_eval(imgs)
            except Exception:
                imgs = []
        urls = ([u for u in imgs if isinstance(u, str)]
                if isinstance(imgs, list) else [])
        if not urls and media != "images":
            v = w.get("video_url") or self._norm_work.get("video_url") or ""
            if v:
                urls = [v]
        if not urls:
            self.log_line("⚠ 无图片/视频 URL", "yellow")
            return
        title = (w.get("title") or "")[:30] or "作品"
        self.push_screen(UrlListScreen(title, urls))
        self.log_line(f"✓ {len(urls)} 个 URL (Esc 关闭, 可复制到浏览器查看)",
                      "green")

    def _act_copy_link(self) -> None:
        url = self._work.get("share_url") or self._norm_work.get("share_url")
        if url:
            self.log_line(f"✓ 作品链接: {url}", "green")
        else:
            self.log_line("⚠ 无作品链接 (先 Ctrl+P 解析预览)", "yellow")

    def _act_comments(self) -> None:
        wid = str(self._work.get("work_id") or "")
        if not wid:
            self.log_line("⚠ 无作品ID (先 Ctrl+P 解析预览)", "yellow")
            return
        self.log_line(f"▸ 获取评论: {wid}", "cyan")

        async def _do():
            from shared.core import norm_comment
            a = self._adapter()
            try:
                data = await a.fetch_comments(wid)
                if isinstance(data, dict):
                    data = data.get("comments") or data.get("data") or []
                return [norm_comment(c) for c in (data or [])
                        if isinstance(c, dict)]
            finally:
                await a.close()

        def _done(items):
            items = [c for c in (items or []) if c.get("content")]
            if not items:
                self.log_line("⚠ 评论: 没有数据", "yellow")
                return
            rows = [[c.get("nickname", "—"), c.get("content", "")]
                    for c in items]
            self.push_screen(DataTableScreen("评论列表", ["用户", "内容"], rows))
            self.log_line(f"✓ 评论 {len(items)} 条 (Esc 关闭表格)", "green")

        self._run_task(_do(), _done, "评论")

    def _download_image(self, url: str, subdir: str, prefix: str) -> None:
        if not url:
            self.log_line(f"⚠ 无{prefix}地址 (先解析/登录)", "yellow")
            return

        async def _do():
            import time
            from curl_cffi.requests import get as _get
            r = await asyncio.to_thread(
                _get, url, timeout=15, impersonate="chrome146")
            d = VOLUME / (self._platform or "common") / subdir
            d.mkdir(parents=True, exist_ok=True)
            path = d / f"{prefix}_{int(time.time())}.jpg"
            path.write_bytes(bytes(r.content))
            return str(path)

        def _done(path):
            if path:
                self.log_line(f"✓ {prefix}已保存: {path}", "green")

        self._run_task(_do(), _done, f"{prefix}下载")

    def _act_download_cover(self) -> None:
        self._download_image(self._cover_url(), "covers", "封面")

    def _act_download_avatar(self) -> None:
        self._download_image(
            (self._author_profile or {}).get("avatar", ""), "avatars", "头像")

    def _sec_uid(self) -> str:
        prof = self._author_profile or {}
        return (prof.get("sec_user_id") or prof.get("sec_uid")
                or prof.get("user_id") or "")

    def _act_fetch_works(self) -> None:
        sec = self._sec_uid()
        if not sec:
            self.log_line("⚠ 未获取到作者 sec_user_id (先登录/解析作品)", "yellow")
            return
        self.log_line("▸ 获取作者所有作品...", "cyan")

        async def _do():
            from shared.core import norm_work
            a = self._adapter()
            try:
                items = []
                cursor = "0"
                for page in range(10):
                    self.log_line(f"  ▸ 第 {page + 1} 页...", "dim")
                    data = await a.fetch_user_posts(sec, count=20,
                                                    max_cursor=cursor)
                    if not data:
                        break
                    if isinstance(data, list):
                        items.extend(norm_work(w, self._platform) for w in data)
                        break
                    aws = data.get("aweme_list") or data.get("data") or []
                    if not aws:
                        break
                    items.extend(norm_work(w, self._platform) for w in aws)
                    if not data.get("has_more"):
                        break
                    cursor = str(data.get("max_cursor") or "0")
                    if cursor == "0":
                        break
                return items
            finally:
                await a.close()

        def _done(items):
            if not items:
                self.log_line("⚠ 没有作品数据", "yellow")
                return
            rows = [[w.get("title", "")[:50], w.get("author_name", ""),
                     f"{w.get('duration', 0)}s",
                     _fmt_count(w.get("digg_count"))] for w in items]
            self.push_screen(DataTableScreen(
                "作者所有作品", ["标题", "作者", "时长", "点赞"], rows))
            self.log_line(f"✓ 共 {len(items)} 个作品 (Esc 关闭表格)", "green")

        self._run_task(_do(), _done, "作者作品")

    def _act_follow_list(self) -> None:
        prof = self._current_user or self._author_profile or {}
        sec = prof.get("sec_user_id") or prof.get("sec_uid") or ""
        if not sec:
            self.log_line("⚠ 未获取到当前登录用户", "yellow")
            return
        self.log_line("▸ 拉取关注列表...", "cyan")

        async def _do():
            from shared.core import norm_user
            a = self._adapter()
            try:
                users = []
                max_time = "0"
                for _ in range(3):
                    data = await a.fetch_user_following(sec, count=20,
                                                        max_time=max_time)
                    if not data:
                        break
                    if isinstance(data, list):
                        users.extend(norm_user(u, self._platform) for u in data)
                        break
                    fl = (data.get("followings") or data.get("follow_list")
                          or (data.get("data") or {}).get("followings") or [])
                    if not fl:
                        break
                    users.extend(norm_user(u, self._platform) for u in fl)
                    if not data.get("has_more"):
                        break
                    max_time = str(data.get("max_time") or "0")
                    if max_time == "0":
                        break
                return users
            finally:
                await a.close()

        def _done(users):
            if not users:
                self.log_line("⚠ 关注列表: 没有数据 (可能需登录)", "yellow")
                return
            rows = [[u.get("nickname", ""), (u.get("signature") or "")[:30],
                     _fmt_count(u.get("follower_count"))] for u in users]
            self.push_screen(DataTableScreen("关注列表",
                                             ["昵称", "签名", "粉丝"], rows))
            self.log_line(f"✓ 共 {len(users)} 个关注", "green")

        self._run_task(_do(), _done, "关注列表")

    def _act_collect_list(self) -> None:
        self.log_line("▸ 拉取收藏列表...", "cyan")

        async def _do():
            from shared.core import norm_work
            a = self._adapter()
            try:
                items = []
                cursor = "0"
                for _ in range(5):
                    data = await a.fetch_collection(cursor=cursor, count=20)
                    if not data:
                        break
                    if isinstance(data, list):
                        items.extend(norm_work(w, self._platform) for w in data)
                        break
                    aws = (data.get("aweme_list")
                           or (data.get("data") or {}).get("aweme_list") or [])
                    if not aws:
                        break
                    items.extend(norm_work(w, self._platform) for w in aws)
                    if not data.get("has_more"):
                        break
                    cursor = str(data.get("cursor") or "0")
                    if cursor == "0":
                        break
                return items
            finally:
                await a.close()

        def _done(items):
            if not items:
                self.log_line("⚠ 收藏列表: 没有数据 (需登录)", "yellow")
                return
            rows = [[w.get("title", "")[:50], w.get("author_name", ""),
                     _fmt_count(w.get("digg_count"))] for w in items]
            self.push_screen(DataTableScreen("收藏列表",
                                             ["标题", "作者", "点赞"], rows))
            self.log_line(f"✓ 共 {len(items)} 个收藏", "green")

        self._run_task(_do(), _done, "收藏列表")

    def _act_open_home(self) -> None:
        sec = self._sec_uid()
        if not sec:
            self.log_line("⚠ 无作者信息", "yellow")
            return
        p = (self._author_profile or {}).get("platform") or self._platform
        home = {
            "bilibili": f"https://space.bilibili.com/{sec}",
            "kuaishou": f"https://www.kuaishou.com/profile/{sec}",
            "xiaohongshu": f"https://www.xiaohongshu.com/user/profile/{sec}",
        }.get(p, f"https://www.douyin.com/user/{sec}")
        self.log_line(f"✓ 作者主页: {home}", "green")

    # ---------------- 模态屏入口 ----------------
    def action_open_login(self) -> None:
        if not self._platform:
            self.notify("请先选择平台", severity="warning")
            return
        try:
            ops = PlatformBus.get_ops(self._platform)
            hint = ops.cookie_hint if ops else ""
        except Exception:
            hint = ""
        self.push_screen(LoginScreen(self._platform, hint), self._after_login)

    def _after_login(self, result) -> None:
        if result and result.get("cookie_changed"):
            self._refresh_status()
            self.log_line("✓ Cookie 已更新, 重新加载当前用户...", "green")
            self._load_current_user()

    def action_open_settings(self) -> None:
        self.push_screen(SettingsScreen(), self._after_settings)

    def _after_settings(self, result) -> None:
        if result and result.get("settings_saved"):
            self.notify("设置已生效")
            self._refresh_status()

    def action_show_dir(self) -> None:
        self.log_line(f"下载目录: {VOLUME}", "cyan")
        self.notify(f"{VOLUME}", timeout=4)
