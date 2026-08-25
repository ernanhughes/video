# Remotion renderer spike

R1c tests whether the canonical `VideoProject` should be visually composed through Remotion while FFmpeg remains a first-class media service.

## Install

```bash
cd renderers/remotion
npm install
npm run typecheck
```

Remotion packages are pinned to the same exact version (`4.0.516`) as recommended by Remotion.

## Render through the main CLI

From the repository root:

```bash
python examples/showcase/generate_assets.py
video validate examples/showcase/video.json
video render examples/showcase/video.json --renderer remotion -o build/showcase-remotion.mp4
```

The Python `RemotionRenderer` invokes this package. The source project is not translated into a new persisted format: the same canonical JSON is passed to the Remotion composition as input props.

## Responsibility boundary tested by R1c

Remotion is being evaluated for:

- scene composition
- typography/layout
- frame-based transforms
- easing
- visual transitions
- browser preview / future editing UI

FFmpeg remains valuable for:

- ffprobe validation
- codec/media diagnostics
- trim/loop/normalization
- audio processing
- muxing/finalization

See `R1C_RENDERER_DECISION.md` for the evidence matrix.
