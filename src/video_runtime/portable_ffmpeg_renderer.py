from __future__ import annotations

import os
from pathlib import Path

from .ffmpeg_renderer import FFmpegRenderer
from .models import AnimationProperty, Layer, TransitionKind, VideoProject
from .rendering import RenderError


class PortableFFmpegRenderer(FFmpegRenderer):
    """FFmpeg renderer with portable text and transition handling.

    Some Windows FFmpeg distributions ship Fontconfig support without a usable
    system Fontconfig configuration. Asking drawtext to choose an implicit font
    can therefore fail before FFmpeg produces a useful diagnostic.

    FFmpeg 7.1 Windows builds can also expose undefined link-level frame-rate
    metadata after otherwise fixed-rate filter chains. The xfade filter rejects
    those streams before rendering. The portable renderer therefore implements
    scene fades as an explicit trimmed/blended overlap instead of depending on
    xfade's constant-frame-rate gate.
    """

    @classmethod
    def _default_font_candidates(cls) -> tuple[Path, ...]:
        windir = Path(os.environ.get("WINDIR", "C:/Windows"))
        return (
            windir / "Fonts" / "segoeui.ttf",
            windir / "Fonts" / "arial.ttf",
            windir / "Fonts" / "calibri.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/Library/Fonts/Arial.ttf"),
        )

    @classmethod
    def _default_font(cls) -> Path:
        for candidate in cls._default_font_candidates():
            if candidate.is_file():
                return candidate
        raise RenderError(
            "no usable default font was found for FFmpeg drawtext; "
            "install Segoe UI/Arial, DejaVu Sans, or Liberation Sans"
        )

    @staticmethod
    def _escape_font_path(path: Path) -> str:
        # FFmpeg filter syntax treats ':' specially. Forward slashes also avoid
        # backslash escaping problems on Windows.
        return path.as_posix().replace(":", "\\:").replace("'", "\\'")

    def _compose_scenes(
        self,
        project: VideoProject,
        scene_labels: list[str],
        filters: list[str],
    ) -> str:
        """Compose scenes without relying on xfade link frame-rate metadata.

        For a fade of duration D:

            current pre | current tail
                              + blend(D) | next post
                          next head

        The tail and head are reset to zero-based timestamps, blended frame by
        frame, then concatenated with the non-overlap sections. This preserves
        the canonical timeline duration while avoiding xfade's CFR metadata
        requirement on FFmpeg builds that report filtered links as 1/0.
        """
        if not scene_labels:
            raise RenderError("cannot render a project with no scenes")
        if len(scene_labels) == 1:
            return self._normalize_scene(scene_labels[0], 0, project, filters)

        normalized: list[str] = []
        for index, label in enumerate(scene_labels):
            normalized.append(self._normalize_scene(label, index, project, filters))

        current = normalized[0]
        current_duration = project.scenes[0].duration

        for index in range(1, len(normalized)):
            previous_scene = project.scenes[index - 1]
            next_label = normalized[index]
            transition = previous_scene.transition_out
            output = f"timeline{index}"

            if transition.kind == TransitionKind.FADE:
                duration = transition.duration
                pre_duration = current_duration - duration
                next_duration = project.scenes[index].duration

                current_pre_src = f"timeline{index}_pre_src"
                current_tail_src = f"timeline{index}_tail_src"
                next_head_src = f"timeline{index}_head_src"
                next_post_src = f"timeline{index}_post_src"
                current_pre = f"timeline{index}_pre"
                current_tail = f"timeline{index}_tail"
                next_head = f"timeline{index}_head"
                next_post = f"timeline{index}_post"
                overlap = f"timeline{index}_overlap"

                filters.append(
                    f"[{current}]split=2[{current_pre_src}][{current_tail_src}]"
                )
                filters.append(
                    f"[{current_pre_src}]trim=start=0:duration={pre_duration:g},"
                    f"setpts=PTS-STARTPTS[{current_pre}]"
                )
                filters.append(
                    f"[{current_tail_src}]trim=start={pre_duration:g}:duration={duration:g},"
                    f"setpts=PTS-STARTPTS[{current_tail}]"
                )
                filters.append(
                    f"[{next_label}]split=2[{next_head_src}][{next_post_src}]"
                )
                filters.append(
                    f"[{next_head_src}]trim=start=0:duration={duration:g},"
                    f"setpts=PTS-STARTPTS[{next_head}]"
                )
                filters.append(
                    f"[{next_post_src}]trim=start={duration:g}:duration={next_duration - duration:g},"
                    f"setpts=PTS-STARTPTS[{next_post}]"
                )
                # T is local overlap time because both inputs were reset to 0.
                # Clamp the blend progress to [0, 1] for deterministic edges.
                progress = f"min(1,max(0,T/{duration:g}))"
                filters.append(
                    f"[{current_tail}][{next_head}]blend=all_expr='A*(1-({progress}))+B*({progress})':"
                    f"shortest=1[{overlap}]"
                )
                filters.append(
                    f"[{current_pre}][{overlap}][{next_post}]"
                    f"concat=n=3:v=1:a=0[{output}]"
                )
                current_duration += next_duration - duration
            else:
                filters.append(
                    f"[{current}][{next_label}]concat=n=2:v=1:a=0[{output}]"
                )
                current_duration += project.scenes[index].duration

            current = output

        return current

    @staticmethod
    def _normalize_scene(
        label: str,
        index: int,
        project: VideoProject,
        filters: list[str],
    ) -> str:
        normalized = f"{label}_portable"
        fps = project.canvas.fps
        filters.append(
            f"[{label}]fps=fps={fps:g},format=yuv420p,settb=AVTB,"
            f"setpts=PTS-STARTPTS[{normalized}]"
        )
        return normalized

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

        fontfile = self._escape_font_path(self._default_font())
        return (
            "drawtext="
            f"fontfile='{fontfile}':text='{text}':x='{x_expr}':y='{y_expr}':"
            f"fontsize={fontsize}:fontcolor={color}:"
            f"enable='between(t,{start:g},{end:g})'"
        )
