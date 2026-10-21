"""Tổng đếm đầy đủ; log và mẫu p95 giới hạn để tránh tăng RAM vô hạn."""
from collections import deque
import math
import time
import uuid

def percentile95(values):
    return sorted(values)[max(0, math.ceil(len(values) * .95) - 1)] if values else 0

class MetricsCollector:
    def __init__(self, backend_ids, max_entries=1000):
        self.ids = list(backend_ids)
        self.max_entries = max_entries
        self.active = 0
        self.reset()

    def reset(self):
        if self.active:
            raise ValueError("Requests still active")
        self.run_id = str(uuid.uuid4())
        self.started = None
        self.finished = None
        self.total = self.success = self.errors = 0
        self.elapsed_sum = 0
        self.samples = deque(maxlen=self.max_entries)
        self.logs = deque(maxlen=self.max_entries)
        self.by_backend = {b: {"assigned": 0, "active": 0, "success": 0, "errors": 0,
                              "elapsed_sum": 0} for b in self.ids}

    def begin(self, request, algorithm):
        now = time.perf_counter()
        if self.started is None:
            self.started = now
        self.total += 1
        self.active += 1
        return {"sequence": self.total, "request_id": request.request_id, "key": request.key,
                "algorithm": algorithm, "backend_id": None, "_start": now}

    def assign(self, event, backend_id):
        event["backend_id"] = backend_id
        self.by_backend[backend_id]["assigned"] += 1
        self.by_backend[backend_id]["active"] += 1

    def finish(self, event, status, message=None):
        self.finished = time.perf_counter()
        elapsed = (self.finished - event.pop("_start")) * 1000
        self.active -= 1
        ok = status == 200
        self.success += int(ok)
        self.errors += int(not ok)
        self.elapsed_sum += elapsed
        self.samples.append(elapsed)
        if event["backend_id"]:
            stat = self.by_backend[event["backend_id"]]
            stat["active"] -= 1
            stat["success" if ok else "errors"] += 1
            stat["elapsed_sum"] += elapsed
        event.update(status=status, elapsed_ms=round(elapsed, 2), timestamp=time.time(), error=message)
        self.logs.append(event.copy())
        return event

    def snapshot(self):
        completed = self.success + self.errors
        end = time.perf_counter() if self.active else self.finished
        duration = max(0, (end - self.started)) if self.started is not None and end is not None else 0
        backends = {}
        for backend_id, stat in self.by_backend.items():
            count = stat["success"] + stat["errors"]
            backends[backend_id] = {**stat, "average_ms": round(stat["elapsed_sum"] / count, 2) if count else 0}
        return {"run_id": self.run_id, "total": self.total, "active": self.active,
                "success": self.success, "errors": self.errors,
                "average_ms": round(self.elapsed_sum/completed, 2) if completed else 0,
                "p95_ms": round(percentile95(self.samples), 2), "p95_sample_size": len(self.samples),
                "error_rate": self.errors/completed if completed else 0,
                "success_per_second": round(self.success/duration, 2) if duration else 0,
                "duration_seconds": round(duration, 3), "backends": backends,
                "logs": list(reversed(self.logs))[:100]}
