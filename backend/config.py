from dotenv import load_dotenv
import os

load_dotenv()

DINGTALK_APP_KEY    = os.environ["DINGTALK_APP_KEY"]
DINGTALK_APP_SECRET = os.environ["DINGTALK_APP_SECRET"]
DINGTALK_AGENT_ID   = os.environ["DINGTALK_AGENT_ID"]
SERVER_BASE_URL     = os.getenv("SERVER_BASE_URL", "http://localhost:8000")
DB_PATH             = os.getenv("DB_PATH", "parcel.db")
MAX_SHELVES         = int(os.getenv("MAX_SHELVES", "2"))   # 货架数量
MAX_LAYERS          = int(os.getenv("MAX_LAYERS", "4"))    # 每个货架的层数
PRINTER_NAME        = os.getenv("PRINTER_NAME", "HUAWEI_PixLab_V1_0409")  # CUPS 打印机名

# 快递公司 → 货架层映射，格式：顺丰:1-1,中通:1-2,圆通:1-3
# 键名需与 barcode.py COURIER_MAP 中文名一致；未配置则退回负载均衡
def _parse_courier_layer_map(raw: str) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        courier, pos = item.split(":", 1)
        if "-" not in pos:
            continue
        s, l = pos.split("-", 1)
        try:
            result[courier.strip()] = (int(s), int(l))
        except ValueError:
            pass
    return result

COURIER_LAYER_MAP: dict[str, tuple[int, int]] = _parse_courier_layer_map(
    os.getenv("COURIER_LAYER_MAP", "")
)
