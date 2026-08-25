# video

**An AI-native programmable video studio.**

`video` treats the editable program that produces a video as the primary artifact. MP4, WebM, GIF, and other media files are build outputs.

```text
intent -> video program -> validate -> render -> evaluate -> revise
```

Instead of collapsing a project into pixels, `video` keeps scenes, layers, timing, animation, narration, assets, and generated clips as structured state. Humans and AI can therefore revise one creative decision without regenerating unrelated work.

## Design principles

1. **Source before pixels** — project source is inspectable, diffable, versionable state.
2. **Small generation surface** — models target a constrained Video IR, not arbitrary renderer APIs.
3. **Deterministic validation first** — structural failures are caught before subjective evaluation.
4. **Generated media are assets** — image/video models can provide clips without becoming the architecture.
5. **Local revision** — scenes, layers, animation, narration, captions, and assets can change independently.
6. **Preferences over magic scores** — candidate comparison is the primary learning signal.
7. **Edits become data** — accepted revisions can later become preference/training examples.

## First milestone

```bash
video new project.json --title "Gradient Descent"
video validate project.json
video render project.json
```

The initial repository defines the canonical Video IR, validator, renderer contract, CLI, example project, and tests. The first renderer remains deliberately undecided.

See [ARCHITECTURE.md](ARCHITECTURE.md) and [ROADMAP.md](ROADMAP.md).

## Development

Python 3.12+:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -e ".[dev]"
pytest
video --help
```

## North star

```bash
video new "Explain gradient descent in 60 seconds"
video validate project.json
video render project.json
video revise project.json --scene scene-03 "Slow the labels down and keep the camera still"
video compare candidate-a.json candidate-b.json
video improve project.json
```

**The video is not the artifact. The editable program that produces the video is the artifact.**
