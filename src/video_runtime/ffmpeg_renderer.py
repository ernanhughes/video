from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .models import Layer, LayerKind, VideoProject
from .rendering import RenderError, RenderResult


class FFmpegRenderer:
    """Deterministic R1 renderer for the first useful Video IR subset.

    R1a intentionally supports only text and shape layers. Image, video,
    audio, chart, simulation, and generated layers stay in the IR but are
    rejected here until their renderer semantics are designed deliberately.
    """

    name = "ffmpeg"
    supported_kinds = {LayerKind.TEXT, LayerKind.SHAPE}

    def render(self, project: VideoProject, output_path: Path) -> RenderResult:
        executable = shutil.which("ffmpeg")
        if executable is None:
            raise RenderError("ffmpeg was not found on PATH")

        unsupported = [
            layer
            for scene in project.scenes
            for layer in scene.layers
            if layer.kind not in self.supported_kinds
        ]
        if unsupported:
            details = ", ".join(f"{layer.id}:{layer.kind.value}" for layer in unsupported)
            raise RenderError(f"ffmpeg R1 renderer does not yet support: {details}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = self.build_command(project, output_path, executable=executable)
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            diagnostic = completed.stderr.strip().splitlines()
            tail = "\n".join(diagnostic[-12:])
            raise RenderError(f"ffmpeg render failed ({completed.returncode})\n{tail}")

        return RenderResult(
            output_path=output_path,
            renderer=self.name,
            duration=project.duration,
        )

    def build_command(
        self,
        project: VideoProject,
        output_path: Path,
        *,
        executable: str = "ffmpeg",
    ) -> list[str]:
        canvas = project.canvas
        background = str(project.metadata.get("background", "black"))
        source = (
            f"color=c={background}:s={canvas.width}x{canvas.height}:"
            f"r={canvas.fps}:d={project.duration}"
        )

        filters: list[str] = []
        scene_offset = 0.0
        for scene in project.scenes:
            for layer in scene.layers:
                start = scene_offset + layer.start
                end = start + layer.duration
                if layer.kind == LayerKind.TEXT:
                    filters.append(self._text_filter(layer, start, end))
                elif layer.kind == LayerKind.SHAPE:
                    filters.append(self._shape_filter(layer, start, end))
            scene_offset += scene.duration

        command = [
            executable,
            "-y",
            "-f",
            "lavfi",
            "-i",
            source,
        ]
        if filters:
            command.extend(["-vf", ",".join(filters)])
        command.extend(
            [
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )
        return command

    def _text_filter(self, layer: Layer, start: float, end: float) -> str:
        props = layer.properties
        text = self._escape_filter_text(layer.text or "")
        fontsize = int(props.get("font_size", 64))
        color = str(props.get("color", "white"))
        x = props.get("x", "center")
        y = props.get("y", "center")
        align = str(props.get("align", "left"))

        if x == "center":
            x_expr = "(w-text_w)/2"
        elif align == "center":
            x_expr = f"{float(x):g}-text_w/2"
        elif align == "right":
            x_expr = f"{float(x):g}-text_w"
        else:
            x_expr = f"{float(x):g}"

        if y == "center":
            y_expr = "(h-text_h)/2"
        else:
            y_expr = f"{float(y):g}"

        return (
            "drawtext="
            f"text='{text}':"
            f"x='{x_expr}':y='{y_expr}':"
            f"fontsize={fontsize}:fontcolor={color}:"
            f"enable='between(t,{start:g},{end:g})'"
        )

    def _shape_filter(self, layer: Layer, start: float, end: float) -> str:
        props = layer.properties
        x = float(props.get("x", 0))
        y = float(props.get("y", 0))
        width = float(props.get("width", 100))
        height = float(props.get("height", 100))
        color = str(props.get("color", "white"))
        opacity = float(props.get("opacity", 1.0))
        return (
            "drawbox="
            f"x={x:g}:y={y:g}:w={width:g}:h={height:g}:"
            f"color={color}@{opacity:g}:t=fill:"
            f"enable='between(t,{start:g},{end:g})'"
        )

    @staticmethod
    def _escape_filter_text(value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace(":", "\\:")
            .replace("%", "\\%")
        )
