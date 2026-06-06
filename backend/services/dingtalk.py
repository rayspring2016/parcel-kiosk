import httpx
from typing import Optional

DINGTALK_API = "https://oapi.dingtalk.com"


class DingTalkClient:
    def __init__(self, app_key: str, app_secret: str, agent_id: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.agent_id = agent_id
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0  # unix timestamp，0 表示从未获取

    async def _get_token(self) -> str:
        import time
        async with httpx.AsyncClient() as http:
            r = await http.get(
                f"{DINGTALK_API}/gettoken",
                params={"appkey": self.app_key, "appsecret": self.app_secret}
            )
        self._access_token = r.json()["access_token"]
        self._token_expires_at = time.time() + 7200 - 60  # 提前 60s 刷新，避免边界失效
        return self._access_token

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        import time
        if not self._access_token or time.time() >= self._token_expires_at:
            await self._get_token()
        url = f"{DINGTALK_API}{path}?access_token={self._access_token}"
        async with httpx.AsyncClient() as http:
            resp = await http.request(method, url, **kwargs)
        return resp.json()

    async def get_user_id_by_phone(self, phone: str) -> Optional[str]:
        data = await self._request("POST", "/topapi/v2/user/getbymobile", json={"mobile": phone})
        if data.get("errcode") != 0:
            return None
        return data.get("result", {}).get("userid")

    async def send_pickup_notification(self, user_id: str, code: str, courier: str, pickup_url: str) -> bool:
        """发送 OA 工作通知，视觉与钉钉考勤等系统通知一致"""
        from datetime import datetime
        arrived_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        data = await self._request(
            "POST",
            "/topapi/message/corpconversation/asyncsend_v2",
            json={
                "agent_id": self.agent_id,
                "userid_list": user_id,
                "msg": {
                    "msgtype": "oa",
                    "oa": {
                        "message_url": pickup_url,
                        "pc_message_url": pickup_url,
                        "head": {
                            "bgcolor": "FF1E88E5",
                            "text": "你有快递到了！"
                        },
                        "body": {
                            "title": f"包裹编号：{code}",
                            "form": [
                                {"key": "快递公司", "value": courier},
                                {"key": "到件时间", "value": arrived_str},
                            ],
                            "content": "请到快递间货架找对应编号取件，点击「已取件」完成确认。"
                        }
                    }
                }
            }
        )
        return data.get("errcode") == 0

    async def send_reminder(self, user_id: str, code: str, pickup_url: str) -> bool:
        """48小时未取件提醒，橙色标题栏区分首次通知"""
        data = await self._request(
            "POST",
            "/topapi/message/corpconversation/asyncsend_v2",
            json={
                "agent_id": self.agent_id,
                "userid_list": user_id,
                "msg": {
                    "msgtype": "oa",
                    "oa": {
                        "message_url": pickup_url,
                        "pc_message_url": pickup_url,
                        "head": {
                            "bgcolor": "FFF59E0B",
                            "text": "快递待取件提醒"
                        },
                        "body": {
                            "title": f"包裹编号：{code}",
                            "content": "你的快递已超过48小时未取，请尽快到快递间领取。"
                        }
                    }
                }
            }
        )
        return data.get("errcode") == 0
