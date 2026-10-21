"""SHA-256 + nút ảo ổn định + tìm kiếm nhị phân trên vòng băm."""
from bisect import bisect_left
from hashlib import sha256
from .base import SelectionAlgorithm, NoHealthyBackend
from ..models import Backend

def stable_hash(value: str) -> int:
    return int.from_bytes(sha256(value.encode("utf-8")).digest(), "big")

class ConsistentHash(SelectionAlgorithm):
    def __init__(self, virtual_nodes: int = 100):
        if not 1 <= virtual_nodes <= 500:
            raise ValueError("virtual_nodes must be 1..500")
        self.virtual_nodes = virtual_nodes
        self.backends = ()
        self.points = ()
        self.owners = ()

    def update_backends(self, backends: tuple[Backend, ...]) -> None:
        ordered = tuple(sorted(backends, key=lambda b: b.id))
        if ordered == self.backends:
            return
        ring = sorted((stable_hash(f"{b.id}#{i}"), b.id, i, b)
                      for b in ordered for i in range(self.virtual_nodes))
        # Một event loop; không await giữa các phép gán ảnh chụp vòng băm.
        self.backends = ordered
        self.points = tuple(node[0] for node in ring)
        self.owners = tuple(node[3] for node in ring)

    def lookup(self, key: str) -> Backend:
        if not self.points:
            raise NoHealthyBackend()
        position = bisect_left(self.points, stable_hash(key)) % len(self.points)
        return self.owners[position]

    async def select(self, key: str) -> Backend:
        return self.lookup(key)

    def describe(self, key: str) -> dict:
        maximum = 2 ** 256
        return {
            "virtual_nodes": self.virtual_nodes,
            "nodes": [{"position": p / maximum, "backend_id": b.id}
                      for p, b in zip(self.points, self.owners)],
            "key_position": stable_hash(key) / maximum,
            "selected": self.lookup(key).id if self.points else None,
        }
