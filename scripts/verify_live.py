"""Kiểm chứng bốn tiến trình thật trên cổng tạm; tự dọn khi thành công hoặc lỗi."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]

def wait_for(predicate, timeout=15):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except httpx.HTTPError:
            pass
        time.sleep(.1)
    raise AssertionError("Timed out waiting for expected state")

def main():
    config = json.loads((ROOT/"config.json").read_text(encoding="utf-8"))
    sockets = []
    try:
        for _ in range(4):
            s=socket.socket()
            s.bind(("127.0.0.1",0))
            sockets.append(s)
        ports=[s.getsockname()[1] for s in sockets]
    finally:
        for s in sockets: s.close()
    config["load_balancer"]["port"]=ports[0]
    config["load_balancer"]["request_timeout_seconds"]=.4
    config["health_check"].update(interval_seconds=.15,timeout_seconds=.1)
    for backend,port in zip(config["backends"],ports[1:]):
        backend.update(port=port,url=f"http://127.0.0.1:{port}",delay_ms=10)
    flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
    with tempfile.TemporaryDirectory(prefix="lb-live-check-") as temp:
        path=Path(temp)/"config.json"
        path.write_text(json.dumps(config),encoding="utf-8")
        log=open(Path(temp)/"server.log","w",encoding="utf-8")
        # Dedicated runner requests cooperative uvicorn shutdown via a stop file.
        stop_file=Path(temp)/"stop"
        env=dict(os.environ,DEMO_CONFIG=str(path),DEMO_MANAGE_BACKENDS="1",PYTHONUTF8="1")
        runner=Path(__file__).with_name("live_test_server.py")
        process=subprocess.Popen([sys.executable,str(runner),str(ports[0]),str(stop_file)],
                                 cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=flags)
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{ports[0]}",timeout=5,trust_env=False) as client:
                def all_healthy():
                    return all(b["status"]=="healthy" for b in client.get("/api/status").json()["backends"])
                wait_for(all_healthy)
                assert client.get("/").status_code==200
                assert client.get("/static/app.js").status_code==200
                def work(key="same"):
                    return client.post("/api/work",json={"request_id":str(time.time_ns()),"key":key})
                results=[work().json() for _ in range(12)]
                assert [r["backend_id"] for r in results]==list("ABC"*4)
                print("PASS: HTTP forwarding and exact Round Robin order",flush=True)
                assert client.put("/api/algorithm",json={"algorithm":"consistent_hash","virtual_nodes":100}).status_code==200
                assert len({work().json()["backend_id"] for _ in range(6)})==1
                assert client.get("/api/mapping-comparison").json()["consistent_hash"]["changed"]>0
                print("PASS: consistent hashing and mapping comparison",flush=True)
                assert client.put("/api/algorithm",json={"algorithm":"round_robin"}).status_code==200
                assert client.post("/api/backends/C/delay",json={"delay_ms":200}).status_code==200
                results=[work().json() for _ in range(3)]
                by_id={r["backend_id"]:r for r in results}
                assert by_id["C"]["elapsed_ms"]>by_id["A"]["elapsed_ms"]+100
                assert client.post("/api/backends/C/delay",json={"delay_ms":1000}).status_code==200
                responses=[work() for _ in range(3)]
                assert [r.status_code for r in responses]==[200,200,504]
                assert client.get("/api/metrics").json()["active"]==0
                assert client.post("/api/backends/C/delay",json={"delay_ms":10}).status_code==200
                print("PASS: slow backend and real upstream timeout 504",flush=True)
                assert client.post("/api/backends/C/process/stop").status_code==200
                wait_for(lambda: next(b for b in client.get("/api/status").json()["backends"] if b["id"]=="C")["status"]=="unhealthy")
                assert all(work().json()["backend_id"]!="C" for _ in range(8))
                assert client.post("/api/backends/C/process/start").status_code==200
                wait_for(all_healthy)
                assert "C" in {work().json()["backend_id"] for _ in range(6)}
                print("PASS: actual process stop, health exclusion, restart and recovery",flush=True)
                for backend in "ABC":
                    assert client.post(f"/api/backends/{backend}/process/stop").status_code==200
                wait_for(lambda: all(b["status"]=="unhealthy" for b in client.get("/api/status").json()["backends"]))
                assert work().status_code==503
                print("PASS: empty healthy pool returns HTTP 503",flush=True)
        except BaseException:
            log.flush()
            print((Path(temp)/"server.log").read_text(encoding="utf-8"))
            raise
        finally:
            stop_file.touch()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)
            log.close()
        assert process.returncode == 0
    print("LIVE VERIFICATION PASSED. Child processes shut down.",flush=True)

if __name__=="__main__":
    main()
