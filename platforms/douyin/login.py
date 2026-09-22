"""抖音 QR 码登录。"""
import httpx
import qrcode
from io import BytesIO
from PIL import Image
from shared.core.login import PlatformLoginManager, LoginBus

SSO_BASE = "https://sso.douyin.com"
QR_CONNECT = "/get_qrcode/"
QR_POLL = "/check_qrconnect/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"


class DouyinLoginManager(PlatformLoginManager):
    platform_id = "douyin"

    def __init__(self):
        self._client = httpx.Client(
            base_url=SSO_BASE,
            headers={"User-Agent": UA},
            timeout=30.0,
        )

    def generate_qr(self) -> tuple[str, str, Image.Image]:
        resp = self._client.get(QR_CONNECT, params={"service": "https://www.douyin.com"})
        resp.raise_for_status()
        data = resp.json().get("data", {})
        url = data.get("qrcode", "")
        token = data.get("token", "")
        if not url or not token:
            raise RuntimeError(f"抖音QR生成失败: {data}")
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return url, token, img

    def check_qr_status(self, token: str) -> dict:
        resp = self._client.get(QR_POLL, params={
            "token": token, "service": "https://www.douyin.com",
        })
        resp.raise_for_status()
        data = resp.json().get("data", {})
        status = data.get("status", "")
        result = {"status": status}
        if status == "1":  # 已确认
            redirect_url = data.get("redirect_url", "")
            result["code"] = 0
            result["cookies"] = self._extract_cookies(redirect_url)
        elif status == "2":
            result["code"] = 86038  # 过期
        else:
            result["code"] = 86090  # 等待扫码
        return result

    def _extract_cookies(self, redirect_url: str) -> dict:
        cookies = {}
        if not redirect_url:
            return cookies
        try:
            with httpx.Client(headers={"User-Agent": UA}, timeout=15.0, follow_redirects=True) as c:
                c.get(redirect_url)
                for ck in c.cookies.jar:
                    if ck.value:
                        cookies[ck.name] = ck.value
        except Exception:
            pass
        return cookies

    def close(self):
        self._client.close()
