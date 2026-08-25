# video

**An AI-native programmable video studio.**

`video` treats the editable program that produces a video as the primary artifact. MP4, WebM, GIF, and other media files are build outputs.

```text
intent -> plan -> VideoProject -> validate -> preview/render -> revise -> evaluate
```

Instead of collapsing a project into pixels, `video` keeps scenes, layers, timing, animation, narration, assets, and generated clips as structured state. Humans and AI can therefore revise one creative decision without regenerating unrelated work.

## Design principles

1. **Source before pixels** — project source is inspectable, diffable, versionable state.
2. **Small generation surface** — models target constrained schemas, never arbitrary renderer APIs.
3. **Deterministic validation first** — structural failures are caught before subjective evaluation.
4. **Generated media are assets** — image/video models can provide clips without becoming the architecture.
5. **Local revision** — a bounded revision cannot silently rewrite unrelated scenes.
6. **Preferences over magic scores** — candidate comparison is the primary future learning signal.
7. **Edits become data** — accepted/rejected revisions can become preference/training examples.

## Current milestone — R2a

R1 established two renderer paths behind one canonical IR:

- **Remotion** for visual composition and future interactive preview
- **FFmpeg** for probing, media operations, audio, encoding and finalization

R2 now adds the model-facing contracts above those renderers.

### Create from intent

```bash
video create "Explain gradient descent in 30 seconds" \
  -o gradient-descent.json \
  --plan-output gradient-descent.plan.json
```

Without a configured model command, this uses a deterministic template planner so the workflow remains executable and testable. An external AI/local-model process can be injected without adding provider code to the runtime:

```bash
video create "Explain gradient descent in 30 seconds" \
  --planner-command "my-video-planner" \
  -o gradient-descent.json
```

The planner command receives a JSON request on stdin containing the intent, strict `VideoPlan` JSON Schema, and the allowed layer/animation/transition vocabulary. It must return one valid `VideoPlan` JSON object on stdout.

### Bounded revision

AI revision does **not** return a replacement project. It returns a typed `RevisionPatch` restricted to one requested scene and a small allowed operation vocabulary.

```bash
video revise gradient-descent.json \
  "Slow the labels down and keep them visible longer" \
  --scene explain \
  --reviser-command "my-video-reviser"
```

Revision is preview-only by default. The CLI prints a structural diff such as:

```text
scenes.explain.layers.label.duration: 2.0 -> 3.2
scenes.explain.layers.label.properties.y: 600 -> 560
```

Nothing is persisted until explicitly accepted:

```bash
video revise gradient-descent.json \
  "Slow the labels down and keep them visible longer" \
  --scene explain \
  --reviser-command "my-video-reviser" \
  --apply
```

A reviser cannot target another scene or a layer outside the bounded scene, and the complete `VideoProject` is revalidated before persistence.

## Render

```bash
video validate examples/showcase/video.json
video render examples/showcase/video.json --renderer ffmpeg -o build/showcase-ffmpeg.mp4
video render examples/showcase/video.json --renderer remotion -o build/showcase-remotion.mp4
```

The canonical `VideoProject` contains no FFmpeg filters, React components, Remotion APIs, or model-provider syntax.

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

The Remotion renderer also requires Node and its npm dependencies. FFmpeg/ffprobe are required for media validation and showcase asset generation.

See [ARCHITECTURE.md](ARCHITECTURE.md), [ROADMAP.md](ROADMAP.md), and [R1C_RENDERER_DECISION.md](R1C_RENDERER_DECISION.md).

## North star

```bash
video create "Explain gradient descent in 60 seconds"
video validate video.json
video render video.json --renderer remotion
video revise video.json "Slow the labels down" --scene explain
video compare candidate-a.json candidate-b.json
video improve video.json
```

**The video is not the artifact. The editable program that produces the video is the artifact.**
