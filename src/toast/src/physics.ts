// Deterministische Physik + Zeitachse für das Toast-Video.
// Einheiten: 1 Szenen-Einheit = 1 dm (10 cm). Tisch = 7,5 dm = 75 cm.
import * as THREE from 'three';

export const FPS = 60;
export const DURATION_S = 45;

export const G = 98.1; // dm/s²
export const TABLE_H = 7.5;
export const TOAST_W = 1.2; // Breite (x) in dm
export const TOAST_T = 0.15; // Dicke in dm
export const HALF_T = TOAST_T / 2;

export const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const smooth = (a: number, b: number, t: number) => {
  const x = clamp((t - a) / (b - a));
  return x * x * (3 - 2 * x);
};
export const smoother = (a: number, b: number, t: number) => {
  const x = clamp((t - a) / (b - a));
  return x * x * x * (x * (x * 6 - 15) + 10);
};
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const easeOutCubic = (x: number) => 1 - Math.pow(1 - clamp(x), 3);

// ---------- Kippen über die Kante + freier Fall ----------
const X_OVER = 0.06; // Schwerpunkt minimal hinter der Kante beim Start des Kippens
const THETA_SEP = (32 * Math.PI) / 180; // Ablösewinkel
const TAU_SEP = 0.12; // s bis zur Ablösung von der Kante

function pivotPose(tau: number) {
  // Rotation um die Tischkante (0, TABLE_H), quadratisch beschleunigt
  const k = clamp(tau / TAU_SEP);
  const th = THETA_SEP * k * k;
  const c = Math.cos(-th), s = Math.sin(-th);
  const ox = X_OVER, oy = HALF_T;
  return { x: ox * c - oy * s, y: TABLE_H + ox * s + oy * c, th };
}

const sepA = pivotPose(TAU_SEP);
const sepB = pivotPose(TAU_SEP - 1e-4);
const VX = (sepA.x - sepB.x) / 1e-4 + 0.9; // kleiner Vorwärtsschub vom Rutschen
const VY = (sepA.y - sepB.y) / 1e-4;

function flightTime(y0: number, vy: number, yEnd: number) {
  // y0 + vy t - g/2 t² = yEnd
  const a = -G / 2, b = vy, c = y0 - yEnd;
  return (-b - Math.sqrt(b * b - 4 * a * c)) / (2 * a);
}

export const T_FLIGHT = flightTime(sepA.y, VY, HALF_T);
export const TAU_LAND = TAU_SEP + T_FLIGHT; // ≈ 0,39 s
const OMEGA = (Math.PI - THETA_SEP) / T_FLIGHT; // landet exakt bei 180°
export const OMEGA_DEG = (OMEGA * 180) / Math.PI;
export const LAND_X = sepA.x + VX * T_FLIGHT;

export function toastPoseAtTau(tau: number) {
  if (tau <= 0) return { x: X_OVER, y: TABLE_H + HALF_T, th: 0 };
  if (tau < TAU_SEP) return pivotPose(tau);
  const dt = Math.min(tau, TAU_LAND) - TAU_SEP;
  return {
    x: sepA.x + VX * dt,
    y: sepA.y + VY * dt - (G / 2) * dt * dt,
    th: THETA_SEP + OMEGA * dt,
  };
}

// ---------- Zeitlupe: Video-Sekunden -> physikalische Zeit τ ----------
export const FALL_START = 5.0;
export const FALL_END = 28.5;
const BT_A = 17.6, BT_B = 23.4; // "Bullet Time"
function speed(t: number) {
  const inBT = smooth(BT_A - 1.0, BT_A, t) * (1 - smooth(BT_B, BT_B + 1.0, t));
  const ramp = smooth(FALL_START, FALL_START + 1.2, t); // sanftes Anlaufen
  return (0.15 + 0.85 * ramp) * lerp(1, 0.1, inBT);
}
const STEPS = 4000;
const cum: number[] = [0];
{
  const dt = (FALL_END - FALL_START) / STEPS;
  for (let i = 1; i <= STEPS; i++) {
    const t = FALL_START + (i - 0.5) * dt;
    cum.push(cum[i - 1] + speed(t) * dt);
  }
}
const SCALE = TAU_LAND / cum[STEPS];
export function tauAt(t: number) {
  if (t <= FALL_START) return 0;
  if (t >= FALL_END) return TAU_LAND;
  const f = ((t - FALL_START) / (FALL_END - FALL_START)) * STEPS;
  const i = Math.floor(f);
  return lerp(cum[i], cum[Math.min(STEPS, i + 1)], f - i) * SCALE;
}
/** Zeitlupen-Faktor (wie viele Video-Sekunden pro Echt-Sekunde) */
export function slowMoAt(t: number) {
  return 1 / (speed(t) * SCALE);
}

export type Pose = { x: number; y: number; z: number; th: number; squash: number };

export function toastPose(t: number): Pose {
  if (t < FALL_START) {
    // Rutscht ruhig Richtung Kante
    const k = easeOutCubic((t - 0.3) / 4.7);
    const x = lerp(-1.6, X_OVER, clamp(k));
    return { x, y: TABLE_H + HALF_T, z: 0, th: 0, squash: 0 };
  }
  const p = toastPoseAtTau(tauAt(t));
  // kleiner, weicher Aufprall
  const sq = t > FALL_END ? Math.exp(-(t - FALL_END) * 5) * Math.sin((t - FALL_END) * 14) * 0.25 : 0;
  return { x: p.x, y: p.y, z: 0, th: p.th, squash: sq };
}

// ---------- 3-Meter-Tisch (Lösung) ----------
export const TALL_H = 30;
export const TALL_EDGE_X = 3.2;
export const GHOST_START = 33.2;
export const GHOST_END = 37.6;
const T2 = flightTime(TALL_H + HALF_T, VY, HALF_T);
const OMEGA2 = (2 * Math.PI - THETA_SEP) / T2;
export const GHOST_LAND_X = TALL_EDGE_X + X_OVER + VX * T2;
export function ghostPoseAtTau(tau: number) {
  if (tau <= 0) return { x: TALL_EDGE_X + X_OVER, y: TALL_H + HALF_T, th: 0 };
  if (tau < TAU_SEP) {
    const p = pivotPose(tau);
    return { x: p.x + TALL_EDGE_X, y: p.y - TABLE_H + TALL_H, th: p.th };
  }
  const dt = Math.min(tau - TAU_SEP, T2);
  return {
    x: TALL_EDGE_X + sepA.x + VX * dt,
    y: sepA.y - TABLE_H + TALL_H + VY * dt - (G / 2) * dt * dt,
    th: THETA_SEP + OMEGA2 * dt,
  };
}
export const GHOST_TAU_END = TAU_SEP + T2;
export function ghostTauAt(t: number) {
  const k = clamp((t - GHOST_START) / (GHOST_END - GHOST_START));
  // leicht verlangsamt am Anfang
  return GHOST_TAU_END * (k * k * 0.35 + k * 0.65);
}

// ---------- Kamera ----------
type Shot = { pos: THREE.Vector3; target: THREE.Vector3; fov: number };
const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);

function shotIntro(t: number): Shot {
  const k = smoother(0, 5.5, t);
  return {
    pos: V(lerp(5.4, 3.0, k), lerp(11.6, 9.4, k), lerp(8.6, 7.0, k)),
    target: V(lerp(-1.0, 0.1, k), lerp(7.0, 7.9, k), 0),
    fov: 34,
  };
}
function followTarget(t: number) {
  const p = toastPose(t);
  const lag = toastPose(Math.max(0, t - 0.6));
  return V(lerp(p.x, lag.x, 0.35) + 0.15, lerp(p.y, lag.y, 0.35) + 0.55, 0);
}
function shotFollow(t: number): Shot {
  const tg = followTarget(t);
  // Orbit während der Bullet Time
  const orb = smoother(16.8, 21.5, t) * (1 - smoother(22.5, 26.5, t));
  const ang = lerp(0.18, 0.95, orb);
  const r = lerp(7.6, 6.4, orb);
  const lift = lerp(1.4, 0.6, orb);
  return {
    pos: V(tg.x + Math.sin(ang) * r, tg.y + lift, Math.cos(ang) * r),
    target: tg,
    fov: 36,
  };
}
function shotLanding(t: number): Shot {
  const k = smoother(28, 31, t);
  return {
    pos: V(LAND_X + lerp(2.2, 2.8, k), lerp(2.0, 1.4, k), lerp(5.4, 4.6, k)),
    target: V(LAND_X - 0.1, 0.75, 0),
    fov: 36,
  };
}
function shotTall(t: number): Shot {
  const k = smoother(31, 36.5, t);
  return {
    pos: V(lerp(14, 16, k), lerp(14, 17, k), lerp(44, 48, k)),
    target: V(lerp(2.4, 2.6, k), lerp(12.5, 14, k), 0),
    fov: 40,
  };
}
function shotFloor(t: number): Shot {
  const k = smoother(38, 45, t);
  return {
    pos: V(LAND_X + lerp(2.6, 1.8, k), lerp(2.0, 1.5, k), lerp(5.0, 3.8, k)),
    target: V(LAND_X - 0.05, lerp(0.8, 0.6, k), 0),
    fov: 36,
  };
}

function blend(a: Shot, b: Shot, k: number): Shot {
  return {
    pos: a.pos.clone().lerp(b.pos, k),
    target: a.target.clone().lerp(b.target, k),
    fov: lerp(a.fov, b.fov, k),
  };
}

export function cameraAt(t: number): Shot {
  if (t < 7) return blend(shotIntro(t), shotFollow(t), smoother(4.4, 7, t));
  if (t < 28.8) return blend(shotFollow(t), shotLanding(t), smoother(26.8, 28.8, t));
  if (t < 33.5) return blend(shotLanding(t), shotTall(t), smoother(31, 33.5, t));
  if (t < 38) return shotTall(t);
  return blend(shotTall(t), shotFloor(t), smoother(38, 41.2, t));
}

export const W = 1080, H = 1920;
const projCam = new THREE.PerspectiveCamera(36, W / H, 0.05, 400);
/** Projiziert einen 3D-Punkt auf Bildschirm-Pixel (für HUD-Labels). */
export function project(t: number, p: THREE.Vector3) {
  const c = cameraAt(t);
  projCam.fov = c.fov;
  projCam.position.copy(c.pos);
  projCam.lookAt(c.target);
  projCam.updateProjectionMatrix();
  projCam.updateMatrixWorld();
  const v = p.clone().project(projCam);
  return { x: (v.x * 0.5 + 0.5) * W, y: (-v.y * 0.5 + 0.5) * H, behind: v.z > 1 };
}
