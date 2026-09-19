"""主窗口。"""
import os
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QPushButton,
    QSplitter, QVBoxLayout, QWidget,
)
from shared.core import PROJECT_NAME, VOLUME, __VERSION__
from shared.core.config import ConfigManager
from shared.core.cookies import CookieManager
from shared.core.ops import PlatformBus
from .dialogs.login_dialog import LoginDialog
from .dialogs.settings_dialog import SettingsDialog
from .threads.worker import FeatureWorker
from .widgets.hero_panel import HeroPanel
from .widgets.feature_panel import FeaturePanel
from .widgets.video_info import VideoInfoWidget
from .widgets.collect_result import CollectResultView
from .widgets.result_view import ResultView
from platforms import load_all_platforms


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(PROJECT_NAME)
        self.setMinimumSize(900, 640)
        self.resize(1200, 800)
        load_all_platforms()
        self._cm = CookieManager()
        self._current_platform = ""
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(2)
        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        self.statusBar().showMessage(f"{PROJECT_NAME} v{__VERSION__}")

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(180)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(16, 20, 16, 16)
        sb.setSpacing(8)
        brand = QLabel(PROJECT_NAME.split()[0])
        brand.setObjectName("BrandTitle")
        sb.addWidget(brand)
        sb.addSpacing(12)
        self._platforms = []
        self._platform_btns = []
        for pid in PlatformBus.list_platforms():
            btn = QPushButton(pid)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, p=pid: self._select_platform(p))
            sb.addWidget(btn)
            self._platform_btns.append(btn)
        sb.addSpacing(16)
        sb.addWidget(QLabel(""))
        login_btn = QPushButton("登录/Cookie")
        login_btn.clicked.connect(self._open_login)
        sb.addWidget(login_btn)
        settings_btn = QPushButton("设置")
        settings_btn.clicked.connect(self._open_settings)
        sb.addWidget(settings_btn)
        sb.addStretch()
        ver = QLabel(f"v{__VERSION__}")
        ver.setObjectName("MutedLabel")
        sb.addWidget(ver)
        shell.addWidget(sidebar)

        # Content
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        hero = HeroPanel()
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(28, 24, 28, 26)
        self._hero_title = QLabel("MediaDownloader")
        self._hero_title.setObjectName("HeroTitle")
        self._hero_sub = QLabel("选择平台开始使用")
        self._hero_sub.setStyleSheet("color: #94a3b8; font-size: 13px;")
        hl.addWidget(self._hero_title)
        hl.addWidget(self._hero_sub)
        hl.addStretch()
        cl.addWidget(hero)

        splitter = QSplitter(Qt.Vertical)
        self._feature_panel = FeaturePanel()
        self._feature_panel.execute_clicked.connect(self._on_execute)
        self._feature_panel.preview_clicked.connect(self._on_preview)
        splitter.addWidget(self._feature_panel)

        bottom = QWidget()
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        self._video_info = VideoInfoWidget()
        bl.addWidget(self._video_info, 3)
        self._result_view = ResultView()
        bl.addWidget(self._result_view, 2)
        splitter.addWidget(bottom)
        splitter.setSizes([400, 300])
        cl.addWidget(splitter, 1)

        shell.addWidget(content, 1)

    def _setup_menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu("文件")
        file_menu.addAction("登录/Cookie", self._open_login)
        file_menu.addAction("设置", self._open_settings)
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close)

        view_menu = mb.addMenu("视图")
        view_menu.addAction("打开下载目录", self._open_download_dir)

        help_menu = mb.addMenu("帮助")
        help_menu.addAction("关于", lambda: self.statusBar().showMessage(f"{PROJECT_NAME} v{__VERSION__}"))

    def _setup_status_bar(self):
        self._status_platform = QLabel("")
        self._status_feature = QLabel("")
        self._status_cookie = QLabel("")
        self.statusBar().addPermanentWidget(self._status_platform)
        self.statusBar().addPermanentWidget(self._status_feature)
        self.statusBar().addPermanentWidget(self._status_cookie)

    def _select_platform(self, platform):
        self._current_platform = platform
        for btn in self._platform_btns:
            btn.setChecked(btn.text() == platform)
        features = PlatformBus.get_features(platform)
        self._feature_panel.set_features(features)
        self._hero_title.setText(platform.title())
        self._hero_sub.setText(f"{len(features)} 个功能可用")
        ops = PlatformBus.get_ops(platform)
        cookie = self._cm.get(platform)
        hint = ops.cookie_hint if ops else ""
        cookie_text = f"Cookie: {'✓ ' + str(len(cookie)) + '字符' if cookie else '✗ 未设置'}" if hint else "Cookie: 不需要"
        self._status_platform.setText(f"平台: {platform}")
        self._status_cookie.setText(cookie_text)
        self._video_info.show_empty()
        self._result_view.clear()

    def _open_login(self):
        if not self._current_platform:
            self.statusBar().showMessage("请先选择平台")
            return
        ops = PlatformBus.get_ops(self._current_platform)
        hint = ops.cookie_hint if ops else ""
        current = self._cm.get(self._current_platform)
        dlg = LoginDialog(self._current_platform, hint, current, self)
        dlg.exec()
        cookie = self._cm.get(self._current_platform)
        cookie_text = f"Cookie: {'✓ ' + str(len(cookie)) + '字符' if cookie else '✗ 未设置'}"
        self._status_cookie.setText(cookie_text)

    def _open_settings(self):
        SettingsDialog(self).exec()

    def _open_download_dir(self):
        import subprocess, sys
        path = str(VOLUME)
        if sys.platform == "darwin": subprocess.Popen(["open", path])
        elif sys.platform == "win32": subprocess.Popen(["explorer", path])
        else: subprocess.Popen(["xdg-open", path])

    def _on_preview(self, url):
        if not url.strip():
            self.statusBar().showMessage("请输入链接")
            return
        self._result_view.clear()
        self._result_view.append("正在解析...", "#94a3b8")
        from shared.core.session import create_async_client
        from shared.flow.link import LinkExtractor
        import asyncio
        async def _do():
            client = create_async_client()
            try:
                links = await LinkExtractor(client).run(url, self._current_platform)
                if links:
                    adapter_cls = get_platform(self._current_platform)
                    if adapter_cls:
                        from shared.core.adapter import PlatformConfig
                        adapter = adapter_cls(config=PlatformConfig(
                            name=self._current_platform, display_name="",
                            domains=[], cookie=self._cm.get(self._current_platform)))
                        raw = await adapter.request_detail(links[0])
                        if raw:
                            work = adapter.parse_detail(raw)
                            if work:
                                self._video_info.show_work(work)
                                self._result_view.append("解析成功", "#22c55e")
                            else:
                                self._video_info.show_error("解析失败")
                                self._result_view.append("解析失败", "#ef4444")
                        else:
                            self._video_info.show_error("获取详情失败")
                        await adapter.close()
                    else:
                        self._result_view.append("平台适配器未找到", "#ef4444")
                else:
                    self._video_info.show_error("未提取到有效链接")
                    self._result_view.append("未提取到有效链接", "#ef4444")
            finally:
                await client.close()
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_do())
        loop.close()

    def _on_execute(self, feature_id, url, output_fmt, storage_mode):
        if not self._current_platform:
            self.statusBar().showMessage("请先选择平台")
            return
        self._result_view.clear()
        self._result_view.append(f"执行: {feature_id}", "#38bdf8")
        self._status_feature.setText(f"功能: {feature_id}")
        cookie = self._cm.get(self._current_platform)
        save_dir = VOLUME / self._current_platform
        save_dir.mkdir(parents=True, exist_ok=True)
        worker = FeatureWorker(self._current_platform, feature_id, url, cookie, str(save_dir))
        worker.signals.log_line.connect(lambda t: self._result_view.append(t))
        worker.signals.work_info.connect(lambda w: self._video_info.show_work(w))
        worker.signals.finished.connect(self._on_result)
        worker.signals.error.connect(lambda e: self._result_view.append(f"错误: {e}", "#ef4444"))
        self._pool.start(worker)

    def _on_result(self, result):
        self._result_view.set_result(result)
        if result.get("success"):
            self.statusBar().showMessage(result.get("message", "完成"))
        else:
            self.statusBar().showMessage(f"失败: {result.get('message', '')}")
from platforms import get_platform
