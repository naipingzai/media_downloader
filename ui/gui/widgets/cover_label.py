"""自适应封面标签 — 按比例缩放、居中显示完整封面（不裁剪），随控件尺寸自动缩放。

样式由主题 QSS 提供 (`#CoverLabel` 与 `#CoverLabel[loaded="true"]`)。

可靠性设计（曾出现"封面不显示"）：
1. 图片异步下载完成后通过信号回调绘制；
2. 额外在 paintEvent 中主动查询缓存兜底 —— 即使信号时机错过、
   或控件当时尺寸为 0，只要图片已进缓存，下一次重绘就会显示。
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

__all__ = ["CoverLabel", "RoundAvatarLabel"]


class CoverLabel(QLabel):
    """封面显示控件：留白居中，随尺寸变化自适应重绘。"""

    def __init__(self, placeholder: str = "封面", parent=None):
        super().__init__(parent)
        self.setObjectName("CoverLabel")
        self._pix: QPixmap | None = None
        self._url = ""
        self._placeholder = placeholder
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(96, 64)
        self._set_loaded(False)
        self.show_placeholder()

    def _set_loaded(self, loaded: bool):
        self.setProperty("loaded", "true" if loaded else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def show_placeholder(self, text: str | None = None):
        """显示占位文字（封面/加载中/无封面）。

        必须同时清空 _url: 否则 paintEvent 兜底会按旧 URL 从缓存把
        上一张封面重新画回来 (表现为切换后仍显示旧封面)。
        """
        if text is not None:
            self._placeholder = text
        self._pix = None
        self._url = ""
        self.setPixmap(QPixmap())
        self.setText(self._placeholder)
        self._set_loaded(False)

    def clear_cover(self):
        """完全清空封面 (无文字、无背景描边)。"""
        self._pix = None
        self._url = ""
        self.setPixmap(QPixmap())
        self.setText("")
        self._set_loaded(True)

    def set_source_url(self, url: str) -> bool:
        """按 URL 设置封面。

        命中缓存则立即显示并返回 True；否则发起请求返回 False，
        后续由 cover_ready 信号或 paintEvent 兜底完成绘制。
        """
        from ..cover_loader import CoverLoader
        self._url = CoverLoader.normalize_url(url)
        if not self._url:
            return False
        pix = CoverLoader.cached(self._url)
        if pix is not None and not pix.isNull():
            self.set_source_pixmap(pix)
            return True
        CoverLoader.instance().request(self._url)
        return False

    def set_source_pixmap(self, pix: QPixmap):
        """设置封面图并自适应缩放显示。"""
        self._pix = pix
        self.setText("")
        self._set_loaded(True)
        self._render()

    # ---- 绘制 ----

    def _render(self):
        if self._pix is None or self._pix.isNull():
            return
        target = self.size()
        if target.width() <= 0 or target.height() <= 0:
            # 尚未完成布局: 交给 resizeEvent / paintEvent 再画,
            # 否则 scaled(0x0) 会得到空图, 表现为封面永远空白。
            return
        scaled = self._pix.scaled(target, Qt.KeepAspectRatio,
                                  Qt.SmoothTransformation)
        if scaled.isNull():
            return
        super().setPixmap(scaled)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._render()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._render()

    def paintEvent(self, ev):
        # 最终兜底: 图片可能已下载进缓存, 但信号回调时机被错过
        if self._pix is None and self._url:
            from ..cover_loader import CoverLoader
            pix = CoverLoader.cached(self._url)
            if pix is not None and not pix.isNull():
                self.set_source_pixmap(pix)
        super().paintEvent(ev)


class RoundAvatarLabel(QLabel):
    """圆形头像控件 — 带缓存兜底，避免信号时机错过导致头像空白。

    paintEvent 中主动查 CoverLoader 缓存：只要图片已下载完成，
    下一次重绘必然显示，不依赖 cover_ready 信号的到达时机。
    """

    def __init__(self, size: int = 40, bind_theme: bool = True,
                 object_name: str = "UserAvatar", parent=None):
        super().__init__(parent)
        if bind_theme:
            self.setObjectName(object_name)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self._size = size
        self._url = ""
        self._fallback = "?"

    def clear_user(self):
        """彻底清空头像 (URL/图/占位符)。

        切换平台时必须调用: 若只清 pixmap 而保留 _url,
        paintEvent 兜底会把旧平台头像从缓存重新画回来。
        """
        self._url = ""
        self._fallback = "?"
        self.setPixmap(QPixmap())
        self.setText("👤")

    def set_user(self, url: str, fallback: str = "?"):
        """设置头像 URL 与占位字符（昵称首字母）。"""
        from ..cover_loader import CoverLoader
        self._fallback = (fallback or "?")[:1].upper()
        self._url = CoverLoader.normalize_url(url or "")
        # 先显示占位符，再尝试缓存
        self.setPixmap(QPixmap())
        self.setText(self._fallback)
        if not self._url:
            return
        pix = CoverLoader.cached(self._url)
        if pix is not None and not pix.isNull():
            self._apply(pix)
            return
        CoverLoader.instance().request(self._url)
        # 订阅完成信号: 下载结束后立即应用 (不依赖下一次重绘)
        if not getattr(self, "_subscribed", False):
            try:
                CoverLoader.instance().cover_ready.connect(self._on_ready)
                self._subscribed = True
            except Exception:
                pass

    def _on_ready(self, url: str, pix: QPixmap):
        """下载完成回调: URL 匹配则立即显示 (否则忽略)。"""
        if self._url and url == self._url and not pix.isNull():
            self._apply(pix)

    def _apply(self, pix: QPixmap):
        scaled = pix.scaled(self._size, self._size, Qt.KeepAspectRatio,
                            Qt.SmoothTransformation)
        rounded = QPixmap(self._size, self._size)
        rounded.fill(Qt.transparent)
        from PySide6.QtGui import QPainter, QPainterPath
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, self._size, self._size)
        painter.setClipPath(path)
        dx = (self._size - scaled.width()) // 2
        dy = (self._size - scaled.height()) // 2
        painter.drawPixmap(dx, dy, scaled)
        painter.end()
        self.setText("")
        super().setPixmap(rounded)

    def paintEvent(self, ev):
        # 兜底: 仅当「绑定了 URL 且当前无图」时才查缓存,
        # clear_user() 清空 _url 后不会再复活旧平台头像。
        if self._url and self.pixmap().isNull():
            from ..cover_loader import CoverLoader
            pix = CoverLoader.cached(self._url)
            if pix is not None and not pix.isNull():
                self._apply(pix)
        super().paintEvent(ev)
