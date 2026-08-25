export type Easing = 'linear' | 'ease_in' | 'ease_out' | 'ease_in_out';
export type AnimationProperty = 'opacity' | 'x' | 'y' | 'scale' | 'rotation';
export type LayerKind = 'text' | 'image' | 'video' | 'shape' | 'audio' | 'chart' | 'simulation' | 'generated';
export type MediaFit = 'contain' | 'cover' | 'stretch';

export type Animation = {
  property: AnimationProperty;
  from_value: number;
  to_value: number;
  start: number;
  duration: number;
  easing: Easing;
};

export type Layer = {
  id: string;
  kind: LayerKind;
  start: number;
  duration: number;
  source?: string | null;
  source_start?: number;
  loop?: boolean;
  volume?: number;
  fit?: MediaFit;
  text?: string | null;
  properties?: Record<string, unknown>;
  animations?: Animation[];
};

export type Scene = {
  id: string;
  duration: number;
  layers: Layer[];
  transition_out: {kind: 'cut' | 'fade'; duration: number};
  metadata?: Record<string, unknown>;
};

export type VideoProject = {
  schema_version: string;
  title: string;
  canvas: {width: number; height: number; fps: number};
  scenes: Scene[];
  metadata?: Record<string, unknown>;
};
