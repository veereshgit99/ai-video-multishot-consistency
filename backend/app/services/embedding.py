import json
from typing import Dict, List, Tuple

import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel


# Load once per process
_clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
_clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")


def _image_to_clip_embedding(image: Image.Image) -> List[float]:
    inputs = _clip_processor(images=image, return_tensors="pt")
    with torch.no_grad():
        outputs = _clip_model.get_image_features(**inputs)
    embedding = outputs[0].cpu().numpy().tolist()
    return embedding


def _extract_dominant_colors(image: Image.Image, k: int = 5) -> List[Tuple[int, int, int]]:
    # Simple palette-based approach; not real k-means but good enough for MVP
    small = image.convert("RGB").resize((64, 64))
    palette = small.convert("P", palette=Image.ADAPTIVE, colors=k)
    palette_colors = palette.getpalette()
    color_counts = sorted(palette.getcolors(), reverse=True)

    colors = []
    for count, idx in color_counts[:k]:
        r = palette_colors[idx * 3]
        g = palette_colors[idx * 3 + 1]
        b = palette_colors[idx * 3 + 2]
        colors.append((r, g, b))
    return colors


def extract_character_dna(image_path: str) -> Dict:
    img = Image.open(image_path).convert("RGB")

    # For v1, use same embedding for "face" + "style"
    clip_embedding = _image_to_clip_embedding(img)
    dominant_colors = _extract_dominant_colors(img)

    return {
        "face_embedding": clip_embedding,
        "style_embedding": clip_embedding,
        "dominant_colors": dominant_colors,
    }


def extract_scene_dna(image_path: str) -> Dict:
    img = Image.open(image_path).convert("RGB")

    scene_embedding = _image_to_clip_embedding(img)
    palette = _extract_dominant_colors(img, k=7)

    return {
        "scene_embedding": scene_embedding,
        "palette": palette,
    }


def to_json_str(obj) -> str:
    return json.dumps(obj)
