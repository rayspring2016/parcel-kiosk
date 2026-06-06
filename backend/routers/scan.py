from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from datetime import datetime
from database import get_session
from models import Package, PackageStatus
from services.barcode import parse_barcode
from services.code_gen import assign_slot
from services.dingtalk import DingTalkClient
from services.printer import get_printer_service
from config import (DINGTALK_APP_KEY, DINGTALK_APP_SECRET,
                    DINGTALK_AGENT_ID, SERVER_BASE_URL, MAX_SLOTS)

router = APIRouter()


class ScanRequest(BaseModel):
    barcode: str


@router.post("/scan")
async def scan(req: ScanRequest, session: Session = Depends(get_session)):
    result  = parse_barcode(req.barcode)
    slot    = assign_slot(session, MAX_SLOTS)
    dt      = DingTalkClient(DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID)
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M")

    employee_id = None
    if result.phone:
        employee_id = await dt.get_user_id_by_phone(result.phone)

    if employee_id:
        pkg = Package(
            slot=slot, code=str(slot),
            courier=result.courier, employee_id=employee_id
        )
        session.add(pkg)
        session.commit()
        session.refresh(pkg)
        pickup_url = f"{SERVER_BASE_URL}/pickup/confirm/{pkg.id}"
        await dt.send_pickup_notification(employee_id, slot, result.courier, pickup_url)
        try:
            get_printer_service().print_label(slot=slot, courier=result.courier, arrived_at=now_str)
        except Exception as e:
            import logging; logging.getLogger(__name__).warning("打印失败（可忽略）: %s", e)
        return {"matched": True, "slot": slot, "code": str(slot), "courier": result.courier}
    else:
        pkg = Package(
            slot=slot, code=f"待认领-{slot:02d}",
            courier=result.courier,
            status=PackageStatus.unclaimed,
            phone_tail=result.phone[-4:] if result.phone else None,
        )
        session.add(pkg)
        session.commit()
        try:
            get_printer_service().print_unclaimed_label(slot=slot, courier=result.courier, arrived_at=now_str)
        except Exception as e:
            import logging; logging.getLogger(__name__).warning("打印失败（可忽略）: %s", e)
        return {"matched": False, "slot": slot, "code": f"待认领-{slot:02d}", "courier": result.courier}
