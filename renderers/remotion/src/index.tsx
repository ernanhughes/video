import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {VideoComposition} from './composition';
import type {VideoProject} from './types';

const placeholder: VideoProject = {
  schema_version: '0.3',
  title: 'Video',
  canvas: {width: 1280, height: 720, fps: 30},
  scenes: [],
  metadata: {},
};

const duration = (project: VideoProject) => {
  const overlap = project.scenes.slice(0, -1).reduce((sum, scene) => sum + scene.transition_out.duration, 0);
  return project.scenes.reduce((sum, scene) => sum + scene.duration, 0) - overlap;
};

const Root: React.FC = () => (
  <Composition
    id="VideoProject"
    component={VideoComposition}
    durationInFrames={1}
    fps={30}
    width={1280}
    height={720}
    defaultProps={{project: placeholder}}
    calculateMetadata={({props}) => ({
      durationInFrames: Math.max(1, Math.round(duration(props.project) * props.project.canvas.fps)),
      fps: props.project.canvas.fps,
      width: props.project.canvas.width,
      height: props.project.canvas.height,
    })}
  />
);

registerRoot(Root);
