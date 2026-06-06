from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class PackageStatus(str, Enum):
    pending = "pending"
    picked_up = "picked_up"
    unclaimed = "unclaimed"
    expired = "expired"


class Package(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)       # e.g. "0606-023"
    courier: str                                      # e.g. "顺丰"
    daily_seq: Optional[int] = None                  # 每日序号，原子性编号生成用
    employee_id: Optional[str] = None                # 钉钉 userId，匹配失败时为 None
    phone_tail: Optional[str] = None                 # 手机后4位，仅未匹配时保存
    status: PackageStatus = PackageStatus.pending
    arrived_at: datetime = Field(default_factory=datetime.now)
    picked_at: Optional[datetime] = None
