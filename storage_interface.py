from abc import ABC, abstractmethod
from typing import List, Dict

class StorageInterface(ABC):
    @abstractmethod
    def save_prediction(self, uid: str, original_path: str, predicted_path: str):
        pass

    @abstractmethod
    def save_detection(self, uid: str, label: str, score: float, bbox: str):
        pass

    @abstractmethod
    def get_prediction(self, uid: str) -> Dict:
        pass

    @abstractmethod
    def get_predictions_by_label(self, label: str) -> List[Dict]:
        pass

    @abstractmethod
    def get_predictions_by_score(self, min_score: float) -> List[Dict]:
        pass