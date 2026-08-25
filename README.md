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

## Current milestone — R1b

The canonical IR now carries motion and transition semantics instead of hiding them in renderer-specific strings.

Implemented:

- text and shape layers
- multi-scene timing
- first-class `Animation`
- typed animation properties: opacity, x, y, scale, rotation
- easing vocabulary: linear, ease-in, ease-out, ease-in-out
- scene transitions: cut and fade
- transition overlap in project duration
- FFmpeg compilation for linear x/y animation on text and shapes
- animation timing validation
- project-relative validation of image/video/audio asset paths
- H.264 MP4 output
- explicit renderer failures for IR features not yet supported by the FFmpeg adapter

FFmpeg must be installed and available on `PATH`.

```bash
video validate examples/hello.json
video render examples/hello.json -o build/hello.mp4
```

`examples/hello.json` is now a two-scene animated program. A fade transition currently defines timeline overlap; actual cross-fade rendering lands with media composition in R1b.1.

The renderer boundary remains independent from FFmpeg: `VideoProject` contains no FFmpeg filters or command syntax, and future renderers can sit behind the same contract.

## Next — R1b.1

The next increment makes real media composable:

```text
ImageLayer + VideoLayer + AudioLayer
              ↓
      deterministic probing
              ↓
     trim / loop / fit rules
              ↓
   opacity / scale / rotation
              ↓
       real transitions
```

That representative project becomes the input to the R1c FFmpeg-vs-Remotion-vs-hybrid renderer decision.

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

See [ARCHITECTURE.md](ARCHITECTURE.md) and [ROADMAP.md](ROADMAP.md).

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
