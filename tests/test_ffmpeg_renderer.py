from pathlib import Path

from video_runtime.ffmpeg_renderer import FFmpegRenderer
from video_runtime.models import (
    Animation,
    AnimationProperty,
    Canvas,
    Layer,
    LayerKind,
    Scene,
    Transition,
    TransitionKind,
    VideoProject,
)


def test_build_command_renders_text_and_shape() -> None:
    project = VideoProject(
        title="Demo",
        canvas=Canvas(width=1280, height=720, fps=30),
        scenes=[
            Scene(
                id="intro",
                duration=2.0,
                layers=[
                    Layer(
                        id="box",
                        kind=LayerKind.SHAPE,
                        duration=2.0,
                        properties={"x": 10, "y": 20, "width": 100, "height": 50},
                    ),
                    Layer(
                        id="title",
                        kind=LayerKind.TEXT,
                        duration=2.0,
                        text="Hello",
                        properties={"x": 640, "y": 300, "align": "center"},
                    ),
                ],
            )
        ],
    )

    command = FFmpegRenderer().build_command(project, Path("demo.mp4"))
    joined = " ".join(command)

    assert "color=c=black:s=1280x720:r=30.0:d=2.0" in joined
    assert "drawbox=" in joined
    assert "drawtext=" in joined
    assert "640-text_w/2" in joined
    assert command[-1] == "demo.mp4"


def test_scene_offsets_are_globalized() -> None:
    project = VideoProject(
        title="Two scenes",
        scenes=[
            Scene(id="one", duration=2.0),
            Scene(
                id="two",
                duration=3.0,
                layers=[
                    Layer(
                        id="late-title",
                        kind=LayerKind.TEXT,
                        start=0.5,
                        duration=1.0,
                        text="Second scene",
                    )
                ],
            ),
        ],
    )

    command = FFmpegRenderer().build_command(project, Path("demo.mp4"))
    filter_graph = command[command.index("-vf") + 1]

    assert "between(t,2.5,3.5)" in filter_graph


def test_transition_duration_overlaps_scene_timelines() -> None:
    project = VideoProject(
        title="Transition",
        scenes=[
            Scene(
                id="one",
                duration=3.0,
                transition_out=Transition(kind=TransitionKind.FADE, duration=0.5),
            ),
            Scene(
                id="two",
                duration=2.0,
                layers=[
                    Layer(
                        id="title",
                        kind=LayerKind.TEXT,
                        duration=1.0,
                        text="Overlap",
                    )
                ],
            ),
        ],
    )

    command = FFmpegRenderer().build_command(project, Path("demo.mp4"))
    filter_graph = command[command.index("-vf") + 1]

    assert project.duration == 4.5
    assert "between(t,2.5,3.5)" in filter_graph


def test_linear_position_animation_compiles_to_expression() -> None:
    project = VideoProject(
        title="Motion",
        scenes=[
            Scene(
                id="one",
                duration=3.0,
                layers=[
                    Layer(
                        id="title",
                        kind=LayerKind.TEXT,
                        duration=3.0,
                        text="Move",
                        properties={"x": 100, "y": 200},
                        animations=[
                            Animation(
                                property=AnimationProperty.X,
                                from_value=100,
                                to_value=500,
                                start=0.5,
                                duration=1.0,
                            )
                        ],
                    )
                ],
            )
        ],
    )

    command = FFmpegRenderer().build_command(project, Path("demo.mp4"))
    filter_graph = command[command.index("-vf") + 1]

    assert "if(lt(t,0.5),100" in filter_graph
    assert "100+(400)*(t-0.5)/1" in filter_graph
    assert "if(gt(t,1.5),500" in filter_graph


def test_filter_text_is_escaped() -> None:
    escaped = FFmpegRenderer._escape_filter_text("It's 10%: ready")

    assert escaped == "It\\'s 10\\%\\: ready"
