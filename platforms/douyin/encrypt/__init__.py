"""抖音 / TikTok 签名参数生成 —— 本项目自维护的加密模块。

来源与协议
==========
签名算法改编自 DouK-Downloader (原 TikTokDownloader) 所采用的逆向实现,
其源头为 Evil0ctal/Douyin_TikTok_Download_API (Apache-2.0):

  - aBogus.py       逆向抖音 bdms.js (v1.0.1.19-fix.01) 的 a_bogus 签名
  - websign.py      逆向 secsdk (runtime_bundler_34.js) 的 x-secsdk-web-signature
  - tiktok_sign.py  逆向 TikTok webmssdk (2.0.0.561) 的 X-Bogus 系签名
  - sm3.py          国密 SM3 哈希 (aBogus 依赖)
  - params.py       参数拼装基类

⚠ 平台前端 JS 更新后签名可能失效 —— 此目录需要跟随上游自行维护:
  跟进地址 https://github.com/Evil0ctal/Douyin_TikTok_Download_API
  (src/dtk/signing/native/) 或 DouK-Downloader releases。

模块结构
========
    DouYinParams   抖音 Web 签名 (a_bogus + 可选 web_sign), 见 douyin_params.py
    TikTokParams   TikTok Web 签名 (X-Bogus 系), 见 tiktok_params.py

使用方式 (adapter 层唯一入口)
============================
    from platforms.douyin.encrypt import DouYinParams
    signed_query = DouYinParams().sign_url(api, params, method="GET",
                                           user_agent=UA)
"""
from .douyin_params import DOUYIN_SIGNED_PATHS, DouYinParams
from .params import Params
from .tiktok_params import TikTokParams

__all__ = ["DOUYIN_SIGNED_PATHS", "DouYinParams", "Params", "TikTokParams"]
