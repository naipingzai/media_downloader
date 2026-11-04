"""作品列表内嵌页 —— 响应式网格瓦片 + 分页渲染。

布局: 紧凑瓦片 (上封面+下信息), 按窗口宽度自适应列数 (3~5 列),
resize 时自动重排; 大列表分页渲染 (PAGE_SIZE=60) 避免一次性卡顿。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QGridLayout, QWidget

from ..widgets.work_card import WorkTile
from .base_page import ListPageBase

PAGE_SIZE = 60
TILE_W = 220          # 与 WorkTile.FIXED_W 一致
GAP = 12


class WorkGridPage(ListPageBase):
    """作品网格页 —— 响应式瓦片 + 勾选 + 批量下载。"""

    download_requested = Signal(list)  # 选中的 work_id 列表

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._cards: list = []
        self._items: list = []
        self._rendered = 0          # 已渲染数量 (分页)
        self._grid: QGridLayout | None = None
        self._grid_host: QWidget | None = None
        # 页脚按钮 (公共设计)
        self.add_footer_button("全选", lambda: self._check_all(True))
        self.add_footer_button("全不选", lambda: self._check_all(False))
        self.add_footer_button("反选", self._invert)
        self._more_btn = self.add_footer_button("加载更多", self._load_more)
        self._more_btn.setVisible(False)
        self._dl_btn = self.add_footer_button(
            "下载所选 (0)", self._on_download, primary=True)
        self._dl_btn.setEnabled(False)

    # ================= 网格容器 =================

    def _ensure_grid(self) -> QGridLayout:
        """惰性创建网格宿主 (挂进基类内容区)。"""
        if self._grid is None:
            self._grid_host = QWidget()
            self._grid = QGridLayout(self._grid_host)
            self._grid.setContentsMargins(0, 0, 0, 0)
            self._grid.setHorizontalSpacing(GAP)
            self._grid.setVerticalSpacing(GAP)
            self._grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
            self.add_content(self._grid_host)
            self._grid_host.show()   # clear/rebuild 后显式恢复可见
        return self._grid

    def _columns(self) -> int:
        """按滚动区宽度计算列数 (3~5)。"""
        w = max(self._scroll.viewport().width(), 480)
        for cols in (5, 4, 3):
            if w >= cols * (TILE_W + GAP) - GAP + 24:
                return cols
        return 3

    # ================= 数据填充 =================

    def set_works(self, items: list, title: str = "作品列表"):
        """填充作品网格 (分页渲染)。"""
        self.clear_content()
        self._cards.clear()
        self._items = list(items)
        self._rendered = 0
        self._grid = None
        self._grid_host = None
        self.set_title(f"{title} · 共 {len(items)} 项")
        if not items:
            self.show_empty("暂无作品", "粘贴链接并解析预览, 或执行一次批量采集")
            self._refresh_count()
            return
        self._render_page()

    def _render_page(self):
        """渲染下一页瓦片到网格。"""
        grid = self._ensure_grid()
        cols = self._columns()
        start, end = self._rendered, min(self._rendered + PAGE_SIZE,
                                         len(self._items))
        for i, work in enumerate(self._items[start:end], start=start):
            tile = WorkTile(work, checked=True)
            tile.checked_changed.connect(self._on_card_toggled)
            self._cards.append(tile)
            grid.addWidget(tile, i // cols, i % cols,
                           Qt.AlignTop | Qt.AlignHCenter)
        self._rendered = end
        self._more_btn.setVisible(self._rendered < len(self._items))
        if self._rendered < len(self._items):
            self.set_status(
                f"已显示 {self._rendered}/{len(self._items)}, "
                f"点击「加载更多」继续")
        self._refresh_count()

    def _load_more(self):
        self._render_page()

    # ================= 响应式重排 =================

    def resizeEvent(self, ev: QResizeEvent):
        """窗口宽度变化 → 网格列数变化 → 重排瓦片。"""
        super().resizeEvent(ev)
        self._reflow()

    def _reflow(self):
        """按新列数重排所有已渲染瓦片。"""
        if not self._grid or not self._cards:
            return
        cols = self._columns()
        # 移除现有布局项 (不销毁控件), 重排
        for i in reversed(range(self._grid.count())):
            self._grid.removeItem(self._grid.itemAt(i))
        for i, tile in enumerate(self._cards):
            self._grid.addWidget(tile, i // cols, i % cols,
                                 Qt.AlignTop | Qt.AlignHCenter)

    # ================= 勾选 =================

    def _on_card_toggled(self, _work_id: str, _checked: bool):
        self._refresh_count()

    def _check_all(self, state: bool):
        for c in self._cards:
            if c.isVisible():
                c.set_checked(state)
        self._refresh_count()

    def _invert(self):
        for c in self._cards:
            if c.isVisible():
                c.set_checked(not c.is_checked)
        self._refresh_count()

    def _refresh_count(self):
        n_sel = sum(1 for c in self._cards if c.is_checked)
        self._dl_btn.setText(f"下载所选 ({n_sel})")
        self._dl_btn.setEnabled(n_sel > 0)
        self.set_status(f"已选 {n_sel} / {len(self._cards)}")

    def selected_ids(self) -> list:
        return [c.work_id for c in self._cards if c.is_checked]

    def _on_download(self):
        ids = self.selected_ids()
        if ids:
            self.download_requested.emit(ids)
        self._refresh_count()
