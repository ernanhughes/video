import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

import type {Animation, Layer, Scene, VideoProject} from './types';

const clamp = {extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const};

const ease = (t: number, kind: Animation['easing']) => {
  if (kind === 'ease_in') return t * t;
  if (kind === 'ease_out') return 1 - (1 - t) * (1 - t);
  if (kind === 'ease_in_out') return t * t * (3 - 2 * t);
  return t;
};

const animationValue = (animation: Animation, time: number) => {
  const progress = interpolate(time, [animation.start, animation.start + animation.duration], [0, 1], clamp);
  const eased = ease(progress, animation.easing);
  return animation.from_value + (animation.to_value - animation.from_value) * eased;
};

const valueFor = (layer: Layer, property: Animation['property'], time: number, fallback: number) => {
  const animation = layer.animations?.find((item) => item.property === property);
  return animation ? animationValue(animation, time) : fallback;
};

const color = (value: unknown, fallback = 'white') => {
  if (typeof value !== 'string') return fallback;
  return value.startsWith('0x') ? `#${value.slice(2)}` : value;
};

const layerStyle = (layer: Layer, time: number): React.CSSProperties => {
  const props = layer.properties ?? {};
  const x = valueFor(layer, 'x', time, Number(props.x ?? 0));
  const y = valueFor(layer, 'y', time, Number(props.y ?? 0));
  const scale = valueFor(layer, 'scale', time, 1);
  const rotation = valueFor(layer, 'rotation', time, 0);
  const opacity = valueFor(layer, 'opacity', time, Number(props.opacity ?? 1));
  return {
    position: 'absolute',
    left: x,
    top: y,
    opacity,
    transform: `scale(${scale}) rotate(${rotation}deg)`,
    transformOrigin: 'center center',
  };
};

const VisualLayer: React.FC<{layer: Layer}> = ({layer}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = frame / fps;
  const props = layer.properties ?? {};
  const style = layerStyle(layer, time);

  if (layer.kind === 'shape') {
    return <div style={{...style, width: Number(props.width ?? 100), height: Number(props.height ?? 100), backgroundColor: color(props.color), opacity: style.opacity}} />;
  }

  if (layer.kind === 'text') {
    const align = String(props.align ?? 'left');
    const transform = `${style.transform ?? ''}${align === 'center' ? ' translateX(-50%)' : align === 'right' ? ' translateX(-100%)' : ''}`;
    return (
      <div
        style={{
          ...style,
          transform,
          color: color(props.color),
          fontFamily: 'Arial, sans-serif',
          fontSize: Number(props.font_size ?? 64),
          fontWeight: 700,
          whiteSpace: 'nowrap',
        }}
      >
        {layer.text}
      </div>
    );
  }

  const width = Number(props.width ?? 1280);
  const height = Number(props.height ?? 720);
  const objectFit = layer.fit === 'stretch' ? 'fill' : layer.fit === 'cover' ? 'cover' : 'contain';

  if (layer.kind === 'image' && layer.source) {
    return <Img src={staticFile(layer.source)} style={{...style, width, height, objectFit}} />;
  }

  if (layer.kind === 'video' && layer.source) {
    return (
      <OffthreadVideo
        src={staticFile(layer.source)}
        startFrom={Math.round((layer.source_start ?? 0) * fps)}
        style={{...style, width, height, objectFit}}
        muted
      />
    );
  }

  return null;
};

const AudioLayer: React.FC<{layer: Layer; fadeIn: number; fadeOut: number; sceneDuration: number}> = ({layer, fadeIn, fadeOut, sceneDuration}) => {
  const {fps} = useVideoConfig();
  if (!layer.source) return null;
  const startFrom = Math.round((layer.source_start ?? 0) * fps);
  return (
    <Audio
      src={staticFile(layer.source)}
      startFrom={startFrom}
      volume={(frame) => {
        const t = frame / fps;
        let gain = layer.volume ?? 1;
        if (fadeIn > 0) gain *= interpolate(t, [0, fadeIn], [0, 1], clamp);
        if (fadeOut > 0) gain *= interpolate(t, [sceneDuration - fadeOut, sceneDuration], [1, 0], clamp);
        return gain;
      }}
    />
  );
};

const SceneView: React.FC<{scene: Scene; fadeIn: number}> = ({scene, fadeIn}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = frame / fps;
  const fadeOut = scene.transition_out.kind === 'fade' ? scene.transition_out.duration : 0;
  let sceneOpacity = 1;
  if (fadeIn > 0) sceneOpacity *= interpolate(time, [0, fadeIn], [0, 1], clamp);
  if (fadeOut > 0) sceneOpacity *= interpolate(time, [scene.duration - fadeOut, scene.duration], [1, 0], clamp);
  const background = color(scene.metadata?.background, 'black');

  return (
    <AbsoluteFill style={{backgroundColor: background, opacity: sceneOpacity}}>
      {scene.layers.filter((layer) => layer.kind !== 'audio').map((layer) => (
        <Sequence key={layer.id} from={Math.round(layer.start * fps)} durationInFrames={Math.round(layer.duration * fps)}>
          <VisualLayer layer={layer} />
        </Sequence>
      ))}
      {scene.layers.filter((layer) => layer.kind === 'audio').map((layer) => (
        <Sequence key={layer.id} from={Math.round(layer.start * fps)} durationInFrames={Math.round(layer.duration * fps)}>
          <AudioLayer layer={layer} fadeIn={fadeIn} fadeOut={fadeOut} sceneDuration={scene.duration} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const VideoComposition: React.FC<{project: VideoProject}> = ({project}) => {
  const fps = project.canvas.fps;
  let cursor = 0;
  return (
    <AbsoluteFill style={{backgroundColor: color(project.metadata?.background, 'black')}}>
      {project.scenes.map((scene, index) => {
        const previous = index > 0 ? project.scenes[index - 1] : null;
        const fadeIn = previous?.transition_out.kind === 'fade' ? previous.transition_out.duration : 0;
        const start = cursor;
        cursor += scene.duration - scene.transition_out.duration;
        return (
          <Sequence key={scene.id} from={Math.round(start * fps)} durationInFrames={Math.round(scene.duration * fps)}>
            <SceneView scene={scene} fadeIn={fadeIn} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
