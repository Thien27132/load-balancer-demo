"""Chọn máy độc lập với HTTP; registry cung cấp danh sách máy khỏe."""
from abc import ABC, abstractmethod
from ..models import Backend

class NoHealthyBackend(Exception):
    pass

class SelectionAlgorithm(ABC):
    @abstractmethod
    def update_backends(self, backends: tuple[Backend, ...]) -> None:
        pass

    @abstractmethod
    async def select(self, key: str) -> Backend:
        pass
