from abc import ABC, abstractmethod
from typing import List


class AbstractQueueJobs(ABC):
    @abstractmethod
    def depends(
        self, offset: int = 0, count: int = 25
    ) -> List[str]:  # pragma: no cover
        ...

    @abstractmethod
    def recurring(
        self,
        offset: int = 0,
        count: int = 25,
    ) -> List[str]:  # pragma: no cover
        ...

    @abstractmethod
    def running(
        self, offset: int = 0, count: int = 25
    ) -> List[str]:  # pragma: no cover
        ...

    @abstractmethod
    def scheduled(
        self,
        offset: int = 0,
        count: int = 25,
    ) -> List[str]:  # pragma: no cover
        ...

    @abstractmethod
    def stalled(
        self, offset: int = 0, count: int = 25
    ) -> List[str]:  # pragma: no cover
        ...
