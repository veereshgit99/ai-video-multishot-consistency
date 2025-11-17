import json
from app import models

class PromptBuilder:

    @staticmethod
    def build_shot_prompt(db, shot: models.Shot):
        """
        Pull character + scene DNA and build a rich prompt.
        This is where your 'continuity engine' logic evolves.
        """

        # Scene
        scene = None
        if shot.scene_id:
            scene = db.query(models.Scene).filter(models.Scene.id == shot.scene_id).first()

        # Characters in the scene (for now: all characters in project)
        characters = (
            db.query(models.Character)
            .filter(models.Character.project_id == shot.project_id)
            .all()
        )

        char_desc = []
        for c in characters:
            desc = f"{c.name}, {c.role}"
            if c.description:
                desc += f", {c.description}"
            char_desc.append(desc)

        char_text = "; ".join(char_desc)

        # Shot description
        base = shot.description or "A video shot."

        # Final prompt
        prompt = f"""
A cinematic shot. 
Characters present: {char_text}.
Scene: {scene.description if scene else 'unspecified'}. 
Shot description: {base}.
Camera: {shot.camera_type or 'default'}.
Style: Keep consistent with previous shots.
"""

        return prompt.strip()
