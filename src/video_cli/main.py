from __future__ import annotations

from pathlib import Path

import typer

from video_runtime.models import VideoProject
from video_runtime.planning import (
    CommandPlanner,
    PlannerError,
    TemplatePlanner,
    project_from_plan,
    save_plan,
)
from video_runtime.project_io import load_project, save_project
from video_runtime.rendering import RenderError, render_project
from video_runtime.revision import (
    CommandReviser,
    RevisionError,
    RevisionPatch,
    apply_revision,
)
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


@app.command("create")
def create_from_intent(
    intent: str = typer.Argument(..., help="Natural-language video intent."),
    output: Path = typer.Option(Path("video.json"), "--output", "-o"),
    plan_output: Path | None = typer.Option(None, "--plan-output"),
    planner_command: str | None = typer.Option(None, "--planner-command"),
) -> None:
    """Plan and materialize a canonical VideoProject from natural-language intent."""

    planner = CommandPlanner(planner_command) if planner_command else TemplatePlanner()
    if not planner_command:
        typer.echo("Using deterministic template planner; pass --planner-command for an AI backend.")
    try:
        plan = planner.plan(intent)
    except PlannerError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc

    project = project_from_plan(plan)
    save_project(project, output)
    if plan_output is not None:
        save_plan(plan, plan_output)
    typer.echo(
        f"Created {output} from {planner.name} planner: "
        f"{len(project.scenes)} scenes, {project.duration:.2f}s"
    )


@app.command("show")
def show(path: Path) -> None:
    project = load_project(path)
    typer.echo(f"{project.title}: {len(project.scenes)} scenes, {project.duration:.2f}s")


@app.command("validate")
def validate(path: Path) -> None:
    project = load_project(path)
    resolved_path = path.resolve()
    report = validate_project(project, project_path=resolved_path, probe_assets=True)

    if not report.issues:
        typer.echo("OK")
        return

    for issue in report.issues:
        typer.echo(f"{issue.severity.upper()} {issue.code} {issue.path}: {issue.message}")

    if not report.ok:
        raise typer.Exit(code=1)


@app.command("revise")
def revise(
    path: Path,
    instruction: str = typer.Argument(..., help="Requested local change."),
    scene: str = typer.Option(..., "--scene", help="The only scene the revision may mutate."),
    patch: Path | None = typer.Option(None, "--patch", help="Use a pre-generated RevisionPatch JSON file."),
    reviser_command: str | None = typer.Option(None, "--reviser-command", help="External AI/model command that emits RevisionPatch JSON."),
    apply: bool = typer.Option(False, "--apply", help="Persist the patch after showing its structural diff."),
) -> None:
    """Generate/apply a scene-bounded revision and always show the structural diff."""

    project = load_project(path)
    try:
        if patch is not None:
            revision_patch = RevisionPatch.model_validate_json(patch.read_text(encoding="utf-8"))
            if revision_patch.scene_id != scene:
                raise RevisionError(
                    f"patch targets scene {revision_patch.scene_id!r}; bounded scene is {scene!r}"
                )
        elif reviser_command is not None:
            revision_patch = CommandReviser(reviser_command).revise(project, scene, instruction)
        else:
            typer.echo("Provide --reviser-command for an AI backend or --patch for a RevisionPatch JSON file.")
            raise typer.Exit(code=2)

        result = apply_revision(project, revision_patch)
    except RevisionError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc

    if not result.changes:
        typer.echo("No structural changes.")
    else:
        typer.echo(f"Revision diff for scene {scene}:")
        for change in result.changes:
            typer.echo(f"  {change.path}: {change.before!r} -> {change.after!r}")

    if not apply:
        typer.echo("Preview only; rerun with --apply to persist.")
        return

    save_project(result.project, path)
    typer.echo(f"Updated {path}")


@app.command("render")
def render(
    path: Path,
    output: Path = typer.Option(Path("output.mp4"), "--output", "-o"),
    renderer: str = typer.Option("ffmpeg", "--renderer"),
) -> None:
    project = load_project(path)
    resolved_path = path.resolve()
    report = validate_project(project, project_path=resolved_path, probe_assets=True)
    if not report.ok:
        typer.echo("Project failed validation")
        for issue in report.issues:
            if issue.severity == "error":
                typer.echo(f"ERROR {issue.code} {issue.path}: {issue.message}")
        raise typer.Exit(code=1)

    try:
        result = render_project(
            project,
            output,
            renderer=renderer,
            source_root=resolved_path.parent,
        )
    except RenderError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc

    typer.echo(f"Rendered {result.output_path} with {result.renderer} ({result.duration:.2f}s)")


if __name__ == "__main__":
    app()
