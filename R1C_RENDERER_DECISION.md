# R1c Renderer Decision

## Question

Which renderer architecture should `video` use after R1?

1. FFmpeg only
2. Remotion only
3. Hybrid: Remotion for composition/preview, FFmpeg for media validation and final media operations

The comparison uses the same canonical source project: `examples/showcase/video.json`.

## Evidence from the FFmpeg implementation

FFmpeg has been excellent for deterministic media operations:

- ffprobe inspection and validation
- trim and source offsets
- looping
- image/video scaling and crop
- audio delay, gain, fades, and mixing
- encoding and muxing
- deterministic headless export

The cost appears when visual composition becomes expressive. The adapter now owns a compiler for:

- scene-local visual graphs
- x/y animation expressions
- easing expressions
- opacity
- animated scale
- animated rotation
- scene concatenation
- xfade offsets
- audio transition coordination
- filter graph label management

Those capabilities work, but every new visual primitive increases renderer-specific expression/compiler complexity.

## Evidence from the Remotion spike

The Remotion spike projects the same `VideoProject` into React components.

The canonical IR remains unchanged. The adapter maps:

- scenes -> overlapping `Sequence`s
- text -> styled DOM text
- shapes -> DOM elements
- image -> `Img`
- video -> `OffthreadVideo`
- audio -> `Audio`
- x/y/opacity/scale/rotation -> frame-derived CSS values
- easing -> ordinary numeric interpolation
- fades -> scene opacity and audio gain envelopes

This makes visual behavior much closer to the source concepts and creates a natural path to browser preview and interactive editing.

## Comparison

| Area | FFmpeg | Remotion | Preferred |
| --- | --- | --- | --- |
| Media probing | Excellent | Not its job | FFmpeg |
| Trim / loop / mux | Excellent | Good | FFmpeg |
| Audio processing | Excellent | Good | FFmpeg |
| Final encoding | Excellent | Good | FFmpeg |
| Typography / layout | Low-level | Native web layout | Remotion |
| Visual transforms | Expression-heavy | Direct CSS/frame math | Remotion |
| Easing | Compiler expressions | Direct interpolation | Remotion |
| Scene composition | Filter graph labels | React composition | Remotion |
| Interactive preview | Poor fit | Core capability | Remotion |
| Future editor UI | Separate system | Natural extension | Remotion |
| Canonical IR independence | Proven | Proven by spike | Tie |

## Decision

**Recommended architecture: hybrid.**

```text
                         VideoProject
                              │
                    canonical Video IR
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
        Composition path                Media services
          Remotion                         FFmpeg
              │                               │
      preview / typography              ffprobe / trim
      layout / animation                audio / encode
      scene composition                 mux / normalize
              │                               │
              └───────────────┬───────────────┘
                              ▼
                           export
```

This does **not** mean every export must always execute two full render passes. It means the architecture assigns responsibilities by strength:

- Remotion is the preferred visual composition and preview engine.
- FFmpeg remains a first-class media service and deterministic export/finalization tool.
- `VideoProject` stays above both and contains no renderer-specific syntax.

## Why not Remotion-only?

Removing FFmpeg would discard the strongest part of R1: deterministic media inspection and manipulation. FFmpeg is also valuable for normalization, probing, codec handling, audio operations, and finalization even when Remotion owns composition.

## Why not FFmpeg-only?

Continuing to add visual language features would turn `FFmpegRenderer` into an increasingly complex compiler for concepts that map naturally to browser layout and animation. It would also leave live preview and a future editing UI as separate problems.

## R2 implication

The AI should continue generating and revising **Video IR**, never React or FFmpeg expressions directly.

The next architecture should therefore be:

```text
intent
  -> project plan
  -> Video IR
  -> validate
  -> preview (Remotion)
  -> revise
  -> render/finalize (Remotion + FFmpeg services)
```

That keeps the central product thesis intact: the editable source program is the artifact; renderers are replaceable execution backends.
