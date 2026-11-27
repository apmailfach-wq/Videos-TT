import React from 'react';
import { Composition } from 'remotion';
import { ToastVideo } from './Video';
import { DURATION_S, FPS, H, W } from './physics';

export const RemotionRoot: React.FC = () => (
  <Composition id="Toast" component={ToastVideo} durationInFrames={DURATION_S * FPS} fps={FPS} width={W} height={H} />
);
