from abc import ABC
from abc import abstractmethod


class RetrievalStrategy(ABC):

    @abstractmethod
    def retrieve(
        self,
        query: str
    ):

        pass
