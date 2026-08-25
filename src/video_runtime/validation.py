from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from .models import LayerKind, VideoProject


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


def validate_project(project: VideoProject, *, project_path: Path | None = None) -> ValidationReport:
    issues: list[ValidationIssue] = []

    scene_ids: set[str] = set()
    layer_ids: set[str] = set()

    for scene_index, scene in enumerate(project.scenes):
        scene_path = f"scenes[{scene_index}]"

        if scene.id in scene_ids:
            issues.append(
                ValidationIssue(
                    code="duplicate_scene_id",
                    message=f"duplicate scene id: {scene.id}",
                    path=f"{scene_path}.id",
                )
            )
        scene_ids.add(scene.id)

        if scene_index == len(project.scenes) - 1 and scene.transition_out.duration:
            issues.append(
                ValidationIssue(
                    code="terminal_transition",
                    message="the final scene cannot transition to another scene",
                    path=f"{scene_path}.transition_out",
                )
            )
        if scene.transition_out.duration >= scene.duration:
            issues.append(
                ValidationIssue(
                    code="transition_too_long",
                    message="transition duration must be shorter than its scene",
                    path=f"{scene_path}.transition_out.duration",
                )
            )

        for layer_index, layer in enumerate(scene.layers):
            layer_path = f"{scene_path}.layers[{layer_index}]"

            if layer.id in layer_ids:
                issues.append(
                    ValidationIssue(
                        code="duplicate_layer_id",
                        message=f"duplicate layer id: {layer.id}",
                        path=f"{layer_path}.id",
                    )
                )
            layer_ids.add(layer.id)

            if layer.start + layer.duration > scene.duration:
                issues.append(
                    ValidationIssue(
                        code="layer_outside_scene",
                        message=(
                            f"layer {layer.id} ends at {layer.start + layer.duration:.3f}s "
                            f"but scene {scene.id} ends at {scene.duration:.3f}s"
                        ),
                        path=layer_path,
                    )
                )

            for animation_index, animation in enumerate(layer.animations):
                if animation.start + animation.duration > layer.duration:
                    issues.append(
                        ValidationIssue(
                            code="animation_outside_layer",
                            message=(
                                f"animation ends at {animation.start + animation.duration:.3f}s "
                                f"but layer {layer.id} lasts {layer.duration:.3f}s"
                            ),
                            path=f"{layer_path}.animations[{animation_index}]",
                        )
                    )

            if project_path and layer.kind in {LayerKind.IMAGE, LayerKind.VIDEO, LayerKind.AUDIO}:
                source = Path(layer.source or "")
                resolved = source if source.is_absolute() else project_path.parent / source
                if not resolved.exists():
                    issues.append(
                        ValidationIssue(
                            code="missing_asset",
                            message=f"asset does not exist: {layer.source}",
                            path=f"{layer_path}.source",
                        )
                    )

    if not project.scenes:
        issues.append(
            ValidationIssue(
                code="empty_project",
                message="project contains no scenes",
                path="scenes",
                severity="warning",
            )
        )

    return ValidationReport(issues=issues)
