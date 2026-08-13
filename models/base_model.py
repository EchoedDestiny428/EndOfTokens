from abc import ABC, abstractmethod

class BaseModel(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a response based on the prompt."""
        pass
