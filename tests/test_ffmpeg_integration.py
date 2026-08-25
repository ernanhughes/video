from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from video_runtime.ffmpeg_renderer import FFmpegRenderer
from video_runtime.models import (
    Animation,
    AnimationProperty,
    Easing,
    Layer,
    LayerKind,
    Scene,
    Transition,
    TransitionKind,
    VideoProject,
)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_ffmpeg_executes_media_transforms_and_scene_fade(tmp_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg is not None

    asset = tmp_path / "asset.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x90:r=24:d=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(asset),
        ],
        check=True,
        capture_output=True,
    )

    project = VideoProject(
        title="Executable smoke test",
        scenes=[
            Scene(
                id="one",
                duration=1.2,
                transition_out=Transition(kind=TransitionKind.FADE, duration=0.2),
                layers=[
                    Layer(
                        id="clip",
                        kind=LayerKind.VIDEO,
                        source=asset.name,
                        duration=1.2,
                        properties={"width": 320, "height": 180, "x": 50, "y": 50},
                        animations=[
                            Animation(
                                property=AnimationProperty.SCALE,
                                from_value=0.9,
                                to_value=1.0,
                                duration=0.5,
                                easing=Easing.EASE_OUT,
                            ),
                            Animation(
                                property=AnimationProperty.ROTATION,
                                from_value=-2,
                                to_value=0,
                                duration=0.5,
                                easing=Easing.EASE_IN_OUT,
                            ),
                            Animation(
                                property=AnimationProperty.OPACITY,
                                from_value=0.25,
                                to_value=1.0,
                                duration=0.4,
                                easing=Easing.EASE_IN,
                            ),
                        ],
                    )
                ],
            ),
            Scene(
                id="two",
                duration=1.0,
                layers=[Layer(id="title", kind=LayerKind.TEXT, text="Done", duration=1.0)],
            ),
        ],
    )

    output = tmp_path / "output.mp4"
    result = FFmpegRenderer().render(project, output, source_root=tmp_path)

    assert result.output_path == output
    assert output.exists()
    assert output.stat().st_size > 0
