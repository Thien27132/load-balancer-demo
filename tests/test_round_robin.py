import asyncio
from collections import Counter
import pytest
from load_balancer.models import Backend
from load_balancer.algorithms.round_robin import RoundRobin
from load_balancer.algorithms.base import NoHealthyBackend

BACKENDS = tuple(Backend(x, f"http://{x}") for x in "ABC")

def test_exact_cycle_and_uneven_count():
    async def scenario():
        rr = RoundRobin()
        rr.update_backends(BACKENDS)
        result = [(await rr.select("ignored")).id for _ in range(10)]
        assert result == list("ABCABCABCA")
        assert Counter(result) == {"A":4,"B":3,"C":3}
    asyncio.run(scenario())

def test_concurrent_selection_and_unchanged_registry():
    async def scenario():
        rr = RoundRobin()
        rr.update_backends(BACKENDS)
        async def select():
            rr.update_backends(BACKENDS)
            return (await rr.select("same")).id
        results = await asyncio.gather(*(select() for _ in range(300)))
        assert Counter(results) == {"A":100,"B":100,"C":100}
    asyncio.run(scenario())

def test_removed_server_and_empty_pool():
    async def scenario():
        rr = RoundRobin()
        rr.update_backends(BACKENDS[:2])
        assert [(await rr.select("")).id for _ in range(4)] == list("ABAB")
        rr.update_backends(())
        with pytest.raises(NoHealthyBackend):
            await rr.select("")
    asyncio.run(scenario())
