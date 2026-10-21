"""Chỉ quản lý tiến trình do demo khởi tạo. Không tìm/kill tiến trình bên ngoài."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]

class BackendProcesses:
    def __init__(self, configs, token):
        self.configs = {item["id"]: dict(item) for item in configs}
        self.children = {}
        self.token = token
        self.lock = threading.Lock()

    def start(self, backend_id):
        with self.lock:
            child = self.children.get(backend_id)
            if child and child.poll() is None:
                return
            config = self.configs[backend_id]
            # Không chiếm hoặc dừng dịch vụ khác đang dùng cổng.
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", config["port"]))
            env = dict(os.environ, BACKEND_ID=backend_id,
                       BACKEND_DELAY_MS=str(config["delay_ms"]), DEMO_CONTROL_TOKEN=self.token)
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self.children[backend_id] = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1",
                 "--port", str(config["port"]), "--no-access-log", "--log-level", "warning"],
                cwd=ROOT, env=env, creationflags=flags)

    def stop(self, backend_id):
        with self.lock:
            child = self.children.get(backend_id)
            if child and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=3)

    def running(self, backend_id):
        child = self.children.get(backend_id)
        return bool(child and child.poll() is None)

    def close(self):
        for backend_id in self.configs:
            self.stop(backend_id)
