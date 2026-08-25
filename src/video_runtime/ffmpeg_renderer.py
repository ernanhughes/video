from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .models import (
    Animation,
    AnimationProperty,
    Easing,
    Layer,
    LayerKind,
    MediaFit,
    TransitionKind,
    VideoProject,
)
from .rendering import RenderError, RenderResult


class FFmpegRenderer:
    """Deterministic FFmpeg compiler for the canonical Video IR.

    Scenes are rendered independently and then composed with cut/fade
    transitions. This keeps scene-transition semantics above individual layers
    and prevents renderer-specific transition hacks from leaking into the IR.
    """

    name = "ffmpeg"
    supported_kinds = {
        LayerKind.TEXT,
        LayerKind.SHAPE,
        LayerKind.IMAGE,
        LayerKind.VIDEO,
        LayerKind.AUDIO,
    }
    supported_animation_properties = {
        AnimationProperty.X,
        AnimationProperty.Y,
        AnimationProperty.OPACITY,
        AnimationProperty.SCALE,
        AnimationProperty.ROTATION,
    }

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
            or (
                animation.property
                in {AnimationProperty.OPACITY, AnimationProperty.SCALE, AnimationProperty.ROTATION}
                and layer.kind not in {LayerKind.IMAGE, LayerKind.VIDEO}
            )
        ]
        if unsupported_animations:
            details = ", ".join(
                f"{layer.id}:{animation.property.value}/{animation.easing.value}"
                for layer, animation in unsupported_animations
            )
            raise RenderError(f"ffmpeg renderer does not support animation for layer: {details}")

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
        command = [executable, "-y"]

        media_inputs: dict[str, int] = {}
        next_input = 0
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

        filters: list[str] = []
        scene_labels: list[str] = []
        audio_labels: list[str] = []
        global_scene_offset = 0.0

        for scene_index, scene in enumerate(project.scenes):
            visual_label = f"scene{scene_index}_0"
            background = str(scene.metadata.get("background", project.metadata.get("background", "black")))
            filters.append(
                f"color=c={background}:s={project.canvas.width}x{project.canvas.height}:"
                f"r={project.canvas.fps}:d={scene.duration:g}[{visual_label}]"
            )
            visual_index = 0

            for layer in scene.layers:
                local_start = layer.start
                local_end = layer.start + layer.duration
                next_visual = f"scene{scene_index}_{visual_index + 1}"

                if layer.kind == LayerKind.TEXT:
                    filters.append(
                        f"[{visual_label}]{self._text_filter(layer, local_start, local_end)}[{next_visual}]"
                    )
                    visual_label = next_visual
                    visual_index += 1
                elif layer.kind == LayerKind.SHAPE:
                    filters.append(
                        f"[{visual_label}]{self._shape_filter(layer, local_start, local_end)}[{next_visual}]"
                    )
                    visual_label = next_visual
                    visual_index += 1
                elif layer.kind in {LayerKind.IMAGE, LayerKind.VIDEO}:
                    input_index = media_inputs[layer.id]
                    media_label = f"m{scene_index}_{input_index}"
                    filters.append(
                        self._prepare_visual_media(
                            layer,
                            input_index,
                            media_label,
                            local_start,
                            project,
                        )
                    )
                    x_expr = self._position_expr(
                        layer,
                        AnimationProperty.X,
                        layer.properties.get("x", 0),
                        local_start,
                    )
                    y_expr = self._position_expr(
                        layer,
                        AnimationProperty.Y,
                        layer.properties.get("y", 0),
                        local_start,
                    )
                    filters.append(
                        f"[{visual_label}][{media_label}]overlay=x='{x_expr}':y='{y_expr}':"
                        f"eof_action=pass:enable='between(t,{local_start:g},{local_end:g})'[{next_visual}]"
                    )
                    visual_label = next_visual
                    visual_index += 1
                elif layer.kind == LayerKind.AUDIO:
                    input_index = media_inputs[layer.id]
                    audio_label = f"a{scene_index}_{input_index}"
                    global_start = global_scene_offset + layer.start
                    delay_ms = max(0, round(global_start * 1000))
                    filters.append(
                        f"[{input_index}:a]atrim=start={layer.source_start:g}:"
                        f"duration={layer.duration:g},asetpts=PTS-STARTPTS,"
                        f"volume={layer.volume:g},adelay={delay_ms}|{delay_ms}[{audio_label}]"
                    )
                    audio_labels.append(audio_label)

            scene_output = f"scene{scene_index}"
            filters.append(
                f"[{visual_label}]trim=duration={scene.duration:g},setpts=PTS-STARTPTS[{scene_output}]"
            )
            scene_labels.append(scene_output)

            global_scene_offset += scene.duration
            if scene_index < len(project.scenes) - 1:
                global_scene_offset -= scene.transition_out.duration

        visual_output = self._compose_scenes(project, scene_labels, filters)

        final_audio: str | None = None
        if audio_labels:
            joined = "".join(f"[{label}]" for label in audio_labels)
            filters.append(
                f"{joined}amix=inputs={len(audio_labels)}:duration=longest:normalize=0[aout]"
            )
            final_audio = "aout"

        command.extend(["-filter_complex", ";".join(filters), "-map", f"[{visual_output}]"])
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

    def _compose_scenes(
        self,
        project: VideoProject,
        scene_labels: list[str],
        filters: list[str],
    ) -> str:
        if not scene_labels:
            raise RenderError("cannot render a project with no scenes")
        if len(scene_labels) == 1:
            return scene_labels[0]

        current = scene_labels[0]
        current_duration = project.scenes[0].duration
        for index in range(1, len(scene_labels)):
            previous_scene = project.scenes[index - 1]
            next_label = scene_labels[index]
            output = f"timeline{index}"
            transition = previous_scene.transition_out

            if transition.kind == TransitionKind.FADE:
                offset = current_duration - transition.duration
                filters.append(
                    f"[{current}][{next_label}]xfade=transition=fade:"
                    f"duration={transition.duration:g}:offset={offset:g}[{output}]"
                )
                current_duration += project.scenes[index].duration - transition.duration
            else:
                filters.append(
                    f"[{current}][{next_label}]concat=n=2:v=1:a=0[{output}]"
                )
                current_duration += project.scenes[index].duration
            current = output
        return current

    def _prepare_visual_media(
        self,
        layer: Layer,
        input_index: int,
        output_label: str,
        local_start: float,
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

        operations = [trim, "setpts=PTS-STARTPTS", sizing, "format=rgba"]
        scale_animation = self._animation(layer, AnimationProperty.SCALE)
        if scale_animation:
            expr = self._value_expression(scale_animation, 0.0, time_symbol="t")
            operations.append(f"scale=w='iw*({expr})':h='ih*({expr})':eval=frame")

        rotation_animation = self._animation(layer, AnimationProperty.ROTATION)
        if rotation_animation:
            expr = self._value_expression(rotation_animation, 0.0, time_symbol="t")
            operations.append(f"rotate=angle='({expr})*PI/180':fillcolor=none")

        opacity_animation = self._animation(layer, AnimationProperty.OPACITY)
        if opacity_animation:
            expr = self._value_expression(opacity_animation, 0.0, time_symbol="t")
            operations.append(f"colorchannelmixer=aa='{expr}'")

        operations.append(f"setpts=PTS+{local_start:g}/TB")
        return f"[{input_index}:v]{','.join(operations)}[{output_label}]"

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
        layer_start: float,
    ) -> str:
        animation = self._animation(layer, property_name)
        if animation is None:
            if default == "center":
                return "center"
            return f"{float(default):g}"
        return self._value_expression(animation, layer_start, time_symbol="t")

    def _value_expression(
        self,
        animation: Animation,
        layer_start: float,
        *,
        time_symbol: str,
    ) -> str:
        animation_start = layer_start + animation.start
        animation_end = animation_start + animation.duration
        progress = f"({time_symbol}-{animation_start:g})/{animation.duration:g}"
        eased = self._easing_expression(animation.easing, progress)
        delta = animation.to_value - animation.from_value
        moving = f"{animation.from_value:g}+({delta:g})*({eased})"
        return (
            f"if(lt({time_symbol},{animation_start:g}),{animation.from_value:g},"
            f"if(gt({time_symbol},{animation_end:g}),{animation.to_value:g},{moving}))"
        )

    @staticmethod
    def _easing_expression(easing: Easing, progress: str) -> str:
        if easing == Easing.LINEAR:
            return progress
        if easing == Easing.EASE_IN:
            return f"({progress})*({progress})"
        if easing == Easing.EASE_OUT:
            return f"1-(1-({progress}))*(1-({progress}))"
        return f"({progress})*({progress})*(3-2*({progress}))"

    @staticmethod
    def _animation(layer: Layer, property_name: AnimationProperty) -> Animation | None:
        return next((item for item in layer.animations if item.property == property_name), None)

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
