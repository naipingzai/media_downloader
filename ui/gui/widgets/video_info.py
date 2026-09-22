"""解析结果卡片 — 左侧封面 + 右侧详情。"""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from shared.core.i18n import t
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)


class VideoInfoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._net = QNetworkAccessManager(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)
        outer.setSpacing(0)
        header = QHBoxLayout()
        header.setContentsMargins(14, 10, 14, 4)
        header.setSpacing(6)
        self._title_label = QLabel(t("video_info"))
        self._title_label.setObjectName("SectionTitle")
        header.addWidget(self._title_label)
        self._state = QLabel("(" + t("waiting_parse") + ")")
        self._state.setObjectName("Caption")
        header.addWidget(self._state)
        header.addStretch()
        outer.addLayout(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        self._inner_layout = QHBoxLayout(inner)
        self._inner_layout.setContentsMargins(14, 4, 14, 12)
        self._inner_layout.setSpacing(12)

        # 左侧：封面
        self._cover = QLabel()
        self._cover.setFixedSize(160, 100)
        self._cover.setAlignment(Qt.AlignCenter)
        self._cover.setStyleSheet("background: #0f172a; border-radius: 4px;")
        self._cover.setVisible(False)
        self._inner_layout.addWidget(self._cover, 0, Qt.AlignTop)

        # 右侧：信息文本
        right = QVBoxLayout()
        right.setSpacing(4)
        self._info = QLabel(t("parse_hint"))
        self._info.setWordWrap(True)
        self._info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._info.setStyleSheet("color: #64748b;")
        self._info.setAlignment(Qt.AlignTop)
        right.addWidget(self._info)
        self._detail = QLabel("")
        self._detail.setWordWrap(True)
        self._detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._detail.setAlignment(Qt.AlignTop)
        self._detail.setVisible(False)
        right.addWidget(self._detail)
        right.addStretch()
        self._inner_layout.addLayout(right, 1)

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def _load_cover(self, url: str):
        """异步加载封面图。"""
        if not url:
            self._cover.setVisible(False)
            return
        self._cover.setVisible(True)
        self._cover.setText("...")
        req = QNetworkRequest(QUrl(url))
        referer = ""
        u = url.lower()
        if "douyin" in u or "douyinpic" in u:
            referer = "https://www.douyin.com/"
        elif "bilibili" in u or "hdslb" in u:
            referer = "https://www.bilibili.com/"
        elif "kuaishou" in u or "ksurl" in u:
            referer = "https://www.kuaishou.com/"
        elif "xiaohongshu" in u or "xhscdn" in u:
            referer = "https://www.xiaohongshu.com/"
        if referer:
            req.setRawHeader(b"Referer", referer.encode())
        req.setRawHeader(b"User-Agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        req.setTransferTimeout(8000)
        reply = self._net.get(req)
        reply.finished.connect(lambda r=reply: self._on_cover_reply(r))

    def _on_cover_reply(self, reply):
        try:
            if reply.error() == reply.NoError:
                img = QImage.fromData(reply.readAll())
                if not img.isNull():
                    pix = QPixmap.fromImage(img).scaled(
                        160, 100, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    x = max(0, (pix.width() - 160) // 2)
                    y = max(0, (pix.height() - 100) // 2)
                    cropped = pix.copy(x, y, min(160, pix.width()), min(100, pix.height()))
                    self._cover.setPixmap(cropped)
                    self._cover.setStyleSheet("border-radius: 4px;")
                    return
            self._cover.setText("🎬")
        except Exception:
            self._cover.setText("🎬")
        finally:
            reply.deleteLater()

    def show_work(self, work):
        self._state.setText("(" + t("parsed") + ")")
        self._state.setStyleSheet("color: #22c55e; font-weight: bold;")
        # 加载封面
        cover_url = work.get("cover_url") or work.get("cover") or ""
        if not cover_url:
            # 从 video 对象中尝试获取
            video = work.get("video") or {}
            for key in ("cover", "origin_cover", "dynamic_cover"):
                c = video.get(key)
                if isinstance(c, dict):
                    urls = c.get("url_list") or []
                    if urls:
                        cover_url = urls[0]
                        break
        self._load_cover(cover_url)
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
            lines.append(f"<b>视频:</b> {url[:80]}{'...' if len(url) > 80 else ''}")
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
        self._detail.setText("<br>".join(lines))
        self._detail.setVisible(True)
        self._info.setVisible(False)

    def show_empty(self):
        self._state.setText("(" + t("waiting_parse") + ")")
        self._state.setStyleSheet("color: #64748b;")
        self._detail.setVisible(False)
        self._info.setVisible(True)
        self._cover.setVisible(False)

    def show_error(self, msg):
        self._state.setText("(" + t("parse_failed") + ")")
        self._state.setStyleSheet("color: #ef4444; font-weight: bold;")
        self._info.setText(msg)
        self._info.setVisible(True)
        self._detail.setVisible(False)
