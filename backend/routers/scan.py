from fastapi import APIRouter, Depends
from sqlmodel import Session
from pydantic import BaseModel
from datetime import datetime
from database import get_session
from models import Package, PackageStatus
from services.barcode import parse_barcode
from services.code_gen import generate_code, next_seq
from services.dingtalk import DingTalkClient
from services.printer import get_printer_service
from config import DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID, SERVER_BASE_URL

router = APIRouter()


class ScanRequest(BaseModel):
    barcode: str


@router.post("/scan")
async def scan(req: ScanRequest, session: Session = Depends(get_session)):
    result = parse_barcode(req.barcode)
    seq = next_seq(session)
    dt = DingTalkClient(DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID)
    printer = get_printer_service()
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M")

    employee_id = None
    if result.phone:
        employee_id = await dt.get_user_id_by_phone(result.phone)

    if employee_id:
        code = generate_code(seq)
        session.add(Package(code=code, courier=result.courier, employee_id=employee_id, daily_seq=seq))
        session.commit()
        pickup_url = f"{SERVER_BASE_URL}/pickup/{code}/confirm"
        await dt.send_pickup_notification(employee_id, code, result.courier, pickup_url)
        printer.print_label(code=code, courier=result.courier, arrived_at=now_str)
        return {"matched": True, "code": code, "courier": result.courier}
    else:
        code = f"待认领-{generate_code(seq)}"
        session.add(Package(
            code=code,
            courier=result.courier,
            status=PackageStatus.unclaimed,
            daily_seq=seq,
            phone_tail=result.phone[-4:] if result.phone else None,
        ))
        session.commit()
        printer.print_unclaimed_label(code=code, courier=result.courier, arrived_at=now_str)
        return {"matched": False, "code": code, "courier": result.courier}
