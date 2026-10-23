"""作品列表内嵌页 —— 单列作品卡行 (复用 WorkCardWidget 公共组件, 统一设计)。

布局 (与关注列表/数据表格页同为单列行, 无横向滚动):
  ┌──────────────────────────────────────┐
  │ 作品列表 · 共 N 项                    │
  │ ┌────────┬───────────────────────┐   │
  │ │ 封面   │ 标题/作者/统计 信息行   │   │ ← WorkCardWidget (公共组件)
  │ └────────┴───────────────────────┘   │
  │ ┌────────┬───────────────────────┐   │
  │ │ ...    │ ...                    │   │
  │ └────────┴───────────────────────┘   │
  │ 状态: 已选 N / M   [全选][下载所选]   │
  └──────────────────────────────────────┘
"""
from __future__ import annotations

from PySide6.QtCore import Signal

from ..widgets.work_card import WorkCardWidget
from .base_page import ListPageBase


class WorkGridPage(ListPageBase):
    """作品列表页 —— 单列卡片行 + 勾选 + 批量下载。"""

    download_requested = Signal(list)  # 选中的 work_id 列表

    def __init__(self, parent=None):
        super().__init__(title="", parent=parent)
        self._cards: list = []
        self._items: list = []
        # 页脚按钮 (公共设计)
        self.add_footer_button("全选", lambda: self._check_all(True))
        self.add_footer_button("全不选", lambda: self._check_all(False))
        self.add_footer_button("反选", self._invert)
        self._dl_btn = self.add_footer_button(
            "下载所选 (0)", self._on_download, primary=True)
        self._dl_btn.setEnabled(False)

    def set_works(self, items: list, title: str = "作品列表"):
        """填充作品列表 (单列卡片行)。"""
        self.clear_content()
        self._cards.clear()
        self._items = list(items)
        for work in items:
            card = WorkCardWidget(work, checked=True)
            card.checked_changed.connect(self._on_card_toggled)
            self._cards.append(card)
            self.add_content(card)
        self.set_title(f"{title} · 共 {len(items)} 项")
        self._refresh_count()

    def _on_card_toggled(self, _work_id: str, _checked: bool):
        self._refresh_count()

    def _check_all(self, state: bool):
        for c in self._cards:
            c.set_checked(state)
        self._refresh_count()

    def _invert(self):
        for c in self._cards:
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
