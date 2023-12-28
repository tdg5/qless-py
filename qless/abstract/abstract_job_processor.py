from abc import ABC, abstractmethod
from typing import Generic, Type, TypeVar, get_args

from typing_extensions import get_original_bases

from qless.abstract.abstract_job import AbstractJob
from qless.abstract.abstract_job_data import AbstractJobData


JD = TypeVar("JD", bound=AbstractJobData)


class AbstractJobProcessor(Generic[JD], ABC):
    @classmethod
    def deserialize_data_json(cls, data: str) -> JD:
        return cls.data_class().from_json(data)

    @classmethod
    def data_class(cls) -> Type[JD]:
        """Override to define an explicit data class, otherwise, try to
        determine data class from type annotation.
        """
        for base in get_original_bases(cls):
            base_args = get_args(base)
            if base_args and issubclass(base_args[0], AbstractJobData):
                data_class: Type[JD] = base_args[0]
                return data_class
        raise RuntimeError(f"Unable to determine data class for {cls}")

    @classmethod
    @abstractmethod
    def process(cls, job: AbstractJob) -> None:  # pragma: no cover
        ...
