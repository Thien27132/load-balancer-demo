"""Chạy một load balancer; lifespan quản lý ba tiến trình backend."""
import argparse
import json
import os
from pathlib import Path
import socket
import uvicorn

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description="Load Balancer Lab — Python")
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    args = parser.parse_args()
    path = Path(args.config).resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    if config["load_balancer"]["host"] != "127.0.0.1":
        raise SystemExit("Demo chỉ hỗ trợ host 127.0.0.1.")
    ports = [config["load_balancer"]["port"]] + [b["port"] for b in config["backends"]]
    if len(ports) != len(set(ports)):
        raise SystemExit("Các dịch vụ phải dùng cổng khác nhau.")
    try:
        for port in ports:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", port))
    except OSError as exc:
        raise SystemExit(f"Cổng {port} không sử dụng được: {exc}") from exc
    os.environ["DEMO_CONFIG"] = str(path)
    os.environ["DEMO_MANAGE_BACKENDS"] = "1"
    print(f"Load Balancer Lab: http://127.0.0.1:{ports[0]}", flush=True)
    print("Ctrl+C để dừng load balancer và các backend.", flush=True)
    try:
        uvicorn.run("load_balancer.app:app", host="127.0.0.1", port=ports[0],
                    workers=1, access_log=False)
    except KeyboardInterrupt:
        # Một số phiên bản Uvicorn phát lại SIGINT sau khi lifespan đã dọn xong.
        print("Demo stopped.", flush=True)

if __name__ == "__main__":
    main()
