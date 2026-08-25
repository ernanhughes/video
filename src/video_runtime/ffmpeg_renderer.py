from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .models import Animation, AnimationProperty, Easing, Layer, LayerKind, MediaFit, VideoProject
from .rendering import RenderError, RenderResult


class FFmpegRenderer:
    """Deterministic FFmpeg renderer for the canonical Video IR."""

    name = "ffmpeg"
    supported_kinds = {
        LayerKind.TEXT,
        LayerKind.SHAPE,
        LayerKind.IMAGE,
        LayerKind.VIDEO,
        LayerKind.AUDIO,
    }
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
            raise RenderError(f"ffmpeg renderer does not yet support layer: {details}")

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
            raise RenderError(f"ffmpeg renderer does not yet support animation: {details}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = self.build_command(
            project,
            output_path,
            executable=executable,
            source_root=source_root,
        )
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            diagnostic = completed.stderr.strip().splitlines()
            tail = "\n".join(diagnostic[-16:])
            raise RenderError(f"ffmpeg render failed ({completed.returncode})\n{tail}")

        return RenderResult(output_path=output_path, renderer=self.name, duration=project.duration)

    def build_command(
        self,
        project: VideoProject,
        output_path: Path,
        *,
        executable: str = "ffmpeg",
        source_root: Path = Path("."),
    ) -> list[str]:
        canvas = project.canvas
        background = str(project.metadata.get("background", "black"))
        source = (
            f"color=c={background}:s={canvas.width}x{canvas.height}:"
            f"r={canvas.fps}:d={project.duration}"
        )
        command = [executable, "-y", "-f", "lavfi", "-i", source]

        media_inputs: dict[str, int] = {}
        next_input = 1
        for scene in project.scenes:
            for layer in scene.layers:
                if layer.kind not in {LayerKind.IMAGE, LayerKind.VIDEO, LayerKind.AUDIO}:
                    continue
                resolved = self._resolve_source(layer, source_root)
                if layer.kind == LayerKind.IMAGE:
                    command.extend(["-loop", "1", "-i", str(resolved)])
                elif layer.loop:
                    command.extend(["-stream_loop", "-1", "-i", str(resolved)])
                else:
                    command.extend(["-i", str(resolved)])
                media_inputs[layer.id] = next_input
                next_input += 1

        filters: list[str] = ["[0:v]setpts=PTS-STARTPTS[v0]"]
        visual_label = "v0"
        visual_index = 0
        audio_labels: list[str] = []
        scene_offset = 0.0

        for scene_index, scene in enumerate(project.scenes):
            for layer in scene.layers:
                start = scene_offset + layer.start
                end = start + layer.duration
                next_visual = f"v{visual_index + 1}"

                if layer.kind == LayerKind.TEXT:
                    filters.append(f"[{visual_label}]{self._text_filter(layer, start, end)}[{next_visual}]")
                    visual_label = next_visual
                    visual_index += 1
                elif layer.kind == LayerKind.SHAPE:
                    filters.append(f"[{visual_label}]{self._shape_filter(layer, start, end)}[{next_visual}]")
                    visual_label = next_visual
                    visual_index += 1
                elif layer.kind in {LayerKind.IMAGE, LayerKind.VIDEO}:
                    input_index = media_inputs[layer.id]
                    media_label = f"m{input_index}"
                    filters.append(self._prepare_visual_media(layer, input_index, media_label, start, project))
                    x_expr = self._position_expr(layer, AnimationProperty.X, layer.properties.get("x", 0), start)
                    y_expr = self._position_expr(layer, AnimationProperty.Y, layer.properties.get("y", 0), start)
                    filters.append(
                        f"[{visual_label}][{media_label}]overlay=x='{x_expr}':y='{y_expr}':"
                        f"eof_action=pass:enable='between(t,{start:g},{end:g})'[{next_visual}]"
                    )
                    visual_label = next_visual
                    visual_index += 1
                elif layer.kind == LayerKind.AUDIO:
                    input_index = media_inputs[layer.id]
                    audio_label = f"a{input_index}"
                    delay_ms = max(0, round(start * 1000))
                    filters.append(
                        f"[{input_index}:a]atrim=start={layer.source_start:g}:"
                        f"duration={layer.duration:g},asetpts=PTS-STARTPTS,"
                        f"volume={layer.volume:g},adelay={delay_ms}|{delay_ms}[{audio_label}]"
                    )
                    audio_labels.append(audio_label)

            scene_offset += scene.duration
            if scene_index < len(project.scenes) - 1:
                scene_offset -= scene.transition_out.duration

        final_audio: str | None = None
        if audio_labels:
            joined = "".join(f"[{label}]" for label in audio_labels)
            filters.append(
                f"{joined}amix=inputs={len(audio_labels)}:duration=longest:normalize=0[aout]"
            )
            final_audio = "aout"

        command.extend(["-filter_complex", ";".join(filters), "-map", f"[{visual_label}]"])
        if final_audio:
            command.extend(["-map", f"[{final_audio}]", "-c:a", "aac", "-b:a", "192k"])
        command.extend(
            [
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-t",
                f"{project.duration:g}",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )
        return command

    def _prepare_visual_media(
        self,
        layer: Layer,
        input_index: int,
        output_label: str,
        global_start: float,
        project: VideoProject,
    ) -> str:
        width = int(layer.properties.get("width", project.canvas.width))
        height = int(layer.properties.get("height", project.canvas.height))
        if layer.fit == MediaFit.CONTAIN:
            sizing = f"scale={width}:{height}:force_original_aspect_ratio=decrease"
        elif layer.fit == MediaFit.COVER:
            sizing = (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}"
            )
        else:
            sizing = f"scale={width}:{height}"

        trim = f"trim=duration={layer.duration:g}"
        if layer.kind == LayerKind.VIDEO and layer.source_start:
            trim = f"trim=start={layer.source_start:g}:duration={layer.duration:g}"
        return (
            f"[{input_index}:v]{trim},setpts=PTS-STARTPTS+{global_start:g}/TB,"
            f"{sizing},format=rgba[{output_label}]"
        )

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
            f"text='{text}':x='{x_expr}':y='{y_expr}':"
            f"fontsize={fontsize}:fontcolor={color}:enable='between(t,{start:g},{end:g})'"
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
            f"color={color}@{opacity:g}:t=fill:enable='between(t,{start:g},{end:g})'"
        )

    def _position_expr(
        self,
        layer: Layer,
        property_name: AnimationProperty,
        default: object,
        global_layer_start: float,
    ) -> str:
        animation = next((item for item in layer.animations if item.property == property_name), None)
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
    def _resolve_source(layer: Layer, source_root: Path) -> Path:
        source = Path(layer.source or "")
        return source if source.is_absolute() else source_root / source

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
