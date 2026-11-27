import React, { useEffect, useState } from 'react';
import { AbsoluteFill, Audio, continueRender, delayRender, staticFile, useCurrentFrame } from 'remotion';
import { ThreeCanvas } from '@remotion/three';
import { Scene3D } from './Scene3D';
import { Hud } from './Hud';
import { FPS, H, W } from './physics';

const FONTS: [string, string, string][] = [
  ['Inter', 'Inter-Medium.otf', '500'],
  ['Inter', 'Inter-SemiBold.otf', '600'],
  ['InterDisplay', 'InterDisplay-SemiBold.otf', '600'],
  ['InterDisplay', 'InterDisplay-Bold.otf', '700'],
  ['JBMono', 'JetBrainsMono-Medium.ttf', '500'],
];

export const ToastVideo: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const [handle] = useState(() => delayRender('fonts'));
  useEffect(() => {
    Promise.all(
      FONTS.map(([fam, file, w]) => {
        const f = new FontFace(fam, `url(${staticFile('fonts/' + file)})`, { weight: w });
        return f.load().then((l) => document.fonts.add(l));
      })
    ).then(() => continueRender(handle));
  }, [handle]);

  return (
    <AbsoluteFill style={{ background: '#0F1115', fontFamily: 'Inter' }}>
      <ThreeCanvas width={W} height={H} gl={{ antialias: true, preserveDrawingBuffer: true }} dpr={1} shadows>
        <Scene3D t={t} />
      </ThreeCanvas>
      <Hud t={t} />
      <Audio src={staticFile('audio.wav')} />
    </AbsoluteFill>
  );
};
