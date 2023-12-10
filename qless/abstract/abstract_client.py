from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from qless.abstract.abstract_config import AbstractConfig
from qless.abstract.abstract_jobs import AbstractJobs
from qless.abstract.abstract_queues import AbstractQueues
from qless.abstract.abstract_throttles import AbstractThrottles
from qless.abstract.abstract_workers import AbstractWorkers


if TYPE_CHECKING:  # pragma: no cover
    from redis import Redis


class AbstractClient(ABC):
    @abstractmethod
    def __call__(self, command: str, *args: Any) -> Any:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def config(self) -> AbstractConfig:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def jobs(self) -> AbstractJobs:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def queues(self) -> AbstractQueues:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def redis(self) -> "Redis":  # pragma: no cover
        ...

    @property
    @abstractmethod
    def throttles(self) -> AbstractThrottles:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def worker_name(self) -> str:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def workers(self) -> AbstractWorkers:  # pragma: no cover
        ...
