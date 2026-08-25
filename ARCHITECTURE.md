# Architecture

## Core proposition

`video` is a programmable video system. The canonical artifact is a structured project, not a rendered media file.

```text
User intent
    |
    v
Planner / Editor
    |
    v
Video IR
    |
    +--> deterministic validation
    |
    +--> renderer adapter --> media artifact
    |
    +--> evaluator / ranker
    |
    +--> revision loop
```

## Boundaries

### Video IR

The IR describes meaningfully editable state:

- project metadata
- canvas and frame rate
- ordered scenes
- scene duration
- typed layers
- temporal placement
- animation specifications
- asset references
- narration/audio references
- transitions

The IR should remain renderer-independent.

### Validation

Validation is deterministic wherever possible. It should answer questions such as:

- Are IDs unique?
- Are dimensions, frame rates, and durations valid?
- Are layers contained within their scenes?
- Do asset references resolve?
- Are timing ranges valid?
- Are renderer-required capabilities available?

Subjective judgments such as pacing or aesthetics belong in evaluation, not structural validation.

### Rendering

Rendering is an adapter boundary. Candidate implementations may use Remotion, Canvas/WebGL/WebGPU, FFmpeg, or combinations of them. The runtime must not leak renderer-specific concepts into the canonical IR unless they prove generally necessary.

Generated image/video clips are treated as assets and can be replaced independently.

### Evaluation

Evaluation is intentionally separate from validation. Future evaluators may compare two renders for explanatory clarity, pacing, composition, motion, or style. Pairwise preference is preferred over a single opaque quality score.

### Revision

A revision should be expressible as a bounded change to project state. The long-term invariant is that a request such as "slow the labels in scene 3" should not rewrite unrelated scenes.

## Initial package layout

```text
src/video_runtime/
  models.py       canonical Video IR
  validation.py   deterministic project checks
  rendering.py    renderer protocol and result types
  project_io.py   JSON persistence

src/video_cli/
  main.py         CLI boundary
```

## Non-goals for the seed

The seed deliberately does not choose:

- a foundation video model
- a renderer implementation
- an RL stack
- a web editor
- a universal creative DSL

Those decisions should follow evidence from the first end-to-end rendering loop.
