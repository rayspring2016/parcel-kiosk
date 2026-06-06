import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.dingtalk import DingTalkClient


@pytest.fixture
def client():
    return DingTalkClient(app_key="test_key", app_secret="test_secret", agent_id="12345")


@pytest.mark.asyncio
async def test_get_user_by_phone_found(client):
    mock_response = {"result": {"userid": "user_abc123"}, "errcode": 0}
    with patch.object(client, "_request", new=AsyncMock(return_value=mock_response)):
        user_id = await client.get_user_id_by_phone("13800138000")
    assert user_id == "user_abc123"


@pytest.mark.asyncio
async def test_get_user_by_phone_not_found(client):
    mock_response = {"errcode": 60121}
    with patch.object(client, "_request", new=AsyncMock(return_value=mock_response)):
        user_id = await client.get_user_id_by_phone("13999999999")
    assert user_id is None


@pytest.mark.asyncio
async def test_send_pickup_notification(client):
    with patch.object(client, "_request", new=AsyncMock(return_value={"errcode": 0})):
        ok = await client.send_pickup_notification(
            user_id="user_abc123",
            code="0606-023",
            courier="顺丰",
            pickup_url="http://localhost:8000/pickup/0606-023/confirm"
        )
    assert ok is True


@pytest.mark.asyncio
async def test_send_reminder(client):
    with patch.object(client, "_request", new=AsyncMock(return_value={"errcode": 0})):
        ok = await client.send_reminder(
            user_id="user_abc123",
            code="0606-023",
            pickup_url="http://localhost:8000/pickup/0606-023/confirm"
        )
    assert ok is True


@pytest.mark.asyncio
async def test_token_expires_and_refreshes(client):
    """token 过期后 _get_token 应被重新调用，不能沿用旧 token"""
    import time
    client._access_token = "old_token"
    client._token_expires_at = time.time() - 1  # 强制过期

    refreshed = False

    async def fake_get_token():
        nonlocal refreshed
        refreshed = True
        client._access_token = "refreshed_token"
        client._token_expires_at = time.time() + 7100

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"errcode": 0}
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_resp)

    with patch.object(client, "_get_token", side_effect=fake_get_token):
        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            await client.send_pickup_notification("u1", "0606-001", "顺丰", "http://x/confirm")

    assert refreshed, "_get_token should have been called when token is expired"
