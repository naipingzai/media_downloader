"""主窗口 —— PySide6 GUI 桌面端主界面。

布局 (左 3 : 右 2):
  ┌───────────────────────────────────────────────────────┐
  │ 顶部横排栏: 品牌 | 平台按钮组 | 设置/暗色/登录/下载目录     │
  ├─────────────────────┬─────────────────────────────────┤
  │ ┌ 左侧外框 (统框) ─┐ │ ┌ 链接 ──────────────────────┐  │
  │ │ 作者资料 (顶部)   │ │ │ 粘贴链接 + 解析预览          │  │
  │ ├─────────────────┤ │ ├ 功能 ──────────────────────┤  │
  │ │ 作品资料 (占满)  │ │ │ 作品操作/作者操作/平台功能    │  │
  │ │  · 封面 + 详情   │ │ ├ 执行日志 (可折叠) ─────────┤  │
  │ │  · 无页签        │ │ │ 实时日志 + 复制粘贴          │  │
  │ └─────────────────┘ │ └───────────────────────────┘  │
  └─────────────────────┴─────────────────────────────────┘
  独立非模态窗口 (ToolWindow):
    登录 / 设置 / 数据 (作品网格/列表/表格/评论)
  底部状态栏: Cookie + 版本 + FFmpeg
"""
import asyncio
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QRunnable, QThreadPool, QTimer, Signal
from .task_keeper import TaskKeeper
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPushButton, QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)
from shared.core import (
    PROJECT_NAME, VOLUME, CookieManager, PlatformBus,
    platform_name as _pn, FFmpegManager, ConfigManager, norm_user,
)
from shared.core.constants import IMPERSONATE, USERAGENT
from .threads.worker import FeatureWorker
from .widgets.feature_panel import FeaturePanel
from .widgets.video_info import VideoInfoWidget
from .widgets.author_profile_panel import AuthorProfilePanel
from .widgets.browse_window import BrowseWindow
from .widgets.log_panel import LogPanel
from .widgets.task_panel import TaskPanel
from .widgets.section_panel import SectionPanel
from .widgets.tool_window import ToolWindow
from .pages.work_grid_page import WorkGridPage
from .pages.users_page import UsersPage
from .pages.data_table_page import DataTablePage
from .pages.login_page import LoginPage
from .pages.settings_page import SettingsPage
from .resources import theme as _theme


APP_VERSION_LABEL = PROJECT_NAME  # 版本号统一由 shared.core.constants 派生


# ===================== 后台任务 =====================


class _UserFetchSignals(QObject):
    done = Signal(object)
    failed = Signal(str)
    log = Signal(str, str)


class _UserFetchTask(QRunnable):
    """后台拉取当前登录用户 (异步, 带日志 + 15s 超时)。"""

    def __init__(self, cookie: str, platform: str = "douyin"):
        super().__init__()
        self.cookie = cookie
        self.platform = platform or "douyin"
        self.signals = _UserFetchSignals()
        self.setAutoDelete(False)

    def _log(self, msg: str, color: str = "#94a3b8"):
        try:
            self.signals.log.emit(msg, color)
        except RuntimeError:
            pass

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._fetch())
            finally:
                loop.close()
            try:
                self.signals.done.emit(result)
            except RuntimeError:
                pass
        except asyncio.TimeoutError:
            self._log("✗ 请求超时 (15s)", "#f87171")
            try:
                self.signals.failed.emit("请求超时 (15s)")
            except RuntimeError:
                pass
        except Exception as e:
            import traceback
            self._log(f"✗ 异常: {type(e).__name__}: {e}", "#f87171")
            self._log(f"  {traceback.format_exc()[-300:]}", "#64748b")
            try:
                self.signals.failed.emit(f"{type(e).__name__}: {e}")
            except RuntimeError:
                pass

    async def _fetch(self):
        from shared.core.adapter import PlatformConfig
        from platforms import get_platform
        cls = get_platform(self.platform)
        if not cls:
            self._log(f"✗ 平台 {self.platform} 适配器未找到", "#f87171")
            return None
        a = cls(config=PlatformConfig(
            name=self.platform, display_name=self.platform,
            domains=[], cookie=self.cookie))
        try:
            if hasattr(a, "fetch_current_user"):
                try:
                    u = await asyncio.wait_for(a.fetch_current_user(), timeout=15)
                    if u:
                        await a.close()
                        return u
                except Exception as e:
                    self._log(f"  fetch_current_user 失败: {e}", "#f59e0b")
            if self.platform == "douyin":
                return await self._fetch_douyin(a)
            await a.close()
            return None
        except Exception:
            await a.close()
            raise

    async def _fetch_douyin(self, a):
        try:
            for url, params in [
                ("https://www.douyin.com/aweme/v1/web/user/profile/self/", {}),
                ("https://www.douyin.com/passport/web/account/info/", {}),
            ]:
                resp = await asyncio.wait_for(a._signed_get(url, params), timeout=15)
                if not isinstance(resp, dict):
                    continue
                if resp.get("status_code") == 0 and (resp.get("data") or resp.get("user")):
                    return self._norm(resp)
            return None
        finally:
            await a.close()

    @staticmethod
    def _norm(resp: dict) -> dict:
        u = (resp.get("user") or resp.get("user_info")
             or (resp.get("data") or {}).get("user")
             or (resp.get("data") or {}).get("user_info")
             or resp.get("data") or resp)
        if not isinstance(u, dict):
            return {}
        avatar = u.get("avatar_larger") or u.get("avatar_medium") or u.get("avatar_thumb") or ""
        urls = avatar.get("url_list") if isinstance(avatar, dict) else []
        return {
            "user_id": u.get("uid") or u.get("user_id") or u.get("id", ""),
            "sec_user_id": u.get("sec_uid") or u.get("sec_user_id", ""),
            "nickname": u.get("nickname") or u.get("nick_name", ""),
            "signature": u.get("signature") or u.get("desc", ""),
            "avatar": urls[0] if urls else "",
            "follower_count": u.get("follower_count") or 0,
            "following_count": u.get("following_count") or 0,
            "total_favorited": u.get("total_favorited") or 0,
            "aweme_count": u.get("aweme_count") or 0,
        }


class _AuthorFetchSignals(QObject):
    done = Signal(object)
    failed = Signal(str)
    log = Signal(str, str)


class _AuthorFetchTask(QRunnable):
    """后台拉取: works / collection / comments / following。"""

    def __init__(self, kind: str, sec_uid: str, cookie: str,
                 platform: str = "douyin"):
        super().__init__()
        self.kind = kind
        self.sec_uid = sec_uid
        self.cookie = cookie
        self.platform = platform or "douyin"
        self.signals = _AuthorFetchSignals()
        self.setAutoDelete(False)

    def _log(self, msg: str, color: str = "#94a3b8"):
        try:
            self.signals.log.emit(msg, color)
        except RuntimeError:
            pass

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._fetch())
            finally:
                loop.close()
            try:
                self.signals.done.emit(result or [])
            except RuntimeError:
                pass
        except Exception as e:
            self._log(f"✗ 拉取失败: {e}", "#f87171")
            try:
                self.signals.failed.emit(str(e))
            except RuntimeError:
                pass

    async def _fetch(self):
        from shared.core.adapter import PlatformConfig, norm_work, norm_user, norm_comment
        from platforms import get_platform
        cls = get_platform(self.platform)
        if not cls:
            return []
        a = cls(config=PlatformConfig(
            name=self.platform, display_name=self.platform,
            domains=[], cookie=self.cookie))
        try:
            if self.kind == "works":
                return await self._fetch_works(a, norm_work)
            if self.kind == "following":
                return await self._fetch_following(a, norm_user)
            if self.kind == "collection":
                return await self._fetch_collection(a, norm_work)
            if self.kind == "comments":
                return await self._fetch_comments(a, norm_comment)
            return []
        finally:
            await a.close()

    async def _fetch_comments(self, a, norm_comment) -> list:
        if not hasattr(a, "fetch_comments"):
            return []
        data = await a.fetch_comments(self.sec_uid)
        if isinstance(data, dict):
            data = data.get("comments") or data.get("data") or []
        if isinstance(data, list):
            return [c for c in (norm_comment(x) for x in data if isinstance(x, dict))
                    if c.get("content")]
        return []

    async def _fetch_works(self, a, norm_work) -> list:
        items = []
        cursor = "0"
        for page in range(5):
            self._log(f"  ▸ 拉取作品 第 {page + 1} 页...", "#94a3b8")
            data = await a.fetch_user_posts(self.sec_uid, count=20, max_cursor=cursor)
            if not data:
                break
            if isinstance(data, list):
                items.extend(norm_work(aw, self.platform) for aw in data)
                break
            awemes = data.get("aweme_list") or data.get("data") or []
            if isinstance(awemes, dict):
                awemes = awemes.get("aweme_list") or []
            if not awemes:
                break
            items.extend(norm_work(aw, self.platform) for aw in awemes)
            if not data.get("has_more"):
                break
            cursor = str(data.get("max_cursor") or "0")
            if cursor == "0":
                break
        self._log(f"✓ 共拉取 {len(items)} 个作品", "#22c55e")
        return items

    async def _fetch_following(self, a, norm_user) -> list:
        users = []
        max_time = "0"
        for page in range(3):
            self._log(f"  ▸ 拉取关注列表 第 {page + 1} 页...", "#94a3b8")
            data = await a.fetch_user_following(self.sec_uid, count=20, max_time=max_time)
            if not data:
                break
            if isinstance(data, list):
                users.extend(norm_user(u, self.platform) for u in data)
                break
            fl = data.get("followings") or data.get("follow_list") or []
            if not fl:
                fl = (data.get("data") or {}).get("followings") or []
            if not fl:
                break
            users.extend(norm_user(u, self.platform) for u in fl)
            if not data.get("has_more"):
                break
            max_time = str(data.get("max_time") or "0")
            if max_time == "0":
                break
        self._log(f"✓ 共拉取 {len(users)} 个关注", "#22c55e")
        return users

    async def _fetch_collection(self, a, norm_work) -> list:
        items = []
        cursor = "0"
        for page in range(3):
            self._log(f"  ▸ 拉取收藏 第 {page + 1} 页...", "#94a3b8")
            data = await a.fetch_collection(cursor=cursor, count=20)
            if not data:
                break
            if isinstance(data, list):
                items.extend(norm_work(aw, self.platform) for aw in data)
                break
            awemes = data.get("aweme_list") or []
            if not awemes:
                awemes = (data.get("data") or {}).get("aweme_list") or []
            if not awemes:
                break
            items.extend(norm_work(aw, self.platform) for aw in awemes)
            if not data.get("has_more"):
                break
            cursor = str(data.get("cursor") or "0")
            if cursor == "0":
                break
        self._log(f"✓ 共拉取 {len(items)} 个收藏作品", "#22c55e")
        return items


class _PreviewSignals(QObject):
    """预览任务信号 (后台线程 → 主线程渲染)。"""
    done = Signal(dict, dict)     # (work, profile)
    failed = Signal(str, str)     # (错误类别, 详情)
    log = Signal(str, str)


class _PreviewTask(QRunnable):
    """后台执行「短链解析 + 详情获取 + 作者资料」，避免阻塞 GUI 主线程。

    pylint: disable=too-few-public-methods
    """

    def __init__(self, url: str, platform: str, cookie: str):
        super().__init__()
        self.url = url
        self.platform = platform
        self.cookie = cookie
        self.signals = _PreviewSignals()
        self.setAutoDelete(False)

    def _log(self, msg: str, color: str = "#94a3b8"):
        try:
            self.signals.log.emit(msg, color)
        except RuntimeError:
            pass

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            work, profile = loop.run_until_complete(self._fetch())
            try:
                self.signals.done.emit(work or {}, profile or {})
            except RuntimeError:
                pass
        except asyncio.TimeoutError:
            self._emit_failed("timeout", "请求超时")
        except Exception as e:  # 兜底: 任何异常都回主线程提示
            import traceback
            self._log(f"  {traceback.format_exc()[-300:]}", "#64748b")
            self._emit_failed("exception", f"{type(e).__name__}: {e}")
        finally:
            loop.close()

    def _emit_failed(self, kind: str, detail: str):
        try:
            self.signals.failed.emit(kind, detail)
        except RuntimeError:
            pass

    async def _fetch(self) -> tuple[dict, dict]:
        from shared.core.session import create_async_client
        from shared.core.adapter import PlatformConfig, norm_user
        from shared.flow.link import LinkExtractor, LinkType
        from platforms import get_platform

        client = create_async_client()
        try:
            links = await asyncio.wait_for(
                LinkExtractor(client).run(self.url, self.platform), timeout=30)
        finally:
            await client.close()
        if not links:
            raise LookupError("未提取到有效链接")
        link = links[0]
        if link.link_type == LinkType.LIVE:
            raise LookupError("直播链接暂不支持完整预览")
        cls = get_platform(self.platform)
        if not cls:
            raise LookupError("平台适配器未找到")
        adapter = cls(config=PlatformConfig(
            name=self.platform, display_name="", domains=[],
            cookie=self.cookie))
        try:
            raw = await asyncio.wait_for(adapter.request_detail(link), timeout=45)
            if not raw:
                raise RuntimeError(getattr(adapter, "last_error", "") or
                                   "获取详情失败")
            work = adapter.parse_detail(raw)
            if not work:
                raise ValueError(getattr(adapter, "last_error", "") or "解析失败")
            work.setdefault("platform", self.platform)
            profile = {}
            sec_uid = work.get("sec_user_id", "")
            if sec_uid:
                try:
                    data = await asyncio.wait_for(
                        adapter.fetch_user_profile(sec_uid), timeout=15)
                    u = ((data or {}).get("user") or (data or {}).get("card")
                         or (data or {}).get("data") or data or {})
                    if isinstance(u, dict) and u:
                        p = norm_user(u, self.platform)
                        if p.get("nickname"):
                            profile = p
                except Exception:
                    pass   # 作者资料非关键路径
            return work, profile
        finally:
            await adapter.close()


class _ImageSaveSignals(QObject):
    done = Signal(str)      # 保存成功路径
    failed = Signal(str)    # 失败原因
    log = Signal(str, str)


class _ImageSaveTask(QRunnable):
    """后台保存图片 (避免主线程同步下载导致界面冻结)。"""

    def __init__(self, url: str, dest: Path):
        super().__init__()
        self.url = url
        self.dest = dest
        self.signals = _ImageSaveSignals()
        self.setAutoDelete(False)

    def run(self):
        from PySide6.QtGui import QImage
        try:
            from curl_cffi import requests as cffi
            h = {"User-Agent": USERAGENT}
            u = self.url.lower()
            if "douyin" in u:
                h["Referer"] = "https://www.douyin.com/"
            elif "bilibili" in u or "hdslb" in u:
                h["Referer"] = "https://www.bilibili.com/"
            elif "xiaohongshu" in u or "xhscdn" in u:
                h["Referer"] = "https://www.xiaohongshu.com/"
            elif "kuaishou" in u or "ksurl" in u:
                h["Referer"] = "https://www.kuaishou.com/"
            r = cffi.get(self.url, headers=h, timeout=20,
                         impersonate=IMPERSONATE, allow_redirects=True)
            if r.status_code != 200 or not r.content:
                self._fail(f"HTTP {r.status_code}")
                return
            img = QImage()
            img.loadFromData(bytes(r.content))
            if img.isNull():
                self._fail("图片数据无效")
                return
            self.dest.parent.mkdir(parents=True, exist_ok=True)
            if img.save(str(self.dest)):
                try:
                    self.signals.done.emit(str(self.dest))
                except RuntimeError:
                    pass
            else:
                self._fail("保存失败")
        except Exception as e:
            self._fail(f"{type(e).__name__}: {e}")

    def _fail(self, msg: str):
        try:
            self.signals.failed.emit(msg)
        except RuntimeError:
            pass


# ===================== 主窗口 =====================


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(PROJECT_NAME)
        # 可缩放窗口: 小屏可缩小, 大屏可放大; 分隔条让左右/上下比例随时调整
        self.setMinimumSize(1024, 680)
        self.resize(1320, 880)
        self.menuBar().setVisible(False)
        PlatformBus  # force import (side effect 注册平台)
        from platforms import load_all_platforms
        load_all_platforms()
        self._cm = CookieManager()
        self._current_platform = ""
        self._current_url = ""
        self._current_user_profile = None
        self._pool = QThreadPool()
        self._tasks = TaskKeeper(self)  # 持有后台任务, 防止 setAutoDelete double-free
        self._pool.setMaxThreadCount(2)
        self._setup_pages()        # 先建可复用页 (login/settings 单例)
        self._setup_status_bar()
        self._setup_queue_timer()
        self._setup_ui()           # 再建主 UI (此处创建 self._log)
        self._setup_cover_diagnostics()  # 必须在 self._log 创建之后

    # ---------------- 可复用页 ----------------

    def _setup_pages(self):
        self._settings_page = SettingsPage()
        self._settings_page.font_changed.connect(self._apply_font_size)
        self._settings_page.settings_saved.connect(self._on_settings_saved)
        self._login_page = LoginPage()
        self._login_page.cookie_changed.connect(self._refresh_cookie_status)
        # 登录/设置以独立非模态窗口显示 (不再塞进作品资料区页签)
        self._login_win = ToolWindow(
            "登录", self._login_page, size=(560, 680), parent=self)
        self._settings_win = ToolWindow(
            "设置", self._settings_page, size=(720, 680), parent=self)
        # 数据页 (作品网格/列表/表格/评论) 用独立窗口, 作品资料区只留作品资料
        self._data_win = ToolWindow(
            "数据", QWidget(), size=(900, 680), parent=self)
        # 内嵌浏览器: App 式浏览窗口 (我的作品/收藏/关注 → 用户作品 → 下载)
        self._browse_win = BrowseWindow(parent=self)
        self._browse_win.download_requested.connect(self._on_browse_download)

    # ---------------- 主 UI:
    #   顶 部  : 品牌 + 平台切换 + 工具/账号 横排按钮
    #   中 部  : 左 = 作者 + 作品资料 (QTabWidget)     (大)
    #            右 = 功能窗口                            (小, 上下分割)
    #                 ├─ 上: 链接输入 + 功能按钮
    #                 └─ 下: 执行日志 (支持复制粘贴)
    # ----------------

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 0) 顶部横排栏 (品牌 + 平台 + 工具 + 账号)
        v.addWidget(self._build_topbar())

        # 1) 中部左右两栏: QSplitter 可拖动 (默认 3:2, 用户可随时调整)
        body = QSplitter(Qt.Horizontal)
        body.setObjectName("BodySplitter")
        body.setChildrenCollapsible(False)
        body.setHandleWidth(10)
        body.addWidget(self._build_left_panel())

        # === 右: 链接 + 功能 + 日志 (可垂直拖动, 日志高度自由调整) ===
        right_col = QSplitter(Qt.Vertical)
        right_col.setObjectName("RightSplitter")
        right_col.setChildrenCollapsible(False)
        right_col.setHandleWidth(10)
        right_col.addWidget(self._build_link_panel())
        right_col.addWidget(self._build_right_column())
        right_col.addWidget(self._build_task_section())
        right_col.addWidget(self._build_log_section())
        right_col.setStretchFactor(0, 0)
        right_col.setStretchFactor(1, 1)
        right_col.setStretchFactor(2, 0)
        right_col.setStretchFactor(3, 0)
        right_col.setSizes([92, 430, 150, 190])
        body.addWidget(right_col)

        body.setStretchFactor(0, 3)
        body.setStretchFactor(1, 2)
        body.setSizes([770, 530])
        v.addWidget(body, 1)

        if "douyin" in PlatformBus.list_platforms():
            self._select_platform("douyin")
        self._update_topbar_density()

    # ---------------- 各区域 (固定高度构造) ----------------

    # ---- 顶部横排栏 ----

    def _build_topbar(self) -> QFrame:
        """顶部横排: 品牌 | 平台按钮组 | 工具按钮 | 账号按钮。"""
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 9, 16, 9)
        row.setSpacing(12)

        # 品牌
        self._brand_label = QLabel("MediaDownloader")
        self._brand_label.setObjectName("BrandTitle")
        row.addWidget(self._brand_label)

        # 分隔点
        self._brand_sep = QLabel("·")
        self._brand_sep.setObjectName("TopSep")
        row.addWidget(self._brand_sep)

        # 平台按钮组 (横排)
        self._platform_label = QLabel("平台")
        self._platform_label.setObjectName("TopGroupLabel")
        row.addWidget(self._platform_label)
        self._platform_btns = []
        plat_row = QHBoxLayout()
        plat_row.setContentsMargins(0, 0, 0, 0)
        plat_row.setSpacing(6)
        for pid in PlatformBus.list_platforms():
            btn = QPushButton(_pn(pid))
            btn.setObjectName("TopPlatformBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, p=pid: self._select_platform(p))
            plat_row.addWidget(btn)
            self._platform_btns.append((pid, btn))
        self._platform_wrap = QWidget()
        self._platform_wrap.setLayout(plat_row)
        row.addWidget(self._platform_wrap)

        # 拉伸弹簧 (把后面的按钮推到右侧)
        row.addStretch()

        # 工具 + 账号 (横排)
        self._top_tool_btns: list[QPushButton] = []

        def add_icon_button(text, slot):
            b = QPushButton(text)
            b.setObjectName("TopToolBtn")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            row.addWidget(b)
            self._top_tool_btns.append(b)
            return b

        add_icon_button("设置", self._open_settings)
        self._theme_btn = add_icon_button("暗色", self._toggle_theme)
        add_icon_button("登录", self._open_login)
        add_icon_button("浏览器", self._open_browser)
        add_icon_button("下载记录", self._open_history)
        add_icon_button("下载目录", self._open_download_dir)
        self._topbar_row = row
        return bar

    def _update_topbar_density(self):
        """窄窗口时依次隐藏品牌/平台标签, 保留全部平台与操作按钮。"""
        if not hasattr(self, "_topbar_row"):
            return
        row = self._topbar_row
        margins = row.contentsMargins()
        spacing = row.spacing()

        def required(include_brand: bool, include_platform_label: bool) -> int:
            widgets = []
            if include_brand:
                widgets.extend((self._brand_label, self._brand_sep))
            if include_platform_label:
                widgets.append(self._platform_label)
            widgets.append(self._platform_wrap)
            widgets.extend(self._top_tool_btns)
            # 平台组和工具组之间还有 stretch，占一个 QHBoxLayout 间隔。
            return (sum(widget.sizeHint().width() for widget in widgets)
                    + margins.left() + margins.right()
                    + spacing * len(widgets))

        available = self.width()
        include_brand = required(True, True) <= available
        include_platform_label = True
        self._brand_label.setVisible(include_brand)
        self._brand_sep.setVisible(include_brand)
        if not include_brand:
            include_platform_label = required(False, True) <= available
        self._platform_label.setVisible(include_platform_label)

    # ---- 右侧功能按钮列 ----

    def _build_right_column(self) -> SectionPanel:
        """右侧: 功能按钮区；大字号/矮窗口下允许纵向滚动。"""
        self._feature_panel = self._build_feature_panel_inner()
        scroll = QScrollArea()
        scroll.setObjectName("FeatureScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self._feature_panel)
        sec = SectionPanel("功能")
        sec.addWidget(scroll, 1)
        sec.setMinimumHeight(220)
        return sec

    def _build_link_panel(self) -> SectionPanel:
        link_bar = QFrame()
        link_bar.setObjectName("LinkBar")
        h = QHBoxLayout(link_bar)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText(
            "粘贴作品链接 (抖音/快手/小红书/B站) → 点击解析预览")
        self._url_input.setObjectName("LinkInput")
        self._url_input.textChanged.connect(self._on_url_changed)
        h.addWidget(self._url_input, 1)
        preview_btn = QPushButton("解析预览")
        preview_btn.setObjectName("PrimaryButton")
        preview_btn.setCursor(Qt.PointingHandCursor)
        preview_btn.clicked.connect(self._on_preview)
        h.addWidget(preview_btn)
        sec = SectionPanel("链接")
        sec.addWidget(link_bar)
        sec.setMinimumHeight(84)
        return sec

    # ---- 左侧外框: 作者资料卡(顶部) + 作品资料区(占满剩余) ----

    def _build_left_panel(self) -> QFrame:
        """左侧外框: 一个边框包住作者资料卡(顶部) 和 作品资料区(占满剩余)。

        作者资料位于顶部固定高度, 下方的作品资料区随父控件拉伸。
        """
        from PySide6.QtWidgets import QSizePolicy

        panel = QFrame()
        panel.setObjectName("LeftPanel")
        # 样式由主题 QSS (#LeftPanel / #AuthorCard / #LeftSubTitle) 提供
        # 高度伸展占满中部
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        v = QVBoxLayout(panel)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(10)

        # 顶部: 作者资料卡 (固定高度)
        self._author_panel = AuthorProfilePanel()
        self._author_panel.fetch_works_clicked.connect(self._on_fetch_works)
        self._author_panel.follow_list_clicked.connect(self._on_follow_list)
        self._author_panel.collect_list_clicked.connect(self._on_collect_list)
        self._author_panel.download_avatar_clicked.connect(self._on_download_avatar)
        self._author_panel.open_home_clicked.connect(self._on_open_home)
        # 作者资料卡子框架: 边框 + 标题 (用 objectName 精确选择, 避免污染子控件)
        author_sec = QFrame()
        author_sec.setObjectName("AuthorCard")
        author_lay = QVBoxLayout(author_sec)
        author_lay.setContentsMargins(10, 6, 10, 6)
        author_lay.setSpacing(4)
        author_title = QLabel("作者资料")
        author_title.setObjectName("LeftSubTitle")
        author_lay.addWidget(author_title)
        author_lay.addWidget(self._author_panel)
        author_sec.setMinimumHeight(136)
        v.addWidget(author_sec)

        # 下部: 作品资料区 (占满剩余高度, 无页签, 只显示作品资料)
        self._video_info = VideoInfoWidget()
        work_sec = QFrame()
        work_sec.setObjectName("WorkInfoCard")
        work_sec.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        work_lay = QVBoxLayout(work_sec)
        work_lay.setContentsMargins(10, 6, 10, 6)
        work_lay.setSpacing(4)
        # 左上角标题 (固定保留)
        work_title = QLabel("作品资料")
        work_title.setObjectName("LeftSubTitle")
        work_lay.addWidget(work_title)
        work_lay.addWidget(self._video_info, 1)
        v.addWidget(work_sec, 1)

        # 保留旧 API (供其他逻辑调用, 不再使用)
        self._video_panel = work_sec
        self._author_panel_section = author_sec
        return panel

    def _build_log_section(self) -> SectionPanel:
        self._log = LogPanel()
        sec = SectionPanel("执行日志")
        sec.addWidget(self._log, 1)
        sec.setMinimumHeight(140)
        return sec

    def _build_task_section(self) -> SectionPanel:
        """下载任务管理面板: 实时进度/暂停全部/继续/限速/全部停止。"""
        self._task_panel = TaskPanel()
        sec = SectionPanel("下载任务")
        sec.addWidget(self._task_panel, 1)
        sec.setMinimumHeight(120)
        return sec

    def _build_feature_panel_inner(self) -> FeaturePanel:
        def _copy_work_link():
            w = self._video_info.work
            self._on_copy_link(w.get("share_url") or w.get("video_url", ""))

        def _show_comments():
            self._on_show_comments(str(self._video_info.work.get("work_id", "")))

        def _download_cover():
            self._on_download_cover(self._video_info.cover_url)

        def _dl_avatar():
            self._on_download_avatar(self._author_panel.profile.get("avatar", ""))

        def _open_home():
            prof = self._author_panel.profile
            sec = (prof.get("sec_user_id") or prof.get("sec_uid")
                   or prof.get("user_id") or "")
            p = prof.get("platform", "") or self._current_platform
            home = ""
            if sec:
                if p == "bilibili":
                    home = f"https://space.bilibili.com/{sec}"
                elif p == "kuaishou":
                    home = f"https://www.kuaishou.com/profile/{sec}"
                elif p == "xiaohongshu":
                    home = f"https://www.xiaohongshu.com/user/profile/{sec}"
                else:
                    home = f"https://www.douyin.com/user/{sec}"
            self._on_open_home(home)

        fp = FeaturePanel(
            work_buttons=[
                ("获取链接", _copy_work_link),
                ("查看评论", _show_comments),
                ("下载封面", _download_cover),
            ],
            author_buttons=[
                ("获取作品", self._on_fetch_works),
                ("关注列表", self._on_follow_list),
                ("收藏列表", self._on_collect_list),
                ("下载头像", _dl_avatar),
                ("获取主页", _open_home),
            ],
        )
        fp.execute_clicked.connect(self._on_execute)
        fp.stop_recording_clicked.connect(self._on_stop_recording)
        self._current_worker = None
        return fp

    # ---------------- 状态栏 ----------------

    def _setup_queue_timer(self):
        """每秒轮询下载队列, 驱动日志面板进度条与状态栏任务数。"""
        from PySide6.QtCore import QTimer
        self._queue_timer = QTimer(self)
        self._queue_timer.timeout.connect(self._poll_queue)
        self._queue_timer.start(1000)

    def _poll_queue(self):
        try:
            from shared.flow.queue import get_queue
            st = get_queue().status()
        except Exception:
            return
        if st:
            # 只统计已知总大小的句柄: total=0 的句柄 (未取到 content-length /
            # 陈旧残留) 会把 cur 顶超过 total, 使进度恒显 100% 并来回跳动。
            valid = [s for s in st if s["total"] > 0]
            if valid:
                cur = sum(min(s["downloaded"], s["total"]) for s in valid)
                total = sum(s["total"] for s in valid)
                self._log.set_progress(cur, total)
                done = sum(1 for s in valid if s["downloaded"] >= s["total"])
                self._cookie_hint.setText(f"下载任务 {len(st)} 个 (完成 {done})")
            else:
                self._cookie_hint.setText(f"下载任务 {len(st)} 个")
        elif hasattr(self, "_cookie_hint"):
            self._log.set_progress(0, 0)

    def _setup_cover_diagnostics(self):
        """把图片加载失败原因写入日志，便于定位「封面/头像不显示」。

        同一 URL 只提示一次，避免重试刷屏。
        """
        try:
            from .cover_loader import CoverLoader
            seen: set[str] = set()

            def _on_fail(url: str, reason: str):
                key = url.rsplit("/", 1)[-1][:40]
                if key in seen:
                    return
                seen.add(key)
                log = getattr(self, "_log", None)
                if log is not None:
                    log.append(
                        f"⚠ 图片加载失败 ({reason})", "#f59e0b")

            CoverLoader.instance().cover_failed.connect(_on_fail)
        except Exception:
            pass

    def _setup_status_bar(self):
        sb = self.statusBar()
        sb.setObjectName("StatusBar")
        self._cookie_label = QLabel("Cookie:")
        self._cookie_label.setObjectName("StatusLabel")
        sb.addWidget(self._cookie_label)
        self._cookie_platform = QLabel("未选择平台")
        self._cookie_platform.setObjectName("StatusPlatform")
        sb.addWidget(self._cookie_platform)
        self._cookie_status = QLabel("—")
        self._cookie_status.setObjectName("StatusCookie")
        sb.addWidget(self._cookie_status)
        self._cookie_hint = QLabel("")
        self._cookie_hint.setObjectName("StatusHint")
        sb.addWidget(self._cookie_hint, 1)
        self._version_label = QLabel(APP_VERSION_LABEL)
        self._version_label.setObjectName("StatusVersion")
        sb.addPermanentWidget(self._version_label)
        self._status_ffmpeg = QLabel("")
        self._status_ffmpeg.setObjectName("StatusFFmpeg")
        sb.addPermanentWidget(self._status_ffmpeg)
        ok, _ = FFmpegManager.check_available()
        self._status_ffmpeg.setText(f"FFmpeg {'✓' if ok else '✗'}")

    def _refresh_cookie_status(self):
        pid = self._current_platform
        if not pid:
            self._cookie_platform.setText("未选择平台")
            self._cookie_status.setText("—")
            self._cookie_hint.setText("")
            return
        cookie = self._cm.get(pid)
        name = _pn(pid)
        self._cookie_platform.setText(name)
        if cookie and cookie.strip():
            length = len(cookie)
            hint = self._cookie_key_hint(pid)
            if hint and not all(k in cookie for k in hint.split("|")):
                self._cookie_status.setText("⚠")
                self._cookie_hint.setText(f"Cookie 不完整 (建议含: {hint})")
            else:
                self._cookie_status.setText("✓")
                self._cookie_hint.setText(
                    f"已配置 ({length} 字符)"
                    + (f" · 含 {hint}" if hint else ""))
        else:
            self._cookie_status.setText("✗")
            self._cookie_hint.setText("未配置 (登录后才有)")

    @staticmethod
    def _cookie_key_hint(platform: str) -> str:
        return {
            "douyin": "ttwid|msToken|sessionid",
            "bilibili": "SESSDATA|bili_jct",
            "kuaishou": "did",
            "xiaohongshu": "web_session",
        }.get(platform, "")

    # ---------------- 平台选择 ----------------

    def _select_platform(self, platform: str):
        self._current_platform = platform
        cookie = self._cm.get(platform)
        features = PlatformBus.get_features(platform)
        self._feature_panel.set_features(features)
        for pid, btn in self._platform_btns:
            btn.setProperty("active", pid == platform)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._video_info.show_empty()
        self._feature_panel.set_work_available(False)
        self._log.clear()
        self._author_panel.show_placeholder(
            f"已选择 {_pn(platform)}", "正在加载当前登录用户...")
        self._refresh_cookie_status()
        try:
            ops = PlatformBus.get_ops(platform)
            hint = ops.cookie_hint if ops else ""
        except Exception:
            hint = ""
        self._login_page.setup(platform, hint, cookie)
        # 清空上一个平台的作者资料, 避免切换后残留旧平台信息
        self._current_user_profile = None
        # 平台代次: 切换平台即 +1, 旧平台的异步回调据此被丢弃
        # (否则 douyin 的用户信息会晚到并覆盖刚切过去的平台)
        self._ui_epoch = getattr(self, "_ui_epoch", 0) + 1
        if cookie:
            self._load_current_user(platform, cookie)
        else:
            self._author_panel.show_placeholder(
                _pn(platform), "未配置 Cookie (请先登录)")

    def _load_current_user(self, platform: str, cookie: str):
        self._log.append("▸ 启动后台任务获取当前用户...", "#38bdf8")
        task = _UserFetchTask(cookie, platform)
        epoch = getattr(self, "_ui_epoch", 0)
        task.signals.log.connect(self._log.append)
        task.signals.done.connect(
            lambda result, e=epoch: self._on_user_loaded(result, e))
        task.signals.failed.connect(
            lambda err, e=epoch: self._on_user_load_failed(err, e))
        self._tasks.keep(task,
                            getattr(task.signals, "done", None),
                            getattr(task.signals, "finished", None),
                            getattr(task.signals, "error", None),
                            getattr(task.signals, "failed", None))
        self._pool.start(task)

    def _stale(self, epoch: int) -> bool:
        """异步回调是否已过期 (期间切换过平台)。"""
        return epoch != getattr(self, "_ui_epoch", 0)

    def _on_user_loaded(self, result, epoch: int = -1):
        if self._stale(epoch):
            return  # 期间已切换平台, 丢弃旧平台结果
        if not result:
            self._log.append("✗ API 未返回用户 (Cookie 可能失效)", "#ef4444")
            self._author_panel.show_placeholder("当前用户未获取", "Cookie 可能失效或未登录")
            return
        self._log.append(f"✓ 当前用户: {result.get('nickname', '?')}", "#22c55e")
        self._current_user_profile = result
        self._author_panel.show_current_user(result)
        # 浏览器窗口同步当前登录用户 (打开过才刷新, 避免无谓请求)
        if self._browse_win.isVisible():
            self._browse_win.open_platform(
                self._current_platform,
                sec_uid=result.get("sec_user_id", ""), profile=result)

    def _on_user_load_failed(self, err: str, epoch: int = -1):
        if self._stale(epoch):
            return
        self._log.append(f"✗ 加载当前用户失败: {err}", "#ef4444")
        self._author_panel.show_placeholder("当前用户加载失败", err[:40])

    # ---------------- 作者功能 ----------------

    def _on_fetch_works(self):
        profile = self._author_panel.profile
        sec_uid = profile.get("sec_user_id") or profile.get("sec_uid", "")
        if not sec_uid:
            self._log.append("⚠ 作者 sec_user_id 未获取", "#f59e0b")
            return
        self._log.append(f"▸ 获取作者所有作品: {profile.get('nickname', '?')}", "#38bdf8")
        task = _AuthorFetchTask("works", sec_uid,
                                self._cm.get(self._current_platform),
                                platform=self._current_platform)
        task.signals.log.connect(self._log.append)
        task.signals.done.connect(self._on_works_loaded)
        task.signals.failed.connect(self._on_author_task_failed)
        self._tasks.keep(task,
                            getattr(task.signals, "done", None),
                            getattr(task.signals, "finished", None),
                            getattr(task.signals, "error", None),
                            getattr(task.signals, "failed", None))
        self._pool.start(task)

    def _on_follow_list(self):
        cur = self._current_user_profile or {}
        shown = self._author_panel.profile
        profile = cur if not (shown.get("sec_user_id") and "当前登录" in shown.get("nickname", "")) else shown
        sec_uid = profile.get("sec_user_id") or profile.get("sec_uid", "")
        if not sec_uid:
            self._log.append("⚠ 未获取到当前登录用户", "#f59e0b")
            return
        self._log.append(f"📋 关注列表: {profile.get('nickname', '?')}", "#38bdf8")
        task = _AuthorFetchTask("following", sec_uid,
                                self._cm.get(self._current_platform),
                                platform=self._current_platform)
        task.signals.log.connect(self._log.append)
        task.signals.done.connect(self._on_following_loaded)
        task.signals.failed.connect(self._on_author_task_failed)
        self._tasks.keep(task,
                            getattr(task.signals, "done", None),
                            getattr(task.signals, "finished", None),
                            getattr(task.signals, "error", None),
                            getattr(task.signals, "failed", None))
        self._pool.start(task)

    def _on_collect_list(self):
        cur = self._current_user_profile or {}
        profile = cur or self._author_panel.profile
        sec_uid = profile.get("sec_user_id") or profile.get("sec_uid", "")
        if not sec_uid:
            self._log.append("⚠ 未获取到当前登录用户", "#f59e0b")
            return
        self._log.append(f"⭐ 收藏列表: {profile.get('nickname', '?')}", "#38bdf8")
        task = _AuthorFetchTask("collection", sec_uid,
                                self._cm.get(self._current_platform),
                                platform=self._current_platform)
        task.signals.log.connect(self._log.append)
        task.signals.done.connect(self._on_collection_loaded)
        task.signals.failed.connect(self._on_author_task_failed)
        self._tasks.keep(task,
                            getattr(task.signals, "done", None),
                            getattr(task.signals, "finished", None),
                            getattr(task.signals, "error", None),
                            getattr(task.signals, "failed", None))
        self._pool.start(task)

    def _on_works_loaded(self, items):
        self._open_works_page("作者所有作品", items)

    def _on_collection_loaded(self, items):
        self._open_works_page("收藏列表", items)

    def _on_following_loaded(self, items):
        if not items:
            self._log.append("⚠ 关注列表: 没有数据", "#f59e0b")
            return
        page = UsersPage(title="关注列表")
        page.set_users(items, title="关注列表")
        self._open_data_window("关注列表", page)

    def _on_author_task_failed(self, err: str):
        self._log.append(f"✗ {err}", "#ef4444")

    # ---------------- 数据窗口 (作品/列表/表格/评论) ----------------

    def _open_data_window(self, title: str, page: QWidget):
        """在独立非模态窗口中显示数据页 (替换作品资料区页签)。"""
        self._data_win.set_content(page, title)
        self._data_win.open()

    def _open_works_page(self, title: str, items: list[dict]):
        """作品列表页 (统一入口: 所有作品/收藏/批量预览 经 norm_work 归一化)。"""
        from shared.core import norm_work
        items = [{**norm_work(it, it.get("platform", "") or self._current_platform),
                  **{k: v for k, v in (it or {}).items() if v not in (None, "")}}
                 for it in (items or [])]
        if not items:
            self._log.append(f"⚠ {title}: 没有数据", "#f59e0b")
            return
        page = WorkGridPage()
        page.set_works(items, title=title)
        page.download_requested.connect(self._on_download_selected)
        self._open_data_window(title, page)
        self._log.append(f"✓ {title}: {len(items)} 个作品 (已打开)", "#22c55e")

    def _open_data_page(self, title: str, data: list,
                        weights: list | None = None):
        if not data:
            return
        if isinstance(data[0], dict):
            keys = list(data[0].keys())[:6]
            headers = [str(k) for k in keys]

            def _val(v):
                s = str(v) if v is not None else ""
                return (s[:40] + "…") if len(s) > 40 else (s or "—")

            rows = [[_val(d.get(k, "")) for k in keys] for d in data[:200]]
        else:
            n = max((len(r) if isinstance(r, (list, tuple)) else 1
                     for r in data), default=1)
            headers = ["#"] + [f"值{i}" for i in range(1, n + 1)]
            rows = []
            for i, r in enumerate(data[:200], 1):
                cells = list(r) if isinstance(r, (list, tuple)) else [r]
                rows.append([str(i)] + [str(c)[:40] for c in cells])
        page = DataTablePage(title=title)
        page.set_rows(headers, rows, weights=weights, title=title)
        self._open_data_window(title, page)

    def _open_comments_page(self, items: list):
        if not items:
            return
        rows = [[c.get("user", "—"), c.get("content", ""),
                 str(c.get("likes", 0))]
                for c in items if c.get("content")]
        page = DataTablePage(title="评论")
        page.set_rows(["用户", "内容", "点赞"], rows,
                      weights=[1, 4, 1], title="评论列表")
        self._open_data_window("评论列表", page)

    def _on_download_selected(self, ids: list):
        if not ids:
            return
        self._log.append(f"✓ 已选择 {len(ids)} 个作品, 开始批量下载", "#22c55e")
        # 按当前平台拼接作者主页链接 (账号功能需要 URL 重新拉列表过滤)
        sec = self._author_panel.profile.get("sec_user_id", "")
        home = {
            "bilibili": f"https://space.bilibili.com/{sec}",
            "kuaishou": f"https://www.kuaishou.com/profile/{sec}",
            "xiaohongshu": f"https://www.xiaohongshu.com/user/profile/{sec}",
        }.get(self._current_platform, f"https://www.douyin.com/user/{sec}")
        self._on_execute("account", home, selected=ids)

    # ---------------- 设置 / 登录 (独立非模态窗口) ----------------

    def _open_settings(self):
        self._settings_page._config = ConfigManager.load()
        self._settings_page._suspend = True
        slider = self._settings_page._font_slider
        slider.setValue(self._settings_page._config.font_size)
        self._settings_page._suspend = False
        self._settings_win.open()

    def _open_login(self):
        if not self._current_platform:
            self.statusBar().showMessage("请先选择平台", 3000)
            return
        cookie = self._cm.get(self._current_platform)
        try:
            ops = PlatformBus.get_ops(self._current_platform)
            hint = ops.cookie_hint if ops else ""
        except Exception:
            hint = ""
        self._login_page.setup(self._current_platform, hint, cookie)
        self._login_win.open()

    def _open_browser(self):
        """打开内嵌浏览器窗口 (App 式: 我的作品/收藏/关注 → 用户作品)。"""
        profile = self._current_user_profile or {}
        self._browse_win.open_platform(
            self._current_platform,
            sec_uid=profile.get("sec_user_id", ""), profile=profile)
        self._browse_win.open()

    def _on_browse_download(self, ids: list):
        """浏览器窗口下载请求 → 复用主窗口账号批量下载链路。"""
        if not ids:
            return
        if not self._current_platform:
            self._log.append("⚠ 请先在左侧选择平台", "#f59e0b")
            return
        profile = self._current_user_profile or {}
        sec = profile.get("sec_user_id", "")
        home = {
            "bilibili": f"https://space.bilibili.com/{sec}",
            "kuaishou": f"https://www.kuaishou.com/profile/{sec}",
            "xiaohongshu": f"https://www.xiaohongshu.com/user/profile/{sec}",
        }.get(self._current_platform, f"https://www.douyin.com/user/{sec}")
        self._log.append(
            f"✓ [浏览器] 已选择 {len(ids)} 个作品, 开始批量下载", "#22c55e")
        self._on_execute("account", home, selected=ids)

    def _open_history(self):
        """打开下载记录窗口 (GUI/TUI 共用 Volume/history.jsonl)。"""
        from shared.core.download_history import get_history
        rows = get_history().load(limit=500)
        if not rows:
            self._log.append("⚠ 暂无下载记录", "#f59e0b")
            return
        # 详情页: 每条记录的完整字段 + 下载日志拼入"详情"列
        table_rows = []
        for r in rows:
            detail = "\n".join([
                f"作者: {r.get('author_name', '—')}",
                f"作者主页: {r.get('author_home', '—')}",
                f"作品链接: {r.get('share_url', '—')}",
                f"发布日期: {r.get('publish_date', '—')}",
                f"下载时间: {r.get('downloaded_at', '—')}",
                f"保存路径: {r.get('file_path', '—')}",
                "---- 下载日志 ----",
                *(r.get("log") or []),
            ])
            table_rows.append([
                r.get("downloaded_at", ""),
                r.get("platform", ""),
                (r.get("title") or "")[:40],
                r.get("author_name", ""),
                r.get("publish_date", ""),
                r.get("share_url", ""),
                detail,
            ])
        page = DataTablePage(title="下载记录")
        page.set_rows(
            ["时间", "平台", "作品介绍", "作者", "发布日期", "作品链接", "详情"],
            table_rows,
            weights=[2, 1, 3, 2, 1.5, 3, 0],   # 详情列 0 = 按需 (弹详情)
            title=f"下载记录 ({len(rows)} 条)")
        self._open_data_window("下载记录", page)
        self._log.append(f"✓ 下载记录: {len(rows)} 条", "#22c55e")

    def _toggle_theme(self):
        app = QApplication.instance()
        new_theme = _theme.toggle_theme(app)
        if hasattr(self, "_theme_btn"):
            self._theme_btn.setText("暗色" if new_theme == "dark" else "亮色")
        self._update_topbar_density()
        QTimer.singleShot(0, self._update_topbar_density)

    def _open_download_dir(self):
        path = str(VOLUME)
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", path])
        else:
            subprocess.Popen(["xdg-open", path])

    # ---------------- 链接 / 预览 ----------------

    def _on_url_changed(self, text: str):
        self._current_url = (text or "").strip()

    def _on_preview(self):
        url = self._url_input.text().strip()
        if not url:
            if not self._current_platform:
                self._log.append("⚠ 请先在左侧选择平台", "#f59e0b")
                return
            cookie = self._cm.get(self._current_platform)
            if not cookie:
                self._log.append("⚠ 未配置 Cookie", "#f59e0b")
                return
            self._log.append("正在加载当前登录用户...", "#38bdf8")
            self._load_current_user(self._current_platform, cookie)
            return
        if not self._current_platform:
            self._log.append("⚠ 请先在左侧选择平台", "#f59e0b")
            return
        self._current_url = url
        self._log.clear()
        self._log.append(
            f"[{_pn(self._current_platform)}] 正在解析 {url[:60]}...", "#38bdf8")
        # 网络流程全部放后台线程: 主线程只更新 UI, 避免界面卡死
        task = _PreviewTask(url, self._current_platform,
                            self._cm.get(self._current_platform) or "")
        task.signals.log.connect(self._log.append)
        task.signals.done.connect(self._on_preview_done)
        task.signals.failed.connect(self._on_preview_failed)
        self._tasks.keep(task,
                            getattr(task.signals, "done", None),
                            getattr(task.signals, "finished", None),
                            getattr(task.signals, "error", None),
                            getattr(task.signals, "failed", None))
        self._pool.start(task)

    def _on_preview_done(self, work: dict, profile: dict):
        """后台预览完成 → 主线程渲染 (此回调在 GUI 线程执行)。"""
        if not work:
            self._on_preview_failed("parse", "返回数据为空")
            return
        self._video_info.show_work(work)
        self._feature_panel.set_work_available(True)
        self._log.append(
            f"✓ 解析成功: {work.get('title', '')[:40]}", "#22c55e")
        if profile:
            self._author_panel.show_work_author(profile)
            self._log.append(f"✓ 作者: {profile.get('nickname', '')}", "#22c55e")

    def _on_preview_failed(self, kind: str, detail: str):
        self._video_info.show_error("解析失败")
        self._feature_panel.set_work_available(False)
        label = {
            "timeout": "请求超时",
            "exception": "解析异常",
            "parse": "解析失败",
        }.get(kind, "解析失败")
        msg = f"✗ {label}" + (f" · {detail}" if detail else "")
        self._log.append(msg, "#ef4444")

    # ---------------- 作者 / 作品 操作 ----------------

    def _save_image(self, url: str, subdir: str, prefix: str):
        """保存图片到磁盘 (后台线程下载, 主线程只显示结果)。"""
        if not url:
            self._log.append("⚠ 无图片地址", "#f59e0b")
            return
        import time
        d = VOLUME / (self._current_platform or "common") / subdir
        path = d / f"{prefix}_{int(time.time())}.png"
        self._log.append("▸ 正在下载图片...", "#38bdf8")
        task = _ImageSaveTask(url, path)
        task.signals.done.connect(
            lambda pth: self._log.append(f"✓ 已保存: {pth}", "#22c55e"))
        task.signals.failed.connect(
            lambda err: self._log.append(f"✗ 下载失败: {err}", "#ef4444"))
        self._tasks.keep(task,
                            getattr(task.signals, "done", None),
                            getattr(task.signals, "finished", None),
                            getattr(task.signals, "error", None),
                            getattr(task.signals, "failed", None))
        self._pool.start(task)

    def _show_link_dialog(self, title: str, url: str):
        if not url:
            self._log.append("⚠ 无链接", "#f59e0b")
            return
        QApplication.clipboard().setText(url)
        self._log.append(f"✓ {title} 已复制: {url}", "#22c55e")
        self.statusBar().showMessage(f"{title} 已复制到剪贴板", 3000)

    def _on_download_avatar(self, url: str):
        self._save_image(url, "avatars", "avatar")

    def _on_open_home(self, url: str):
        self._show_link_dialog("作者主页链接", url)

    def _on_copy_link(self, url: str):
        self._show_link_dialog("作品链接", url)

    def _on_download_cover(self, url: str):
        self._save_image(url, "covers", "cover")

    def _on_show_comments(self, work_id: str):
        if not work_id:
            self._log.append("⚠ 无作品ID, 无法获取评论", "#f59e0b")
            return
        self._log.append(f"💬 获取评论: {work_id}", "#38bdf8")
        task = _AuthorFetchTask("comments", work_id,
                                self._cm.get(self._current_platform),
                                platform=self._current_platform)
        task.signals.log.connect(self._log.append)
        task.signals.done.connect(self._on_comments_loaded)
        task.signals.failed.connect(self._on_author_task_failed)
        self._tasks.keep(task,
                            getattr(task.signals, "done", None),
                            getattr(task.signals, "finished", None),
                            getattr(task.signals, "error", None),
                            getattr(task.signals, "failed", None))
        self._pool.start(task)

    def _on_comments_loaded(self, items):
        if not items:
            self._log.append("⚠ 评论: 没有数据", "#f59e0b")
            return
        self._open_comments_page(items)
        self._log.append(f"✓ 评论 {len(items)} 条 (已打开)", "#22c55e")

    # ---------------- 功能执行 ----------------

    def _on_execute(self, feature_id: str, url: str = "",
                    opts=None, selected=None):
        if not self._current_platform:
            self._log.append("⚠ 请先在左侧选择平台", "#f59e0b")
            return
        url = (url or "").strip()
        if not url:
            work = self._video_info.work
            url = (work.get("share_url") or work.get("video_url") or "").strip()
        if not url:
            url = (self._current_url or "").strip()
        if not url:
            url = self._url_input.text().strip()
        if not url and feature_id not in ("hot", "collection"):
            self._log.append("⚠ 请先粘贴链接并解析", "#f59e0b")
            return
        cookie = self._cm.get(self._current_platform)
        save_dir = VOLUME / self._current_platform
        save_dir.mkdir(parents=True, exist_ok=True)
        worker = FeatureWorker(self._current_platform, feature_id, url,
                               cookie, str(save_dir), selected=selected)
        worker.signals.log_line.connect(self._log.append)
        worker.signals.finished.connect(self._on_result)
        worker.signals.error.connect(
            lambda e: self._log.append(f"错误: {e}", "#ef4444"))
        from .widgets.feature_panel import LIVE_FEATURES
        if feature_id in LIVE_FEATURES:
            self._current_worker = worker
            self._feature_panel.set_recording(True)
        self._tasks.keep(worker,
                            getattr(worker.signals, "done", None),
                            getattr(worker.signals, "finished", None),
                            getattr(worker.signals, "error", None),
                            getattr(worker.signals, "failed", None))
        self._pool.start(worker)
        self._log.append(
            f"[{_pn(self._current_platform)}] 启动 {feature_id}", "#38bdf8")

    def _on_stop_recording(self):
        if self._current_worker:
            self._current_worker.stop()
            self._log.append("正在停止录制...", "#f59e0b")

    def _on_result(self, result: dict):
        self._current_worker = None
        self._feature_panel.set_recording(False)
        self._log.set_result(result)
        success = result.get("success", False)
        msg = result.get("message", "")
        self.statusBar().showMessage(msg)
        if success and result.get("preview") == "batch":
            items = result.get("data") or []
            self._open_works_page("批量下载预览", items)
        elif success and result.get("data"):
            data = result.get("data") or []
            self._open_data_table(msg, data)

    def _open_data_table(self, title: str, data: list):
        if not data:
            return
        self._open_data_page(title[:24] or "数据", data)

    # ---------------- 字号 / 设置保存 ----------------

    def _apply_font_size(self, value: int):
        """实时应用全局字号，并重新生成当前主题的 QSS 字号令牌。"""
        app = QApplication.instance()
        if app is None:
            return
        _theme.apply_font_size(app, int(value))
        self._update_topbar_density()
        QTimer.singleShot(0, self._update_topbar_density)

    def _on_settings_saved(self):
        cfg = ConfigManager.load()
        self._apply_font_size(cfg.font_size)
        self._log.append("✓ 设置已保存", "#22c55e")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_topbar_density()

    def closeEvent(self, event):
        try:
            self._tasks.clear()   # 释放后台任务强引用
        except Exception:
            pass
        try:
            self._login_page.shutdown()
        except Exception:
            pass
        for win in (getattr(self, "_login_win", None),
                    getattr(self, "_settings_win", None),
                    getattr(self, "_data_win", None)):
            if win is not None:
                win.close()
        super().closeEvent(event)
