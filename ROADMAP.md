# Roadmap

## R0 — Source model ✅

Goal: make a video project a durable, validatable source artifact.

- canonical Video IR
- JSON persistence
- CLI: `video new`, `video validate`, `video show`
- deterministic validation
- example projects and tests

## R1 — First renderer ✅

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
- explicit failure for renderer features represented in the IR but not yet implemented
- animated two-scene example

### R1b.1a — multimedia composition core ✅

- image/video/audio layers
- typed fit/source_start/loop/volume semantics
- ffprobe inspection and media validation
- trim/loop/overlay/audio mixing

### R1b.1b — transforms and transitions ✅

- opacity/scale/rotation animation
- nonlinear easing
- real visual fades
- transition-aware audio fades
- executable FFmpeg smoke tests

### R1b.2 — representative project ✅

- four-scene showcase
- deterministic generated media
- text + shape + image + video + audio
- transforms/easing/cross-fades
- end-to-end CI render

### R1c — renderer decision gate ✅

Decision: **hybrid**.

- Remotion is the preferred visual composition/preview path
- FFmpeg remains the media probing/manipulation/finalization path
- both consume the same renderer-neutral `VideoProject`
- the full Remotion showcase render passes CI
- decision rationale lives in `R1C_RENDERER_DECISION.md`

## R2 — AI generation and bounded editing

Goal: generate and revise the IR rather than arbitrary renderer code.

### R2a — planning and bounded revision contracts ✅

- typed `VideoPlan`
- deterministic template planner for bootstrap/tests
- external command planner adapter for AI/local-model integration
- `VideoPlan -> VideoProject` materialization
- `video create INTENT`
- typed `RevisionPatch`
- scene-bounded allowed operation vocabulary
- external command reviser adapter
- structural diff before persistence
- `video revise ... --scene ...` defaults to preview-only
- full-project revalidation after every patch
- tests proving revisions cannot reach layers outside the bounded scene

### R2b — native model adapters

- provider-neutral model request/response contract
- first local-model adapter
- first hosted-model adapter
- structured-output retry/repair
- prompt/version fingerprints
- planner/reviser tracing

### R2c — generated asset orchestration

- generated image/video/audio asset requests as typed plan state
- deterministic asset IDs and provenance
- provider adapters remain tools, not architecture
- materialize assets before validation/render

### R2d — editor loop

- preview candidate revision
- accept/reject/revert
- persist revision history
- capture accepted/rejected changes as future preference data

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
