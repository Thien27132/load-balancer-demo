"""Benchmark qua HTTP thật. Không dùng khoảng nghỉ của giao diện."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
import time
import uuid
import httpx
from load_balancer.metrics import percentile95

async def run_requests(client, count, concurrency, pattern):
    cursor = 0
    results = []
    prefix = str(uuid.uuid4())
    async def worker():
        nonlocal cursor
        while cursor < count:
            i = cursor
            cursor += 1
            key = "hot-user" if pattern == "same" or (pattern == "hot" and i % 5 != 0) else f"user-{i:04d}"
            started = time.perf_counter()
            try:
                response = await client.post("/api/work", json={"request_id": f"{prefix}-{i}", "key": key})
                payload = response.json()
                status = response.status_code
                backend = payload.get("backend_id")
            except (httpx.HTTPError, ValueError):
                status, backend = 0, None
            results.append({"status": status, "backend_id": backend,
                            "elapsed_ms": (time.perf_counter()-started)*1000})
    started = time.perf_counter()
    await asyncio.gather(*(worker() for _ in range(min(count, concurrency))))
    elapsed = time.perf_counter()-started
    success = sum(r["status"] == 200 for r in results)
    latencies = [r["elapsed_ms"] for r in results]
    return {"requests": count, "success": success, "errors": count-success,
            "seconds": round(elapsed, 4), "success_per_second": round(success/elapsed, 2),
            "average_ms": round(sum(latencies)/count, 2), "p95_ms": round(percentile95(latencies), 2),
            "error_rate": (count-success)/count,
            "distribution": dict(Counter(r["backend_id"] for r in results if r["backend_id"])),
            "http_statuses": dict(Counter(str(r["status"]) for r in results))}

async def benchmark(args):
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "python": sys.version, "platform": platform.platform(), "parameters": vars(args),
              "measurement": "client end-to-end; excludes worker queue wait; includes HTTP errors",
              "runs": []}
    async with httpx.AsyncClient(base_url=args.url, timeout=15, trust_env=False,
            limits=httpx.Limits(max_connections=args.concurrency+5)) as client:
        status = (await client.get("/api/status")).json()
        if not all(b["status"] == "healthy" for b in status["backends"]):
            raise RuntimeError("Chờ tất cả backend khỏe trước benchmark.")
        report["backend_configuration"] = status["backends"]
        original = {"algorithm": status["algorithm"], "virtual_nodes": status["virtual_nodes"]}
        algorithms = ["round_robin", "consistent_hash"] if args.algorithm == "both" else [args.algorithm]
        try:
            for iteration in range(args.repeat):
                # Đảo thứ tự giữa các vòng lặp để giảm ảnh hưởng luôn chạy một thuật toán trước.
                order = algorithms if iteration % 2 == 0 else list(reversed(algorithms))
                for algorithm in order:
                    response = await client.put("/api/algorithm", json={"algorithm": algorithm, "virtual_nodes": args.virtual_nodes})
                    response.raise_for_status()
                    await run_requests(client, min(12,args.requests), args.concurrency, args.pattern)
                    (await client.post("/api/metrics/reset")).raise_for_status()
                    result = await run_requests(client, args.requests, args.concurrency, args.pattern)
                    result.update(algorithm=algorithm, iteration=iteration+1)
                    result["health_after"] = (await client.get("/api/status")).json()["backends"]
                    report["runs"].append(result)
                    print(f"{algorithm} #{iteration+1}: {result['success_per_second']} req/s, p95={result['p95_ms']} ms, errors={result['errors']}", flush=True)
        finally:
            response = await client.put("/api/algorithm", json=original)
            response.raise_for_status()
    out = Path(__file__).resolve().parent/"results"
    out.mkdir(parents=True, exist_ok=True)
    filename = out/("http-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json")
    filename.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved:", filename)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--requests", type=int, default=120)
    parser.add_argument("--concurrency", type=int, default=12)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--pattern", choices=["unique", "same", "hot"], default="unique")
    parser.add_argument("--algorithm", choices=["both", "round_robin", "consistent_hash"], default="both")
    parser.add_argument("--virtual-nodes", type=int, default=100)
    args = parser.parse_args()
    if not (1<=args.requests<=100000 and 1<=args.concurrency<=100 and 1<=args.repeat<=20
            and 1<=args.virtual_nodes<=500):
        parser.error("requests: 1..100000; concurrency: 1..100; repeat: 1..20; virtual-nodes: 1..500")
    asyncio.run(benchmark(args))

if __name__ == "__main__":
    main()
