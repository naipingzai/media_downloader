"""统一面板容器 — 带边框 + 左上角纯文字标题。

样式完全由主题 QSS 提供 (`#SectionPanel` / `#SectionTitle`), 组件内不再写死颜色,
保证暗/亮主题切换与全局字号缩放都能生效。

用法:
    p = SectionPanel("作者资料")
    p.addWidget(some_widget)         # 标题下方的内容
    p.addLayout(some_layout)
"""
from __future__ import annotations
from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QWidget,
)


class SectionPanel(QFrame):
    """统一的「带边框 + 左上角文字标题」面板。"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SectionPanel")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 10)
        outer.setSpacing(6)

        # 顶部: 左上角纯文字标题 (无图标)
        self._title = QLabel(title)
        self._title.setObjectName("SectionTitle")
        outer.addWidget(self._title)

        # 内容区 (由调用方 addWidget / addLayout)
        self._body = QVBoxLayout()
        self._body.setContentsMargins(0, 0, 0, 0)
        self._body.setSpacing(6)
        outer.addLayout(self._body)

    def addWidget(self, w: QWidget, stretch: int = 0):
        self._body.addWidget(w, stretch)

    def addLayout(self, layout):
        self._body.addLayout(layout)

    def addStretch(self, stretch: int = 0):
        self._body.addStretch(stretch)

    def set_title(self, text: str):
        self._title.setText(text)
