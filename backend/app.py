"""Một file chạy ba tiến trình. Sleep chỉ giả lập thời gian công việc, không phải CPU."""
import asyncio
import os
import secrets
import time
from fastapi import FastAPI, Header, HTTPException
from load_balancer.models import WorkRequest, DelaySettings

app = FastAPI(title="Demo backend")
BACKEND_ID = os.getenv("BACKEND_ID", "A")
TOKEN = os.getenv("DEMO_CONTROL_TOKEN", "")
delay_ms = int(os.getenv("BACKEND_DELAY_MS", "100"))

@app.get("/health")
async def health():
    return {"backend_id": BACKEND_ID, "status": "healthy"}

@app.post("/work")
async def work(request: WorkRequest):
    started = time.perf_counter()
    await asyncio.sleep(delay_ms / 1000)
    return {**request.model_dump(), "backend_id": BACKEND_ID,
            "processing_ms": round((time.perf_counter()-started)*1000, 2)}

@app.post("/admin/delay")
async def set_delay(settings: DelaySettings, x_demo_control: str = Header(default="")):
    if not TOKEN or not secrets.compare_digest(TOKEN, x_demo_control):
        raise HTTPException(403, "Chỉ load balancer được đổi cấu hình backend.")
    global delay_ms
    delay_ms = settings.delay_ms
    return {"backend_id": BACKEND_ID, "delay_ms": delay_ms}
