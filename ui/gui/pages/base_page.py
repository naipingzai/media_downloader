"""列表内嵌页公共基类 —— WorkGridPage / UsersPage / DataTablePage 共用。

统一设计:
  ┌────────────────────────────────────────┐
  │ 标题                    共 N 条  [按钮]│ ← 页头 (统一)
  │ 🔍 [过滤关键词…                      ] │ ← 过滤框 (enable_filter 开启)
  ├────────────────────────────────────────┤
  │                                        │
  │   内容区 (仅纵向滚动, 无横向滚动)        │ ← 子类填充
  │                                        │
  └────────────────────────────────────────┘
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)


class ListPageBase(QWidget):
    """列表内嵌页基类 —— 页头/过滤/滚动区/页脚统一, 子类只填内容。"""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ---- 页头: 标题 | 计数 | 右侧按钮区 ----
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        self._title_label = QLabel(title)
        self._title_label.setObjectName("PageTitle")
        hdr.addWidget(self._title_label)
        hdr.addStretch()
        self._count_label = QLabel("")
        self._count_label.setObjectName("PageStatus")
        hdr.addWidget(self._count_label)
        self._header_actions = QHBoxLayout()
        self._header_actions.setSpacing(8)
        hdr.addLayout(self._header_actions)
        root.addLayout(hdr)

        # ---- 过滤框 (子类 enable_filter() 开启) ----
        self._filter_row = QHBoxLayout()
        self._filter_row.setSpacing(8)
        self._filter_le = QLineEdit()
        self._filter_le.setPlaceholderText("🔍 输入关键词过滤 (标题/作者)…")
        self._filter_le.setObjectName("FilterInput")
        self._filter_le.setClearButtonEnabled(True)
        self._filter_le.textChanged.connect(self._on_filter_changed)
        self._filter_row.addWidget(self._filter_le, 1)
        self._filter_row.setVisible(False)
        root.addLayout(self._filter_row)

        # ---- 内容区: 仅纵向滚动 ----
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._container = QWidget()
        self._content = QVBoxLayout(self._container)
        self._content.setContentsMargins(0, 0, 0, 0)
        self._content.setSpacing(6)
        self._content.addStretch()
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll, 1)

        # ---- 页脚: 状态 | 按钮区 ----
        self._footer = QHBoxLayout()
        self._footer.setSpacing(8)
        self._status_label = QLabel("")
        self._status_label.setObjectName("PageStatus")
        self._footer.addWidget(self._status_label)
        self._footer.addStretch()
        self._footer_actions = QHBoxLayout()
        self._footer_actions.setSpacing(8)
        self._footer.addLayout(self._footer_actions)
        root.addLayout(self._footer)
        # ---- 空态组件 (数据为空时显示, 有数据时隐藏) ----
        self._empty = QLabel("")
        self._empty.setObjectName("EmptyState")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.setVisible(False)
        root.addWidget(self._empty)

    # ---------- 子类辅助 ----------
    def set_title(self, text: str):
        self._title_label.setText(text)

    def set_count(self, text: str):
        self._count_label.setText(text)

    def set_status(self, text: str):
        self._status_label.setText(text)

    def add_header_button(self, text: str, slot) -> QPushButton:
        return self._add_button(self._header_actions, text, slot)

    def add_footer_button(self, text: str, slot,
                          primary: bool = False) -> QPushButton:
        return self._add_button(self._footer_actions, text, slot, primary)

    @staticmethod
    def _add_button(layout, text, slot, primary: bool = False) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("PagePrimaryButton" if primary else "PageGhostButton")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(slot)
        layout.addWidget(b)
        return b

    # ---------- 过滤 ----------
    def enable_filter(self, placeholder: str = "🔍 输入关键词过滤…"):
        """开启页头过滤框 (子类覆写 _apply_filter 响应)。"""
        self._filter_le.setPlaceholderText(placeholder)
        self._filter_row.setVisible(True)

    def filter_text(self) -> str:
        return self._filter_le.text().strip().lower()

    def _on_filter_changed(self, _text: str):
        self._apply_filter(self.filter_text())

    def _apply_filter(self, keyword: str):
        """子类覆写: 按 keyword 显隐内容项。"""

    # ---------- 内容 ----------
    def clear_content(self):
        """清空内容区 (保留尾部 stretch)。"""
        while self._content.count():
            it = self._content.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._content.addStretch()

    def add_content(self, widget: QWidget):
        """在内容区追加子控件 (插到尾部 stretch 之前)。"""
        self._content.insertWidget(self._content.count() - 1, widget)
        self._empty.setVisible(False)

    def show_empty(self, text: str = "暂无数据", hint: str = ""):
        """显示空态提示 (隐藏滚动区)。"""
        self._scroll.setVisible(False)
        msg = f"<p style='font-size:16px; font-weight:bold;'>{text}</p>"
        if hint:
            msg += f"<p style='font-size:13px;'>{hint}</p>"
        self._empty.setText(msg)
        self._empty.setVisible(True)

    def ensure_content(self):
        """有数据时恢复内容区可见 (add_content 自动调用)。"""
        self._scroll.setVisible(True)
        self._empty.setVisible(False)
