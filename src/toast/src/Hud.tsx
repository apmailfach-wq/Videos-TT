import React from 'react';
import * as THREE from 'three';
import {
  clamp, FALL_END, FALL_START, H, HALF_T, LAND_X, OMEGA_DEG, project, slowMoAt, smooth, TABLE_H, tauAt, toastPose, W,
} from './physics';

const C = {
  white: '#F2F4F7',
  dim: '#8A93A3',
  faint: 'rgba(138,147,163,0.35)',
  accent: '#5AC8FA',
  butter: '#FFD84A',
  crit: '#FF6B5E',
  ok: '#5EE29A',
};
const mono: React.CSSProperties = { fontFamily: 'JBMono', fontVariantNumeric: 'tabular-nums', letterSpacing: '0.04em' };
const de = (v: number, d = 1) => v.toFixed(d).replace('.', ',');

// ---------- Untertitel ----------
type Cap = { a: number; b: number; label: string; text: string; size?: number; hi?: string[] };
const CAPS: Cap[] = [
  { a: 0.25, b: 4.6, label: 'Wissenschaftliche Analyse', text: 'Warum dein Morgen eigentlich schon vor dem ersten Kaffee ruiniert ist.', size: 66, hi: ['ruiniert'] },
  { a: 5.0, b: 15.4, label: 'Falldynamik · Messreihe 01', text: 'Bei einer Standard-Tischhöhe von 75 cm reicht die Zeit exakt für eine halbe Drehung.', size: 60, hi: ['75 cm', 'halbe Drehung.'] },
  { a: 16.0, b: 23.8, label: 'Massenverteilung · Seite A', text: 'Die Butter erhöht das Gewicht auf Seite A um 4,2 Gramm.', size: 62, hi: ['4,2 Gramm.'] },
  { a: 24.2, b: 30.6, label: 'Prognose', text: 'Das Schicksal ist besiegelt.', size: 84, hi: ['besiegelt.'] },
  { a: 31.0, b: 38.0, label: 'Lösung laut Physik', text: 'Entweder 3 Meter hohe Tische kaufen –', size: 66, hi: ['3 Meter'] },
  { a: 38.2, b: 45.2, label: 'Lösung laut Physik · Alternative', text: '– oder das Toast direkt vom Boden essen.', size: 66, hi: ['vom Boden'] },
];

const Caption: React.FC<{ t: number; c: Cap }> = ({ t, c }) => {
  if (t < c.a - 0.1 || t > c.b + 0.6) return null;
  const out = 1 - smooth(c.b - 0.35, c.b + 0.15, t);
  const words = c.text.split(' ');
  const labelIn = smooth(c.a, c.a + 0.4, t);
  const per = Math.min(0.11, 1.6 / words.length);
  // Highlights: Wörter, die (Teil-)Treffer einer Highlight-Phrase sind
  const hiWords = new Set((c.hi ?? []).flatMap((h) => h.split(' ')));
  return (
    <div style={{ position: 'absolute', left: 84, right: 84, top: 250, opacity: out }}>
      <div
        style={{
          fontFamily: 'Inter', fontWeight: 600, fontSize: 25, letterSpacing: '0.22em', textTransform: 'uppercase',
          color: C.accent, opacity: labelIn, display: 'flex', alignItems: 'center', gap: 18, marginBottom: 26,
        }}
      >
        <div style={{ width: 46 * labelIn, height: 2, background: C.accent }} />
        {c.label}
      </div>
      <div style={{ fontFamily: 'InterDisplay', fontWeight: 600, fontSize: c.size ?? 64, lineHeight: 1.1, letterSpacing: '-0.025em', color: C.white }}>
        {words.map((w, i) => {
          const k = smooth(c.a + 0.15 + i * per, c.a + 0.15 + i * per + 0.45, t);
          const hi = hiWords.has(w);
          return (
            <span
              key={i}
              style={{
                display: 'inline-block', marginRight: '0.24em', opacity: k,
                transform: `translateY(${(1 - k) * 18}px)`, filter: `blur(${(1 - k) * 8}px)`,
                color: hi ? (c.label === 'Prognose' ? C.crit : C.butter) : C.white,
              }}
            >
              {w}
            </span>
          );
        })}
      </div>
    </div>
  );
};

// ---------- Ecken / Rahmen ----------
const Frame: React.FC<{ t: number }> = ({ t }) => {
  const a = smooth(0, 0.8, t);
  const L = 44, m = 48;
  const corner = (x: number, y: number, sx: number, sy: number) => (
    <path d={`M${x} ${y + sy * L} L${x} ${y} L${x + sx * L} ${y}`} stroke={C.faint} strokeWidth={2} fill="none" />
  );
  const blink = Math.floor(t * 1.2) % 2 === 0 ? 1 : 0.25;
  const fps = t < FALL_START ? 60 : Math.round(60 * slowMoAt(t));
  return (
    <>
      <svg width={W} height={H} style={{ position: 'absolute', inset: 0, opacity: a }}>
        {corner(m, 150, 1, 1)}
        {corner(W - m, 150, -1, 1)}
        {corner(m, 1560, 1, -1)}
        {corner(W - m, 1560, -1, -1)}
      </svg>
      <div style={{ position: 'absolute', top: 166, left: 84, right: 84, display: 'flex', justifyContent: 'space-between', opacity: a, ...mono, fontSize: 21, color: C.dim }}>
        <span>
          <span style={{ color: C.crit, opacity: blink }}>●</span>&nbsp; REC&nbsp;&nbsp;CAM A · 85 MM
        </span>
        <span>{t < FALL_START ? 'ECHTZEIT' : `${fps.toLocaleString('de-DE')} FPS`}</span>
      </div>
    </>
  );
};

// ---------- Datenleiste unten ----------
const DataBar: React.FC<{ t: number }> = ({ t }) => {
  const a = smooth(5.4, 6.4, t) * (1 - smooth(30.2, 31.2, t));
  if (a <= 0) return null;
  const tau = tauAt(t);
  const p = toastPose(t);
  const deg = (p.th * 180) / Math.PI;
  const h = Math.max(0, (p.y - HALF_T) * 10); // cm
  const crit = smooth(26.6, 28.3, t);
  const slow = t >= FALL_END ? 1 : slowMoAt(t);
  const Cell: React.FC<{ k: string; v: string; col?: string; w?: number }> = ({ k, v, col, w = 210 }) => (
    <div style={{ width: w }}>
      <div style={{ fontFamily: 'Inter', fontWeight: 500, fontSize: 19, letterSpacing: '0.18em', color: C.dim, marginBottom: 8 }}>{k}</div>
      <div style={{ ...mono, fontSize: 40, color: col ?? C.white }}>{v}</div>
    </div>
  );
  return (
    <div style={{ position: 'absolute', left: 84, right: 84, top: 1390, opacity: a }}>
      <div style={{ height: 1, background: C.faint, marginBottom: 22 }} />
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <Cell k="ZEIT" v={`${de(tau, 3)} s`} />
        <Cell k="WINKEL θ" v={`${de(deg, 1)}°`} col={crit > 0.5 ? C.crit : C.accent} w={220} />
        <Cell k="HÖHE" v={`${de(h, 1)} cm`} />
        <Cell k="ZEITLUPE" v={`1:${Math.round(slow)}`} w={170} />
      </div>
    </div>
  );
};

// ---------- Höhen-Lineal links ----------
const Ruler: React.FC<{ t: number }> = ({ t }) => {
  const a = smooth(5.8, 7, t) * (1 - smooth(28.6, 30, t));
  if (a <= 0) return null;
  const p = toastPose(t);
  const h = Math.max(0, (p.y - HALF_T) / TABLE_H);
  const top = 640, bot = 1290;
  const y = bot - h * (bot - top);
  const ticks = [];
  for (let i = 0; i <= 15; i++) {
    const yy = bot - (i / 15) * (bot - top);
    ticks.push(<line key={i} x1={i % 5 === 0 ? 0 : 8} x2={20} y1={yy} y2={yy} stroke={C.faint} strokeWidth={2} />);
  }
  return (
    <svg width={260} height={H} style={{ position: 'absolute', left: 52, top: 0, opacity: a }}>
      {ticks}
      <line x1={20} x2={20} y1={top} y2={bot} stroke={C.faint} strokeWidth={2} />
      <text x={30} y={top + 7} fill={C.dim} style={{ ...mono, fontSize: 18 }}>75</text>
      <text x={30} y={bot + 7} fill={C.dim} style={{ ...mono, fontSize: 18 }}>0 cm</text>
      <line x1={20} x2={20} y1={y} y2={bot} stroke={C.accent} strokeWidth={3} />
      <path d={`M24 ${y} l14 -8 v16 z`} fill={C.accent} />
    </svg>
  );
};

// ---------- 3D-verankerte Labels ----------
const Tag: React.FC<{ t: number; at: THREE.Vector3; dx: number; dy: number; a: number; title: string; sub?: string; col?: string; align?: 'l' | 'r' }> = ({
  t, at, dx, dy, a, title, sub, col = C.accent, align,
}) => {
  if (a <= 0.001) return null;
  const s = project(t, at);
  if (s.behind) return null;
  const ex = s.x + dx, ey = s.y + dy;
  const right = align ? align === 'l' : dx > 0;
  const len = Math.hypot(dx, dy) * a;
  return (
    <>
      <svg width={W} height={H} style={{ position: 'absolute', inset: 0, opacity: a }}>
        <circle cx={s.x} cy={s.y} r={6} fill="none" stroke={col} strokeWidth={2} />
        <circle cx={s.x} cy={s.y} r={2.5} fill={col} />
        <line x1={s.x} y1={s.y} x2={s.x + (dx / Math.hypot(dx, dy)) * len} y2={s.y + (dy / Math.hypot(dx, dy)) * len} stroke={col} strokeWidth={1.5} />
      </svg>
      <div
        style={{
          position: 'absolute', top: ey - 24, left: right ? ex + 12 : undefined, right: right ? undefined : W - ex + 12,
          opacity: smooth(0.4, 1, a), textAlign: right ? 'left' : 'right', whiteSpace: 'nowrap',
        }}
      >
        <div style={{ fontFamily: 'Inter', fontWeight: 600, fontSize: 24, letterSpacing: '0.14em', color: col, textTransform: 'uppercase' }}>{title}</div>
        {sub && <div style={{ ...mono, fontSize: 22, color: C.dim, marginTop: 6 }}>{sub}</div>}
      </div>
    </>
  );
};

const win = (t: number, a: number, b: number, f = 0.5) => smooth(a, a + f, t) * (1 - smooth(b - f, b, t));

const Tags: React.FC<{ t: number }> = ({ t }) => {
  const p = toastPose(t);
  const c = new THREE.Vector3(p.x, p.y, 0);
  const n = new THREE.Vector3(Math.sin(p.th), Math.cos(p.th), 0); // Normale Seite A
  const sideA = c.clone().addScaledVector(n, 0.09);
  const sideB = c.clone().addScaledVector(n, -0.09);
  return (
    <>
      <Tag t={t} at={new THREE.Vector3(-0.15, TABLE_H, 1.6)} dx={110} dy={230} a={win(t, 1.6, 4.4)} title="Tischkante" sub="h = 75,0 cm" />
      <Tag t={t} at={c.clone().add(new THREE.Vector3(0, 0, 2.2))} dx={-120} dy={-300} a={win(t, 8.6, 14.6)} align="r" title="Rotationsachse" sub={`ω = ${de(OMEGA_DEG, 0)} °/s`} />
      <Tag t={t} at={sideA} dx={-30} dy={-300} a={win(t, 18.2, 23.6)} align="r" title="Seite A · Butter" sub="Δm = +4,2 g" col={C.butter} />
      <Tag t={t} at={sideB} dx={90} dy={240} a={win(t, 18.8, 23.6)} align="l" title="Seite B · trocken" sub="Δm = 0,0 g" />
      <Tag t={t} at={c} dx={-240} dy={40} a={win(t, 19.6, 23.6)} align="r" title="Schwerpunkt" sub="verschoben: 0,3 mm" col={C.butter} />
      <Tag t={t} at={new THREE.Vector3(LAND_X + 0.6, 0.02, 0.6)} dx={120} dy={-200} a={win(t, 28.8, 30.6, 0.3)} title="Kontakt: Butter" sub="Wahrscheinlichkeit 100 %" col={C.crit} />
    </>
  );
};

// ---------- Kritischer Punkt ----------
const Critical: React.FC<{ t: number }> = ({ t }) => {
  const a = win(t, 26.4, 29.6, 0.4);
  if (a <= 0) return null;
  const pulse = 0.75 + 0.25 * Math.sin(t * 6);
  return (
    <div style={{ position: 'absolute', left: 0, right: 0, top: 1215, display: 'flex', justifyContent: 'center', opacity: a }}>
      <div
        style={{
          border: `2px solid ${C.crit}`, borderRadius: 999, padding: '14px 30px', display: 'flex', gap: 16, alignItems: 'center',
          background: 'rgba(255,107,94,0.08)', boxShadow: `0 0 ${40 * pulse}px rgba(255,107,94,0.35)`,
        }}
      >
        <span style={{ ...mono, fontSize: 34, color: C.crit }}>180°</span>
        <span style={{ fontFamily: 'Inter', fontWeight: 600, fontSize: 26, letterSpacing: '0.2em', color: C.white }}>KRITISCHER PUNKT</span>
      </div>
    </div>
  );
};

// ---------- 3-Meter-Lösung: Vergleich ----------
const Compare: React.FC<{ t: number }> = ({ t }) => {
  const a = win(t, 33.6, 38.2, 0.5);
  if (a <= 0) return null;
  const ok = smooth(37.4, 37.9, t);
  const Row: React.FC<{ h: string; r: string; v: string; col: string }> = ({ h, r, v, col }) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '16px 0', borderTop: `1px solid ${C.faint}` }}>
      <span style={{ ...mono, fontSize: 30, color: C.white, width: 200 }}>{h}</span>
      <span style={{ ...mono, fontSize: 30, color: C.dim, width: 230 }}>{r}</span>
      <span style={{ fontFamily: 'Inter', fontWeight: 600, fontSize: 28, color: col }}>{v}</span>
    </div>
  );
  return (
    <div style={{ position: 'absolute', left: 84, right: 84, top: 1330, opacity: a }}>
      <Row h="0,75 m" r="≈ ½ Drehung" v="Butter unten" col={C.crit} />
      <div style={{ opacity: smooth(34.4, 34.9, t) }}>
        <Row h="3,00 m" r="≈ 1 Drehung" v={ok > 0.5 ? 'Butter oben ✓' : 'läuft …'} col={ok > 0.5 ? C.ok : C.dim} />
      </div>
    </div>
  );
};

// ---------- Boden-Toast ----------
const Floor: React.FC<{ t: number }> = ({ t }) => {
  const a = win(t, 40.6, 45.4, 0.6);
  if (a <= 0) return null;
  const items = [
    ['Umsetzbarkeit', '100 %', C.ok],
    ['Kosten', '0,00 €', C.ok],
    ['Würde', 'nicht messbar', C.dim],
  ];
  return (
    <div style={{ position: 'absolute', left: 84, right: 84, top: 1330, opacity: a }}>
      {items.map(([k, v, col], i) => (
        <div
          key={k}
          style={{
            display: 'flex', justifyContent: 'space-between', padding: '16px 0', borderTop: `1px solid ${C.faint}`,
            opacity: smooth(40.8 + i * 0.45, 41.3 + i * 0.45, t),
          }}
        >
          <span style={{ fontFamily: 'Inter', fontWeight: 500, fontSize: 28, color: C.dim, letterSpacing: '0.08em' }}>{k}</span>
          <span style={{ ...mono, fontSize: 30, color: col }}>{v}</span>
        </div>
      ))}
    </div>
  );
};

// ---------- Flash / Vignette ----------
export const Vignette: React.FC = () => (
  <div
    style={{
      position: 'absolute', inset: 0, pointerEvents: 'none',
      background: 'radial-gradient(ellipse 80% 60% at 50% 48%, rgba(0,0,0,0) 55%, rgba(5,6,8,0.65) 100%)',
    }}
  />
);

export const Hud: React.FC<{ t: number }> = ({ t }) => {
  const xray = smooth(17.2, 18.4, t) * (1 - smooth(23.6, 25, t));
  const flash = Math.exp(-Math.max(0, t - FALL_END) * 6) * (t >= FALL_END ? 1 : 0);
  return (
    <>
      <Vignette />
      <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 760, background: 'linear-gradient(rgba(10,11,14,0.82) 0%, rgba(10,11,14,0.6) 55%, rgba(10,11,14,0) 100%)' }} />
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 700, background: 'linear-gradient(rgba(10,11,14,0) 0%, rgba(10,11,14,0.7) 45%, rgba(10,11,14,0.85) 100%)' }} />
      {xray > 0 && (
        <div style={{ position: 'absolute', inset: 0, background: `rgba(90,200,250,${0.05 * xray})`, mixBlendMode: 'screen' }} />
      )}
      <div style={{ position: 'absolute', inset: 0, background: `rgba(255,250,235,${0.18 * flash})` }} />
      <Frame t={t} />
      {CAPS.map((c, i) => (
        <Caption key={i} t={t} c={c} />
      ))}
      <Ruler t={t} />
      <Tags t={t} />
      <DataBar t={t} />
      <Critical t={t} />
      <Compare t={t} />
      <Floor t={t} />
      {xray > 0.01 && (
        <div style={{ position: 'absolute', top: 1340, left: 0, right: 0, textAlign: 'center', opacity: xray, ...mono, fontSize: 22, color: C.accent, letterSpacing: '0.3em' }}>
          ◆ BULLET TIME · MASSENANALYSE
        </div>
      )}
      {/* Abspann */}
      <div style={{ position: 'absolute', top: 1262, left: 0, right: 0, textAlign: 'center', opacity: smooth(42.6, 43.4, t) }}>
        <span style={{ fontFamily: 'Inter', fontWeight: 500, fontSize: 26, letterSpacing: '0.2em', color: C.dim }}>
          FOLGE FÜR MEHR UNNÖTIGE PHYSIK
        </span>
      </div>
    </>
  );
};
