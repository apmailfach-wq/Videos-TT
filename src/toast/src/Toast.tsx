import React, { useMemo } from 'react';
import * as THREE from 'three';
import { TOAST_T, TOAST_W } from './physics';

// Silhouette einer Toastscheibe (in der XY-Ebene, zentriert)
function toastShape(scale = 1, wobble = 0) {
  const w = (TOAST_W / 2) * scale;
  const s = new THREE.Shape();
  const bottom = -0.56 * scale;
  const shoulder = 0.28 * scale;
  const r = 0.07 * scale;
  s.moveTo(-w + r, bottom);
  s.lineTo(w - r, bottom);
  s.quadraticCurveTo(w, bottom, w, bottom + r);
  s.lineTo(w * 0.97, shoulder);
  // Krone: zwei Bögen
  s.bezierCurveTo(w * 1.1, shoulder + 0.18 * scale, w * 0.95, 0.6 * scale, w * 0.45, 0.6 * scale);
  s.bezierCurveTo(w * 0.2, 0.62 * scale, w * 0.05, 0.56 * scale, 0, 0.55 * scale);
  s.bezierCurveTo(-w * 0.05, 0.56 * scale, -w * 0.2, 0.62 * scale, -w * 0.45, 0.6 * scale);
  s.bezierCurveTo(-w * 0.95, 0.6 * scale, -w * 1.1, shoulder + 0.18 * scale, -w * 0.97, shoulder);
  s.lineTo(-w, bottom + r);
  s.quadraticCurveTo(-w, bottom, -w + r, bottom);
  if (wobble > 0) {
    const raw = s.getSpacedPoints(160);
    const out = new THREE.Shape();
    raw.forEach((p, i) => {
      const ang = Math.atan2(p.y, p.x);
      const k = 1 + wobble * (Math.sin(ang * 5 + 1.3) * 0.6 + Math.sin(ang * 11 + 0.4) * 0.4);
      const q = new THREE.Vector2(p.x * k, p.y * k);
      if (i === 0) out.moveTo(q.x, q.y);
      else out.lineTo(q.x, q.y);
    });
    return out;
  }
  return s;
}

function seeded(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function crumbTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 512;
  const g = c.getContext('2d')!;
  const rnd = seeded(7);
  const grd = g.createRadialGradient(256, 256, 40, 256, 256, 360);
  grd.addColorStop(0, '#f3dcaa');
  grd.addColorStop(0.75, '#e9c487');
  grd.addColorStop(1, '#c98f4c');
  g.fillStyle = grd;
  g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 2600; i++) {
    const x = rnd() * 512, y = rnd() * 512, r = rnd() * rnd() * 5 + 0.6;
    g.fillStyle = `rgba(${150 + rnd() * 40},${100 + rnd() * 30},${50 + rnd() * 20},${0.12 + rnd() * 0.25})`;
    g.beginPath();
    g.ellipse(x, y, r, r * (0.5 + rnd() * 0.6), rnd() * 3, 0, Math.PI * 2);
    g.fill();
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}
function crustTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d')!;
  const rnd = seeded(3);
  g.fillStyle = '#9a5a26';
  g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 900; i++) {
    g.fillStyle = `rgba(${90 + rnd() * 60},${45 + rnd() * 30},${15},${0.2 + rnd() * 0.3})`;
    g.fillRect(rnd() * 256, rnd() * 256, 1 + rnd() * 6, 1 + rnd() * 2);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

export const Toast: React.FC<{
  ghost?: boolean;
  opacity?: number;
  butterGlow?: number;
  splat?: number;
}> = ({ ghost = false, opacity = 1, butterGlow = 0, splat = 0 }) => {
  const geo = useMemo(() => {
    const g = new THREE.ExtrudeGeometry(toastShape(1), {
      depth: TOAST_T - 0.04,
      bevelEnabled: true,
      bevelThickness: 0.02,
      bevelSize: 0.02,
      bevelSegments: 3,
      curveSegments: 24,
    });
    g.translate(0, 0, -(TOAST_T - 0.04) / 2);
    // UVs für Deckflächen auf [0,1] normieren
    const uv = g.attributes.uv as THREE.BufferAttribute;
    for (let i = 0; i < uv.count; i++) {
      uv.setXY(i, uv.getX(i) / TOAST_W + 0.5, uv.getY(i) / TOAST_W + 0.5);
    }
    return g;
  }, []);
  const butterGeo = useMemo(() => {
    const g = new THREE.ExtrudeGeometry(toastShape(0.84, 0.018), {
      depth: 0.006,
      bevelEnabled: true,
      bevelThickness: 0.022,
      bevelSize: 0.03,
      bevelSegments: 6,
      curveSegments: 24,
    });
    return g;
  }, []);
  const edges = useMemo(() => new THREE.EdgesGeometry(geo, 30), [geo]);

  const mats = useMemo(() => {
    if (ghost) return null;
    const crumb = new THREE.MeshStandardMaterial({ map: crumbTexture(), roughness: 0.92, bumpMap: undefined });
    const crust = new THREE.MeshStandardMaterial({ map: crustTexture(), roughness: 0.75, color: '#ffffff' });
    return [crumb, crust];
  }, [ghost]);

  const butterMat = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: '#ffc21a',
        roughness: 0.12,
        envMapIntensity: 1.6,
        metalness: 0,
        clearcoat: 1,
        clearcoatRoughness: 0.08,
        sheen: 0.15,
        sheenColor: new THREE.Color('#fff3b0'),
        emissive: new THREE.Color('#ffb300'),
        emissiveIntensity: 0,
        transparent: ghost,
      }),
    [ghost]
  );
  butterMat.emissiveIntensity = butterGlow * 0.55;
  butterMat.opacity = ghost ? opacity : 1;

  // Shape liegt in XY, Extrusion entlang z. Drehen, damit Seite A (Butter) nach oben zeigt.
  return (
    <group rotation={[-Math.PI / 2, 0, 0]}>
      {ghost ? (
        <>
          <mesh geometry={geo}>
            <meshBasicMaterial color="#5ac8fa" transparent opacity={0.1 * opacity} depthWrite={false} blending={THREE.AdditiveBlending} />
          </mesh>
          <lineSegments geometry={edges}>
            <lineBasicMaterial color="#8fdcff" transparent opacity={0.85 * opacity} />
          </lineSegments>
        </>
      ) : (
        <mesh geometry={geo} material={mats!} castShadow receiveShadow />
      )}
      <mesh
        geometry={butterGeo}
        material={butterMat}
        position={[0, 0, TOAST_T / 2 - 0.004]}
        scale={[1 + splat * 0.22, 1 + splat * 0.22, 1 - splat * 0.6]}
        castShadow
      />
    </group>
  );
};
