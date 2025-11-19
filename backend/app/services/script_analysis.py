# app/services/script_analysis.py

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional

from app import models
from dotenv import load_dotenv
load_dotenv()

# Choose your LLM provider
USE_OPENAI = True  # Set to False to use Vertex AI Gemini

if USE_OPENAI:
    from openai import OpenAI
else:
    import vertexai
    from vertexai.generative_models import GenerativeModel, SafetySetting


@dataclass
class ShotSpec:
    index: int
    description: str
    camera_type: str
    motion: str
    duration_seconds: int
    continuity_notes: Optional[str] = None


@dataclass
class SceneSpec:
    index: int
    title: str
    description: str
    shots: List[ShotSpec]


@dataclass
class ScriptStructure:
    scenes: List[SceneSpec]


class ScriptAnalysisService:
    """
    Turn raw script text into structured scenes/shots using an LLM.
    Supports OpenAI GPT-4 or Vertex AI Gemini 2.0 Pro.
    """

    def __init__(self):
        if USE_OPENAI:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        else:
            from app.core.config import settings
            vertexai.init(
                project=settings.GOOGLE_CLOUD_PROJECT_ID,
                location=settings.GOOGLE_CLOUD_LOCATION
            )
            self.model = GenerativeModel("gemini-2.0-flash-exp")

    def analyze_script(
        self,
        script_text: str,
        characters: List[models.Character],
        *,
        language: str = "en",
        max_scenes: int = 10,
        max_shots_per_scene: int = 12,
        target_shot_duration_seconds: int = 4,
    ) -> ScriptStructure:
        llm_output = self._call_llm(
            script_text=script_text,
            characters=characters,
            language=language,
            max_scenes=max_scenes,
            max_shots_per_scene=max_shots_per_scene,
            target_shot_duration_seconds=target_shot_duration_seconds,
        )

        # Parse LLM output into structured dataclasses
        scenes: List[SceneSpec] = []
        for i, s in enumerate(llm_output.get("scenes", []), start=1):
            shots: List[ShotSpec] = []
            for j, sh in enumerate(s.get("shots", []), start=1):
                shots.append(
                    ShotSpec(
                        index=j,
                        description=sh.get("description", "").strip(),
                        camera_type=sh.get("camera_type", "medium").strip(),
                        motion=sh.get("motion", "static").strip(),
                        duration_seconds=int(
                            sh.get("duration_seconds", target_shot_duration_seconds)
                        ),
                        continuity_notes=sh.get("continuity_notes"),
                    )
                )

            scenes.append(
                SceneSpec(
                    index=i,
                    title=s.get("title", f"Scene {i}").strip(),
                    description=s.get("description", "").strip(),
                    shots=shots,
                )
            )

        return ScriptStructure(scenes=scenes)

    def _call_llm(
        self,
        *,
        script_text: str,
        characters: List[models.Character],
        language: str,
        max_scenes: int,
        max_shots_per_scene: int,
        target_shot_duration_seconds: int,
    ) -> dict:
        """
        Call LLM to break down script into scenes and shots.
        Returns structured JSON dict.
        """
        # Build character context
        character_context = []
        for c in characters:
            character_context.append({
                "name": c.name,
                "role": getattr(c, "role", "") or "",
                "description": c.description or "",
                "dominant_colors": getattr(c, "dominant_colors", None)
            })

        # Build system prompt
        system_prompt = self._script_breakdown_system_prompt()
        
        # Build user context
        user_context = {
            "script_text": script_text,
            "characters": character_context,
            "language": language,
            "max_scenes": max_scenes,
            "max_shots_per_scene": max_shots_per_scene,
            "target_shot_duration_seconds": target_shot_duration_seconds
        }

        if USE_OPENAI:
            return self._call_openai(system_prompt, user_context)
        else:
            return self._call_gemini(system_prompt, user_context)

    def _call_openai(self, system_prompt: str, user_context: dict) -> dict:
        """Call OpenAI GPT-4/GPT-4o for script breakdown."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # or "gpt-4-turbo", "gpt-4"
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_context, indent=2)}
                ],
                temperature=0.2,
                max_tokens=4000
            )

            data = json.loads(response.choices[0].message.content)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON from OpenAI: {e}")
        except Exception as e:
            raise ValueError(f"OpenAI API error: {e}")

        # Validate structure
        if "scenes" not in data:
            raise ValueError("Missing 'scenes' in LLM output")

        return data

    def _call_gemini(self, system_prompt: str, user_context: dict) -> dict:
        """Call Vertex AI Gemini for script breakdown."""
        try:
            response = self.model.generate_content(
                contents=[
                    system_prompt + "\n\n" + json.dumps(user_context, indent=2)
                ],
                generation_config={
                    "temperature": 0.2,
                    "top_p": 0.9,
                    "max_output_tokens": 4000,
                    "response_mime_type": "application/json",
                },
                safety_settings=[
                    SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="BLOCK_NONE"
                    )
                ],
            )

            data = json.loads(response.text)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON from Gemini: {e}\nRaw output: {response.text}")
        except Exception as e:
            raise ValueError(f"Gemini API error: {e}")

        # Validate structure
        if "scenes" not in data:
            raise ValueError("Missing 'scenes' in LLM output")

        return data

    def _script_breakdown_system_prompt(self) -> str:
        """Production-grade system prompt for script breakdown."""
        return """
You are a film scene decomposition engine designed to turn a script into structured
SCENES and SHOTS for a multi-shot video generation pipeline.
Return ONLY valid JSON. No text outside JSON.

--- OBJECTIVE ---
Given a narrative script, break it into:
1. SCENES: coherent locations/time blocks
2. SHOTS: the smallest cinematic units within each scene

--- RULES ---
• ALWAYS produce at least 1 scene.
• NEVER exceed max_scenes or max_shots_per_scene.
• Maintain chronological order.
• Use the characters provided (with names/roles/descriptions).
• Ensure shot descriptions are compact, visual, and generative-model-friendly.
• Every shot MUST specify:
    - description  
    - camera_type  ("close-up", "medium", "wide", "over-shoulder", "tracking", etc.)
    - motion       ("static", "pan-left", "pan-right", "dolly-in", "dolly-out")
    - duration_seconds
    - continuity_notes (optional)

--- SHOT DESCRIPTION REQUIREMENTS ---
• Describe composition, pose, action, environment.
• Avoid redundant exposition.
• DO NOT include camera jargon outside {camera_type, motion} fields.

--- CONTINUITY NOTES ---
For shots after the first:
• Reference direct carryover from previous shot (pose, direction, action).
• Example: "Naruto begins moving forward from last pose."

--- OUTPUT JSON FORMAT ---
{
  "scenes": [
    {
      "title": "string",
      "description": "string",
      "shots": [
        {
          "description": "string",
          "camera_type": "string",
          "motion": "string",
          "duration_seconds": number,
          "continuity_notes": "string or null"
        }
      ]
    }
  ]
}

Return ONLY valid JSON.
"""
