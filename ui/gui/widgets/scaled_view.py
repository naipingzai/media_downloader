"""等比缩放容器 —— 窗口 resize 时整体等比压缩/放大整个界面。

原理:
  内容 widget 固定为「设计尺寸」, 放入 QGraphicsScene 经 QGraphicsProxyWidget
  承载; 外层 QGraphicsView 在 resizeEvent 中按
      scale = min(视口宽/设计宽, 视口高/设计高)
  设置等比变换。效果与浏览器缩放一致:
  - 所有组件/文字/图片/按钮 同比例缩放
  - 相对位置完全不变 (不会因布局重排而移动)
  - QGraphicsProxyWidget 保留鼠标/键盘交互 (按钮仍可点击、输入框仍可输入)

用法:
    central = QWidget(); ... 原布局代码不变 ...
    self.setCentralWidget(ScaledContentView(central, design_size=(1380, 900)))
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import (
    QFrame, QGraphicsScene, QGraphicsView, QWidget,
)


class ScaledContentView(QGraphicsView):
    """把任意 widget 变成「随窗口等比缩放」的视图。"""

    def __init__(self, content: QWidget,
                 design_size: tuple[int, int] = (1380, 900),
                 parent=None):
        # QGraphicsView 基类必须先初始化, 再创建 scene
        super().__init__(parent)
        scene = QGraphicsScene(self)
        scene.setSceneRect(0, 0, design_size[0], design_size[1])
        # 内容固定为设计尺寸 (场景内不受窗口 resize 影响 → 布局稳定)
        content.setFixedSize(*design_size)
        self._proxy = scene.addWidget(content)
        self.setScene(scene)
        self._design_w, self._design_h = design_size
        self._current_scale = 1.0
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: #0f172a; border: none;")
        self._apply_scale()

    @property
    def current_scale(self) -> float:
        """当前等比缩放系数 (诊断/测试用)。"""
        return self._current_scale

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._apply_scale()

    def _apply_scale(self):
        vp = self.viewport()
        if vp.width() <= 0 or vp.height() <= 0:
            return
        # 等比: 取宽高比中较小者, 保证内容完整可见 (不变形)
        s = min(vp.width() / self._design_w, vp.height() / self._design_h)
        self._current_scale = s
        self.setTransform(QTransform.fromScale(s, s))
        self.setAlignment(Qt.AlignCenter)
