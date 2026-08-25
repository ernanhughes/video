# Roadmap

## R0 — Source model ✅

Goal: make a video project a durable, validatable source artifact.

- canonical Video IR
- JSON persistence
- CLI: `video new`, `video validate`, `video show`
- deterministic validation
- example projects and tests

## R1 — First renderer

Goal: render a small useful subset end to end.

### R1a — deterministic visual core ✅

- FFmpeg renderer adapter
- text layers
- shape layers
- multi-scene timeline offsets
- project background
- H.264 MP4 output
- render diagnostics
- command-generation tests

### R1b — motion and portable project semantics ✅

- first-class `Animation` in the canonical IR
- typed animation properties and easing vocabulary
- first-class scene transitions
- transition overlap in project duration/timeline calculations
- linear x/y animation compilation for text and shapes
- animation timing validation
- project-relative media asset validation
- explicit failure for renderer features that are represented in the IR but not yet implemented
- animated two-scene example

### R1b.1 — media composition

- image layers
- video layers
- audio layers
- media probing and duration diagnostics
- opacity/scale/rotation animation
- actual visual fade transition rendering
- trim/loop/fit semantics for media assets

### R1c — renderer decision gate

Use the R1 implementation experience to decide whether:

1. FFmpeg remains the primary renderer,
2. Remotion becomes a second/primary adapter,
3. or a hybrid renderer is justified.

The decision gate should use one representative project containing text, shapes, image/video assets, audio, transforms, easing, and transitions. Do not leak renderer-specific concepts into the canonical IR to make any one implementation easier.

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
