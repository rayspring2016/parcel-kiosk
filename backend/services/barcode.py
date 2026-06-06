import json
import re
from dataclasses import dataclass
from typing import Optional

COURIER_MAP = {
    "SF": "顺丰", "JD": "京东", "YTO": "圆通",
    "ZTO": "中通", "STO": "申通", "YUNDA": "韵达",
    "EMS": "EMS", "HTKY": "百世",
}


@dataclass
class BarcodeResult:
    phone:         Optional[str]
    courier:       str = "未知"
    tracking_tail: str = ""    # 条码尾4位，用于推送展示，不暴露完整单号


def _detect_courier(text: str) -> str:
    for code, name in COURIER_MAP.items():
        if code in text.upper():
            return name
    return "未知"


def _extract_phone(text: str) -> Optional[str]:
    match = re.search(r"1[3-9]\d{9}", text)
    return match.group() if match else None


def parse_barcode(raw: str) -> BarcodeResult:
    try:
        data = json.loads(raw)
        phone = data.get("mobile") or data.get("phone") or data.get("receiverMobile")
        courier_code = data.get("courier", "")
        courier = COURIER_MAP.get(courier_code.upper(), _detect_courier(raw))
        return BarcodeResult(phone=phone, courier=courier, tracking_tail=raw[-4:])
    except (json.JSONDecodeError, AttributeError):
        pass

    parts = raw.split("|")
    if len(parts) >= 2 and parts[0].upper() in COURIER_MAP:
        phone = _extract_phone(parts[1]) or _extract_phone(raw)
        return BarcodeResult(phone=phone, courier=COURIER_MAP[parts[0].upper()], tracking_tail=raw[-4:])

    return BarcodeResult(phone=_extract_phone(raw), courier=_detect_courier(raw), tracking_tail=raw[-4:])
