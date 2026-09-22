"""作品卡片 — 与作品资料卡一致的「左封面 + 右资料」布局，供批量预览复用。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from .cover_label import CoverLabel

__all__ = ["build_work_html", "WorkCardWidget"]


def build_work_html(work: dict) -> str:
    """生成作品资料 HTML — 与作品资料卡详情字段保持一致。"""
    lines = []
    if work.get('title'):
        lines.append(f"<b>标题:</b> {work['title']}")
    if work.get('author_name'):
        lines.append(f"<b>作者:</b> {work['author_name']}")
    if work.get('platform'):
        lines.append(f"<b>平台:</b> {work['platform']}")
    if work.get('status'):
        lines.append(f"<b>状态:</b> {work['status']}")
    if work.get('digg_count'):
        lines.append(f"<b>点赞:</b> {work['digg_count']}")
    if work.get('comment_count'):
        lines.append(f"<b>评论:</b> {work['comment_count']}")
    if work.get('view_count'):
        lines.append(f"<b>播放:</b> {work['view_count']}")
    if work.get('duration'):
        lines.append(f"<b>时长:</b> {work['duration']}秒")
    if work.get('video_url'):
        url = work['video_url']
        lines.append(f"<b>视频:</b> {url[:70]}{'...' if len(url) > 70 else ''}")
    if work.get('image_urls'):
        lines.append(f"<b>图片:</b> {len(work['image_urls'])} 张")
    if work.get('has_stream'):
        lines.append(f"<b>流地址:</b> {'有' if work['has_stream'] else '无'}")
    if work.get('flv_qualities'):
        lines.append(f"<b>FLV 清晰度:</b> {', '.join(work['flv_qualities'])}")
    if work.get('hls_qualities'):
        lines.append(f"<b>HLS 清晰度:</b> {', '.join(work['hls_qualities'])}")
    if not lines:
        lines.append(f"<b>作品ID:</b> {work.get('work_id', '?')}")
    return "<br>".join(lines)


class WorkCardWidget(QFrame):
    """作品卡片：左封面 + 右资料（与作品资料卡一致），点击卡片切换选中。

    选中态通过高亮边框 + 角落对勾角标表达，鼠标点击卡片任意位置即可切换，
    右上角同时提供复选框用于精确勾选。
    """

    checked_changed = Signal(str, bool)

    _BORDER_NORMAL = "#334155"
    _BORDER_CHECKED = "#38bdf8"

    def __init__(self, work: dict, checked: bool = True, parent=None):
        super().__init__(parent)
        self._work_id = str(work.get("work_id", ""))
        self._cover_url = str(work.get("cover_url") or work.get("cover") or "")
        self._checked = checked
        self.setCursor(Qt.PointingHandCursor)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._body = QFrame()
        self._body.setObjectName("WorkCardBody")
        body = QHBoxLayout(self._body)
        body.setContentsMargins(10, 10, 10, 10)
        body.setSpacing(12)

        # 左侧：封面
        self._cover = CoverLabel("封面")
        self._cover.setMinimumSize(128, 80)
        self._cover.setFixedSize(152, 96)
        body.addWidget(self._cover, 0, Qt.AlignTop)

        # 右侧：资料（与作品资料卡一致的字段展示）
        right = QVBoxLayout()
        right.setSpacing(4)

        check_row = QHBoxLayout()
        check_row.setSpacing(6)
        self._check = QCheckBox()
        self._check.setCursor(Qt.PointingHandCursor)
        self._check.setChecked(checked)
        self._check.toggled.connect(self._on_check_toggled)
        check_row.addWidget(self._check)
        check_row.addStretch()
        self._badge = QLabel()
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setFixedSize(22, 22)
        self._badge.setStyleSheet(
            "background: #0ea5e9; color: #0f172a; border-radius: 11px;"
            " font-size: 13px; font-weight: bold;")
        self._badge.setText("✓")
        check_row.addWidget(self._badge)
        right.addLayout(check_row)

        self._info = QLabel(build_work_html(work))
        self._info.setWordWrap(True)
        self._info.setTextFormat(Qt.RichText)
        self._info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._info.setAlignment(Qt.AlignTop)
        self._info.setStyleSheet("color: #cbd5e1; background: transparent;"
                                " border: none;")
        right.addWidget(self._info, 1)
        body.addLayout(right, 1)

        outer.addWidget(self._body)
        self._refresh_style()

    # ---- 属性 ----
    @property
    def work_id(self) -> str:
        return self._work_id

    @property
    def cover_url(self) -> str:
        return self._cover_url

    @property
    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, v: bool, emit: bool = False):
        self._checked = v
        self._check.blockSignals(True)
        self._check.setChecked(v)
        self._check.blockSignals(False)
        self._refresh_style()
        if emit:
            self.checked_changed.emit(self._work_id, v)

    def set_cover_pixmap(self, pix: QPixmap):
        self._cover.set_source_pixmap(pix)

    # ---- 交互 ----
    def _on_check_toggled(self, v: bool):
        self._checked = v
        self._refresh_style()
        self.checked_changed.emit(self._work_id, v)

    def mousePressEvent(self, ev: QMouseEvent):
        # 点击卡片任意处（除复选框/文本选择）切换选中
        if ev.button() == Qt.LeftButton and not self._info.hasSelectedText():
            self.set_checked(not self._checked, emit=True)
        super().mousePressEvent(ev)

    # ---- 样式 ----
    def _refresh_style(self):
        border = self._BORDER_CHECKED if self._checked else self._BORDER_NORMAL
        bg = "#22314a" if self._checked else "#1e293b"
        self._body.setStyleSheet(
            f"#WorkCardBody {{ background: {bg}; border: 2px solid {border};"
            " border-radius: 8px; }")
        self._badge.setVisible(self._checked)
