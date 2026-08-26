from pathlib import Path

from video_runtime.models import Layer, LayerKind
from video_runtime.portable_ffmpeg_renderer import PortableFFmpegRenderer
from video_runtime.rendering import get_renderer


def test_ffmpeg_default_uses_portable_renderer() -> None:
    assert isinstance(get_renderer("ffmpeg"), PortableFFmpegRenderer)


def test_windows_font_path_is_escaped_for_filter_syntax() -> None:
    escaped = PortableFFmpegRenderer._escape_font_path(
        Path("C:/Windows/Fonts/segoeui.ttf")
    )
    assert escaped == "C\\:/Windows/Fonts/segoeui.ttf"


def test_text_filter_includes_explicit_fontfile(monkeypatch) -> None:
    renderer = PortableFFmpegRenderer()
    monkeypatch.setattr(
        PortableFFmpegRenderer,
        "_default_font",
        classmethod(lambda cls: Path("C:/Windows/Fonts/segoeui.ttf")),
    )
    layer = Layer(
        id="title",
        kind=LayerKind.TEXT,
        text="Hello",
        duration=1.0,
    )

    rendered = renderer._text_filter(layer, 0.0, 1.0)

    assert "fontfile='C\\:/Windows/Fonts/segoeui.ttf'" in rendered
    assert "text='Hello'" in rendered
