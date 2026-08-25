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

    def render(self, project: VideoProject, output_path: Path) -> RenderResult:
        """Render a validated project to a media artifact."""
        ...


class RendererNotConfigured(RuntimeError):
    pass


def render_project(project: VideoProject, output_path: Path) -> RenderResult:
    raise RendererNotConfigured(
        "No renderer is configured yet. R1 will select and implement the first renderer adapter."
    )
