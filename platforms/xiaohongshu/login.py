"""小红书 QR 码登录。"""
import httpx
import qrcode
from PIL import Image
from shared.core.login import PlatformLoginManager, LoginBus

API_BASE = "https://edith.xiaohongshu.com"
QR_CREATE = "/api/sns/web/v1/login/qrcode/create"
QR_POLL = "/api/sns/web/v1/login/qrcode/status"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"


class XiaohongshuLoginManager(PlatformLoginManager):
    platform_id = "xiaohongshu"

    def __init__(self):
        self._client = httpx.Client(
            base_url=API_BASE,
            headers={
                "User-Agent": UA,
                "Origin": "https://www.xiaohongshu.com",
                "Referer": "https://www.xiaohongshu.com/",
            },
            timeout=30.0,
        )

    def generate_qr(self) -> tuple[str, str, Image.Image]:
        resp = self._client.post(QR_CREATE, json={"source": "web"})
        resp.raise_for_status()
        data = resp.json().get("data", {})
        qr_id = data.get("qr_id", "")
        qr_url = data.get("url", "")
        if not qr_id or not qr_url:
            raise RuntimeError(f"小红书QR生成失败: {data}")
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return qr_url, qr_id, img

    def check_qr_status(self, qr_id: str) -> dict:
        resp = self._client.get(QR_POLL, params={"qr_id": qr_id})
        resp.raise_for_status()
        data = resp.json().get("data", {})
        status = data.get("status", "")
        result = {"status": status}
        if status == "1":  # 已确认
            result["code"] = 0
            result["cookies"] = {}
            for ck in resp.cookies.jar:
                if ck.value:
                    result["cookies"][ck.name] = ck.value
            for ck in self._client.cookies.jar:
                if ck.value:
                    result["cookies"][ck.name] = ck.value
        elif status == "3":  # 过期
            result["code"] = 86038
        else:  # 等待中
            result["code"] = 86090
        return result

    def close(self):
        self._client.close()
