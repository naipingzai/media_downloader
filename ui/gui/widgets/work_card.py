"""作品卡片 — 与作品资料卡一致的「左封面 + 右资料」布局，供批量预览复用。

详情行使用真 QWidget 边框行 (QLabel 富文本不支持 div border CSS)。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout,
)

from .cover_label import CoverLabel

__all__ = ["build_work_rows", "build_full_work_rows", "InfoRow", "WorkCardWidget"]


def build_full_work_rows(work: dict) -> list[tuple[str, str]]:
    """作品 → [(标签, 值)] 行列表 (作品资料卡用, 全字段)。"""
    rows: list[tuple[str, str]] = []
    used: set[str] = set()   # 记录已处理的原始 key (防止中英文重复)

    def add(key, label, fmt=None):
        v = work.get(key)
        used.add(key)
        if v in (None, "", [], {}):
            return
        rows.append((label, fmt(v) if fmt else str(v)))

    # 固定信息项 (统一中文标签, 不显示原始英文字段名)
    add("title", "标题")
    add("desc", "描述")
    add("author_name", "作者")
    used.update(("author_id", "user_id", "sec_user_id", "sec_uid",
                 "author_mid", "nickname", "name"))
    for k in ("author_id", "user_id", "sec_user_id", "sec_uid", "author_mid"):
        if work.get(k):
            rows.append(("作者ID", str(work[k])))
            break
    add("platform", "平台")
    add("media_type", "类型", fmt=lambda v: {
        "images": "图集", "video": "视频", "note": "图文",
    }.get(str(v), str(v)))
    add("work_id", "作品ID")
    add("mix_id", "合集ID")
    add("status", "状态")
    add("digg_count", "点赞")
    add("comment_count", "评论")
    add("view_count", "播放")
    add("collect_count", "收藏")
    add("share_count", "转发")
    add("duration", "时长", fmt=lambda v: f"{v} 秒")
    add("create_time", "发布时间")
    add("share_url", "分享链接")
    add("video_url", "视频地址")
    add("image_urls", "图片", fmt=lambda v: f"{len(v)} 张"
        if isinstance(v, list) else "1 张")
    add("has_stream", "流地址", fmt=lambda v: "有" if v else "无")
    add("flv_qualities", "FLV 清晰度", fmt=lambda v: ", ".join(map(str, v)))
    add("hls_qualities", "HLS 清晰度", fmt=lambda v: ", ".join(map(str, v)))
    # 其余字段不再展示 (避免英文字段名泄露到界面)
    return rows


def build_work_rows(work: dict) -> list[tuple[str, str]]:
    """作品 → 精简行列表 (批量卡片用)。"""
    rows: list[tuple[str, str]] = []
    if work.get("title"):
        rows.append(("标题", str(work["title"])))
    if work.get("author_name"):
        rows.append(("作者", str(work["author_name"])))
    aid = work.get("author_id") or work.get("user_id") or work.get("sec_user_id")
    if aid:
        rows.append(("作者ID", str(aid)))
    if work.get("platform"):
        rows.append(("平台", str(work["platform"])))
    if work.get("digg_count"):
        rows.append(("点赞", str(work["digg_count"])))
    if work.get("comment_count"):
        rows.append(("评论", str(work["comment_count"])))
    if work.get("view_count"):
        rows.append(("播放", str(work["view_count"])))
    if work.get("duration"):
        rows.append(("时长", f"{work['duration']}秒"))
    if work.get("image_urls"):
        rows.append(("图片", f"{len(work['image_urls'])} 张"))
    wid = work.get("work_id") or "?"
    rows.append(("作品ID", str(wid)))
    return rows


class InfoRow(QFrame):
    """信息行 (真边框): 标签 | 值。所有详情展示统一用此行。"""

    def __init__(self, label: str, value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("InfoRow")  # 样式由主题 QSS #InfoRow 提供
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)
        lab = QLabel(str(label))
        lab.setStyleSheet(
            "color: #64748b; font-size: 14px; background: transparent;"
            " border: none;")
        lab.setMinimumWidth(64)
        lay.addWidget(lab, 0)
        val = QLabel(str(value))
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        val.setStyleSheet(
            "color: #e2e8f0; font-size: 14px; background: transparent;"
            " border: none;")
        lay.addWidget(val, 1)


class WorkCardWidget(QFrame):
    """作品卡片：左封面 + 右资料（边框行），点击卡片切换选中。"""

    checked_changed = Signal(str, bool)

    _BORDER_NORMAL = "#334155"
    _BORDER_CHECKED = "#38bdf8"

    def __init__(self, work: dict, checked: bool = True, parent=None):
        super().__init__(parent)
        self._work = work  # 原始数据 (列表过滤用)
        self._work_id = str(work.get("work_id", ""))
        cov = (work.get("cover_url") or work.get("cover")
               or work.get("pic") or "")
        if isinstance(cov, dict):
            urls = cov.get("url_list") or cov.get("url") or []
            cov = (urls[0] if isinstance(urls, list) and urls
                   else urls if isinstance(urls, str) else "")
        self._cover_url = str(cov)
        self._checked = checked
        self.setCursor(Qt.PointingHandCursor)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._body = QFrame()
        self._body.setObjectName("WorkCardBody")
        body = QHBoxLayout(self._body)
        body.setContentsMargins(10, 10, 10, 10)
        body.setSpacing(12)

        # 左侧：封面 (组件自加载, 调用方无需喂图)
        self._cover = CoverLabel("封面")
        self._cover.setMinimumSize(128, 80)
        self._cover.setFixedSize(152, 96)
        if self._cover_url:
            from ..cover_loader import CoverLoader
            loader = CoverLoader.instance()
            loader.cover_ready.connect(self._on_cover_ready)
            cached = loader.request(self._cover_url)
            if cached is not None:
                self._cover.set_source_pixmap(cached)
        body.addWidget(self._cover, 0, Qt.AlignTop)

        # 右侧：资料 (边框行)
        right = QVBoxLayout()
        right.setSpacing(3)

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
            " font-size: 14px; font-weight: bold;")
        self._badge.setText("✓")
        check_row.addWidget(self._badge)
        right.addLayout(check_row)

        for label, value in build_work_rows(work):
            right.addWidget(InfoRow(label, value))
        right.addStretch()
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

    def _on_cover_ready(self, url: str, pix: QPixmap):
        if url == self._cover_url and not pix.isNull():
            self._cover.set_source_pixmap(pix)

    # ---- 交互 ----
    def _on_check_toggled(self, v: bool):
        self._checked = v
        self._refresh_style()
        self.checked_changed.emit(self._work_id, v)

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.LeftButton:
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
