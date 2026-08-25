from __future__ import annotations

from pydantic import BaseModel, Field

from .models import VideoProject


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


def validate_project(project: VideoProject) -> ValidationReport:
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
