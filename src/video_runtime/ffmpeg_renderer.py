from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .models import Animation, AnimationProperty, Easing, Layer, LayerKind, VideoProject
from .rendering import RenderError, RenderResult


class FFmpegRenderer:
    """Deterministic renderer for the first useful Video IR subset.

    R1b adds first-class animation compilation while deliberately keeping the
    supported surface small. Text and shape layers support linear x/y motion.
    Media layers remain explicit IR concepts and are validated before fuller
    media composition lands in the next renderer increment.
    """

    name = "ffmpeg"
    supported_kinds = {LayerKind.TEXT, LayerKind.SHAPE}
    supported_animation_properties = {AnimationProperty.X, AnimationProperty.Y}

    def render(
        self,
        project: VideoProject,
        output_path: Path,
        *,
        source_root: Path = Path("."),
    ) -> RenderResult:
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
            raise RenderError(f"ffmpeg R1b renderer does not yet support media layer: {details}")

        unsupported_animations = [
            (layer, animation)
            for scene in project.scenes
            for layer in scene.layers
            for animation in layer.animations
            if animation.property not in self.supported_animation_properties
            or animation.easing != Easing.LINEAR
        ]
        if unsupported_animations:
            details = ", ".join(
                f"{layer.id}:{animation.property.value}/{animation.easing.value}"
                for layer, animation in unsupported_animations
            )
            raise RenderError(f"ffmpeg R1b renderer does not yet support animation: {details}")

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
        for scene_index, scene in enumerate(project.scenes):
            for layer in scene.layers:
                start = scene_offset + layer.start
                end = start + layer.duration
                if layer.kind == LayerKind.TEXT:
                    filters.append(self._text_filter(layer, start, end))
                elif layer.kind == LayerKind.SHAPE:
                    filters.append(self._shape_filter(layer, start, end))
            scene_offset += scene.duration
            if scene_index < len(project.scenes) - 1:
                scene_offset -= scene.transition_out.duration

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
        align = str(props.get("align", "left"))

        x_expr = self._position_expr(layer, AnimationProperty.X, props.get("x", "center"), start)
        y_expr = self._position_expr(layer, AnimationProperty.Y, props.get("y", "center"), start)

        if not self._has_animation(layer, AnimationProperty.X):
            if x_expr == "center":
                x_expr = "(w-text_w)/2"
            elif align == "center":
                x_expr = f"{float(x_expr):g}-text_w/2"
            elif align == "right":
                x_expr = f"{float(x_expr):g}-text_w"
        elif align == "center":
            x_expr = f"({x_expr})-text_w/2"
        elif align == "right":
            x_expr = f"({x_expr})-text_w"

        if not self._has_animation(layer, AnimationProperty.Y) and y_expr == "center":
            y_expr = "(h-text_h)/2"

        return (
            "drawtext="
            f"text='{text}':"
            f"x='{x_expr}':y='{y_expr}':"
            f"fontsize={fontsize}:fontcolor={color}:"
            f"enable='between(t,{start:g},{end:g})'"
        )

    def _shape_filter(self, layer: Layer, start: float, end: float) -> str:
        props = layer.properties
        x_expr = self._position_expr(layer, AnimationProperty.X, props.get("x", 0), start)
        y_expr = self._position_expr(layer, AnimationProperty.Y, props.get("y", 0), start)
        width = float(props.get("width", 100))
        height = float(props.get("height", 100))
        color = str(props.get("color", "white"))
        opacity = float(props.get("opacity", 1.0))
        return (
            "drawbox="
            f"x='{x_expr}':y='{y_expr}':w={width:g}:h={height:g}:"
            f"color={color}@{opacity:g}:t=fill:"
            f"enable='between(t,{start:g},{end:g})'"
        )

    def _position_expr(
        self,
        layer: Layer,
        property_name: AnimationProperty,
        default: object,
        global_layer_start: float,
    ) -> str:
        animation = next(
            (item for item in layer.animations if item.property == property_name),
            None,
        )
        if animation is None:
            if default == "center":
                return "center"
            return f"{float(default):g}"
        return self._linear_expression(animation, global_layer_start)

    @staticmethod
    def _linear_expression(animation: Animation, global_layer_start: float) -> str:
        animation_start = global_layer_start + animation.start
        animation_end = animation_start + animation.duration
        delta = animation.to_value - animation.from_value
        moving = (
            f"{animation.from_value:g}+({delta:g})*"
            f"(t-{animation_start:g})/{animation.duration:g}"
        )
        return (
            f"if(lt(t,{animation_start:g}),{animation.from_value:g},"
            f"if(gt(t,{animation_end:g}),{animation.to_value:g},{moving}))"
        )

    @staticmethod
    def _has_animation(layer: Layer, property_name: AnimationProperty) -> bool:
        return any(animation.property == property_name for animation in layer.animations)

    @staticmethod
    def _escape_filter_text(value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace(":", "\\:")
            .replace("%", "\\%")
        )
