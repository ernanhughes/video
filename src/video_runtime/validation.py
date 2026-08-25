from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from .media_probe import probe_media
from .models import LayerKind, VideoProject
from .rendering import RenderError


class ValidationIssue(BaseModel):
    code: str
    message: str
    path: str
    severity: str = "error"


class ValidationReport(BaseModel):
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


def validate_project(
    project: VideoProject,
    *,
    project_path: Path | None = None,
    probe_assets: bool = False,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    scene_ids: set[str] = set()
    layer_ids: set[str] = set()

    for scene_index, scene in enumerate(project.scenes):
        scene_path = f"scenes[{scene_index}]"

        if scene.id in scene_ids:
            issues.append(ValidationIssue(code="duplicate_scene_id", message=f"duplicate scene id: {scene.id}", path=f"{scene_path}.id"))
        scene_ids.add(scene.id)

        if scene_index == len(project.scenes) - 1 and scene.transition_out.duration:
            issues.append(ValidationIssue(code="terminal_transition", message="the final scene cannot transition to another scene", path=f"{scene_path}.transition_out"))
        if scene.transition_out.duration >= scene.duration:
            issues.append(ValidationIssue(code="transition_too_long", message="transition duration must be shorter than its scene", path=f"{scene_path}.transition_out.duration"))

        for layer_index, layer in enumerate(scene.layers):
            layer_path = f"{scene_path}.layers[{layer_index}]"

            if layer.id in layer_ids:
                issues.append(ValidationIssue(code="duplicate_layer_id", message=f"duplicate layer id: {layer.id}", path=f"{layer_path}.id"))
            layer_ids.add(layer.id)

            if layer.start + layer.duration > scene.duration:
                issues.append(
                    ValidationIssue(
                        code="layer_outside_scene",
                        message=f"layer {layer.id} ends at {layer.start + layer.duration:.3f}s but scene {scene.id} ends at {scene.duration:.3f}s",
                        path=layer_path,
                    )
                )

            for animation_index, animation in enumerate(layer.animations):
                if animation.start + animation.duration > layer.duration:
                    issues.append(
                        ValidationIssue(
                            code="animation_outside_layer",
                            message=f"animation ends at {animation.start + animation.duration:.3f}s but layer {layer.id} lasts {layer.duration:.3f}s",
                            path=f"{layer_path}.animations[{animation_index}]",
                        )
                    )

            if project_path and layer.kind in {LayerKind.IMAGE, LayerKind.VIDEO, LayerKind.AUDIO}:
                source = Path(layer.source or "")
                resolved = source if source.is_absolute() else project_path.parent / source
                if not resolved.exists():
                    issues.append(ValidationIssue(code="missing_asset", message=f"asset does not exist: {layer.source}", path=f"{layer_path}.source"))
                    continue

                if probe_assets:
                    try:
                        info = probe_media(resolved)
                    except RenderError as exc:
                        issues.append(ValidationIssue(code="media_probe_failed", message=str(exc), path=f"{layer_path}.source"))
                        continue

                    if layer.kind in {LayerKind.IMAGE, LayerKind.VIDEO} and not info.has_video:
                        issues.append(ValidationIssue(code="missing_video_stream", message=f"asset has no video/image stream: {layer.source}", path=f"{layer_path}.source"))
                    if layer.kind == LayerKind.AUDIO and not info.has_audio:
                        issues.append(ValidationIssue(code="missing_audio_stream", message=f"asset has no audio stream: {layer.source}", path=f"{layer_path}.source"))
                    if (
                        layer.kind in {LayerKind.VIDEO, LayerKind.AUDIO}
                        and not layer.loop
                        and info.duration is not None
                        and layer.source_start + layer.duration > info.duration + 0.001
                    ):
                        issues.append(
                            ValidationIssue(
                                code="media_too_short",
                                message=(
                                    f"layer needs {layer.source_start + layer.duration:.3f}s of source "
                                    f"but asset duration is {info.duration:.3f}s; enable loop or shorten the layer"
                                ),
                                path=layer_path,
                            )
                        )

    if not project.scenes:
        issues.append(ValidationIssue(code="empty_project", message="project contains no scenes", path="scenes", severity="warning"))

    return ValidationReport(issues=issues)
