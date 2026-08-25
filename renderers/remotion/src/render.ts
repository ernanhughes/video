import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import type {VideoProject} from './types';

const [, , projectPathArg, outputPathArg] = process.argv;
if (!projectPathArg || !outputPathArg) {
  console.error('usage: npm run render -- <project.json> <output.mp4>');
  process.exit(2);
}

const projectPath = path.resolve(projectPathArg);
const outputPath = path.resolve(outputPathArg);
const project = JSON.parse(fs.readFileSync(projectPath, 'utf8')) as VideoProject;
const sourceRoot = path.dirname(projectPath);
const here = path.dirname(fileURLToPath(import.meta.url));
const entryPoint = path.resolve(here, 'index.tsx');

fs.mkdirSync(path.dirname(outputPath), {recursive: true});

const serveUrl = await bundle({
  entryPoint,
  publicDir: sourceRoot,
  webpackOverride: (config) => config,
});

const inputProps = {project};
const composition = await selectComposition({
  serveUrl,
  id: 'VideoProject',
  inputProps,
});

await renderMedia({
  composition,
  serveUrl,
  codec: 'h264',
  outputLocation: outputPath,
  inputProps,
});

console.log(outputPath);
