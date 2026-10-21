"""Trạng thái được cập nhật bởi health check, không bởi nút dừng tiến trình."""
import time
from .models import Backend

class BackendRegistry:
    def __init__(self, backends, failure_threshold=2, success_threshold=2):
        self.backends = tuple(backends)
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.states = {b.id: {"status": "unknown", "success_streak": 0,
                      "failure_streak": 0, "last_check": None, "changed_at": None,
                      "latency_ms": None, "last_error": None} for b in backends}

    def record(self, backend_id, success, latency_ms=None, error=None):
        state = self.states[backend_id]
        old = state["status"]
        state["last_check"] = time.time()
        state["latency_ms"] = latency_ms
        state["last_error"] = error
        if success:
            state["failure_streak"] = 0
            state["success_streak"] += 1
            if state["success_streak"] >= self.success_threshold:
                state["status"] = "healthy"
        else:
            state["success_streak"] = 0
            state["failure_streak"] += 1
            if state["failure_streak"] >= self.failure_threshold:
                state["status"] = "unhealthy"
        if state["status"] != old:
            state["changed_at"] = time.time()
        return state["status"] != old

    def healthy_backends(self) -> tuple[Backend, ...]:
        return tuple(b for b in self.backends if self.states[b.id]["status"] == "healthy")

    def snapshot(self):
        return [{"id": b.id, "url": b.url, **self.states[b.id]} for b in self.backends]
