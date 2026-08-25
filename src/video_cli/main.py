from __future__ import annotations

from pathlib import Path

import typer

from video_runtime.models import VideoProject
from video_runtime.project_io import load_project, save_project
from video_runtime.rendering import RenderError, render_project
from video_runtime.validation import validate_project

app = typer.Typer(no_args_is_help=True, help="Programmable AI-native video tooling")


@app.command("new")
def new_project(
    path: Path = typer.Argument(Path("video.json")),
    title: str = typer.Option("Untitled video", "--title", "-t"),
) -> None:
    project = VideoProject(title=title)
    save_project(project, path)
    typer.echo(f"Created {path}")


@app.command("show")
def show(path: Path) -> None:
    project = load_project(path)
    typer.echo(f"{project.title}: {len(project.scenes)} scenes, {project.duration:.2f}s")


@app.command("validate")
def validate(path: Path) -> None:
    project = load_project(path)
    report = validate_project(project)

    if not report.issues:
        typer.echo("OK")
        return

    for issue in report.issues:
        typer.echo(f"{issue.severity.upper()} {issue.code} {issue.path}: {issue.message}")

    if not report.ok:
        raise typer.Exit(code=1)


@app.command("render")
def render(
    path: Path,
    output: Path = typer.Option(Path("output.mp4"), "--output", "-o"),
    renderer: str = typer.Option("ffmpeg", "--renderer"),
) -> None:
    project = load_project(path)
    report = validate_project(project)
    if not report.ok:
        typer.echo("Project failed validation")
        raise typer.Exit(code=1)

    try:
        result = render_project(project, output, renderer=renderer)
    except RenderError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc

    typer.echo(
        f"Rendered {result.output_path} with {result.renderer} "
        f"({result.duration:.2f}s)"
    )


if __name__ == "__main__":
    app()
