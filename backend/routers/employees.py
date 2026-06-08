from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, delete
from database import get_session
from models import Employee
from services.dingtalk import DingTalkClient
from config import DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

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
    """从钉钉同步所有员工到本地缓存"""
    import traceback
    dt = DingTalkClient(DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID)
    try:
        employees = await dt.sync_all_employees()
        logger.info("钉钉同步返回 %d 条员工数据", len(employees))
    except Exception as e:
        logger.error("钉钉同步异常: %s\n%s", e, traceback.format_exc())
        return {"synced": 0, "error": str(e), "detail": traceback.format_exc()}

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


@router.post("/employees/add")
def add_employee(employee_id: str, name: str, phone_tail: str,
                 session: Session = Depends(get_session)):
    """手动添加员工（绕过钉钉同步，调试用）"""
    if len(phone_tail) != 4 or not phone_tail.isdigit():
        return {"error": "phone_tail 必须是 4 位数字"}
    existing = session.get(Employee, employee_id)
    if existing:
        return {"error": f"员工 {employee_id} 已存在"}
    emp = Employee(
        employee_id=employee_id,
        name=name,
        phone_tail=phone_tail,
        synced_at=datetime.now(),
    )
    session.add(emp)
    session.commit()
    return {"ok": True, "employee_id": employee_id, "name": name}


@router.get("/employees/list")
def list_employees(session: Session = Depends(get_session)):
    """查看所有已同步的员工"""
    emps = session.exec(select(Employee)).all()
    return [
        {"employee_id": e.employee_id, "name": e.name, "phone_tail": e.phone_tail}
        for e in emps
    ]
