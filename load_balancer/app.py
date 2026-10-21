"""Điều phối một event loop/worker; không await giữa kiểm tra idle và đổi cấu hình."""
import asyncio
from contextlib import asynccontextmanager, suppress
import json
import os
from pathlib import Path
import secrets
import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .algorithms.base import NoHealthyBackend
from .algorithms.round_robin import RoundRobin
from .algorithms.consistent_hash import ConsistentHash
from .health_checker import monitor_backends
from .metrics import MetricsCollector
from .models import Backend, WorkRequest, AlgorithmSettings, DelaySettings
from .processes import BackendProcesses
from .proxy import forward_request, ProxyError
from .registry import BackendRegistry

ROOT = Path(__file__).resolve().parents[1]

def load_config():
    config = json.loads(Path(os.getenv("DEMO_CONFIG", str(ROOT / "config.json"))).read_text(encoding="utf-8"))
    backends = config["backends"]
    if not backends or len({b["id"] for b in backends}) != len(backends):
        raise ValueError("Backend IDs phải khác nhau và danh sách không rỗng.")
    for b in backends:
        if b["url"] != f"http://127.0.0.1:{b['port']}":
            raise ValueError("URL backend phải trỏ đúng cổng trên 127.0.0.1.")
    settings = config["health_check"]
    if any(settings[k] <= 0 for k in ("interval_seconds", "timeout_seconds",
                                    "failure_threshold", "success_threshold")):
        raise ValueError("Thông số health check phải dương.")
    if config["load_balancer"]["algorithm"] not in ("round_robin", "consistent_hash"):
        raise ValueError("Thuật toán không hợp lệ.")
    return config

def create_app(config=None, manage=None, transport=None):
    config = config or load_config()
    if manage is None:
        manage = os.getenv("DEMO_MANAGE_BACKENDS") == "1"
    backend_list = tuple(Backend(b["id"], b["url"]) for b in config["backends"])
    hc = config["health_check"]

    @asynccontextmanager
    async def lifespan(app):
        state = app.state
        state.registry = BackendRegistry(backend_list, hc["failure_threshold"], hc["success_threshold"])
        state.algorithm_name = config["load_balancer"]["algorithm"]
        state.virtual_nodes = config["consistent_hash"]["virtual_nodes"]
        state.algorithms = {"round_robin": RoundRobin(),
                            "consistent_hash": ConsistentHash(state.virtual_nodes)}
        state.metrics = MetricsCollector([b.id for b in backend_list], config["metrics"]["max_log_entries"])
        state.token = secrets.token_urlsafe(32)
        state.processes = BackendProcesses(config["backends"], state.token) if manage else None
        state.delays = {b["id"]: b["delay_ms"] for b in config["backends"]}
        state.control_lock = asyncio.Lock()
        state.controls_busy = False
        task = None
        try:
            if state.processes:
                for backend in backend_list:
                    await asyncio.to_thread(state.processes.start, backend.id)
            async with httpx.AsyncClient(trust_env=False, transport=transport,
                    limits=httpx.Limits(max_connections=250, max_keepalive_connections=100)) as client:
                state.client = client
                # Client riêng để health checks không bị kẹt sau các request công việc.
                async with httpx.AsyncClient(trust_env=False, transport=transport) as health_client:
                    task = asyncio.create_task(monitor_backends(state.registry, health_client, hc))
                    try:
                        yield
                    finally:
                        task.cancel()
                        with suppress(asyncio.CancelledError):
                            await task
                        task = None
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            if state.processes:
                await asyncio.to_thread(state.processes.close)

    app = FastAPI(title="Load Balancer Lab", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        # Không cho trang web khác điều khiển các tiến trình local qua trình duyệt.
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Cross-site request rejected"}, status_code=403)
            if origin:
                expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
                if origin.rstrip("/") != expected:
                    return JSONResponse({"detail": "Origin không hợp lệ"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def idle():
        if app.state.metrics.active or app.state.controls_busy:
            raise HTTPException(409, "Chờ yêu cầu hoặc thao tác điều khiển hiện tại hoàn tất.")

    def sync_algorithms():
        healthy = app.state.registry.healthy_backends()
        for algorithm in app.state.algorithms.values():
            algorithm.update_backends(healthy)

    def find_backend(backend_id):
        for backend in backend_list:
            if backend.id == backend_id:
                return backend
        raise HTTPException(404, "Không có backend này.")

    @app.get("/")
    async def index():
        return FileResponse(ROOT / "web/index.html")

    @app.get("/api/status")
    async def status():
        state = app.state
        return {"algorithm": state.algorithm_name, "virtual_nodes": state.virtual_nodes,
                "port": config["load_balancer"]["port"],
                "health_check": hc, "managed": bool(state.processes),
                "controls_busy": state.controls_busy,
                "backends": [{**b, "delay_ms": state.delays[b["id"]],
                              "process_running": state.processes.running(b["id"]) if state.processes else None}
                             for b in state.registry.snapshot()]}

    @app.post("/api/work")
    async def work(request: WorkRequest):
        state = app.state
        if state.controls_busy:
            raise HTTPException(409, "Đang đổi cấu hình backend; thử lại sau.")
        event = state.metrics.begin(request, state.algorithm_name)
        code, error = 500, "Lỗi nội bộ."
        result = None
        try:
            sync_algorithms()
            backend = await state.algorithms[state.algorithm_name].select(request.key)
            state.metrics.assign(event, backend.id)
            result = await forward_request(state.client, backend, request,
                                          config["load_balancer"]["request_timeout_seconds"])
            code, error = 200, None
        except NoHealthyBackend:
            code, error = 503, "Chưa có backend khỏe. Chờ health check hoặc khởi động lại máy."
        except ProxyError as exc:
            code, error = exc.status, exc.message
        except asyncio.CancelledError:
            code, error = 499, "Yêu cầu bị hủy."
            raise
        finally:
            record = state.metrics.finish(event, code, error)
        if code != 200:
            return JSONResponse({"detail": error, **record}, status_code=code)
        return {**result, **record}

    @app.get("/api/metrics")
    async def metrics():
        return app.state.metrics.snapshot()

    @app.post("/api/metrics/reset")
    async def reset():
        idle()
        app.state.metrics.reset()
        return {"run_id": app.state.metrics.run_id}

    @app.put("/api/algorithm")
    async def algorithm(settings: AlgorithmSettings):
        idle()
        state = app.state
        state.algorithm_name = settings.algorithm
        state.virtual_nodes = settings.virtual_nodes
        state.algorithms = {"round_robin": RoundRobin(),
                            "consistent_hash": ConsistentHash(settings.virtual_nodes)}
        sync_algorithms()
        state.metrics.reset()
        return {"algorithm": state.algorithm_name, "virtual_nodes": state.virtual_nodes}

    @app.get("/api/hash-ring")
    async def ring(key: str = Query(default="user-001", min_length=1, max_length=128)):
        sync_algorithms()
        return app.state.algorithms["consistent_hash"].describe(key)

    @app.get("/api/mapping-comparison")
    async def mapping_comparison():
        from benchmarks.compare_mapping import mapping_report
        return mapping_report(backend_list, app.state.virtual_nodes)

    @app.post("/api/backends/{backend_id}/process/{action}")
    async def process_control(backend_id: str, action: str):
        find_backend(backend_id)
        state = app.state
        if action not in ("start", "stop"):
            raise HTTPException(404, "Chỉ hỗ trợ start hoặc stop.")
        if not state.processes:
            raise HTTPException(409, "Chạy bằng python run_demo.py để điều khiển tiến trình.")
        async with state.control_lock:
            # Dừng máy được phép trong lúc đang tải để đo cửa sổ lỗi.
            try:
                await asyncio.to_thread(getattr(state.processes, action), backend_id)
            except OSError as exc:
                raise HTTPException(409, f"Không thể {action}: {exc}") from exc
        return {"backend_id": backend_id, "action": action,
                "message": "Đã điều khiển tiến trình; chờ health check cập nhật."}

    @app.post("/api/backends/{backend_id}/delay")
    async def delay(backend_id: str, settings: DelaySettings):
        backend = find_backend(backend_id)
        state = app.state
        idle()
        state.controls_busy = True
        try:
            response = await state.client.post(backend.url + "/admin/delay",
                json=settings.model_dump(), headers={"X-Demo-Control": state.token}, timeout=2)
            if response.status_code != 200:
                raise HTTPException(502, "Backend không chấp nhận đổi độ trễ.")
            state.delays[backend_id] = settings.delay_ms
            if state.processes:
                state.processes.configs[backend_id]["delay_ms"] = settings.delay_ms
            state.metrics.reset()
            return response.json()
        except httpx.HTTPError as exc:
            raise HTTPException(502, "Không đổi được độ trễ; kiểm tra backend đang chạy.") from exc
        finally:
            state.controls_busy = False

    return app

app = create_app()
