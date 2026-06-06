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
