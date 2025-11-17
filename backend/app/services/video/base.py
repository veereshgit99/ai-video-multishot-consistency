from abc import ABC, abstractmethod

class BaseVideoService(ABC):

    @abstractmethod
    def generate_video(self, prompt: str, num_frames: int = 60):
        """
        Returns: raw video bytes
        """
        pass
