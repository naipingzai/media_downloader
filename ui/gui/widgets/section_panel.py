"""统一面板容器 — 4 个区都使用这种边框 (左上角纯文字标题)。

四个区域从上到下:
  1. 作者资料卡
  2. 链接
  3. 作品资料卡
  4. 功能
"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QWidget,
)


# 4 个区都使用这套样式
PANEL_QSS = """
QFrame#SectionPanel { background: #1e293b; border: 1px solid #334155; border-radius: 8px; }
QLabel#SectionTitle { color: #cbd5e1; font-size: 14px; font-weight: bold;
                     background: transparent; border: none; padding: 0; margin: 0; }
"""


class SectionPanel(QFrame):
    """统一的「带边框 + 左上角文字标题」面板。

    用法:
        p = SectionPanel("作者资料")
        p.addWidget(some_widget)         # 标题下方的内容
        p.addLayout(some_layout)
    """

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SectionPanel")
        self.setStyleSheet(PANEL_QSS)

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

    def addWidget(self, w: QWidget):
        self._body.addWidget(w)

    def addLayout(self, layout):
        self._body.addLayout(layout)

    def addStretch(self, stretch: int = 0):
        self._body.addStretch(stretch)
