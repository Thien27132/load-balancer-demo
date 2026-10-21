"""Dữ liệu và cấu hình. Không chứa thuật toán hoặc I/O."""
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, Field

@dataclass(frozen=True)
class Backend:
    id: str
    url: str

class WorkRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    key: str = Field(min_length=1, max_length=128)

class AlgorithmSettings(BaseModel):
    algorithm: Literal["round_robin", "consistent_hash"]
    virtual_nodes: int = Field(default=100, ge=1, le=500)

class DelaySettings(BaseModel):
    delay_ms: int = Field(ge=0, le=10000)
