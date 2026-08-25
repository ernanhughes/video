from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from .models import VideoProject


class RenderResult(BaseModel):
    output_path: Path
    renderer: str
    duration: float


class Renderer(Protocol):
    name: str

    def render(
        self,
        project: VideoProject,
        output_path: Path,
        *,
        source_root: Path = Path("."),
    ) -> RenderResult:
        """Render a validated project to a media artifact."""
        ...


class RenderError(RuntimeError):
    pass


class UnknownRenderer(RenderError):
    pass


def get_renderer(name: str = "ffmpeg") -> Renderer:
    if name == "ffmpeg":
        from .ffmpeg_renderer import FFmpegRenderer

        return FFmpegRenderer()
    if name == "remotion":
        from .remotion_renderer import RemotionRenderer

        return RemotionRenderer()
    raise UnknownRenderer(f"unknown renderer: {name}")


def render_project(
    project: VideoProject,
    output_path: Path,
    *,
    renderer: str = "ffmpeg",
    source_root: Path = Path("."),
) -> RenderResult:
    return get_renderer(renderer).render(project, output_path, source_root=source_root)
