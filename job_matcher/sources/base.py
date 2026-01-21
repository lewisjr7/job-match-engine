from abc import ABC, abstractmethod
from typing import List, Dict


class JobSource(ABC):
    @abstractmethod
    def fetch_jobs(self) -> List[Dict]:
        pass
