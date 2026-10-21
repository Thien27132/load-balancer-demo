"""Mỗi lần chọn tăng chỉ số một đơn vị; không đo độ bận của backend."""
import asyncio
from .base import SelectionAlgorithm, NoHealthyBackend
from ..models import Backend

class RoundRobin(SelectionAlgorithm):
    def __init__(self):
        self.backends = ()
        self.next_index = 0
        self.lock = asyncio.Lock()

    def update_backends(self, backends: tuple[Backend, ...]) -> None:
        ordered = tuple(sorted(backends, key=lambda b: b.id))
        if ordered != self.backends:
            self.backends = ordered
            self.next_index = 0

    async def select(self, key: str) -> Backend:
        async with self.lock:
            if not self.backends:
                raise NoHealthyBackend()
            chosen = self.backends[self.next_index]
            self.next_index = (self.next_index + 1) % len(self.backends)
            return chosen
