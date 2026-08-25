from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class LayerKind(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    SHAPE = "shape"
    AUDIO = "audio"
    CHART = "chart"
    SIMULATION = "simulation"
    GENERATED = "generated"


class Canvas(BaseModel):
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)
    fps: float = Field(default=30.0, gt=0, le=240)


class Layer(BaseModel):
    id: str = Field(min_length=1)
    kind: LayerKind
    start: float = Field(default=0.0, ge=0)
    duration: float = Field(gt=0)
    source: str | None = None
    text: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_content(self) -> "Layer":
        if self.kind == LayerKind.TEXT and not self.text:
            raise ValueError("text layers require text")
        if self.kind in {LayerKind.IMAGE, LayerKind.VIDEO, LayerKind.AUDIO} and not self.source:
            raise ValueError(f"{self.kind.value} layers require source")
        return self


class Scene(BaseModel):
    id: str = Field(min_length=1)
    duration: float = Field(gt=0)
    layers: list[Layer] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VideoProject(BaseModel):
    schema_version: str = "0.1"
    title: str = Field(min_length=1)
    canvas: Canvas = Field(default_factory=Canvas)
    scenes: list[Scene] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def duration(self) -> float:
        return sum(scene.duration for scene in self.scenes)
