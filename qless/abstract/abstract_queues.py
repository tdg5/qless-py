from abc import ABC, abstractmethod
from typing import Dict

from qless.abstract.abstract_queue import AbstractQueue


class AbstractQueues(ABC):
    @property
    @abstractmethod
    def counts(self) -> Dict:  # pragma: no cover
        ...

    @abstractmethod
    def __getitem__(self, queue_name: str) -> AbstractQueue:  # pragma: no cover
        ...
