import asyncio
import pytest
from load_balancer.models import Backend
from load_balancer.algorithms.consistent_hash import ConsistentHash, stable_hash
from load_balancer.algorithms.base import NoHealthyBackend
from benchmarks.compare_mapping import mapping_report

B = tuple(Backend(x,f"http://{x}") for x in "ABC")

def test_stable_hash_known_value():
    assert format(stable_hash("abc"), "064x") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

def test_order_independence_and_repeatability():
    first, second = ConsistentHash(100), ConsistentHash(100)
    first.update_backends(B)
    second.update_backends(tuple(reversed(B)))
    assert len(first.points) == 300
    for i in range(1000):
        assert first.lookup(str(i)) == second.lookup(str(i))

def test_only_keys_owned_by_removed_backend_move():
    before, after = ConsistentHash(), ConsistentHash()
    before.update_backends(B)
    after.update_backends(B[:2])
    for i in range(3000):
        key = str(i)
        if before.lookup(key).id != "C":
            assert before.lookup(key) == after.lookup(key)
        assert after.lookup(key).id != "C"

def test_addition_only_moves_keys_to_new_backend():
    before, after = ConsistentHash(), ConsistentHash()
    before.update_backends(B[:2])
    after.update_backends(B)
    for i in range(1000):
        old, new = before.lookup(str(i)), after.lookup(str(i))
        assert old == new or new.id == "C"

def test_wraparound_empty_and_virtual_node_validation(monkeypatch):
    ring = ConsistentHash(1)
    ring.update_backends(B)
    monkeypatch.setattr("load_balancer.algorithms.consistent_hash.stable_hash", lambda key: 2**256-1)
    assert ring.lookup("end") == ring.owners[0]
    ring.update_backends(())
    with pytest.raises(NoHealthyBackend):
        asyncio.run(ring.select("key"))
    with pytest.raises(ValueError):
        ConsistentHash(0)

def test_mapping_report_preserves_total():
    report = mapping_report(B,100,1000)
    assert sum(report["consistent_hash"]["before"].values()) == 1000
    assert report["consistent_hash"]["changed"] == report["consistent_hash"]["before"]["C"]
    assert report["modulo"]["changed"] > report["consistent_hash"]["changed"]
