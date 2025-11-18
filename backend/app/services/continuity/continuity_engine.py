# app/services/continuity/continuity_engine.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from app import models


@dataclass
class ContinuityState:
    """
    Per-project continuity state, kept in memory by the worker.
    In the future you can persist this in DB if needed.
    """
    shot_index: int = 0
    last_shot_id: Optional[int] = None
    last_camera: Optional[str] = None
    last_shot_summary: Optional[str] = None
    global_palette: List[Any] = field(default_factory=list)
    global_style_hint: Optional[str] = None


class ContinuityEngine:
    """
    Builds continuity-aware prompts, and updates continuity state
    after each rendered shot.
    """

    def _summarize_characters(self, characters: List[models.Character]) -> str:
        parts = []
        for c in characters:
            desc_bits = [c.name]
            if c.role:
                desc_bits.append(c.role)
            if c.description:
                desc_bits.append(c.description)

            line = ", ".join(desc_bits)

            # dominant_colors might be stored as JSON/text; just include raw
            if getattr(c, "dominant_colors", None):
                line += f", dominant colors = {c.dominant_colors}"

            parts.append(line)

        return " | ".join(parts) if parts else "No specific characters defined."

    def build_continuity_prompt(
        self,
        base_prompt: str,
        shot: models.Shot,
        characters: List[models.Character],
        state: ContinuityState,
    ) -> str:
        """
        Take the base shot prompt (already scene-aware) and inject
        continuity instructions + character/style metadata.
        """

        char_summary = self._summarize_characters(characters)

        continuity_lines = []

        # Cross-shot continuity hints
        if state.shot_index > 0:
            continuity_lines.append(
                "This shot must visually and stylistically CONTINUE from the previous shot."
            )
            if state.last_camera:
                continuity_lines.append(
                    f"Keep camera language consistent with previous shot ({state.last_camera})."
                )
            else:
                continuity_lines.append(
                    "Maintain similar framing and composition as the previous shot."
                )

            if state.last_shot_summary:
                continuity_lines.append(
                    f"Previous shot summary: {state.last_shot_summary}"
                )

        # Palette and style continuity
        if state.global_palette:
            continuity_lines.append(
                f"Global color palette to preserve across shots: {state.global_palette}."
            )

        if state.global_style_hint:
            continuity_lines.append(f"Global style: {state.global_style_hint}.")
        else:
            continuity_lines.append(
                "Global style: cinematic, coherent, and consistent across all shots."
            )

        continuity_text = "\n".join(continuity_lines)

        final_prompt = f"""
{base_prompt}

Characters and roles (keep faces, outfits, and overall look consistent across all shots):
{char_summary}

Shot index in sequence: {state.shot_index + 1}

Continuity requirements:
{continuity_text}
""".strip()

        return final_prompt

    def update_state_after_shot(
        self,
        shot: models.Shot,
        characters: List[models.Character],
        state: ContinuityState,
    ) -> ContinuityState:
        """
        Update in-memory continuity state once a shot has been rendered.
        Right now we only track text + palette – no heavy frame analysis.
        """

        state.shot_index += 1
        state.last_shot_id = shot.id
        state.last_camera = getattr(shot, "camera_type", None) or getattr(
            shot, "camera", None
        )
        state.last_shot_summary = shot.description

        # Initialize global palette from characters on first shot
        if not state.global_palette:
            palette = []
            for c in characters:
                if getattr(c, "dominant_colors", None):
                    palette.append(c.dominant_colors)
            state.global_palette = palette

        # Optionally set a global style hint once, based on first shot
        if not state.global_style_hint and shot.description:
            state.global_style_hint = (
                "Match the mood and style implied by this description: "
                + shot.description[:200]
            )

        return state
