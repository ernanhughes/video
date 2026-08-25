from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from .models import VideoProject
from .rendering import RenderError, RenderResult


class RemotionRenderer:
    """R1c adapter that renders the canonical VideoProject through Remotion."""

    name = "remotion"

    def render(
        self,
        project: VideoProject,
        output_path: Path,
        *,
        source_root: Path = Path("."),
    ) -> RenderResult:
        npm = shutil.which("npm")
        if npm is None:
            raise RenderError("npm was not found on PATH")

        renderer_root = Path(__file__).resolve().parents[2] / "renderers" / "remotion"
        if not (renderer_root / "node_modules").exists():
            raise RenderError(
                "Remotion dependencies are not installed. Run `npm install` in renderers/remotion."
            )

        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="video-remotion-",
            dir=source_root,
            delete=False,
            encoding="utf-8",
        ) as handle:
            json.dump(project.model_dump(mode="json"), handle, indent=2)
            project_path = Path(handle.name)

        try:
            completed = subprocess.run(
                [
                    npm,
                    "run",
                    "render",
                    "--",
                    str(project_path),
                    str(output_path),
                ],
                cwd=renderer_root,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            project_path.unlink(missing_ok=True)

        if completed.returncode != 0:
            diagnostic = (completed.stderr or completed.stdout).strip().splitlines()
            tail = "\n".join(diagnostic[-20:])
            raise RenderError(f"Remotion render failed ({completed.returncode})\n{tail}")

        return RenderResult(
            output_path=output_path,
            renderer=self.name,
            duration=project.duration,
        )
