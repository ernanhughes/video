from video_runtime.models import LayerKind
from video_runtime.planning import TemplatePlanner, VideoPlan, project_from_plan
from video_runtime.revision import (
    PatchOperation,
    PatchOperationKind,
    RevisionError,
    RevisionPatch,
    apply_revision,
)


def test_template_planner_produces_canonical_project() -> None:
    plan = TemplatePlanner().plan("Explain gradient descent in 30 seconds")
    project = project_from_plan(plan)

    assert isinstance(plan, VideoPlan)
    assert project.title.startswith("Explain gradient descent")
    assert len(project.scenes) == 3
    assert project.scenes[0].layers[0].kind == LayerKind.TEXT
    assert project.metadata["intent"] == "Explain gradient descent in 30 seconds"
    assert project.duration > 0


def test_revision_changes_only_requested_scene() -> None:
    project = project_from_plan(TemplatePlanner().plan("Explain gradient descent"))
    before_explain = project.scenes[1].model_dump(mode="json")
    before_close = project.scenes[2].model_dump(mode="json")

    patch = RevisionPatch(
        scene_id="hook",
        instruction="Make the title lower and more concise",
        operations=[
            PatchOperation(kind=PatchOperationKind.SET_LAYER_TEXT, layer_id="hook-title", value="Gradient descent follows the slope."),
            PatchOperation(kind=PatchOperationKind.SET_LAYER_PROPERTY, layer_id="hook-title", key="y", value=520),
        ],
    )
    result = apply_revision(project, patch)

    assert result.project.scenes[0].layers[0].text == "Gradient descent follows the slope."
    assert result.project.scenes[0].layers[0].properties["y"] == 520
    assert result.project.scenes[1].model_dump(mode="json") == before_explain
    assert result.project.scenes[2].model_dump(mode="json") == before_close
    assert {change.path for change in result.changes} == {
        "scenes.hook.layers.hook-title.text",
        "scenes.hook.layers.hook-title.properties.y",
    }


def test_revision_rejects_layer_outside_bounded_scene() -> None:
    project = project_from_plan(TemplatePlanner().plan("Explain gradient descent"))
    patch = RevisionPatch(
        scene_id="hook",
        instruction="Edit another scene by mistake",
        operations=[
            PatchOperation(kind=PatchOperationKind.SET_LAYER_TEXT, layer_id="close-title", value="Nope"),
        ],
    )

    try:
        apply_revision(project, patch)
    except RevisionError as exc:
        assert "bounded scene" in str(exc)
    else:
        raise AssertionError("expected bounded revision failure")


def test_revision_revalidates_project_after_patch() -> None:
    project = project_from_plan(TemplatePlanner().plan("Explain gradient descent"))
    patch = RevisionPatch(
        scene_id="hook",
        instruction="Break duration",
        operations=[
            PatchOperation(kind=PatchOperationKind.SET_LAYER_DURATION, layer_id="hook-title", value=-1),
        ],
    )

    try:
        apply_revision(project, patch)
    except RevisionError as exc:
        assert "invalid VideoProject" in str(exc)
    else:
        raise AssertionError("expected model revalidation failure")
