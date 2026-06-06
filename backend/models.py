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
    shelf:       int  = Field(index=True)   # 货架号，如 1 或 2
    layer:       int  = Field(index=True)   # 层号，如 1-4
    seq:         int  = Field(index=True)   # 全局顺序号，4 位显示，永不重置
    code:        str  = Field(index=True)   # = "{shelf}-{layer}-{seq:04d}"，方便显示
    courier:     str
    employee_id: Optional[str] = None
    phone_tail:  Optional[str] = None
    status:      PackageStatus = PackageStatus.pending
    arrived_at:  datetime = Field(default_factory=datetime.now)
    picked_at:   Optional[datetime] = None


class Employee(SQLModel, table=True):
    """钉钉员工本地缓存：只存 phone_tail（尾4位），保护隐私"""
    employee_id: str      = Field(primary_key=True)
    name:        str
    phone_tail:  str      = Field(index=True)   # 手机尾 4 位
    synced_at:   datetime = Field(default_factory=datetime.now)
