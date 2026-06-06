import httpx
from typing import Optional

DINGTALK_API = "https://oapi.dingtalk.com"


class DingTalkClient:
    def __init__(self, app_key: str, app_secret: str, agent_id: str):
        self.app_key    = app_key
        self.app_secret = app_secret
        self.agent_id   = agent_id
        self._access_token:    Optional[str] = None
        self._token_expires_at: float = 0

    async def _get_token(self) -> str:
        import time
        async with httpx.AsyncClient() as http:
            r = await http.get(
                f"{DINGTALK_API}/gettoken",
                params={"appkey": self.app_key, "appsecret": self.app_secret}
            )
        self._access_token    = r.json()["access_token"]
        self._token_expires_at = time.time() + 7200 - 60
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
        data = await self._request("POST", "/topapi/v2/user/getbymobile",
                                   json={"mobile": phone})
        if data.get("errcode") != 0:
            return None
        return data.get("result", {}).get("userid")

    async def send_pickup_notification(
        self, user_id: str, code: str, courier: str, pickup_url: str
    ) -> bool:
        """蓝色 OA 通知：快递到了，位置编号 code (如 1-2-0001)"""
        from datetime import datetime
        arrived_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        # 解析 shelf/layer 用于提示文字
        parts = code.split("-")
        location_hint = f"货架 {parts[0]} — 第 {parts[1]} 层" if len(parts) == 3 else code
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
                            "title": f"取件编号：{code}",
                            "form": [
                                {"key": "位置",     "value": location_hint},
                                {"key": "快递公司",  "value": courier},
                                {"key": "到件时间",  "value": arrived_str},
                            ],
                            "content": f"请到快递间找编号 {code} 的包裹取件，点击「已取件」完成确认。"
                        }
                    }
                }
            }
        )
        return data.get("errcode") == 0


    async def _get_dept_user_ids(self, dept_id: int = 1) -> list:
        """获取部门下所有 userid（分页）"""
        ids = []
        data = await self._request("POST", "/topapi/user/listid",
                                   json={"dept_id": dept_id})
        if data.get("errcode") == 0:
            ids.extend(data.get("result", {}).get("userid_list", []))
        return ids

    async def _get_user_detail(self, user_id: str) -> dict:
        """获取用户详情（含手机号、姓名）"""
        data = await self._request("POST", "/topapi/v2/user/get",
                                   json={"userid": user_id, "language": "zh_CN"})
        if data.get("errcode") != 0:
            return {}
        r = data.get("result", {})
        return {
            "employee_id": r.get("userid", ""),
            "name":        r.get("name", ""),
            "mobile":      r.get("mobile", ""),
        }

    async def sync_all_employees(self) -> list:
        """同步全部员工到本地缓存，返回 [{employee_id, name, phone_tail}]"""
        user_ids = await self._get_dept_user_ids()
        result = []
        for uid in user_ids:
            detail = await self._get_user_detail(uid)
            if detail.get("mobile"):
                result.append({
                    "employee_id": detail["employee_id"],
                    "name":        detail["name"],
                    "phone_tail":  detail["mobile"][-4:],
                })
        return result


    async def send_ambiguous_notification(
        self, employee_review_urls: dict, courier: str, tracking_tail: str, code: str
    ) -> int:
        """重复匹配时逐人推送：每人收到专属认领链接，包含认领/不认领按钮
        employee_review_urls: {employee_id: review_url}
        返回成功推送数量
        """
        parts    = code.split("-")
        location = f"货架 {parts[0]} — 第 {parts[1]} 层" if len(parts) == 3 else code
        sent = 0
        for uid, review_url in employee_review_urls.items():
            data = await self._request(
                "POST",
                "/topapi/message/corpconversation/asyncsend_v2",
                json={
                    "agent_id":    self.agent_id,
                    "userid_list": uid,
                    "msg": {
                        "msgtype": "oa",
                        "oa": {
                            "message_url":    review_url,
                            "pc_message_url": review_url,
                            "head": {
                                "bgcolor": "FF78909C",
                                "text":    "有快递可能是你的，请确认"
                            },
                            "body": {
                                "title": f"快递待认领 · {code}",
                                "form": [
                                    {"key": "快递公司", "value": courier},
                                    {"key": "单号尾号", "value": f"···{tracking_tail}"},
                                    {"key": "货架位置", "value": location},
                                ],
                                "content": "请核对单号尾号，点击「是我的，认领」完成认领后会收到取件通知。"
                            }
                        }
                    }
                }
            )
            if data.get("errcode") == 0:
                sent += 1
        return sent

    async def send_reminder(self, user_id: str, code: str, pickup_url: str) -> bool:
        """橙色提醒：超过 48h 未取件"""
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
                            "title": f"取件编号：{code}",
                            "content": f"编号 {code} 的快递已超过 48 小时未取，请尽快领取。"
                        }
                    }
                }
            }
        )
        return data.get("errcode") == 0
