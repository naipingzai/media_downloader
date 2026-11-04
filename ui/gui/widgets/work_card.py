"""批量作品卡片 — 网格紧凑卡 (上封面 + 下信息) + 整卡点击切换选中。

样式全部由主题 QSS 提供 (`#WorkTile*` / `#WorkTileBody`),
组件内不写死颜色, 保证暗/亮主题与字号缩放生效。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout,
)

from .cover_label import CoverLabel

__all__ = ["build_work_rows", "build_full_work_rows", "InfoRow",
           "WorkTile", "WorkCardWidget"]


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
    """作品 → 精简行列表（兼容旧调用；批量卡片正文已改为仅标题）。"""
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
        self.setObjectName("InfoRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 5, 8, 5)
        lay.setSpacing(8)

        lab = QLabel(str(label))
        lab.setObjectName("InfoRowLabel")
        lab.setMinimumWidth(64)
        lay.addWidget(lab, 0)

        val = QLabel(str(value))
        val.setObjectName("InfoRowValue")
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(val, 1)


def _fmt_count(n) -> str:
    """数字 → 紧凑字符串 (1.2万 / 3.5亿)。"""
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return ""
    if n >= 100_000_000:
        return f"{n / 100_000_000:.1f}亿"
    if n >= 10_000:
        return f"{n / 10_000:.1f}万"
    return str(n) if n else ""


class WorkTile(QFrame):
    """网格作品瓦片: 上封面 (16:9) + 下信息 (标题/作者/统计)。

    点击任意位置切换选中; 选中态由 QSS [selected] 蓝框表达。
    """

    checked_changed = Signal(str, bool)

    FIXED_W = 220          # 瓦片固定宽度 (网格按此分列)
    COVER_H = 118          # 封面高度

    def __init__(self, work: dict, checked: bool = True, parent=None):
        super().__init__(parent)
        self._work = work
        self._work_id = str(work.get("work_id", ""))
        cov = (work.get("cover_url") or work.get("cover")
               or work.get("pic") or "")
        if isinstance(cov, dict):
            urls = cov.get("url_list") or cov.get("url") or []
            cov = (urls[0] if isinstance(urls, list) and urls
                   else urls if isinstance(urls, str) else "")
        from ..cover_loader import CoverLoader
        self._cover_url = CoverLoader.normalize_url(str(cov))
        self._checked = checked
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(self.FIXED_W)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._body = QFrame()
        self._body.setObjectName("WorkTileBody")
        v = QVBoxLayout(self._body)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ---- 封面 ----
        self._cover = CoverLabel("封面")
        self._cover.setFixedSize(self.FIXED_W, self.COVER_H)
        if self._cover_url:
            loader = CoverLoader.instance()
            loader.cover_ready.connect(self._on_cover_ready)
            cached = loader.request(self._cover_url)
            if cached is not None:
                self._cover.set_source_pixmap(cached)
        v.addWidget(self._cover)

        # ---- 信息区 ----
        info = QVBoxLayout()
        info.setContentsMargins(10, 8, 10, 10)
        info.setSpacing(4)

        title = str(work.get("title") or work.get("desc")
                    or work.get("caption") or "未命名作品")
        self._title = QLabel(title)
        self._title.setObjectName("WorkTileTitle")
        self._title.setWordWrap(True)
        self._title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info.addWidget(self._title)

        author = str(work.get("author_name")
                     or work.get("extra") or "")
        row = QHBoxLayout()
        row.setSpacing(8)
        self._author = QLabel(f"👤 {author}" if author else "")
        self._author.setObjectName("WorkTileAuthor")
        row.addWidget(self._author, 1)

        digg = _fmt_count(work.get("digg_count"))
        dur = work.get("duration")
        try:
            dur = int(dur or 0)
        except (TypeError, ValueError):
            dur = 0
        if dur > 10000:          # 毫秒兜底
            dur //= 1000
        meta_bits = []
        if digg:
            meta_bits.append(f"❤ {digg}")
        if dur:
            meta_bits.append(f"{dur // 60}:{dur % 60:02d}")
        meta = "  ".join(meta_bits)
        self._meta = QLabel(meta)
        self._meta.setObjectName("WorkTileMeta")
        if meta:
            row.addWidget(self._meta, 0)
        info.addLayout(row)
        v.addLayout(info)
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
        self._checked = bool(v)
        self._refresh_style()
        if emit:
            self.checked_changed.emit(self._work_id, self._checked)

    def set_cover_pixmap(self, pix: QPixmap):
        self._cover.set_source_pixmap(pix)

    def _on_cover_ready(self, url: str, pix: QPixmap):
        if url == self._cover_url and not pix.isNull():
            self._cover.set_source_pixmap(pix)

    # ---- 交互: 卡片任意位置点击都切换选中 ----

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.LeftButton:
            self.set_checked(not self._checked, emit=True)
            ev.accept()
            return
        super().mousePressEvent(ev)

    # ---- 样式 (QSS [selected] 属性选择器: 选中蓝框) ----

    def _refresh_style(self):
        self._body.setProperty("selected",
                               "true" if self._checked else "false")
        self._body.style().unpolish(self._body)
        self._body.style().polish(self._body)
        for child in self._body.findChildren(QLabel):
            child.style().unpolish(child)
            child.style().polish(child)


# 兼容旧名 (其他模块引用 WorkCardWidget)
WorkCardWidget = WorkTile
