from dotenv import load_dotenv
import os

load_dotenv()

DINGTALK_APP_KEY    = os.environ["DINGTALK_APP_KEY"]
DINGTALK_APP_SECRET = os.environ["DINGTALK_APP_SECRET"]
DINGTALK_AGENT_ID   = os.environ["DINGTALK_AGENT_ID"]
SERVER_BASE_URL     = os.getenv("SERVER_BASE_URL", "http://localhost:8000")
DB_PATH             = os.getenv("DB_PATH", "parcel.db")
MAX_SLOTS           = int(os.getenv("MAX_SLOTS", "30"))   # 格子总数，按实际货架调整
