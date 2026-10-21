"""HTTP client được cấp từ lifespan; không retry ngầm."""
import asyncio
import httpx
from pydantic import BaseModel, Field, ValidationError
from .models import Backend, WorkRequest

class ProxyError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)

class BackendResponse(BaseModel):
    request_id: str
    key: str
    backend_id: str
    processing_ms: float = Field(ge=0, allow_inf_nan=False)

async def forward_request(client, backend: Backend, request: WorkRequest, timeout=5):
    try:
        # wait_for giới hạn tổng thời gian, HTTPX còn có timeout từng pha.
        response = await asyncio.wait_for(client.post(backend.url + "/work",
            json=request.model_dump(), timeout=timeout), timeout=timeout)
    except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
        raise ProxyError(504, "Backend vượt quá thời gian chờ.") from exc
    except httpx.HTTPError as exc:
        raise ProxyError(502, "Không kết nối được backend.") from exc
    if response.status_code != 200:
        raise ProxyError(502, f"Backend trả HTTP {response.status_code}.")
    try:
        result = BackendResponse.model_validate(response.json())
        if (result.backend_id != backend.id or result.request_id != request.request_id
                or result.key != request.key):
            raise ValueError("Mismatched backend response")
    except (ValueError, ValidationError) as exc:
        raise ProxyError(502, "Backend trả dữ liệu không hợp lệ.") from exc
    return result.model_dump()
