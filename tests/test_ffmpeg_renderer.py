from pathlib import Path

from video_runtime.ffmpeg_renderer import FFmpegRenderer
from video_runtime.models import (
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


def test_build_command_renders_text_and_shape() -> None:
    project = VideoProject(
        title="Demo",
        canvas=Canvas(width=1280, height=720, fps=30),
        scenes=[
            Scene(
                id="intro",
                duration=2.0,
                layers=[
                    Layer(id="box", kind=LayerKind.SHAPE, duration=2.0, properties={"x": 10, "y": 20, "width": 100, "height": 50}),
                    Layer(id="title", kind=LayerKind.TEXT, duration=2.0, text="Hello", properties={"x": 640, "y": 300, "align": "center"}),
                ],
            )
        ],
    )

    command = FFmpegRenderer().build_command(project, Path("demo.mp4"))
    graph = command[command.index("-filter_complex") + 1]

    assert "color=c=black:s=1280x720:r=30.0:d=2" in graph
    assert "drawbox=" in graph
    assert "drawtext=" in graph
    assert "640-text_w/2" in graph
    assert command[-1] == "demo.mp4"


def test_scene_offsets_are_local_and_cut_scenes_concat() -> None:
    project = VideoProject(
        title="Two scenes",
        scenes=[
            Scene(id="one", duration=2.0),
            Scene(id="two", duration=3.0, layers=[Layer(id="late-title", kind=LayerKind.TEXT, start=0.5, duration=1.0, text="Second scene")]),
        ],
    )

    command = FFmpegRenderer().build_command(project, Path("demo.mp4"))
    graph = command[command.index("-filter_complex") + 1]
    assert "between(t,0.5,1.5)" in graph
    assert "concat=n=2:v=1:a=0" in graph


def test_fade_transition_uses_xfade_and_overlap_offset() -> None:
    project = VideoProject(
        title="Fade",
        scenes=[
            Scene(
                id="one",
                duration=4.0,
                transition_out=Transition(kind=TransitionKind.FADE, duration=0.5),
            ),
            Scene(id="two", duration=3.0),
        ],
    )

    command = FFmpegRenderer().build_command(project, Path("demo.mp4"))
    graph = command[command.index("-filter_complex") + 1]

    assert "xfade=transition=fade:duration=0.5:offset=3.5" in graph
    assert "-t" in command
    assert command[command.index("-t") + 1] == "6.5"


def test_transition_fades_scene_audio_out_and_in() -> None:
    project = VideoProject(
        title="Audio fade",
        scenes=[
            Scene(
                id="one",
                duration=4.0,
                transition_out=Transition(kind=TransitionKind.FADE, duration=0.5),
                layers=[Layer(id="outgoing", kind=LayerKind.AUDIO, source="out.wav", duration=4.0)],
            ),
            Scene(
                id="two",
                duration=3.0,
                layers=[Layer(id="incoming", kind=LayerKind.AUDIO, source="in.wav", duration=3.0)],
            ),
        ],
    )

    command = FFmpegRenderer().build_command(project, Path("demo.mp4"))
    graph = command[command.index("-filter_complex") + 1]

    assert "afade=t=out:st=3.5:d=0.5" in graph
    assert "afade=t=in:st=0:d=0.5" in graph
    assert "adelay=3500|3500" in graph


def test_media_inputs_generate_overlay_audio_and_trim_graph() -> None:
    project = VideoProject(
        title="Media",
        canvas=Canvas(width=1280, height=720, fps=30),
        scenes=[
            Scene(
                id="main",
                duration=5.0,
                layers=[
                    Layer(
                        id="photo",
                        kind=LayerKind.IMAGE,
                        source="assets/photo.png",
                        start=0.0,
                        duration=5.0,
                        fit=MediaFit.COVER,
                    ),
                    Layer(
                        id="clip",
                        kind=LayerKind.VIDEO,
                        source="assets/clip.mp4",
                        source_start=2.0,
                        start=1.0,
                        duration=3.0,
                        properties={"x": 100, "y": 80, "width": 640, "height": 360},
                    ),
                    Layer(
                        id="music",
                        kind=LayerKind.AUDIO,
                        source="assets/music.wav",
                        start=0.5,
                        duration=4.0,
                        volume=0.5,
                    ),
                ],
            )
        ],
    )

    command = FFmpegRenderer().build_command(project, Path("demo.mp4"), source_root=Path("project"))
    graph = command[command.index("-filter_complex") + 1]
    joined = " ".join(command)

    assert "project/assets/photo.png" in joined
    assert "project/assets/clip.mp4" in joined
    assert "project/assets/music.wav" in joined
    assert "force_original_aspect_ratio=increase" in graph
    assert "trim=start=2:duration=3" in graph
    assert "overlay=x='100':y='80'" in graph
    assert "volume=0.5" in graph
    assert "adelay=500|500" in graph
    assert "amix=inputs=1" in graph
    assert "[aout]" in command


def test_media_transforms_compile_to_ffmpeg_filters() -> None:
    project = VideoProject(
        title="Transforms",
        scenes=[
            Scene(
                id="main",
                duration=3.0,
                layers=[
                    Layer(
                        id="photo",
                        kind=LayerKind.IMAGE,
                        source="photo.png",
                        duration=3.0,
                        animations=[
                            Animation(property=AnimationProperty.SCALE, from_value=0.8, to_value=1.0, duration=1.0, easing=Easing.EASE_OUT),
                            Animation(property=AnimationProperty.ROTATION, from_value=-5, to_value=0, duration=1.0, easing=Easing.EASE_IN_OUT),
                            Animation(property=AnimationProperty.OPACITY, from_value=0, to_value=1, duration=0.5, easing=Easing.EASE_IN),
                        ],
                    )
                ],
            )
        ],
    )

    command = FFmpegRenderer().build_command(project, Path("demo.mp4"))
    graph = command[command.index("-filter_complex") + 1]

    assert "scale=w='iw*(" in graph
    assert ":eval=frame" in graph
    assert "rotate=angle='(" in graph
    assert "*PI/180'" in graph
    assert "colorchannelmixer=aa='" in graph
    assert "1-(1-(" in graph
    assert "*(3-2*(" in graph


def test_eased_position_animation_compiles_expression() -> None:
    project = VideoProject(
        title="Ease",
        scenes=[
            Scene(
                id="main",
                duration=2.0,
                layers=[
                    Layer(
                        id="title",
                        kind=LayerKind.TEXT,
                        text="Hello",
                        duration=2.0,
                        animations=[
                            Animation(
                                property=AnimationProperty.X,
                                from_value=100,
                                to_value=500,
                                duration=1.0,
                                easing=Easing.EASE_IN_OUT,
                            )
                        ],
                    )
                ],
            )
        ],
    )

    command = FFmpegRenderer().build_command(project, Path("demo.mp4"))
    graph = command[command.index("-filter_complex") + 1]
    assert "(t-0)/1" in graph
    assert "(3-2*((t-0)/1))" in graph


def test_looping_media_uses_stream_loop() -> None:
    project = VideoProject(
        title="Loop",
        scenes=[Scene(id="main", duration=4.0, layers=[Layer(id="clip", kind=LayerKind.VIDEO, source="clip.mp4", duration=4.0, loop=True)])],
    )
    command = FFmpegRenderer().build_command(project, Path("demo.mp4"))
    assert "-stream_loop" in command
    assert command[command.index("-stream_loop") + 1] == "-1"


def test_filter_text_is_escaped() -> None:
    escaped = FFmpegRenderer._escape_filter_text("It's 10%: ready")
    assert escaped == "It\\'s 10\\%\\: ready"
