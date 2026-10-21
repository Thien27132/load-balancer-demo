"""Chạy benchmark trên cụm tiến trình riêng, không ảnh hưởng trang demo đang mở."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import httpx

ROOT=Path(__file__).resolve().parents[1]

def main():
    config=json.loads((ROOT/"config.json").read_text(encoding="utf-8"))
    probes=[]
    try:
        for _ in range(4):
            probe=socket.socket()
            probe.bind(("127.0.0.1",0))
            probes.append(probe)
        ports=[p.getsockname()[1] for p in probes]
    finally:
        for probe in probes: probe.close()
    config["load_balancer"]["port"]=ports[0]
    for backend,port in zip(config["backends"],ports[1:]):
        backend.update(port=port,url=f"http://127.0.0.1:{port}",delay_ms=100)
    with tempfile.TemporaryDirectory(prefix="lb-benchmark-") as temp:
        path=Path(temp)/"config.json"
        path.write_text(json.dumps(config),encoding="utf-8")
        stop=Path(temp)/"stop"
        env=dict(os.environ,DEMO_CONFIG=str(path),DEMO_MANAGE_BACKENDS="1",PYTHONUTF8="1")
        flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
        with open(Path(temp)/"server.log","w",encoding="utf-8") as log:
            process=subprocess.Popen([sys.executable,str(Path(__file__).with_name("live_test_server.py")),str(ports[0]),str(stop)],
                cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=flags)
            try:
                deadline=time.monotonic()+20
                with httpx.Client(timeout=2,trust_env=False) as client:
                    while True:
                        try:
                            data=client.get(f"http://127.0.0.1:{ports[0]}/api/status").json()
                            if all(b["status"]=="healthy" for b in data["backends"]): break
                        except httpx.HTTPError:
                            pass
                        if time.monotonic()>deadline: raise RuntimeError("Backend startup timed out")
                        time.sleep(.2)
                subprocess.run([sys.executable,"-m","benchmarks.run_load","--url",f"http://127.0.0.1:{ports[0]}",
                                "--requests","120","--concurrency","12","--repeat","3"],cwd=ROOT,check=True,env=env)
                for nodes in ("1","100"):
                    subprocess.run([sys.executable,"-m","benchmarks.compare_mapping","--virtual-nodes",nodes],cwd=ROOT,check=True,env=env)
            finally:
                stop.touch()
                try: process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=5)

if __name__=="__main__":
    main()
