"""Đo ánh xạ, không gửi HTTP. Chạy: python -m benchmarks.compare_mapping."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from load_balancer.algorithms.consistent_hash import ConsistentHash, stable_hash
from load_balancer.models import Backend

def mapping_report(backends, virtual_nodes=100, count=1000, removed=None):
    ordered = tuple(sorted(backends, key=lambda b: b.id))
    if len(ordered) < 2:
        raise ValueError("Cần ít nhất hai backend.")
    removed = removed or ("C" if any(b.id == "C" for b in ordered) else ordered[-1].id)
    remaining = tuple(b for b in ordered if b.id != removed)
    if len(remaining) == len(ordered):
        raise ValueError("Backend cần bỏ không tồn tại.")
    keys = [f"user-{i:04d}" for i in range(count)]
    before, after = ConsistentHash(virtual_nodes), ConsistentHash(virtual_nodes)
    before.update_backends(ordered)
    after.update_backends(remaining)
    ch_old = [before.lookup(key).id for key in keys]
    ch_new = [after.lookup(key).id for key in keys]
    mod_old = [ordered[stable_hash(key) % len(ordered)].id for key in keys]
    mod_new = [remaining[stable_hash(key) % len(remaining)].id for key in keys]
    def compare(old, new):
        changed = sum(a != b for a, b in zip(old, new))
        return {"changed": changed, "changed_percent": round(changed/count*100, 2),
                "before": dict(Counter(old)), "after": dict(Counter(new))}
    return {"keys": count, "removed": removed, "virtual_nodes": virtual_nodes,
            "consistent_hash": compare(ch_old, ch_new), "modulo": compare(mod_old, mod_new)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--virtual-nodes", type=int, default=100)
    parser.add_argument("--keys", type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.keys <= 100000:
        parser.error("--keys must be 1..100000")
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root/"config.json").read_text(encoding="utf-8"))
    report = mapping_report([Backend(b["id"], b["url"]) for b in config["backends"]],
                            args.virtual_nodes, args.keys)
    out = root/"benchmarks/results"
    out.mkdir(parents=True, exist_ok=True)
    filename = out / ("mapping-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    filename.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("Saved:", filename)

if __name__ == "__main__":
    main()
