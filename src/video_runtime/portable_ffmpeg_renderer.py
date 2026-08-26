from __future__ import annotations

import os
from pathlib import Path

from .ffmpeg_renderer import FFmpegRenderer
from .models import AnimationProperty, Layer, VideoProject
from .rendering import RenderError


class PortableFFmpegRenderer(FFmpegRenderer):
    """FFmpeg renderer with portable text and transition handling.

    Some Windows FFmpeg distributions ship Fontconfig support without a usable
    system Fontconfig configuration. Asking drawtext to choose an implicit font
    can therefore fail before FFmpeg produces a useful diagnostic. Windows
    builds can also expose undefined frame-rate metadata after scene-local
    filter chains; xfade rejects those streams. This adapter resolves a real
    system font and normalizes every scene to the project FPS/timebase before
    scene composition, without leaking those renderer concerns into the IR.
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
        """Normalize scene streams before concat/xfade composition.

        FFmpeg's xfade requires both inputs to report a constant frame rate.
        Some filter chains, notably on Windows FFmpeg 7.1 builds, can emerge
        with an undefined 1/0 frame rate even when their source was generated
        at a fixed rate. Applying fps plus a common AVTB timebase at the scene
        boundary makes transition inputs deterministic across platforms.
        """
        normalized_labels: list[str] = []
        fps = project.canvas.fps
        for index, label in enumerate(scene_labels):
            normalized = f"{label}_cfr"
            filters.append(
                f"[{label}]fps=fps={fps:g},settb=AVTB,setpts=PTS-STARTPTS[{normalized}]"
            )
            normalized_labels.append(normalized)
        return super()._compose_scenes(project, normalized_labels, filters)

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
