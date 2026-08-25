# Roadmap

## R0 — Source model

Goal: make a video project a durable, validatable source artifact.

- canonical Video IR
- JSON persistence
- CLI: `video new`, `video validate`, `video show`
- deterministic validation
- example projects and tests

## R1 — First renderer

Goal: render a small useful subset end to end.

- select renderer after a narrow spike
- text, image, shape, and video layers
- basic transforms and opacity animation
- audio track
- MP4 output
- render diagnostics

## R2 — AI generation and bounded editing

Goal: generate and revise the IR rather than arbitrary renderer code.

- prompt -> project plan -> Video IR
- constrained generation vocabulary
- scene-local revision
- structural diff before acceptance
- generated-image/video asset adapters

## R3 — Evaluation and candidates

Goal: make improvement measurable.

- render candidate variants
- pairwise comparison
- specialist evaluators: clarity, pacing, composition, motion, typography
- preference corpus
- human accept/reject capture

## R4 — Improve loop

Goal: automatically locate weak decisions and test bounded interventions.

```text
inspect -> hypothesize -> generate candidates -> render -> validate -> rank -> accept/reject
```

## R5 — Learned taste

Goal: learn from accumulated project edits and pairwise preferences.

- train preference rankers
- reference pools
- author/style profiles
- optional fine-tuning/RL only when the corpus justifies it

## Near-term decision gate

Do not commit the canonical IR to Remotion, Three.js, FFmpeg, or any one model provider until R1 experiments show which concepts actually need to cross the renderer boundary.
