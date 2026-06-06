from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class PackageStatus(str, Enum):
    pending   = "pending"
    picked_up = "picked_up"
    unclaimed = "unclaimed"
    expired   = "expired"


class Package(SQLModel, table=True):
    id:          Optional[int] = Field(default=None, primary_key=True)
    slot:        int  = Field(index=True)           # 物理格子编号，包裹取走后可复用
    code:        str  = Field(index=True)            # = str(slot)，方便前端显示；不强制唯一
    courier:     str
    employee_id: Optional[str] = None
    phone_tail:  Optional[str] = None
    status:      PackageStatus = PackageStatus.pending
    arrived_at:  datetime = Field(default_factory=datetime.now)
    picked_at:   Optional[datetime] = None
