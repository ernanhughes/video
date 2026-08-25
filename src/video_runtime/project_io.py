from __future__ import annotations

import json
from pathlib import Path

from .models import VideoProject


def load_project(path: str | Path) -> VideoProject:
    project_path = Path(path)
    return VideoProject.model_validate_json(project_path.read_text(encoding="utf-8"))


def save_project(project: VideoProject, path: str | Path) -> None:
    project_path = Path(path)
    project_path.parent.mkdir(parents=True, exist_ok=True)
    payload = project.model_dump(mode="json")
    project_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
