"""Kiểm tra các backend song song; lỗi /work không trực tiếp đổi health."""
import asyncio
import time
import httpx

async def check_once(registry, client, timeout):
    async def check(backend):
        started = time.perf_counter()
        error = None
        try:
            response = await client.get(backend.url + "/health", timeout=timeout)
            body = response.json()
            success = (response.status_code == 200 and body.get("backend_id") == backend.id
                       and body.get("status") == "healthy")
            if not success:
                error = f"Invalid health response (HTTP {response.status_code})"
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            success, error = False, type(exc).__name__
        registry.record(backend.id, success, round((time.perf_counter()-started)*1000, 2), error)
    await asyncio.gather(*(check(b) for b in registry.backends))

async def monitor_backends(registry, client, settings):
    while True:
        await check_once(registry, client, settings["timeout_seconds"])
        await asyncio.sleep(settings["interval_seconds"])
