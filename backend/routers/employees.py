from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, delete
from database import get_session
from models import Employee
from services.dingtalk import DingTalkClient
from config import DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID
from datetime import datetime

router = APIRouter()


@router.get("/auth/dingtalk")
async def dingtalk_auth(code: str):
    """小程序免登：用授权码换取 userId"""
    dt   = DingTalkClient(DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID)
    data = await dt._request("GET", "/user/getuserinfo", params={"code": code})
    if data.get("errcode") != 0:
        raise HTTPException(status_code=401, detail=data.get("errmsg", "授权失败"))
    return {"user_id": data.get("userid", "")}


@router.post("/employees/sync")
async def sync_employees(session: Session = Depends(get_session)):
    """从钉钉同步所有员工到本地缓存（管理员手动触发或定时任务调用）"""
    dt = DingTalkClient(DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID)
    employees = await dt.sync_all_employees()

    session.exec(delete(Employee))
    for e in employees:
        session.add(Employee(
            employee_id=e["employee_id"],
            name=e["name"],
            phone_tail=e["phone_tail"],
            synced_at=datetime.now(),
        ))
    session.commit()
    return {"synced": len(employees)}


@router.get("/employees/count")
def employee_count(session: Session = Depends(get_session)):
    count = len(session.exec(select(Employee)).all())
    return {"count": count}


@router.get("/employees/by-tail/{tail}")
def employee_by_tail(tail: str, session: Session = Depends(get_session)):
    """工作台免登：手机尾号查员工（精确匹配唯一时才返回）"""
    matches = session.exec(select(Employee).where(Employee.phone_tail == tail)).all()
    if len(matches) == 1:
        return {"employee_id": matches[0].employee_id, "name": matches[0].name}
    elif len(matches) == 0:
        return {"error": "未找到该手机尾号对应员工，请确认后重试"}
    else:
        return {"error": "该尾号对应多名员工，请联系管理员"}
