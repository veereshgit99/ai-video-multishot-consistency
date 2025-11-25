from abc import ABC, abstractmethod
from typing import Optional


class BaseVideoService(ABC):

    @abstractmethod
    def generate_video(self, prompt: str, num_frames: int = 60):
        """
        Returns: raw video bytes
        """
        pass


def get_video_service(model: str = "veo-2.0"):
    """
    Factory function to create video service based on model name.
    
    Args:
        model: Model identifier (e.g., "veo-2.0", "veo-3.1", "gen4_turbo", "minimax", "seedance")
        
    Returns:
        Video service instance
    """
    if model.startswith("gen4") or model == "runway":
        from app.services.video.runway_flow import RunwayVideoService
        return RunwayVideoService()
    elif model == "veo-2.0":
        from app.services.video.google_flow import GoogleFlowVideoService
        from app.core.config import settings
        return GoogleFlowVideoService(model_id=settings.VEO_2_MODEL_ID)
    elif model == "veo-3.1":
        from app.services.video.google_flow import GoogleFlowVideoService
        from app.core.config import settings
        return GoogleFlowVideoService(model_id=settings.VEO_3_MODEL_ID)
    elif model == "minimax" or model.startswith("MiniMax"):
        from app.services.video.minimax_flow import MinimaxVideoService
        return MinimaxVideoService()
    elif model == "seedance":
        from app.services.video.seedance_flow import SeedanceVideoService
        return SeedanceVideoService()
    elif model == "seedance-pro-fast":
        from app.services.video.seedance_pro_fast_flow import SeedanceProFastVideoService
        return SeedanceProFastVideoService()
    elif model == "seedance-pro":
        from app.services.video.seedance_pro_flow import SeedanceProVideoService
        return SeedanceProVideoService()
    else:
        raise ValueError(f"Unknown model: {model}. Supported: veo-2.0, veo-3.1, gen4_turbo, minimax, seedance, seedance-pro-fast, seedance-pro")

