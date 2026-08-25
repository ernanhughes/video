from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel

from .rendering import RenderError


class MediaInfo(BaseModel):
    path: Path
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    has_video: bool = False
    has_audio: bool = False


def probe_media(path: Path) -> MediaInfo:
    executable = shutil.which("ffprobe")
    if executable is None:
        raise RenderError("ffprobe was not found on PATH")

    completed = subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RenderError(f"ffprobe failed for {path}: {completed.stderr.strip()}")

    payload = json.loads(completed.stdout or "{}")
    streams = payload.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    raw_duration = payload.get("format", {}).get("duration")

    return MediaInfo(
        path=path,
        duration=float(raw_duration) if raw_duration is not None else None,
        width=video_stream.get("width") if video_stream else None,
        height=video_stream.get("height") if video_stream else None,
        has_video=video_stream is not None,
        has_audio=audio_stream is not None,
    )
