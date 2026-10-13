"""工具窗口 —— 登录 / 设置 以独立非模态窗口显示。

替代原先塞进"作品资料区"页签的做法:
- 普通顶层窗口: 可拖动 / 可缩放 / 可最小化
- 非模态: 不阻塞主窗口, 可与主界面同时操作
- 关闭仅隐藏窗口, 内容对象保留复用 (登录/设置为单例页, 避免销毁后再用崩溃)
"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget


class ToolWindow(QWidget):
    """承载单例页面 (登录/设置) 的非模态窗口。"""

    def __init__(self, title: str, content: QWidget,
                 size: tuple[int, int] = (620, 720), parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle(title)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._content = content
        self._placed = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(content)
        self.resize(*size)

    # ================= 替换内容 =================
    def set_content(self, widget: QWidget, title: str = ""):
        """替换窗口内容 (数据页复用同一窗口时使用)。"""
        lay = self.layout()
        if self._content is not None and self._content is not widget:
            lay.removeWidget(self._content)
            self._content.setParent(None)
        self._content = widget
        lay.addWidget(widget)
        if title:
            self.setWindowTitle(title)

    # ================= 打开 =================
    def open(self):
        """显示窗口 (首次打开时居中于主窗口)。"""
        if not self._placed:
            parent = self.parentWidget()
            if parent is not None:
                pc = parent.frameGeometry().center()
                self.move(pc.x() - self.width() // 2,
                          pc.y() - self.height() // 2)
            self._placed = True
        self.show()
        self.raise_()
        self.activateWindow()

    # ================= 关闭: 仅隐藏 =================
    def closeEvent(self, event):
        self.hide()
        event.ignore()
