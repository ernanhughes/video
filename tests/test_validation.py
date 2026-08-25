from video_runtime.models import Layer, LayerKind, Scene, VideoProject
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
