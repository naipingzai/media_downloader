"""作品列表内嵌页 —— 单列作品卡行 + 过滤 + 分页渲染。

性能: 大列表分页渲染 (PAGE_SIZE=50), 「加载更多」按需追加,
避免数百 WorkCard 一次性构建导致卡顿。
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton

from ..widgets.work_card import WorkCardWidget
from .base_page import ListPageBase

PAGE_SIZE = 50


class WorkGridPage(ListPageBase):
    """作品列表页 —— 单列卡片行 + 过滤 + 勾选 + 批量下载。"""

    download_requested = Signal(list)  # 选中的 work_id 列表

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._cards: list = []
        self._items: list = []
        self._rendered = 0          # 已渲染数量 (分页)
        # 页脚按钮 (公共设计)
        self.add_footer_button("全选", lambda: self._check_all(True))
        self.add_footer_button("全不选", lambda: self._check_all(False))
        self.add_footer_button("反选", self._invert)
        self._more_btn = self.add_footer_button("加载更多", self._load_more)
        self._more_btn.setVisible(False)
        self._dl_btn = self.add_footer_button(
            "下载所选 (0)", self._on_download, primary=True)
        self._dl_btn.setEnabled(False)
        # 过滤框
        self.enable_filter("🔍 过滤作品 (标题/作者)…")

    # ================= 数据填充 =================
    def set_works(self, items: list, title: str = "作品列表"):
        """填充作品列表 (分页渲染)。"""
        self.clear_content()
        self._cards.clear()
        self._items = list(items)
        self._rendered = 0
        self._filter_le.clear()
        self.set_title(f"{title} · 共 {len(items)} 项")
        if not items:
            self.show_empty("暂无作品", "粘贴链接并解析预览, 或执行一次批量采集")
            self._refresh_count()
            return
        self._render_page()

    def _render_page(self):
        """渲染下一页 (PAGE_SIZE 条)。"""
        start, end = self._rendered, min(self._rendered + PAGE_SIZE,
                                         len(self._items))
        for work in self._items[start:end]:
            card = WorkCardWidget(work, checked=True)
            card.checked_changed.connect(self._on_card_toggled)
            self._cards.append(card)
            self.add_content(card)
        self._rendered = end
        self._more_btn.setVisible(self._rendered < len(self._items))
        if self._rendered < len(self._items):
            self.set_status(
                f"已显示 {self._rendered}/{len(self._items)}, 点击「加载更多」继续")
        self._refresh_count()

    def _load_more(self):
        self._render_page()

    # ================= 过滤 =================
    def _apply_filter(self, keyword: str):
        """按标题/作者显隐卡片 (纯 UI 层过滤)。"""
        shown = 0
        for card in self._cards:
            w = getattr(card, "_work", None) or {}
            title = str(w.get("title") or w.get("desc") or "")
            author = str(w.get("author_name") or "")
            hit = (not keyword or keyword in title.lower()
                   or keyword in author.lower())
            card.setVisible(hit)
            if hit:
                shown += 1
        if self._cards:
            self.set_status(f"过滤后显示 {shown}/{len(self._cards)} 项")

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
