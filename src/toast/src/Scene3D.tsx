import React, { useMemo } from 'react';
import * as THREE from 'three';
import { useThree } from '@react-three/fiber';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { Toast } from './Toast';
import {
  cameraAt, clamp, FALL_END, GHOST_END, GHOST_START, ghostPoseAtTau, ghostTauAt, GHOST_TAU_END,
  LAND_X, smooth, TABLE_H, TALL_EDGE_X, TALL_H, tauAt, toastPose,
} from './physics';

const BG = '#0F1115';

const CameraRig: React.FC<{ t: number }> = ({ t }) => {
  const { camera, scene, gl } = useThree();
  const c = cameraAt(t);
  const cam = camera as THREE.PerspectiveCamera;
  cam.fov = c.fov;
  cam.near = 0.05;
  cam.far = 400;
  cam.position.copy(c.pos);
  cam.lookAt(c.target);
  cam.updateProjectionMatrix();

  useMemo(() => {
    const pm = new THREE.PMREMGenerator(gl);
    scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.background = new THREE.Color(BG);
    scene.fog = new THREE.Fog(BG, 14, 70);
    gl.toneMapping = THREE.ACESFilmicToneMapping;
    gl.toneMappingExposure = 1.05;
    gl.shadowMap.enabled = true;
    gl.shadowMap.type = THREE.PCFSoftShadowMap;
  }, [gl, scene]);
  return null;
};

// Technisches Raster auf Boden + Rückwand
const Grid: React.FC = () => {
  const floor = useMemo(() => {
    const g = new THREE.GridHelper(80, 160, '#2a3140', '#1a1f28');
    (g.material as THREE.Material).transparent = true;
    (g.material as THREE.Material).opacity = 0.9;
    return g;
  }, []);
  const fine = useMemo(() => {
    const g = new THREE.GridHelper(80, 800, '#161a22', '#161a22');
    (g.material as THREE.Material).transparent = true;
    (g.material as THREE.Material).opacity = 0.5;
    return g;
  }, []);
  const wall = useMemo(() => {
    const g = new THREE.GridHelper(80, 80, '#1d2330', '#171b23');
    g.rotation.x = Math.PI / 2;
    g.position.set(0, 40, -9);
    return g;
  }, []);
  return (
    <>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.002, 0]} receiveShadow>
        <planeGeometry args={[200, 200]} />
        <meshStandardMaterial color="#12151b" roughness={0.55} metalness={0.2} />
      </mesh>
      <primitive object={fine} position={[0, 0.001, 0]} />
      <primitive object={floor} position={[0, 0.002, 0]} />
      <primitive object={wall} />
    </>
  );
};

// Minimalistischer Studiotisch mit leuchtender Kante
const Table: React.FC = () => (
  <group>
    <mesh position={[-4, TABLE_H - 0.2, 0]} castShadow receiveShadow>
      <boxGeometry args={[8, 0.4, 5]} />
      <meshStandardMaterial color="#1b1f27" roughness={0.35} metalness={0.4} />
    </mesh>
    <mesh position={[0.003, TABLE_H - 0.012, 0]}>
      <boxGeometry args={[0.006, 0.018, 5]} />
      <meshBasicMaterial color="#5ac8fa" toneMapped={false} />
    </mesh>
    <mesh position={[-4, TABLE_H + 0.001, 2.5]}>
      <boxGeometry args={[8, 0.004, 0.01]} />
      <meshBasicMaterial color="#3d6c88" />
    </mesh>
    {[[-0.6, 2.1], [-0.6, -2.1], [-7.4, 2.1], [-7.4, -2.1]].map(([x, z], i) => (
      <mesh key={i} position={[x, (TABLE_H - 0.4) / 2, z]} castShadow>
        <boxGeometry args={[0.18, TABLE_H - 0.4, 0.18]} />
        <meshStandardMaterial color="#171a21" roughness={0.4} metalness={0.5} />
      </mesh>
    ))}
  </group>
);

// Leuchtende Strömungslinien (statische Röhren, Puls läuft per Shader)
const flowVert = /* glsl */ `
  attribute float u;
  varying float vU;
  varying vec3 vW;
  void main(){
    vU = u;
    vec4 w = modelMatrix * vec4(position,1.0);
    vW = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }`;
const flowFrag = /* glsl */ `
  uniform float uPhase; uniform float uAlpha; uniform float uHalo;
  varying float vU;
  void main(){
    float ends = smoothstep(0.0,0.18,vU)*(1.0-smoothstep(0.82,1.0,vU));
    float p = fract(vU*2.2 - uPhase);
    float pulse = smoothstep(0.0,0.12,p)*(1.0-smoothstep(0.12,0.4,p));
    vec3 col = mix(vec3(0.20,0.62,0.95), vec3(0.85,0.97,1.0), pulse);
    float a = (0.14 + 0.75*pulse) * ends * uAlpha * uHalo;
    gl_FragColor = vec4(col*a, a);
  }`;

function makeFlowLines() {
  const lines: { geo: THREE.TubeGeometry; halo: THREE.TubeGeometry; seed: number }[] = [];
  const zs = [-0.42, 0, 0.42];
  const xs = [-1.15, -0.8, -0.5, -0.22, 0.22, 0.5, 0.8, 1.15];
  let seed = 0;
  for (const z of zs) {
    for (const x0 of xs) {
      if (z !== 0 && Math.abs(x0) > 1) continue;
      const pts: THREE.Vector3[] = [];
      for (let i = 0; i <= 60; i++) {
        const y = -3.6 + (i / 60) * 5.8;
        const bump = Math.exp(-(y * y) / 0.55);
        const push = (0.75 / (Math.abs(x0) + 0.25)) * 0.42 * bump * Math.sign(x0);
        const wake = y > 0 ? Math.sin(y * 3 + seed) * 0.05 * Math.exp(-y * 0.4) * (1 - bump) : 0;
        pts.push(new THREE.Vector3(x0 + push + wake, y, z * (1 + bump * 0.3)));
      }
      const curve = new THREE.CatmullRomCurve3(pts);
      const geo = new THREE.TubeGeometry(curve, 140, 0.007, 6, false);
      const halo = new THREE.TubeGeometry(curve, 140, 0.026, 6, false);
      for (const g of [geo, halo]) {
        const n = g.attributes.position.count;
        const u = new Float32Array(n);
        const uv = g.attributes.uv;
        for (let i = 0; i < n; i++) u[i] = uv.getX(i);
        g.setAttribute('u', new THREE.BufferAttribute(u, 1));
      }
      lines.push({ geo, halo, seed: seed++ });
    }
  }
  return lines;
}

const FlowLines: React.FC<{ t: number; pos: THREE.Vector3; alpha: number }> = ({ t, pos, alpha }) => {
  const lines = useMemo(makeFlowLines, []);
  const mats = useMemo(
    () =>
      lines.map((l) => {
        const mk = (halo: number) =>
          new THREE.ShaderMaterial({
            vertexShader: flowVert,
            fragmentShader: flowFrag,
            uniforms: { uPhase: { value: 0 }, uAlpha: { value: 1 }, uHalo: { value: halo } },
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
          });
        return { core: mk(1), halo: mk(0.22), off: (l.seed * 0.137) % 1 };
      }),
    [lines]
  );
  const tau = tauAt(t);
  if (alpha <= 0.001) return null;
  return (
    <group position={pos}>
      {lines.map((l, i) => {
        const m = mats[i];
        const ph = tau * 9 + t * 0.06 + m.off;
        m.core.uniforms.uPhase.value = ph;
        m.halo.uniforms.uPhase.value = ph;
        m.core.uniforms.uAlpha.value = alpha;
        m.halo.uniforms.uAlpha.value = alpha;
        return (
          <group key={i}>
            <mesh geometry={l.geo} material={m.core} />
            <mesh geometry={l.halo} material={m.halo} />
          </group>
        );
      })}
    </group>
  );
};

// Rotationsachse + Winkel-Bogen (Winkelmesser)
const RotationGizmo: React.FC<{ pos: THREE.Vector3; th: number; alpha: number; crit: number }> = ({ pos, th, alpha, crit }) => {
  const arc = useMemo(() => new THREE.RingGeometry(0.98, 1.0, 96, 1, 0, Math.max(0.001, th)), [th]);
  const fill = useMemo(() => new THREE.RingGeometry(0.0, 0.98, 96, 1, 0, Math.max(0.001, th)), [th]);
  const ticks = useMemo(() => {
    const pts: THREE.Vector3[] = [];
    for (let d = 0; d <= 360; d += 10) {
      const a = (d * Math.PI) / 180;
      const r1 = d % 90 === 0 ? 1.08 : 1.04;
      pts.push(new THREE.Vector3(Math.cos(a) * 1.0, Math.sin(a) * 1.0, 0));
      pts.push(new THREE.Vector3(Math.cos(a) * r1, Math.sin(a) * r1, 0));
    }
    return new THREE.BufferGeometry().setFromPoints(pts);
  }, []);
  const axis = useMemo(() => {
    const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, -2.2), new THREE.Vector3(0, 0, 2.2)]);
    return g;
  }, []);
  const axisLine = useMemo(() => {
    const l = new THREE.Line(axis, new THREE.LineDashedMaterial({ color: '#9fe3ff', dashSize: 0.08, gapSize: 0.06, transparent: true }));
    l.computeLineDistances();
    return l;
  }, [axis]);
  (axisLine.material as THREE.LineDashedMaterial).opacity = alpha;
  if (alpha <= 0.001) return null;
  const col = new THREE.Color('#5ac8fa').lerp(new THREE.Color('#ff6b5e'), crit);
  // Bogen startet "oben" (Butter zeigt nach oben) und dreht im Uhrzeigersinn
  return (
    <group position={pos}>
      <primitive object={axisLine} />
      <group position={[0, 0, -0.3]} rotation={[0, 0, Math.PI / 2]} scale={[1, -1, 1]}>
        <mesh geometry={fill}>
          <meshBasicMaterial color={col} transparent opacity={0.07 * alpha} depthWrite={false} side={THREE.DoubleSide} />
        </mesh>
        <mesh geometry={arc}>
          <meshBasicMaterial color={col} transparent opacity={0.95 * alpha} side={THREE.DoubleSide} toneMapped={false} />
        </mesh>
        <lineSegments geometry={ticks}>
          <lineBasicMaterial color="#6b7a90" transparent opacity={0.7 * alpha} />
        </lineSegments>
        {/* 180°-Markierung */}
        <mesh position={[-1.0, 0, 0]}>
          <circleGeometry args={[0.035, 24]} />
          <meshBasicMaterial color="#ff6b5e" transparent opacity={alpha} toneMapped={false} />
        </mesh>
      </group>
      <mesh position={[0, 0, 2.2]} rotation={[Math.PI / 2, 0, 0]}>
        <coneGeometry args={[0.035, 0.1, 16]} />
        <meshBasicMaterial color="#9fe3ff" transparent opacity={alpha} />
      </mesh>
    </group>
  );
};

// Hologramm-Tisch: 3 Meter
const TallTable: React.FC<{ alpha: number }> = ({ alpha }) => {
  const box = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(8, 0.4, 5)), []);
  const leg = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(0.18, TALL_H - 0.4, 0.18)), []);
  if (alpha <= 0.001) return null;
  const grow = smooth(0, 1, alpha);
  return (
    <group position={[TALL_EDGE_X + 4, 0, -0.6]} scale={[1, grow, 1]}>
      <lineSegments geometry={box} position={[0, TALL_H - 0.2, 0]}>
        <lineBasicMaterial color="#5ac8fa" transparent opacity={alpha} />
      </lineSegments>
      <mesh position={[0, TALL_H - 0.2, 0]}>
        <boxGeometry args={[8, 0.4, 5]} />
        <meshBasicMaterial color="#5ac8fa" transparent opacity={0.06 * alpha} depthWrite={false} />
      </mesh>
      {[[-3.4, 2.1], [-3.4, -2.1], [3.4, 2.1], [3.4, -2.1]].map(([x, z], i) => (
        <lineSegments key={i} geometry={leg} position={[x, (TALL_H - 0.4) / 2, z]}>
          <lineBasicMaterial color="#5ac8fa" transparent opacity={0.6 * alpha} />
        </lineSegments>
      ))}
    </group>
  );
};

const GhostFall: React.FC<{ t: number; alpha: number }> = ({ t, alpha }) => {
  if (alpha <= 0.001) return null;
  const tau = ghostTauAt(t);
  const trail = [];
  const N = 9;
  for (let i = 0; i < N; i++) {
    const tt = tau - i * 0.028;
    if (tt < 0) break;
    const p = ghostPoseAtTau(Math.min(tt, GHOST_TAU_END));
    trail.push(
      <group key={i} position={[p.x, p.y, -0.6]} rotation={[0, 0, -p.th]} scale={2.2}>
        <Toast ghost opacity={alpha * (i === 0 ? 1 : 0.35 * (1 - i / N))} butterGlow={1} />
      </group>
    );
  }
  return <>{trail}</>;
};

export const Scene3D: React.FC<{ t: number }> = ({ t }) => {
  const p = toastPose(t);
  const pos = new THREE.Vector3(p.x, p.y, p.z);
  const flowA = smooth(6.2, 8.5, t) * (1 - smooth(27.2, 28.6, t));
  const gizA = smooth(7.2, 9.0, t) * (1 - smooth(28.6, 30, t));
  const crit = smooth(26.5, 28.4, t);
  const xray = smooth(17.2, 18.4, t) * (1 - smooth(23.6, 25, t));
  const splat = smooth(FALL_END, FALL_END + 0.35, t);
  const tallA = smooth(31.8, 33.2, t) * (1 - smooth(39.5, 41, t));
  const ghostA = smooth(GHOST_START - 0.6, GHOST_START, t) * (1 - smooth(39.5, 41, t));
  const keyInt = 2.4;

  return (
    <>
      <CameraRig t={t} />
      <ambientLight intensity={0.12} />
      <hemisphereLight args={['#9fb6d6', '#0b0d10', 0.35]} />
      <directionalLight
        position={[4, 16, 8]}
        intensity={keyInt}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-6}
        shadow-camera-right={6}
        shadow-camera-top={12}
        shadow-camera-bottom={-4}
        shadow-camera-near={1}
        shadow-camera-far={40}
        shadow-bias={-0.0004}
      />
      <spotLight position={[-6, 12, -6]} angle={0.5} penumbra={1} intensity={60} color="#7fbfff" distance={40} />
      <pointLight position={[LAND_X + 2, 2.5, 3]} intensity={6 + 10 * splat} color="#ffe6b0" distance={9} />
      <Grid />
      <Table />
      <group position={pos} rotation={[0, 0, -p.th]} scale={[1 + p.squash * 0.15, 1 - p.squash, 1 + p.squash * 0.15]}>
        <Toast butterGlow={xray * 0.9 + crit * 0.4} splat={splat} />
      </group>
      <FlowLines t={t} pos={pos} alpha={flowA * (1 - xray * 0.6)} />
      <RotationGizmo pos={pos} th={p.th} alpha={gizA} crit={crit} />
      <TallTable alpha={tallA} />
      <GhostFall t={t} alpha={ghostA} />
      {/* Schwerpunkt-Marker während der Röntgen-Analyse */}
      {xray > 0.01 && (
        <group position={pos} rotation={[0, 0, -p.th]}>
          <mesh position={[0, 0.03, 0]}>
            <sphereGeometry args={[0.045, 24, 16]} />
            <meshBasicMaterial color="#ffd84a" transparent opacity={xray} toneMapped={false} depthTest={false} />
          </mesh>
        </group>
      )}
      {/* weiches Licht auf dem Boden nach der Landung */}
      <mesh position={[LAND_X, 0.004, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[1.6, 48]} />
        <meshBasicMaterial color="#ffd84a" transparent opacity={0.05 * clamp(splat) * (1 - tallA)} depthWrite={false} />
      </mesh>
    </>
  );
};
