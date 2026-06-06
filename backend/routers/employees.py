from fastapi import APIRouter, Depends
from sqlmodel import Session, select, delete
from database import get_session
from models import Employee
from services.dingtalk import DingTalkClient
from config import DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID
from datetime import datetime

router = APIRouter()


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
