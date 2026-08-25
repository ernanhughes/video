# Showcase

This is the representative R1 project used to pressure-test the canonical Video IR and FFmpeg renderer as one real composition rather than isolated features.

It deliberately exercises:

- four scenes
- text and shape layers
- image and video assets
- audio layers
- x/y motion
- scale, rotation, and opacity animation
- linear and eased interpolation
- scene-local composition
- visual cross-fades
- transition-aware audio fades
- project-relative assets

## Build the deterministic assets

```bash
python examples/showcase/generate_assets.py
```

The assets are generated locally so the repository remains source-first and does not need checked-in binary media.

## Validate

```bash
video validate examples/showcase/video.json
```

## Render

```bash
video render examples/showcase/video.json -o build/showcase.mp4
```

The project is intentionally small enough to inspect in JSON but rich enough to reveal whether the current IR and renderer remain pleasant once features are combined.

## What to evaluate after watching it

1. Is scene/layer authoring still understandable without renderer knowledge?
2. Are timing and transition semantics predictable?
3. Is animation composition expressive enough without arbitrary code?
4. Does FFmpeg remain maintainable as the primary composition backend?
5. Which concepts, if any, should be added to the IR before AI generation begins?

This project is the evidence base for the R1c renderer decision gate.
