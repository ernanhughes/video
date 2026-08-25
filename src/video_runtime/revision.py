from __future__ import annotations

import json
import shlex
import subprocess
from copy import deepcopy
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field, model_validator

from .models import Animation, Layer, Scene, VideoProject


class RevisionError(RuntimeError):
    pass


class PatchOperationKind(StrEnum):
    SET_SCENE_DURATION = "set_scene_duration"
    SET_SCENE_METADATA = "set_scene_metadata"
    SET_LAYER_TEXT = "set_layer_text"
    SET_LAYER_START = "set_layer_start"
    SET_LAYER_DURATION = "set_layer_duration"
    SET_LAYER_PROPERTY = "set_layer_property"
    REPLACE_LAYER_ANIMATIONS = "replace_layer_animations"


class PatchOperation(BaseModel):
    kind: PatchOperationKind
    layer_id: str | None = None
    key: str | None = None
    value: Any = None
    animations: list[Animation] | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "PatchOperation":
        layer_ops = {
            PatchOperationKind.SET_LAYER_TEXT,
            PatchOperationKind.SET_LAYER_START,
            PatchOperationKind.SET_LAYER_DURATION,
            PatchOperationKind.SET_LAYER_PROPERTY,
            PatchOperationKind.REPLACE_LAYER_ANIMATIONS,
        }
        if self.kind in layer_ops and not self.layer_id:
            raise ValueError(f"{self.kind.value} requires layer_id")
        if self.kind in {PatchOperationKind.SET_SCENE_METADATA, PatchOperationKind.SET_LAYER_PROPERTY} and not self.key:
            raise ValueError(f"{self.kind.value} requires key")
        if self.kind == PatchOperationKind.REPLACE_LAYER_ANIMATIONS and self.animations is None:
            raise ValueError("replace_layer_animations requires animations")
        return self


class RevisionPatch(BaseModel):
    schema_version: str = "0.1"
    scene_id: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    operations: list[PatchOperation] = Field(min_length=1)


class RevisionChange(BaseModel):
    path: str
    before: Any
    after: Any


class RevisionResult(BaseModel):
    project: VideoProject
    changes: list[RevisionChange]


class Reviser(Protocol):
    name: str

    def revise(self, project: VideoProject, scene_id: str, instruction: str) -> RevisionPatch:
        ...


class CommandReviser:
    """External model adapter that may emit only a bounded RevisionPatch."""

    name = "command"

    def __init__(self, command: str):
        self.command = command

    def revise(self, project: VideoProject, scene_id: str, instruction: str) -> RevisionPatch:
        scene = _find_scene(project, scene_id)
        request = {
            "task": "revise_video_scene",
            "scene_id": scene_id,
            "instruction": instruction,
            "scene": scene.model_dump(mode="json"),
            "project_context": {
                "title": project.title,
                "canvas": project.canvas.model_dump(mode="json"),
                "duration": project.duration,
                "scene_ids": [item.id for item in project.scenes],
            },
            "output_schema": RevisionPatch.model_json_schema(),
            "constraints": {
                "target_scene_only": True,
                "existing_layers_only": [layer.id for layer in scene.layers],
                "allowed_operations": [kind.value for kind in PatchOperationKind],
                "renderer_code_forbidden": True,
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
            raise RevisionError(f"could not start reviser command: {exc}") from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip() or f"exit code {completed.returncode}"
            raise RevisionError(f"reviser command failed: {detail}")
        try:
            patch = RevisionPatch.model_validate_json(completed.stdout)
        except Exception as exc:
            raise RevisionError(f"reviser returned invalid RevisionPatch JSON: {exc}") from exc
        if patch.scene_id != scene_id:
            raise RevisionError(
                f"reviser attempted to target scene {patch.scene_id!r}; bounded scene is {scene_id!r}"
            )
        return patch


def _find_scene(project: VideoProject, scene_id: str) -> Scene:
    for scene in project.scenes:
        if scene.id == scene_id:
            return scene
    raise RevisionError(f"scene not found: {scene_id}")


def _find_layer(scene: Scene, layer_id: str) -> Layer:
    for layer in scene.layers:
        if layer.id == layer_id:
            return layer
    raise RevisionError(f"layer {layer_id!r} is not in bounded scene {scene.id!r}")


def apply_revision(project: VideoProject, patch: RevisionPatch) -> RevisionResult:
    """Apply a patch that is structurally restricted to exactly one scene."""

    updated = deepcopy(project)
    scene = _find_scene(updated, patch.scene_id)
    changes: list[RevisionChange] = []

    def record(path: str, before: Any, after: Any) -> None:
        if before != after:
            changes.append(RevisionChange(path=path, before=before, after=after))

    for op in patch.operations:
        base = f"scenes.{scene.id}"
        if op.kind == PatchOperationKind.SET_SCENE_DURATION:
            before = scene.duration
            scene.duration = float(op.value)
            record(f"{base}.duration", before, scene.duration)
        elif op.kind == PatchOperationKind.SET_SCENE_METADATA:
            before = scene.metadata.get(op.key)
            scene.metadata[op.key] = op.value
            record(f"{base}.metadata.{op.key}", before, op.value)
        else:
            assert op.layer_id is not None
            layer = _find_layer(scene, op.layer_id)
            layer_base = f"{base}.layers.{layer.id}"
            if op.kind == PatchOperationKind.SET_LAYER_TEXT:
                before = layer.text
                layer.text = None if op.value is None else str(op.value)
                record(f"{layer_base}.text", before, layer.text)
            elif op.kind == PatchOperationKind.SET_LAYER_START:
                before = layer.start
                layer.start = float(op.value)
                record(f"{layer_base}.start", before, layer.start)
            elif op.kind == PatchOperationKind.SET_LAYER_DURATION:
                before = layer.duration
                layer.duration = float(op.value)
                record(f"{layer_base}.duration", before, layer.duration)
            elif op.kind == PatchOperationKind.SET_LAYER_PROPERTY:
                before = layer.properties.get(op.key)
                layer.properties[op.key] = op.value
                record(f"{layer_base}.properties.{op.key}", before, op.value)
            elif op.kind == PatchOperationKind.REPLACE_LAYER_ANIMATIONS:
                before = [item.model_dump(mode="json") for item in layer.animations]
                layer.animations = list(op.animations or [])
                after = [item.model_dump(mode="json") for item in layer.animations]
                record(f"{layer_base}.animations", before, after)
            else:  # pragma: no cover - enum exhaustiveness guard
                raise RevisionError(f"unsupported operation: {op.kind}")

    try:
        validated = VideoProject.model_validate(updated.model_dump(mode="json"))
    except Exception as exc:
        raise RevisionError(f"revision would produce invalid VideoProject: {exc}") from exc
    return RevisionResult(project=validated, changes=changes)
