"""作品资料区域 —— 多页内嵌 (QTabWidget 替代原 QStackedWidget)。

可关闭的页签: 作品网格 / 用户列表 / 数据表格 / 登录 / 设置
默认页: 作品资料 (VideoInfoWidget)
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)
from shared.core.i18n import t


class EmbeddedTabs(QFrame):
    """内嵌页签: 替代原作品资料卡的位置, 支持多页面切换/关闭。"""
    page_closed = Signal(str)

    def __init__(self, default_widget: QWidget, default_title: str = "作品资料",
                 parent=None):
        super().__init__(parent)
        self.setObjectName("EmbeddedTabs")

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("EmbeddedTabBar")
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(False)
        self._tabs.setDocumentMode(True)
        self._tabs.tabCloseRequested.connect(self._on_close)
        self._default_widget = default_widget
        self._default_title = default_title
        self._default_key = "__default__"
        self._pages: dict[str, tuple[str, QWidget]] = {}
        # 默认页
        idx = self._tabs.addTab(default_widget, default_title)
        self._tabs.setTabToolTip(idx, default_title)
        v.addWidget(self._tabs)

    # ===== 公开 API =====
    def add_page(self, key: str, title: str, widget: QWidget,
                 switch: bool = True) -> bool:
        """添加/复用页面。已存在 key 则切换过去。"""
        if key in self._pages:
            if switch:
                self._tabs.setCurrentWidget(widget)
            return False
        idx = self._tabs.addTab(widget, title)
        self._tabs.setTabToolTip(idx, title)
        self._pages[key] = (title, widget)
        # 默认页 idx=0 不能关, 其它可关
        if key == self._default_key:
            close_btn = self._tabs.tabBar().tabButton(0, self._tabs.tabBar().RightSide)
            if close_btn:
                close_btn.setVisible(False)
        if switch:
            self._tabs.setCurrentWidget(widget)
        return True

    def has_page(self, key: str) -> bool:
        return key in self._pages

    def set_current(self, key: str):
        pair = self._pages.get(key)
        if pair:
            self._tabs.setCurrentWidget(pair[1])

    def current_key(self) -> str:
        w = self._tabs.currentWidget()
        for k, (_t, ww) in self._pages.items():
            if ww is w:
                return k
        return self._default_key

    def close_all(self):
        """关闭所有可关闭页面, 切回默认。"""
        for key in list(self._pages.keys()):
            if key == self._default_key:
                continue
            self.close_page(key)
        self._tabs.setCurrentWidget(self._default_widget)

    def close_page(self, key: str):
        pair = self._pages.get(key)
        if not pair or key == self._default_key:
            return
        title, w = pair
        idx = self._tabs.indexOf(w)
        if idx < 0:
            return
        self._tabs.removeTab(idx)
        w.deleteLater()
        self._pages.pop(key, None)
        self.page_closed.emit(key)
        if self._tabs.currentWidget() is None or \
                self._tabs.currentWidget() is w:
            self._tabs.setCurrentWidget(self._default_widget)

    def default_widget(self) -> QWidget:
        return self._default_widget

    # ===== 内部 =====
    def _on_close(self, index: int):
        w = self._tabs.widget(index)
        for key, (_t, ww) in list(self._pages.items()):
            if ww is w:
                if key == self._default_key:
                    return   # 默认页不可关
                self.close_page(key)
                return
