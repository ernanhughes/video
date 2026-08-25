from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from video_runtime.ffmpeg_renderer import FFmpegRenderer
from video_runtime.project_io import load_project
from video_runtime.validation import validate_project


REPO_ROOT = Path(__file__).resolve().parents[1]
SHOWCASE_ROOT = REPO_ROOT / "examples" / "showcase"
PROJECT_PATH = SHOWCASE_ROOT / "video.json"


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg/ffprobe required")
def test_showcase_generates_validates_and_renders(tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, str(SHOWCASE_ROOT / "generate_assets.py")],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    project = load_project(PROJECT_PATH)
    report = validate_project(project, project_path=PROJECT_PATH)
    assert report.ok, report.issues
    assert len(project.scenes) == 4
    assert project.duration == pytest.approx(15.7)

    output = tmp_path / "showcase.mp4"
    result = FFmpegRenderer().render(
        project,
        output,
        source_root=SHOWCASE_ROOT,
    )

    assert result.output_path == output
    assert result.duration == pytest.approx(15.7)
    assert output.exists()
    assert output.stat().st_size > 0
