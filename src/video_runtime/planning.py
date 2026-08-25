from __future__ import annotations

import json
import shlex
import subprocess
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field, model_validator

from .models import (
    Animation,
    AnimationProperty,
    Canvas,
    Easing,
    Layer,
    LayerKind,
    MediaFit,
    Scene,
    Transition,
    TransitionKind,
    VideoProject,
)


class PlannerError(RuntimeError):
    pass


class PlannedLayer(BaseModel):
    id: str = Field(min_length=1)
    kind: LayerKind
    start: float = Field(default=0.0, ge=0)
    duration: float = Field(gt=0)
    text: str | None = None
    source: str | None = None
    source_start: float = Field(default=0.0, ge=0)
    loop: bool = False
    fit: MediaFit = MediaFit.CONTAIN
    volume: float = Field(default=1.0, ge=0, le=4)
    properties: dict[str, Any] = Field(default_factory=dict)
    animations: list[Animation] = Field(default_factory=list)


class PlannedScene(BaseModel):
    id: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    duration: float = Field(gt=0)
    layers: list[PlannedLayer] = Field(default_factory=list)
    transition_out: Transition = Field(default_factory=Transition)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VideoPlan(BaseModel):
    schema_version: str = "0.1"
    title: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    canvas: Canvas = Field(default_factory=Canvas)
    scenes: list[PlannedScene] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ids(self) -> "VideoPlan":
        scene_ids = [scene.id for scene in self.scenes]
        if len(scene_ids) != len(set(scene_ids)):
            raise ValueError("planned scene ids must be unique")
        layer_ids = [layer.id for scene in self.scenes for layer in scene.layers]
        if len(layer_ids) != len(set(layer_ids)):
            raise ValueError("planned layer ids must be project-unique")
        return self


class Planner(Protocol):
    name: str

    def plan(self, intent: str) -> VideoPlan:
        ...


class TemplatePlanner:
    """Deterministic bootstrap planner used when no model backend is configured.

    It intentionally creates a small text/shape-only project. It is a fallback and
    test fixture, not a substitute for an AI planner.
    """

    name = "template"

    def plan(self, intent: str) -> VideoPlan:
        title = intent.strip().rstrip(".")[:80] or "Untitled video"
        scenes = [
            PlannedScene(
                id="hook",
                purpose="Introduce the topic quickly.",
                duration=3.5,
                layers=[
                    PlannedLayer(
                        id="hook-title",
                        kind=LayerKind.TEXT,
                        duration=3.5,
                        text=title,
                        properties={"x": 960, "y": 470, "align": "center", "font_size": 64, "color": "white"},
                        animations=[Animation(property=AnimationProperty.Y, from_value=560, to_value=470, duration=0.8, easing=Easing.EASE_OUT)],
                    )
                ],
                transition_out=Transition(kind=TransitionKind.FADE, duration=0.5),
                metadata={"background": "0x0b1020"},
            ),
            PlannedScene(
                id="explain",
                purpose="State the central explanatory idea.",
                duration=5.0,
                layers=[
                    PlannedLayer(
                        id="explain-accent",
                        kind=LayerKind.SHAPE,
                        duration=5.0,
                        properties={"x": 300, "y": 700, "width": 1320, "height": 6, "color": "0x3a86ff"},
                    ),
                    PlannedLayer(
                        id="explain-text",
                        kind=LayerKind.TEXT,
                        start=0.4,
                        duration=4.2,
                        text="Build the explanation from editable scenes and layers.",
                        properties={"x": 960, "y": 500, "align": "center", "font_size": 48, "color": "white"},
                        animations=[Animation(property=AnimationProperty.X, from_value=1200, to_value=960, duration=0.9, easing=Easing.EASE_OUT)],
                    ),
                ],
                transition_out=Transition(kind=TransitionKind.FADE, duration=0.5),
                metadata={"background": "0x111827"},
            ),
            PlannedScene(
                id="close",
                purpose="Close with a concise takeaway.",
                duration=3.5,
                layers=[
                    PlannedLayer(
                        id="close-title",
                        kind=LayerKind.TEXT,
                        duration=3.5,
                        text="The source stays editable.",
                        properties={"x": 960, "y": 500, "align": "center", "font_size": 56, "color": "white"},
                    )
                ],
                metadata={"background": "0x050816"},
            ),
        ]
        return VideoPlan(title=title, intent=intent, scenes=scenes, metadata={"planner": self.name})


class CommandPlanner:
    """Planner adapter for an external model command.

    The command receives a JSON request on stdin and must emit one VideoPlan JSON
    object on stdout. This keeps model/provider dependencies outside the runtime.
    """

    name = "command"

    def __init__(self, command: str):
        self.command = command

    def plan(self, intent: str) -> VideoPlan:
        request = {
            "task": "plan_video",
            "intent": intent,
            "output_schema": VideoPlan.model_json_schema(),
            "constraints": {
                "canonical_ir_only": True,
                "renderer_code_forbidden": True,
                "layer_kinds": [kind.value for kind in LayerKind],
                "animation_properties": [prop.value for prop in AnimationProperty],
                "easing": [value.value for value in Easing],
                "transition_kinds": [kind.value for kind in TransitionKind],
            },
        }
        try:
            completed = subprocess.run(
                shlex.split(self.command),
                input=json.dumps(request),
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise PlannerError(f"could not start planner command: {exc}") from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip() or f"exit code {completed.returncode}"
            raise PlannerError(f"planner command failed: {detail}")
        try:
            return VideoPlan.model_validate_json(completed.stdout)
        except Exception as exc:
            raise PlannerError(f"planner returned invalid VideoPlan JSON: {exc}") from exc


def project_from_plan(plan: VideoPlan) -> VideoProject:
    return VideoProject(
        title=plan.title,
        canvas=plan.canvas,
        scenes=[
            Scene(
                id=scene.id,
                duration=scene.duration,
                transition_out=scene.transition_out,
                metadata={**scene.metadata, "purpose": scene.purpose},
                layers=[
                    Layer(
                        id=layer.id,
                        kind=layer.kind,
                        start=layer.start,
                        duration=layer.duration,
                        source=layer.source,
                        source_start=layer.source_start,
                        loop=layer.loop,
                        fit=layer.fit,
                        volume=layer.volume,
                        text=layer.text,
                        properties=layer.properties,
                        animations=layer.animations,
                    )
                    for layer in scene.layers
                ],
            )
            for scene in plan.scenes
        ],
        metadata={**plan.metadata, "intent": plan.intent, "plan_schema_version": plan.schema_version},
    )


def save_plan(plan: VideoPlan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
