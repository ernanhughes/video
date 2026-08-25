from pathlib import Path

from video_runtime.models import (
    Animation,
    AnimationProperty,
    Layer,
    LayerKind,
    Scene,
    Transition,
    TransitionKind,
    VideoProject,
)
from video_runtime.validation import validate_project


def test_valid_project_passes() -> None:
    project = VideoProject(
        title="Demo",
        scenes=[
            Scene(
                id="scene-01",
                duration=3.0,
                layers=[Layer(id="title", kind=LayerKind.TEXT, text="Hello", duration=2.0)],
            )
        ],
    )

    assert validate_project(project).ok


def test_layer_must_fit_inside_scene() -> None:
    project = VideoProject(
        title="Demo",
        scenes=[
            Scene(
                id="scene-01",
                duration=2.0,
                layers=[Layer(id="title", kind=LayerKind.TEXT, text="Hello", start=1.0, duration=2.0)],
            )
        ],
    )

    report = validate_project(project)
    assert not report.ok
    assert report.issues[0].code == "layer_outside_scene"


def test_layer_ids_are_project_unique() -> None:
    project = VideoProject(
        title="Demo",
        scenes=[
            Scene(id="a", duration=1.0, layers=[Layer(id="shared", kind=LayerKind.TEXT, text="A", duration=1.0)]),
            Scene(id="b", duration=1.0, layers=[Layer(id="shared", kind=LayerKind.TEXT, text="B", duration=1.0)]),
        ],
    )

    report = validate_project(project)
    assert any(issue.code == "duplicate_layer_id" for issue in report.issues)


def test_animation_must_fit_inside_layer() -> None:
    project = VideoProject(
        title="Demo",
        scenes=[
            Scene(
                id="scene-01",
                duration=3.0,
                layers=[
                    Layer(
                        id="title",
                        kind=LayerKind.TEXT,
                        text="Hello",
                        duration=2.0,
                        animations=[
                            Animation(
                                property=AnimationProperty.X,
                                from_value=0,
                                to_value=100,
                                start=1.5,
                                duration=1.0,
                            )
                        ],
                    )
                ],
            )
        ],
    )

    report = validate_project(project)
    assert any(issue.code == "animation_outside_layer" for issue in report.issues)


def test_final_scene_cannot_have_transition() -> None:
    project = VideoProject(
        title="Demo",
        scenes=[
            Scene(
                id="scene-01",
                duration=3.0,
                transition_out=Transition(kind=TransitionKind.FADE, duration=0.5),
            )
        ],
    )

    report = validate_project(project)
    assert any(issue.code == "terminal_transition" for issue in report.issues)


def test_missing_media_asset_is_reported_relative_to_project(tmp_path: Path) -> None:
    project = VideoProject(
        title="Demo",
        scenes=[
            Scene(
                id="scene-01",
                duration=2.0,
                layers=[
                    Layer(
                        id="image",
                        kind=LayerKind.IMAGE,
                        source="assets/missing.png",
                        duration=2.0,
                    )
                ],
            )
        ],
    )

    report = validate_project(project, project_path=tmp_path / "project.json")
    assert any(issue.code == "missing_asset" for issue in report.issues)
