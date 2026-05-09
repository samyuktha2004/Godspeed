from __future__ import annotations

from abc import ABC, abstractmethod

from ingestion.models import RawDocument


class BaseSource(ABC):
    @abstractmethod
    async def fetch(self) -> list[RawDocument]:
        ...

    @abstractmethod
    def source_type(self) -> str:
        ...
