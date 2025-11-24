from abc import ABC, abstractmethod
from typing import Optional
from PIL import Image
import io


class BaseVideoService(ABC):

    @abstractmethod
    def generate_video(self, prompt: str, num_frames: int = 60):
        """
        Returns: raw video bytes
        """
        pass


def create_composite_image(image_bytes_list: list[bytes], max_aspect_ratio: float = 2.0) -> bytes:
    """
    Merge multiple character DNA images into a single composite image.
    Used for Runway which only accepts one reference image.
    Creates a grid layout to maintain acceptable aspect ratio (max 2.358:1).
    
    Args:
        image_bytes_list: List of image bytes to merge
        max_aspect_ratio: Maximum width/height ratio (Runway limit is 2.358)
        
    Returns:
        Composite image as JPEG bytes
    """
    if not image_bytes_list:
        raise ValueError("No images provided for composite")
    
    if len(image_bytes_list) == 1:
        # Single image, return as-is
        return image_bytes_list[0]
    
    # Load all images
    images = [Image.open(io.BytesIO(img_bytes)) for img_bytes in image_bytes_list]
    
    # Resize all images to same dimensions for uniform grid
    target_size = (512, 512)  # Standard square size
    images = [img.resize(target_size, Image.Resampling.LANCZOS) for img in images]
    
    num_images = len(images)
    
    # Calculate grid dimensions to keep aspect ratio under max_aspect_ratio
    # Try different grid layouts
    best_cols = 1
    best_rows = num_images
    
    for cols in range(1, num_images + 1):
        rows = (num_images + cols - 1) // cols  # Ceiling division
        aspect_ratio = (cols * target_size[0]) / (rows * target_size[1])
        
        if aspect_ratio <= max_aspect_ratio:
            best_cols = cols
            best_rows = rows
            break
    
    # Create composite canvas
    canvas_width = best_cols * target_size[0]
    canvas_height = best_rows * target_size[1]
    composite = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))
    
    # Paste images in grid layout
    for idx, img in enumerate(images):
        col = idx % best_cols
        row = idx // best_cols
        x = col * target_size[0]
        y = row * target_size[1]
        composite.paste(img, (x, y))
    
    print(f"[Composite] Created {best_cols}x{best_rows} grid with {num_images} images (aspect ratio: {canvas_width/canvas_height:.2f}:1)")
    
    # Convert to bytes
    output = io.BytesIO()
    composite.save(output, format='JPEG', quality=95)
    output.seek(0)
    
    return output.read()


def get_video_service(model: str = "veo-2.0"):
    """
    Factory function to create video service based on model name.
    
    Args:
        model: Model identifier (e.g., "veo-2.0", "gen4_turbo")
        
    Returns:
        Video service instance
    """
    if model.startswith("gen4") or model == "runway":
        from app.services.video.runway_flow import RunwayVideoService
        return RunwayVideoService()
    elif model.startswith("veo"):
        from app.services.video.google_flow import GoogleFlowVideoService
        return GoogleFlowVideoService()
    else:
        raise ValueError(f"Unknown model: {model}. Supported: veo-2.0, gen4_turbo")

