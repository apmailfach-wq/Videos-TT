// "Was wäre, wenn … Teil 1" – 45 s, 1080x1920, low-poly 3D, rendered frame by frame.
// Every visual state is a pure function of the film time t (seconds), so any frame can be rendered alone.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { TIMELINE, HUD_LINES, BATTERY, TEXTS, TITLE } from './timeline.js';

const W = 1080, H = 1920;

// ------------------------------------------------------------------ helpers
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const sstep = (a, b, x) => { const k = clamp((x - a) / (b - a)); return k * k * (3 - 2 * k); };
const easeIO = k => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
function mulberry(seed) { return () => { seed |= 0; seed = (seed + 0x6D2B79F5) | 0; let r = Math.imul(seed ^ (seed >>> 15), 1 | seed); r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r; return ((r ^ (r >>> 14)) >>> 0) / 4294967296; }; }
const hash1 = n => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
function noise1(x, seed = 0) { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return lerp(hash1(i + seed * 57.3), hash1(i + 1 + seed * 57.3), u) * 2 - 1; }
const R = mulberry(1859);
const pick = (r, arr) => arr[Math.floor(r() * arr.length)];

// ------------------------------------------------------------------ renderer
const glCanvas = document.createElement('canvas');
glCanvas.width = W; glCanvas.height = H; glCanvas.id = 'gl';
document.body.appendChild(glCanvas);
const renderer = new THREE.WebGLRenderer({ canvas: glCanvas, antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;

const scene = new THREE.Scene();
const fog = new THREE.FogExp2(0x070b18, 0.0016);
scene.fog = fog;
const camera = new THREE.PerspectiveCamera(68, W / H, 0.05, 30000);
camera.rotation.order = 'YXZ';
scene.add(camera);

// ------------------------------------------------------------------ materials
const flat = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, flatShading: true, roughness: 0.92, metalness: 0.0, ...extra });

// ------------------------------------------------------------------ sky with ray-marched aurora
const skyU = {
  uTime: { value: 0 }, uAurora: { value: 1 }, uRed: { value: 0 }, uDust: { value: 0 }, uFlash: { value: 0 },
  uGlow: { value: 0 }, uCity: { value: 1 }, uImpact: { value: new THREE.Vector3(-0.1, 0.0, -1).normalize() },
  uDustCol: { value: new THREE.Color(0x3a332d) }, uStars: { value: 1 },
};
const skyMat = new THREE.ShaderMaterial({
  uniforms: skyU, side: THREE.BackSide, depthWrite: false, fog: false,
  vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); vec4 p = projectionMatrix*modelViewMatrix*vec4(position,1.); gl_Position = p.xyww; }`,
  fragmentShader: `
  varying vec3 vDir;
  uniform float uTime,uAurora,uRed,uDust,uFlash,uGlow,uCity,uStars; uniform vec3 uImpact,uDustCol;
  float hash(vec2 p){ p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y);}
  float noise(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x), mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x), f.y);}
  float fbm(vec2 p){ return noise(p)*.6+noise(p*2.07+3.1)*.28+noise(p*4.3+7.7)*.12; }
  // curtain density in the horizontal plane: thin, folding bands
  float curtain(vec2 q, float t){
    float d = 0.;
    for(int b=0;b<3;b++){
      float fb=float(b);
      vec2 r = q*.5 + vec2(fb*13.1, fb*7.3);
      float w = r.y + 1.9*fbm(vec2(r.x*.16 + t*.03*(1.+fb*.4), fb*3.)) + .5*sin(r.x*.45 + t*.22 + fb*2.);
      float line = abs(fract(w*.22 + fb*.37) - .5);
      float k = exp(-line*line*(260. + fb*120.));
      float rays = noise(vec2(r.x*7. + t*.25, fb*5.)); rays = .25 + .75*rays*rays;
      float fold = .6 + .4*sin(r.x*1.3 + t*.4 + fb);
      d += k*rays*fold*(1. - fb*.25);
    }
    return d;
  }
  void main(){
    vec3 d = normalize(vDir);
    float el = d.y;
    vec3 zen = vec3(.006,.010,.030), hor = vec3(.018,.035,.060);
    vec3 col = mix(hor, zen, pow(clamp(el,0.,1.),.55));
    if(el < 0.) col = hor*.6;
    // city light pollution
    col += uCity*vec3(.10,.055,.025)*exp(-max(el,0.)*14.);
    // stars
    vec2 sp = d.xz/(abs(d.y)+.35)*520.;
    float s = hash(floor(sp)); float tw = .6+.4*sin(uTime*3.+s*40.);
    col += uStars*.7*step(.9975,s)*tw*smoothstep(.0,.15,el)*vec3(.8,.85,1.)*(1.-uDust);
    // aurora: march through the emission layer
    vec3 acc = vec3(0.);
    if(el > .015){
      float jit = hash(gl_FragCoord.xy)*.9;
      for(int i=0;i<22;i++){
        float fi = (float(i)+jit)/22.;
        float h = 1. + fi*1.6;
        vec2 q = d.xz/el*h*1.35 + vec2(0., 2.0);
        float c = curtain(q, uTime);
        vec3 lo = mix(vec3(.08,1.,.42), vec3(.2,1.,.75), .5+.5*sin(q.x*.15));
        vec3 mid = vec3(1.,.18,.62);
        vec3 hi = mix(vec3(.55,.2,1.), vec3(1.,.12,.2), uRed);
        vec3 ac = fi < .35 ? mix(lo, mid, smoothstep(.12,.35,fi)) : mix(mid, hi, smoothstep(.35,.9,fi));
        float fall = exp(-fi*2.2)*(.35+.65*smoothstep(0.,.08,fi));
        acc += ac*c*fall;
      }
      acc *= .42*uAurora*smoothstep(.015,.12,el)*(.75+.25*smoothstep(.0,.5,el));
    }
    col += acc*(1.-uDust*.97);
    // aurora glow on the horizon haze
    col += vec3(.01,.05,.035)*uAurora*exp(-max(el,0.)*7.)*(1.-uDust);
    // impact glow + flash
    float ia = max(dot(d,uImpact),0.);
    col += uGlow*(vec3(1.,.42,.12)*pow(ia,40.)*1.1 + vec3(1.,.3,.08)*pow(ia,6.)*.6 + vec3(.5,.16,.05)*exp(-max(el,0.)*5.)*.5);
    col += uFlash*vec3(1.,.97,.92)*(.6+2.*pow(ia,8.));
    // dust swallows the sky
    vec3 dc = uDustCol*(.55+.6*fbm(d.xz/(abs(d.y)+.3)*3.+vec2(uTime*.05,0.)));
    dc += uGlow*vec3(.35,.12,.03)*pow(ia,2.)*.6;
    col = mix(col, dc, uDust);
    gl_FragColor = vec4(col,1.);
  }`,
});
const sky = new THREE.Mesh(new THREE.SphereGeometry(20000, 48, 24), skyMat);
sky.renderOrder = -10; sky.frustumCulled = false;
scene.add(sky);

// ------------------------------------------------------------------ lighting
const hemi = new THREE.HemisphereLight(0x5fd9b0, 0x10121a, 0.55);
scene.add(hemi);
const auroraLight = new THREE.DirectionalLight(0x7cffc8, 0.5); auroraLight.position.set(-0.4, 1, -0.6); scene.add(auroraLight);
const pinkLight = new THREE.DirectionalLight(0xff5fb0, 0.25); pinkLight.position.set(0.6, 0.8, -0.3); scene.add(pinkLight);
const blastLight = new THREE.DirectionalLight(0xffe2c0, 0); blastLight.position.set(-0.1, 0.15, -1); scene.add(blastLight);
const fireLight = new THREE.PointLight(0xff6a20, 0, 60, 1.6); fireLight.position.set(-6, 3, -14); scene.add(fireLight);
const fireLight2 = new THREE.PointLight(0xff7a30, 0, 50, 1.6); fireLight2.position.set(7, 2, -28); scene.add(fireLight2);

// ------------------------------------------------------------------ textures (canvas)
function canvasTex(w, h, draw, srgb = true) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}
function windowTextures(seed, cols, rows, litFrac, warm = true) {
  const r = mulberry(seed);
  const lit = [];
  for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) lit.push(r() < litFrac ? 0.55 + r() * 0.45 : 0);
  const cw = 32, ch = 32;
  const draw = emissive => (g, w, h) => {
    g.fillStyle = emissive ? '#000' : '#ffffff'; g.fillRect(0, 0, w, h);
    for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
      const v = lit[y * cols + x];
      if (emissive) {
        if (!v) continue;
        const hue = warm ? (r() < 0.8 ? [255, 196, 120] : [190, 220, 255]) : [210, 230, 255];
        g.fillStyle = `rgb(${hue[0] * v | 0},${hue[1] * v | 0},${hue[2] * v | 0})`;
      } else g.fillStyle = '#1a1d26';
      g.fillRect(x * cw + 7, y * ch + 6, cw - 14, ch - 13);
    }
  };
  return {
    map: canvasTex(cols * cw, rows * ch, draw(false)),
    emi: canvasTex(cols * cw, rows * ch, draw(true)),
    cols, rows,
  };
}
const facadeTex = [windowTextures(3, 8, 8, 0.45), windowTextures(5, 8, 8, 0.35), windowTextures(9, 8, 8, 0.55)];
const towerTex = [windowTextures(21, 8, 16, 0.4, false), windowTextures(22, 8, 16, 0.3, false)];
for (const s of [...facadeTex, ...towerTex]) for (const k of ['map', 'emi']) { s[k].wrapS = s[k].wrapT = THREE.RepeatWrapping; }

const windowMats = []; // emissiveIntensity animated (blackout)
function boxWithWindows(w, h, d, tex, color, bayW, floorH, seed) {
  const geo = new THREE.BoxGeometry(w, h, d);
  const uv = geo.attributes.uv; const r = mulberry(seed);
  const ox = Math.floor(r() * 8) / 8, oy = Math.floor(r() * 8) / 8;
  // faces: px nx py ny pz nz, 4 verts each
  for (let f = 0; f < 6; f++) {
    const fw = f < 2 ? d : w, fh = f === 2 || f === 3 ? d : h;
    for (let v = 0; v < 4; v++) {
      const i = f * 4 + v;
      uv.setXY(i, uv.getX(i) * fw / (bayW * tex.cols) + ox, uv.getY(i) * fh / (floorH * tex.rows) + oy);
    }
  }
  const mat = new THREE.MeshStandardMaterial({ color, map: tex.map, emissiveMap: tex.emi, emissive: 0xffffff, emissiveIntensity: 1, flatShading: true, roughness: 0.9 });
  const roof = flat(new THREE.Color(color).multiplyScalar(0.55));
  windowMats.push(mat);
  const m = new THREE.Mesh(geo, [mat, mat, roof, roof, mat, mat]);
  return m;
}

// ------------------------------------------------------------------ street
const world = new THREE.Group(); scene.add(world);
const ground = new THREE.Mesh(new THREE.PlaneGeometry(6000, 6000), flat(0x0d0f14));
ground.rotation.x = -Math.PI / 2; ground.position.y = -0.02; world.add(ground);
const road = new THREE.Mesh(new THREE.PlaneGeometry(26, 260), flat(0x1b1d24, { roughness: 0.75 }));
road.rotation.x = -Math.PI / 2; road.position.set(0, 0, -110); world.add(road);
for (const sx of [-1, 1]) {
  const sw = new THREE.Mesh(new THREE.BoxGeometry(7, 0.16, 260), flat(0x2c2e36));
  sw.position.set(sx * 16.5, 0.08, -110); world.add(sw);
}
const markMat = flat(0xb9bcc4, { emissive: 0x111111 });
for (let z = 6; z > -235; z -= 9) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.02, 3.2), markMat); m.position.set(0, 0.012, z); world.add(m);
}
// tram rails hint
for (const x of [-4.2, -2.8, 2.8, 4.2]) { const m = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.02, 250), flat(0x3a3d46)); m.position.set(x, 0.01, -110); world.add(m); }

// side buildings
const buildings = []; // {mesh, side, z, depth}
for (const sx of [-1, 1]) {
  let z = 22;
  let k = 0;
  while (z > -160) {
    const w = 10 + R() * 9, h = 13 + R() * 9, d = 14;
    const tex = facadeTex[(k + (sx > 0 ? 1 : 0)) % 3];
    const col = pick(R, [0x8a7f74, 0x7d8088, 0x9a8a78, 0x6f7380, 0x8c8478, 0x7a6e66]);
    const b = boxWithWindows(d, h, w, tex, col, 3.4, 3.1, k * 7 + (sx > 0 ? 100 : 0));
    b.position.set(sx * (20 + d / 2), h / 2, z - w / 2);
    world.add(b);
    // simple pitched/flat roof detail
    if (R() < 0.6) {
      const rf = new THREE.Mesh(new THREE.CylinderGeometry(0.01, d * 0.62, 3 + R() * 2, 4, 1), flat(0x3b3438));
      rf.rotation.y = Math.PI / 4; rf.scale.set(1, 1, w / d); rf.position.set(b.position.x, h + 1.5, b.position.z); world.add(rf);
    }
    buildings.push({ mesh: b, side: sx, z: z - w / 2, w, h });
    z -= w + 0.4; k++;
  }
}
// far city carpet + skyline
const cityGroup = new THREE.Group(); world.add(cityGroup);
for (let i = 0; i < 260; i++) {
  const x = (R() - 0.5) * 2600, z = -230 - R() * 2200;
  if (Math.abs(x) < 30 && z > -400) continue;
  const w = 20 + R() * 40, h = 10 + R() * 35, d = 20 + R() * 40;
  const b = boxWithWindows(w, h, d, facadeTex[i % 3], pick(R, [0x4d4f58, 0x5a5650, 0x45484f]), 3.6, 3.2, 300 + i);
  b.position.set(x, h / 2, z); cityGroup.add(b);
}
// skyline (generic towers, Frankfurt-like cluster)
const towers = [];
function tower(x, z, w, d, h, top) {
  const t = boxWithWindows(w, h, d, towerTex[towers.length % 2], pick(R, [0x5b6878, 0x4f5b6b, 0x6a7282, 0x56606e]), 3.2, 3.6, 900 + towers.length);
  t.position.set(x, h / 2, z); cityGroup.add(t); towers.push(t);
  if (top === 'pyramid') { const p = new THREE.Mesh(new THREE.ConeGeometry(w * 0.72, w * 0.9, 4, 1), flat(0x77808d)); p.rotation.y = Math.PI / 4; p.position.set(x, h + w * 0.45, z); cityGroup.add(p); }
  if (top === 'antenna') { const a = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 1, 40, 5), flat(0x9aa0aa)); a.position.set(x + w * 0.2, h + 20, z); cityGroup.add(a); }
  if (top === 'slant') { const s = new THREE.Mesh(new THREE.CylinderGeometry(0.1, w * 0.7, 18, 3, 1), flat(0x6e7787)); s.position.set(x, h + 9, z); cityGroup.add(s); }
  // aircraft warning light
  const red = new THREE.Mesh(new THREE.SphereGeometry(1.4, 6, 4), new THREE.MeshBasicMaterial({ color: 0xff2020 }));
  red.position.set(x, h + (top === 'pyramid' ? w * 0.9 : top === 'antenna' ? 40 : top === 'slant' ? 18 : 1), z); red.userData.blink = R(); cityGroup.add(red); towers.push(red);
}
tower(-150, -900, 50, 50, 260, 'slant');      // tallest, triangular top
tower(-60, -840, 42, 42, 240, 'pyramid');     // pencil tower
tower(-230, -980, 36, 30, 210, 'antenna');
tower(-110, -1050, 34, 34, 195, null);
tower(-90, -1010, 34, 34, 190, null);          // twin glass towers
tower(20, -980, 40, 34, 200, 'antenna');
tower(-310, -1080, 40, 40, 170, null);
tower(90, -1120, 44, 40, 165, 'slant');
tower(160, -900, 30, 30, 130, null);
tower(-20, -760, 30, 30, 120, null);
tower(240, -1200, 40, 40, 150, null);
tower(-400, -1150, 34, 34, 140, 'antenna');
// TV tower needle far right
{
  const tvx = 520, tvz = -1500;
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(6, 12, 300, 8), flat(0x8d939d)); shaft.position.set(tvx, 150, tvz); cityGroup.add(shaft);
  const pod = new THREE.Mesh(new THREE.CylinderGeometry(26, 20, 22, 10), flat(0x9aa0aa)); pod.position.set(tvx, 240, tvz); cityGroup.add(pod);
  const ant = new THREE.Mesh(new THREE.CylinderGeometry(1, 3, 70, 6), flat(0xb0b5be)); ant.position.set(tvx, 335, tvz); cityGroup.add(ant);
}

// street lamps
const lamps = [];
const poleMat = flat(0x2a2d35);
const poolTex = canvasTex(128, 128, (g, w, h) => { const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64); gr.addColorStop(0, 'rgba(255,190,110,1)'); gr.addColorStop(0.5, 'rgba(255,170,90,.35)'); gr.addColorStop(1, 'rgba(255,160,80,0)'); g.fillStyle = gr; g.fillRect(0, 0, w, h); });
const glowTex = canvasTex(128, 128, (g, w, h) => { const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64); gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.2, 'rgba(255,255,255,.55)'); gr.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = gr; g.fillRect(0, 0, w, h); });
for (const sx of [-1, 1]) for (let i = 0; i < 9; i++) {
  const z = -4 - i * 19 - (sx > 0 ? 9 : 0);
  const g = new THREE.Group(); g.position.set(sx * 12.6, 0, z); world.add(g);
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.14, 7.5, 6), poleMat); pole.position.y = 3.75; g.add(pole);
  const arm = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.08, 0.08), poleMat); arm.position.set(-sx * 0.7, 7.45, 0); g.add(arm);
  const headMat = new THREE.MeshBasicMaterial({ color: 0xffc27a });
  const head = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.4, 0.22, 6), headMat); head.position.set(-sx * 1.4, 7.35, 0); g.add(head);
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0xffb36b, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  glow.scale.set(3.2, 3.2, 1); glow.position.copy(head.position); g.add(glow);
  const pool = new THREE.Mesh(new THREE.PlaneGeometry(12, 12), new THREE.MeshBasicMaterial({ map: poolTex, transparent: true, opacity: 0.38, blending: THREE.AdditiveBlending, depthWrite: false }));
  pool.rotation.x = -Math.PI / 2; pool.position.set(-sx * 2.5, 0.03, 0); g.add(pool);
  lamps.push({ g, headMat, glow, pool, z, side: sx, seed: R() * 100 });
}
const lampLights = [];
for (let i = 0; i < 4; i++) { const l = new THREE.PointLight(0xffb070, 0, 26, 1.4); scene.add(l); lampLights.push(l); }

// trees
const trees = [];
for (const sx of [-1, 1]) for (let i = 0; i < 6; i++) {
  const z = -14 - i * 22 + (sx > 0 ? -6 : 0);
  const g = new THREE.Group(); g.position.set(sx * 15.2, 0.16, z); world.add(g);
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.2, 2.6, 5), flat(0x3a2c22)); trunk.position.y = 1.3; g.add(trunk);
  const crown = new THREE.Mesh(new THREE.IcosahedronGeometry(1.9, 0), flat(0x1f3a2c)); crown.position.y = 3.8; crown.scale.set(1, 1.25, 1); g.add(crown);
  trees.push({ g, crown, z, seed: R() * 50 });
}

// cars
const cars = [];
function makeCar(color) {
  const g = new THREE.Group(); const body = new THREE.Group(); g.add(body);
  const m = flat(color, { roughness: 0.6, metalness: 0.2 });
  const lower = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.7, 4.3), m); lower.position.y = 0.6; body.add(lower);
  const cab = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.85, 1.75, 4, 1), m); cab.rotation.y = Math.PI / 4; cab.scale.set(1.0, 0.36, 1.3);
  const cabG = new THREE.Group(); cabG.add(cab); cabG.position.set(0, 1.18, -0.15); cabG.scale.set(1.45, 1, 1.4); body.add(cabG);
  const glass = new THREE.Mesh(new THREE.BoxGeometry(1.62, 0.36, 2.0), flat(0x0e1420, { roughness: 0.2, metalness: 0.6 })); glass.position.set(0, 1.2, -0.15); body.add(glass);
  const wm = flat(0x111111);
  for (const [x, z] of [[-0.85, 1.35], [0.85, 1.35], [-0.85, -1.35], [0.85, -1.35]]) { const w = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.34, 0.24, 8), wm); w.rotation.z = Math.PI / 2; w.position.set(x, 0.34, z); body.add(w); }
  const hazMat = new THREE.MeshBasicMaterial({ color: 0x331a00 });
  for (const [x, z] of [[-0.75, 2.16], [0.75, 2.16], [-0.75, -2.16], [0.75, -2.16]]) { const h = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.14, 0.05), hazMat); h.position.set(x, 0.78, z); body.add(h); }
  return { g, body, hazMat };
}
const carColors = [0x8a1f24, 0x2a3d6b, 0xb8bcc4, 0x1d1f24, 0x355a45, 0x6b6f78, 0xc9a14a, 0x5a2a5a];
for (const sx of [-1, 1]) for (let i = 0; i < 7; i++) {
  const z = -9 - i * 14 - R() * 4 - (sx > 0 ? 5 : 0);
  const c = makeCar(pick(R, carColors));
  c.g.position.set(sx * 11.1, 0, z); c.g.rotation.y = (sx > 0 ? Math.PI : 0) + (R() - 0.5) * 0.06;
  world.add(c.g); cars.push({ ...c, x: sx * 11.1, z, ry: c.g.rotation.y, seed: R() * 100, spin: (R() < 0.5 ? 1 : 2) * Math.PI * (R() < 0.5 ? 1 : -1) });
}
for (const [x, z, ry] of [[-6, -48, 0.3], [5.5, -72, -0.5], [-3, -105, 0.1]]) {
  const c = makeCar(pick(R, carColors)); c.g.position.set(x, 0, z); c.g.rotation.y = ry; world.add(c.g);
  cars.push({ ...c, x, z, ry, seed: R() * 100, spin: Math.PI });
}

// cracks in the road (revealed during the quake)
const crackMat = new THREE.MeshBasicMaterial({ color: 0x020203, side: THREE.DoubleSide });
const cracks = [];
for (let c = 0; c < 7; c++) {
  const pts = []; let x = (R() - 0.5) * 18, z = -90 + R() * 30;
  const zEnd = -3 - R() * 14;
  while (z < zEnd) { pts.push([x, z]); z += 1.2 + R() * 1.8; x += (R() - 0.5) * 2.4; x = clamp(x, -12, 12); }
  pts.push([x, z]);
  const n = pts.length; const pos = new Float32Array(n * 2 * 3);
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const idx = []; for (let i = 0; i < n - 1; i++) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
  geo.setIndex(idx);
  const m = new THREE.Mesh(geo, crackMat); m.frustumCulled = false; world.add(m);
  cracks.push({ m, pts, pos, delay: R() * 0.8, w0: 0.16 + R() * 0.16, seed: R() * 10 });
}

// ------------------------------------------------------------------ people (stylised, no faces)
const auroraScreenTex = canvasTex(64, 128, (g, w, h) => { const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#5a2a9a'); gr.addColorStop(0.35, '#ff4fa0'); gr.addColorStop(0.7, '#3cffa0'); gr.addColorStop(1, '#0a2a30'); g.fillStyle = gr; g.fillRect(0, 0, w, h); });
const crowdScreenMat = new THREE.MeshBasicMaterial({ map: auroraScreenTex, color: 0xffffff });
const phoneBodyMat = flat(0x15161a, { roughness: 0.4 });
const coats = [0x2b2f3a, 0x46303a, 0x24332e, 0x3b3546, 0x4a3b2a, 0x1f2633, 0x5a4a3a, 0x3d4450, 0x6b2e3a, 0x2e4a5a, 0x7a6a50, 0x3a2a4a];
const pants = [0x1a1c22, 0x23262e, 0x2c2a26, 0x1d2430];
const skins = [0xd8b090, 0xb88a68, 0x8a5e40, 0xe8c4a8, 0x6a4630];
const hairs = [0x1a1410, 0x3a2a1a, 0x6a4a2a, 0xa08060, 0x222222];
const people = [];
function makePerson(r) {
  const s = 0.86 + r() * 0.24;
  const root = new THREE.Group(), fallYaw = new THREE.Group(), tilt = new THREE.Group(), body = new THREE.Group();
  root.add(fallYaw); fallYaw.add(tilt); tilt.add(body);
  const coat = flat(pick(r, coats)), pant = flat(pick(r, pants)), skin = flat(pick(r, skins)), hair = flat(pick(r, hairs));
  const legs = [];
  for (const sx of [-1, 1]) {
    const lg = new THREE.Group(); lg.position.set(sx * 0.1, 0.92, 0); body.add(lg);
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.92, 0.19), pant); m.position.y = -0.46; lg.add(m); legs.push(lg);
  }
  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.21, 0.25, 0.66, 6), coat); torso.position.y = 1.24; body.add(torso);
  const neck = new THREE.Group(); neck.position.y = 1.6; body.add(neck);
  const head = new THREE.Mesh(new THREE.IcosahedronGeometry(0.125, 0), skin); head.position.y = 0.1; neck.add(head);
  const hairM = new THREE.Mesh(new THREE.IcosahedronGeometry(0.13, 0), hair); hairM.position.set(0, 0.14, -0.035); hairM.scale.set(1, 0.85, 1); neck.add(hairM);
  const arms = [];
  for (const sx of [-1, 1]) {
    const ag = new THREE.Group(); ag.position.set(sx * 0.27, 1.5, 0); body.add(ag);
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.11, 0.62, 0.12), coat); m.position.y = -0.31; ag.add(m);
    const hand = new THREE.Mesh(new THREE.IcosahedronGeometry(0.05, 0), skin); hand.position.y = -0.64; ag.add(hand);
    arms.push(ag);
  }
  // phone in right hand (screen faces the person = +z local)
  const phone = new THREE.Group(); phone.position.set(0, -0.68, 0.02); arms[1].add(phone);
  const pb = new THREE.Mesh(new THREE.BoxGeometry(0.075, 0.15, 0.01), phoneBodyMat); phone.add(pb);
  const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.066, 0.138), crowdScreenMat); scr.position.z = 0.0055; phone.add(scr);
  // the screen faces back towards the camera; add a soft glow sprite so they read at distance
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0x9fffd8, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false }));
  glow.scale.set(0.35, 0.45, 1); glow.position.z = 0.02; phone.add(glow);
  root.scale.setScalar(s);
  return { root, fallYaw, tilt, body, legs, arms, neck, phone, scr, glow, s };
}
// dropped phones (world space)
function makeLooseGroup() { const g = new THREE.Group(); const pb = new THREE.Mesh(new THREE.BoxGeometry(0.075, 0.15, 0.01), phoneBodyMat); g.add(pb); const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.066, 0.138), crowdScreenMat); scr.position.z = 0.0055; g.add(scr); return g; }

const PR = mulberry(77);
const crowdSpots = [];
crowdSpots.push([-1.9, -4.8], [2.2, -5.4], [-3.4, -6.6]);
for (let i = 0; i < 64; i++) {
  const z = -5 - Math.pow(PR(), 1.25) * 75;
  const spread = 7 + (-z) * 0.06;
  crowdSpots.push([(PR() - 0.5) * 2 * spread, z]);
}
crowdSpots.forEach(([x, z], i) => {
  const r = mulberry(1000 + i);
  const p = makePerson(r);
  const kind = i < 3 ? (i === 1 ? 'point' : 'film') : r() < 0.62 ? 'film' : r() < 0.5 ? 'point' : 'watch';
  const heading = Math.PI + (r() - 0.5) * (kind === 'watch' ? 1.6 : 0.6);
  world.add(p.root);
  const loose = makeLooseGroup(); loose.visible = false; world.add(loose);
  people.push({
    ...p, x, z, kind, heading, loose,
    ph: r() * 10, cheer: r() < 0.65, jump: r() < 0.35,
    runAt: r() < 0.45 ? 17.2 + r() * 2.5 : 99, runDir: (x < 0 ? -1 : 1) * (0.5 + r() * 0.8),
    quakeFall: r() < 0.45 ? 20.6 + r() * 2.6 : 99, quakeDir: r() * Math.PI * 2,
    dropAt: 20.4 + r() * 2.2, dropCache: null, rs: r,
  });
});

// ------------------------------------------------------------------ meteor streak
const meteorHead = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0xffffff, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false }));
meteorHead.renderOrder = 5; scene.add(meteorHead);
const TRAIL = 60;
const trailGeo = new THREE.BufferGeometry();
trailGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(TRAIL * 2 * 3), 3));
trailGeo.setAttribute('a', new THREE.BufferAttribute(new Float32Array(TRAIL * 2), 1));
{ const idx = []; for (let i = 0; i < TRAIL - 1; i++) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); } trailGeo.setIndex(idx); }
const trailMat = new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false, side: THREE.DoubleSide,
  uniforms: { uI: { value: 0 } },
  vertexShader: 'attribute float a; varying float va; void main(){ va=a; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }',
  fragmentShader: 'uniform float uI; varying float va; void main(){ vec3 c=mix(vec3(1.,.55,.25),vec3(1.,1.,.95),va*va); gl_FragColor=vec4(c*va*uI,1.); }',
});
const trail = new THREE.Mesh(trailGeo, trailMat); trail.frustumCulled = false; trail.renderOrder = 4; scene.add(trail);
const IMPACT_DIR = new THREE.Vector3(-0.12, 0, -1).normalize();
function meteorDir(tt) {
  const k = clamp((tt - 10.6) / 5.4);
  const kk = k * k * 0.25 + k * 0.75;
  const az = lerp(-0.42, Math.atan2(IMPACT_DIR.x, -IMPACT_DIR.z), kk);
  const el = lerp(0.62, 0.0, kk);
  return new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el));
}

// ------------------------------------------------------------------ fireball / mushroom (far away)
const fireU = { uTime: { value: 0 }, uHeat: { value: 1 }, uA: { value: 1 } };
const fireMat = new THREE.ShaderMaterial({
  uniforms: fireU, fog: false, transparent: true, depthWrite: false,
  vertexShader: 'varying vec3 vN; varying vec3 vP; void main(){ vN=normalize(normalMatrix*normal); vP=position; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }',
  fragmentShader: `uniform float uTime,uHeat,uA; varying vec3 vN; varying vec3 vP;
    float h(vec3 p){ return fract(sin(dot(p,vec3(12.9898,78.233,45.164)))*43758.5453); }
    void main(){ float rim = pow(1.-abs(vN.z),1.5); float n = h(floor(vP*3.+uTime*.5));
      vec3 hot = vec3(1.,.95,.7), mid = vec3(1.,.45,.08), cool = vec3(.2,.07,.04);
      vec3 c = mix(mix(hot, mid, clamp(1.-uHeat+rim*.6,0.,1.)), cool, clamp((1.-uHeat)*.8+rim*.5-n*.2,0.,1.));
      gl_FragColor = vec4(c*(1.05+n*.4)*mix(.55,1.,uHeat), .97*uA); }`,
});
const fire = new THREE.Group(); fire.position.set(IMPACT_DIR.x * 7000, 0, IMPACT_DIR.z * 7000); scene.add(fire);
const fireBall = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 2), fireMat); fire.add(fireBall);
const fireStem = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.6, 1, 9, 3), fireMat); fire.add(fireStem);
const fireSkirt = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 1), fireMat); fire.add(fireSkirt);
fireBall.renderOrder = fireStem.renderOrder = fireSkirt.renderOrder = 2;

// ------------------------------------------------------------------ shock wave wall
const wallMat = new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, side: THREE.DoubleSide, fog: false,
  uniforms: { uTime: { value: 0 }, uA: { value: 0 }, uSeed: { value: 0 } },
  vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }',
  fragmentShader: `uniform float uTime,uA,uSeed; varying vec2 vUv;
    float hash(vec2 p){ p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y);}
    float noise(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f); return mix(mix(hash(i),hash(i+vec2(1,0)),f.x), mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x), f.y);}
    void main(){ vec2 p = vUv*vec2(14.,6.) + vec2(uSeed, -uTime*1.6);
      float n = noise(p)*.55 + noise(p*2.3+5.)*.3 + noise(p*5.1+1.)*.15;
      float top = smoothstep(1., .45 + n*.35, vUv.y);
      float side = smoothstep(0., .12, vUv.x)*smoothstep(1., .88, vUv.x);
      float a = uA*top*side*(.55 + .45*n);
      vec3 c = mix(vec3(.16,.12,.09), vec3(.62,.48,.34), n) + vec3(.35,.15,.04)*(1.-vUv.y);
      gl_FragColor = vec4(c, a); }`,
});
const wallLayers = [];
for (let i = 0; i < 4; i++) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), wallMat.clone());
  m.material.uniforms.uSeed.value = i * 17.3; m.renderOrder = 8 + i; m.frustumCulled = false; scene.add(m); wallLayers.push(m);
}
const WAVE_T0 = 25.0, WAVE_Z0 = -700, WAVE_V = 260;
const waveZ = t => WAVE_Z0 + (t - WAVE_T0) * WAVE_V;
const waveHit = z => WAVE_T0 + (z - WAVE_Z0) / WAVE_V;
const T_HIT_CAM = waveHit(0);

// glass shards (instanced)
const SHARDS = 2600;
const shardGeo = new THREE.BufferGeometry();
shardGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array([-0.12, 0, 0, 0.12, 0, 0, 0.02, 0.22, 0]), 3));
shardGeo.computeVertexNormals();
const shardMat = new THREE.MeshBasicMaterial({ color: 0xbfe6ff, side: THREE.DoubleSide, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false });
const shards = new THREE.InstancedMesh(shardGeo, shardMat, SHARDS); shards.frustumCulled = false; scene.add(shards);
const shardData = [];
{ const r = mulberry(4242); for (let i = 0; i < SHARDS; i++) { const b = buildings[Math.floor(r() * buildings.length)]; const z = b.z + (r() - 0.5) * b.w; shardData.push({ x: b.side * 20, y: 2 + r() * (b.h - 3), z, side: b.side, vx: -b.side * (3 + r() * 9), vy: r() * 4, vz: 10 + r() * 30, rx: r() * 6, ry: r() * 6, rz: r() * 6, sp: 4 + r() * 14, sc: 0.4 + r() * 1.3 }); } }

// burning debris + trails (instanced)
const DEB = 260;
const debGeo = new THREE.IcosahedronGeometry(0.35, 0);
const debMat = new THREE.MeshBasicMaterial({ color: 0xffa040 });
const debris = new THREE.InstancedMesh(debGeo, debMat, DEB); debris.frustumCulled = false; scene.add(debris);
const trailBoxMat = new THREE.MeshBasicMaterial({ color: 0xff6a1a, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false });
const debTrails = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.02, 0.22, 1, 5, 1, true), trailBoxMat, DEB); debTrails.frustumCulled = false; scene.add(debTrails);
const debData = [];
{ const r = mulberry(555); for (let i = 0; i < DEB; i++) debData.push({ t0: 27.9 + r() * 6.2, x: (r() - 0.5) * 60, z: -6 - r() * 110, y0: 50 + r() * 90, vy: -(14 + r() * 22), vx: (r() - 0.5) * 6, vz: 3 + r() * 6, sc: 0.5 + r() * 1.4, spin: r() * 5 }); }

// dust billows + fires (sprites)
const dustTex = canvasTex(256, 256, (g, w, h) => {
  const r = mulberry(8);
  for (let i = 0; i < 40; i++) { const x = 60 + r() * 136, y = 60 + r() * 136, rad = 30 + r() * 60; const gr = g.createRadialGradient(x, y, 0, x, y, rad); gr.addColorStop(0, 'rgba(255,255,255,.22)'); gr.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = gr; g.fillRect(0, 0, w, h); }
});
const dusts = [];
{ const r = mulberry(99); for (let i = 0; i < 46; i++) { const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: dustTex, color: 0x6d6258, transparent: true, depthWrite: false, opacity: 0 })); scene.add(sp); dusts.push({ sp, x: (r() - 0.5) * 70, z: -8 - r() * 140, y0: r() * 10, t0: 27.4 + r() * 4, size: 20 + r() * 40, rise: 2 + r() * 5, rot: r() }); } }
const flameTex = canvasTex(64, 128, (g, w, h) => { const gr = g.createRadialGradient(32, 90, 2, 32, 80, 60); gr.addColorStop(0, 'rgba(255,240,180,1)'); gr.addColorStop(0.3, 'rgba(255,150,40,.9)'); gr.addColorStop(0.7, 'rgba(200,50,10,.35)'); gr.addColorStop(1, 'rgba(120,20,0,0)'); g.fillStyle = gr; g.fillRect(0, 0, w, h); });
const fires = [];
{ const r = mulberry(31); const spots = [];
  for (let i = 0; i < 18; i++) { const b = buildings[2 + Math.floor(r() * (buildings.length - 4))]; spots.push([b.side * 19.8, 3 + r() * (b.h - 5), b.z + (r() - 0.5) * b.w * 0.7, 2 + r() * 3]); }
  for (const c of cars.slice(0, 6)) spots.push([c.x * 0.8, 0.8, c.z + 6, 2.5]);
  for (const [x, y, z, s] of spots) { const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: flameTex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })); sp.position.set(x, y, z); scene.add(sp); fires.push({ sp, s, seed: r() * 50, t0: 28 + r() * 3 }); } }

// ------------------------------------------------------------------ your phone + hand (child of camera)
const PHONE_W = 0.074, PHONE_H = 0.156;
const rtPhone = new THREE.WebGLRenderTarget(360, 760, { type: THREE.HalfFloatType });
rtPhone.texture.colorSpace = THREE.LinearSRGBColorSpace;
const uiCanvas = document.createElement('canvas'); uiCanvas.width = 360; uiCanvas.height = 760;
const uiTex = new THREE.CanvasTexture(uiCanvas); uiTex.colorSpace = THREE.SRGBColorSpace;
const crackCanvas = document.createElement('canvas'); crackCanvas.width = 360; crackCanvas.height = 760;
const crackTex = new THREE.CanvasTexture(crackCanvas);
const ashCanvas = document.createElement('canvas'); ashCanvas.width = 360; ashCanvas.height = 760;
const ashTex = new THREE.CanvasTexture(ashCanvas);
function screenMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: { tVid: { value: rtPhone.texture }, tUI: { value: uiTex }, tCrack: { value: crackTex }, tAsh: { value: ashTex }, uOn: { value: 1 }, uCrack: { value: 0 }, uAsh: { value: 0 }, uGain: { value: 1 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }',
    fragmentShader: `uniform sampler2D tVid,tUI,tCrack,tAsh; uniform float uOn,uCrack,uAsh,uGain; varying vec2 vUv;
      vec3 toLin(vec3 c){ return pow(c, vec3(2.2)); }
      void main(){
        vec2 uv = vUv;
        vec4 cr = texture2D(tCrack, uv);
        uv += (cr.g-.5)*.02*uCrack;            // refraction along cracks
        vec3 v = texture2D(tVid, uv).rgb;
        if(any(isnan(v)) || any(isinf(v))) v = vec3(0.);
        v = clamp(v, 0., 40.)*uGain;
        v = v/(1.+v*.6);
        vec4 ui = texture2D(tUI, uv);
        vec3 c = mix(v, toLin(ui.rgb), ui.a);
        c *= uOn;
        vec3 glass = vec3(.012,.013,.016);
        c += glass;
        c += vec3(.32)*cr.r*uCrack*(.4+.6*uOn);   // bright crack lines
        vec4 ash = texture2D(tAsh, vUv);
        c = mix(c, vec3(.32,.31,.30), ash.a*uAsh);
        gl_FragColor = vec4(c,1.);
      }`,
  });
}
const myScreenMat = screenMaterial();
function makeMyPhone(screenMat) {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(PHONE_W, PHONE_H, 0.009), flat(0x1b1c21, { roughness: 0.35, metalness: 0.5 }));
  g.add(body);
  const scr = new THREE.Mesh(new THREE.PlaneGeometry(PHONE_W - 0.005, PHONE_H - 0.006), screenMat); scr.position.z = 0.0046; g.add(scr);
  return { g, scr };
}
const handRig = new THREE.Group(); camera.add(handRig);
const myPhone = makeMyPhone(myScreenMat); handRig.add(myPhone.g);
const phoneCam = new THREE.PerspectiveCamera(66, 360 / 760, 0.05, 30000); phoneCam.rotation.order = 'YXZ';
handRig.add(phoneCam);
{
  const skin = flat(0xc89a7a), sleeve = flat(0x45506a);
  const palm = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.085, 0.03), skin); palm.position.set(0.004, -0.045, -0.02); handRig.add(palm);
  const thumb = new THREE.Mesh(new THREE.BoxGeometry(0.018, 0.06, 0.02), skin); thumb.position.set(-0.042, -0.02, 0.0); thumb.rotation.z = -0.35; handRig.add(thumb);
  for (let i = 0; i < 3; i++) { const f = new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.014, 0.014), skin); f.position.set(0.039, -0.005 - i * 0.022, -0.002); handRig.add(f); }
  const wristS = new THREE.Mesh(new THREE.CylinderGeometry(0.024, 0.026, 0.06, 6), skin); wristS.position.set(0.012, -0.11, -0.035); wristS.rotation.set(0.6, 0, 0.3); handRig.add(wristS);
  const wrist = new THREE.Mesh(new THREE.CylinderGeometry(0.034, 0.042, 0.26, 7), sleeve); wrist.position.set(0.045, -0.24, -0.1); wrist.rotation.set(0.6, 0, 0.3); handRig.add(wrist);
}

// ------------------------------------------------------------------ close-up scene (cracked phone in the dust)
const closeScene = new THREE.Scene();
closeScene.fog = new THREE.Fog(0x2a2724, 0.4, 1.4);
closeScene.background = new THREE.Color(0x1d1b19);
const closeCam = new THREE.PerspectiveCamera(42, W / H, 0.01, 10);
const closeScreenMat = screenMaterial();
const lyingPhone = makeMyPhone(closeScreenMat);
lyingPhone.g.rotation.set(-Math.PI / 2, 0, 0.1); lyingPhone.g.position.set(0, 0.006, 0);
closeScene.add(lyingPhone.g);
{
  const geo = new THREE.PlaneGeometry(2.4, 2.4, 40, 40); const p = geo.attributes.position; const r = mulberry(6);
  for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i); const d = Math.hypot(x, y); p.setZ(i, (r() - 0.5) * 0.012 + (d < 0.12 ? -0.004 : 0)); }
  geo.computeVertexNormals();
  const g = new THREE.Mesh(geo, flat(0x77716b)); g.rotation.x = -Math.PI / 2; closeScene.add(g);
  for (let i = 0; i < 90; i++) {
    const sz = 0.004 + r() * 0.02; const m = new THREE.Mesh(new THREE.IcosahedronGeometry(sz, 0), flat(r() < 0.3 ? 0x3a3532 : r() < 0.5 ? 0x9a948c : 0x5d5751));
    let x, z; do { x = (r() - 0.5) * 0.9; z = (r() - 0.5) * 0.9; } while (Math.abs(x) < 0.06 && Math.abs(z) < 0.1);
    m.position.set(x, sz * 0.4, z); m.rotation.set(r() * 3, r() * 3, r() * 3); closeScene.add(m);
  }
  const chunk = new THREE.Mesh(new THREE.IcosahedronGeometry(0.06, 0), flat(0x2a2422)); chunk.position.set(0.16, 0.02, -0.12); chunk.scale.set(1.4, 0.6, 1); closeScene.add(chunk);
  const glassShard = new THREE.Mesh(shardGeo, new THREE.MeshBasicMaterial({ color: 0x8aa0aa, side: THREE.DoubleSide })); glassShard.scale.setScalar(0.25); glassShard.rotation.x = -Math.PI / 2; glassShard.position.set(-0.11, 0.004, 0.09); closeScene.add(glassShard);
}
closeScene.add(new THREE.AmbientLight(0x9a9aa0, 1.25));
const closeKey = new THREE.DirectionalLight(0xff9a50, 0.9); closeKey.position.set(1, 0.6, -0.4); closeScene.add(closeKey);
const closeFill = new THREE.DirectionalLight(0x8090a0, 0.35); closeFill.position.set(-0.5, 1, 0.6); closeScene.add(closeFill);
const screenGlow = new THREE.PointLight(0x60ffc0, 0.0, 0.5, 1.5); screenGlow.position.set(0, 0.04, 0); closeScene.add(screenGlow);
// falling ash (grey snow)
const ASH = 700;
const ashGeo = new THREE.BufferGeometry(); ashGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(ASH * 3), 3));
const ashSprite = canvasTex(32, 32, (g) => { const gr = g.createRadialGradient(16, 16, 0, 16, 16, 16); gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.5, 'rgba(255,255,255,.6)'); gr.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = gr; g.fillRect(0, 0, 32, 32); });
const ashPts = new THREE.Points(ashGeo, new THREE.PointsMaterial({ map: ashSprite, color: 0xa29c96, size: 0.007, transparent: true, depthWrite: false, sizeAttenuation: true }));
ashPts.frustumCulled = false; closeScene.add(ashPts);
const ashData = []; { const r = mulberry(12); for (let i = 0; i < ASH; i++) ashData.push({ x: (r() - 0.5) * 0.7, z: (r() - 0.5) * 0.9, y0: r() * 0.5, sp: 0.035 + r() * 0.03, ph: r() * 6 }); }

// crack + ash overlays for the phone screen
(function drawCracks() {
  const g = crackCanvas.getContext('2d'); const r = mulberry(404);
  g.clearRect(0, 0, 360, 760);
  // red channel = bright crack line, green = refraction offset
  g.fillStyle = 'rgb(0,128,0)'; g.fillRect(0, 0, 360, 760);
  const cx = 250, cy = 210;
  g.lineCap = 'round';
  const branch = (x, y, ang, len, w, depth) => {
    let px = x, py = y;
    const steps = 6 + Math.floor(r() * 5);
    for (let s = 0; s < steps; s++) {
      ang += (r() - 0.5) * 0.6; const l = len / steps;
      const nx = px + Math.cos(ang) * l, ny = py + Math.sin(ang) * l;
      g.strokeStyle = `rgb(255,${100 + r() * 100 | 0},0)`; g.lineWidth = w; g.beginPath(); g.moveTo(px, py); g.lineTo(nx, ny); g.stroke();
      if (depth < 2 && r() < 0.28) branch(nx, ny, ang + (r() - 0.5) * 1.6, len * 0.45, w * 0.7, depth + 1);
      px = nx; py = ny;
    }
  };
  for (let i = 0; i < 9; i++) branch(cx, cy, (i / 9) * Math.PI * 2 + r() * 0.3, 200 + r() * 520, 1.6 + r() * 1.2, 0);
  for (let k = 1; k < 4; k++) { g.strokeStyle = 'rgb(200,160,0)'; g.lineWidth = 1.2; g.beginPath(); for (let a = 0; a <= 12; a++) { const an = a / 12 * Math.PI * 2; const rr = k * 22 + r() * 10; const x = cx + Math.cos(an) * rr, y = cy + Math.sin(an) * rr; a ? g.lineTo(x, y) : g.moveTo(x, y); } g.stroke(); }
  crackTex.needsUpdate = true;
})();
const ashSpots = []; { const r = mulberry(77); for (let i = 0; i < 70; i++) ashSpots.push({ x: r() * 360, y: r() * 760, rad: 1.5 + r() * 3.5, t: 34.5 + r() * 7.5 }); }
function drawAsh(t) {
  const g = ashCanvas.getContext('2d'); g.clearRect(0, 0, 360, 760);
  for (const s of ashSpots) { if (t < s.t) continue; const a = clamp((t - s.t) / 0.4); g.fillStyle = `rgba(255,255,255,${0.75 * a})`; g.beginPath(); g.arc(s.x, s.y, s.rad, 0, Math.PI * 2); g.fill(); }
  ashTex.needsUpdate = true;
}

// ------------------------------------------------------------------ phone UI (2D canvas, 360x760)
function rr(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
function batteryIcon(g, x, y, pct, col) { g.strokeStyle = col; g.lineWidth = 2; rr(g, x, y, 34, 16, 4); g.stroke(); g.fillStyle = col; g.fillRect(x + 35, y + 5, 3, 6); g.fillRect(x + 3, y + 3, Math.max(1.5, 28 * pct / 100), 10); }
function drawPhoneUI(t, mode, battery, replayT) {
  const g = uiCanvas.getContext('2d'); g.clearRect(0, 0, 360, 760);
  g.font = '600 22px Inter, Arial, sans-serif'; g.textBaseline = 'middle';
  const noNet = mode === 'live' && t >= 7.35;
  // status bar
  g.fillStyle = 'rgba(0,0,0,.25)'; g.fillRect(0, 0, 360, 44);
  g.fillStyle = '#fff'; g.textAlign = 'left'; g.fillText(mode === 'live' ? `23:${(41 + Math.floor(t / 60)).toString().padStart(2, '0')}` : '23:41', 22, 23);
  g.textAlign = 'right';
  const low = battery <= 19;
  g.font = '600 18px Inter, Arial, sans-serif';
  g.fillStyle = low ? '#ff453a' : '#fff'; g.fillText(`${battery} %`, 288, 23);
  batteryIcon(g, 296, 15, battery, low ? '#ff453a' : '#fff');
  if (noNet) { g.fillStyle = '#fff'; g.fillText('Kein Netz', 210, 23); }
  else { for (let i = 0; i < 4; i++) { g.fillStyle = '#fff'; g.fillRect(170 + i * 8, 30 - i * 5, 5, 6 + i * 5); } g.fillText('5G', 228, 23); }
  if (mode === 'live') {
    // recording UI
    const blink = Math.floor(t * 2) % 2 === 0;
    g.fillStyle = 'rgba(0,0,0,.35)'; rr(g, 120, 58, 120, 34, 17); g.fill();
    g.fillStyle = blink ? '#ff3b30' : 'rgba(255,59,48,.35)'; g.beginPath(); g.arc(140, 75, 7, 0, 7); g.fill();
    const rec = Math.floor(t + 7);
    g.fillStyle = '#fff'; g.textAlign = 'left'; g.font = '600 19px Inter, Arial, sans-serif';
    g.fillText(`00:${String(Math.floor(rec / 60)).padStart(2, '0')}:${String(rec % 60).padStart(2, '0')}`.slice(3), 156, 76);
    g.strokeStyle = '#fff'; g.lineWidth = 4; g.beginPath(); g.arc(180, 690, 34, 0, 7); g.stroke();
    g.fillStyle = '#ff3b30'; rr(g, 166, 676, 28, 28, 6); g.fill();
    if (noNet && t < 16) {
      const a = sstep(7.35, 7.6, t);
      g.globalAlpha = a; g.fillStyle = 'rgba(20,20,24,.85)'; rr(g, 70, 330, 220, 70, 18); g.fill();
      g.fillStyle = '#fff'; g.textAlign = 'center'; g.font = '700 26px Inter, Arial, sans-serif'; g.fillText('Kein Netz', 180, 357);
      g.font = '500 15px Inter, Arial, sans-serif'; g.fillStyle = '#bbb'; g.fillText('Notrufe nicht möglich', 180, 382); g.globalAlpha = 1;
    }
  } else {
    // playback UI
    const dur = 7, pos = clamp(replayT, 0, dur);
    g.fillStyle = 'rgba(0,0,0,.35)'; g.fillRect(0, 640, 360, 120);
    g.fillStyle = 'rgba(255,255,255,.35)'; g.fillRect(24, 668, 312, 5);
    g.fillStyle = '#fff'; g.fillRect(24, 668, 312 * pos / dur, 5); g.beginPath(); g.arc(24 + 312 * pos / dur, 670, 8, 0, 7); g.fill();
    g.font = '500 16px Inter, Arial, sans-serif'; g.textAlign = 'left'; g.fillText(`0:0${Math.floor(pos)}`, 24, 695); g.textAlign = 'right'; g.fillText('0:07', 336, 695);
    // speaker / captions
    const cap = t < 36.6 ? '[Jubel]' : t < 38.6 ? '[Lachen]' : '[Jubel, Rufe: „Wahnsinn!“]';
    g.textAlign = 'center'; g.font = '600 23px Inter, Arial, sans-serif';
    const tw = g.measureText(cap).width + 30; g.fillStyle = 'rgba(0,0,0,.6)'; rr(g, 180 - tw / 2, 584, tw, 38, 8); g.fill();
    g.fillStyle = '#fff'; g.fillText(cap, 180, 604);
    if (t > 39.7) {
      const a = sstep(39.7, 39.9, t);
      g.globalAlpha = a; g.fillStyle = 'rgba(15,15,18,.9)'; rr(g, 50, 300, 260, 130, 22); g.fill();
      batteryIcon(g, 162, 322, 1, '#ff453a');
      g.fillStyle = '#fff'; g.font = '700 24px Inter, Arial, sans-serif'; g.fillText('Akku leer', 180, 370);
      g.font = '500 16px Inter, Arial, sans-serif'; g.fillStyle = '#c8c8c8'; g.fillText('Gerät wird ausgeschaltet …', 180, 400); g.globalAlpha = 1;
    }
  }
  uiTex.needsUpdate = true;
}

// ------------------------------------------------------------------ post
const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 }));
const renderPass = new RenderPass(scene, camera); composer.addPass(renderPass);
const bloom = new UnrealBloomPass(new THREE.Vector2(W / 2, H / 2), 0.9, 0.55, 0.62); composer.addPass(bloom);
composer.addPass(new OutputPass());

// ------------------------------------------------------------------ battery value (shared with HUD)
export function batteryAt(t) {
  let prev = BATTERY[0][1], cur = BATTERY[0][1], start = 0;
  for (let i = 0; i < BATTERY.length; i++) if (t >= BATTERY[i][0]) { prev = i ? BATTERY[i - 1][1] : BATTERY[i][1]; cur = BATTERY[i][1]; start = BATTERY[i][0]; }
  const k = cur === 0 ? 1 : clamp((t - start) / 0.7);
  return Math.round(lerp(prev, cur, k));
}

// ------------------------------------------------------------------ world state as f(t)
const tmpM = new THREE.Matrix4(), tmpQ = new THREE.Quaternion(), tmpE = new THREE.Euler(), tmpV = new THREE.Vector3(), tmpS = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0);

function camPose(t) {
  // returns {x,y,z,yaw,pitch,roll}
  const sway = (s, f) => noise1(t * f, s) ;
  let p = { x: 0, y: 1.68, z: 0, yaw: -0.03, pitch: 0.17, roll: 0 };
  // 0–2.9 s: looking up into the aurora, then tilt down to the street
  const tilt = easeIO(clamp((t - 1.55) / 1.45));
  p.pitch = lerp(0.66, 0.17, tilt); p.yaw = lerp(-0.16, -0.03, tilt);
  // handheld
  p.yaw += sway(1, 0.35) * 0.012; p.pitch += sway(2, 0.4) * 0.01; p.roll += sway(3, 0.3) * 0.012;
  if (t > 16 && t < 20) { const k = sstep(16, 16.4, t) * (1 - sstep(18, 20, t)); p.z += 0.25 * sstep(16, 17, t); p.pitch -= 0.02 * k; }
  if (t >= 17) p.z += 0.25;
  // quake
  const q = sstep(19.9, 20.4, t) * (1 - sstep(23.6, 24.0, t));
  if (q > 0) { p.x += noise1(t * 11, 4) * 0.09 * q; p.y += noise1(t * 13, 5) * 0.08 * q; p.pitch += noise1(t * 9, 6) * 0.035 * q; p.roll += noise1(t * 10, 7) * 0.05 * q; p.yaw += noise1(t * 7, 8) * 0.03 * q; }
  // 24–25 silence: still. wave approaching -> trembling, then hit
  const tr = sstep(25.6, T_HIT_CAM, t) * (t < T_HIT_CAM ? 1 : 0);
  p.pitch += noise1(t * 25, 9) * 0.012 * tr; p.roll += noise1(t * 22, 10) * 0.015 * tr;
  if (t >= T_HIT_CAM) {
    const k = easeIO(clamp((t - T_HIT_CAM) / 0.75));
    const shake = Math.exp(-(t - T_HIT_CAM) * 2.5);
    p.x = lerp(p.x, 0.9, k); p.y = lerp(p.y, 0.42, k); p.z = lerp(p.z, 7.5, k);
    p.pitch = lerp(p.pitch, 0.42, k); p.roll = lerp(p.roll, 0.16, k); p.yaw = lerp(p.yaw, 0.06, k);
    p.pitch += noise1(t * 30, 11) * 0.12 * shake; p.roll += noise1(t * 27, 12) * 0.2 * shake; p.yaw += noise1(t * 24, 13) * 0.08 * shake;
    p.pitch += 0.04 * sstep(29, 34, t); p.z -= 0.3 * sstep(29, 34, t);
    p.pitch += noise1(t * 0.5, 14) * 0.01; p.roll += noise1(t * 0.4, 15) * 0.012;
  }
  return p;
}

function setPerson(P, t) {
  const { kind } = P;
  let x = P.x, z = P.z, heading = P.heading, y = 0;
  let fallDir = 0, fall = 0;
  let armR = -0.15, armL = 0.15, armRz = 0, armLz = 0, headX = -0.35, legSwing = 0, lean = 0;
  const ph = P.ph;
  if (kind === 'film') { armR = -2.45 + Math.sin(t * 0.8 + ph) * 0.05; armRz = 0.25; armL = R2(P) ? -2.3 : -0.1; armLz = R2(P) ? -0.35 : 0.1; headX = -0.25; }
  if (kind === 'point') { armL = -2.6 + Math.sin(t * 0.6 + ph) * 0.15; armLz = -0.2; armR = -0.1; headX = -0.45; }
  if (kind === 'watch') { armR = -0.05 + Math.sin(t + ph) * 0.03; armL = 0.05; headX = -0.5; }
  // idle sway
  lean = Math.sin(t * 0.7 + ph) * 0.03;
  // meteor: cheering
  if (t > 11.6 && t < 16.2 && P.cheer) {
    const k = sstep(11.6, 12.2, t) * (1 - sstep(15.9, 16.2, t));
    const pump = Math.sin((t + ph) * 7.5);
    if (kind === 'film') { armL = lerp(armL, -2.75 + pump * 0.35, k); armLz = lerp(armLz, -0.3, k); }
    else { armR = lerp(armR, -2.8 + pump * 0.3, k); armRz = lerp(armRz, 0.3, k); armL = lerp(armL, -2.7 - pump * 0.3, k); }
    if (P.jump) y += Math.max(0, Math.sin((t + ph) * 7.5)) * 0.12 * k;
    headX = lerp(headX, -0.55, k);
  }
  // flash: recoil, arms sink; some run away
  if (t > 16.1) {
    const k = sstep(16.1, 16.9, t);
    z += 0.6 * k; headX = lerp(headX, -0.1, k);
    const sink = sstep(17.0, 19.5, t);
    armR = lerp(armR, kind === 'film' ? -1.4 : -0.3, sink); armL = lerp(armL, -0.2, sink);
    if (t > P.runAt) {
      const k2 = sstep(P.runAt, P.runAt + 0.5, t);
      const dt = Math.max(0, t - P.runAt - 0.2);
      const dir = Math.atan2(P.runDir, 0.9); // mostly towards camera, sideways away from centre
      heading = lerp(P.heading, dir, k2);
      const sp = 3.2 * Math.min(dt, 6.5 - (dt > 6.5 ? 0 : 0));
      x += Math.sin(dir) * sp * k2; z += Math.cos(dir) * sp * k2;
      // stop before reaching the camera
      if (z > -1.2) { z = -1.2; }
      legSwing = Math.sin((t + ph) * 11) * 0.7 * k2; armR = lerp(armR, -Math.sin((t + ph) * 11) * 0.8, k2); armL = lerp(armL, Math.sin((t + ph) * 11) * 0.8, k2);
      armRz = armLz = 0;
    }
  }
  // quake: stumble / fall
  if (t > 20.1) {
    const q = sstep(20.1, 20.5, t) * (1 - sstep(23.6, 24, t));
    lean += noise1(t * 6 + ph, 3) * 0.12 * q; y += Math.abs(noise1(t * 14 + ph, 2)) * 0.05 * q;
    if (t > P.quakeFall) { fallDir = P.quakeDir; fall = sstep(P.quakeFall, P.quakeFall + 0.55, t) * 1.45; legSwing = 0; }
  }
  // shock wave: thrown towards the camera
  const th = waveHit(z);
  if (t > th) {
    const dt = t - th;
    fallDir = fall > 0 ? lerp(fallDir, 0, 0.5) : 0;
    fall = Math.max(fall, sstep(0, 0.35, dt) * 1.5);
    z += 9 * (1 - Math.exp(-dt * 2.2)); x += (x > 0 ? 1 : -1) * 1.5 * (1 - Math.exp(-dt * 2));
    y += Math.max(0, 1.4 * Math.sin(Math.min(dt * 4, Math.PI)));
  }
  P.root.position.set(x, y, z);
  P.fallYaw.rotation.y = fallDir;
  P.tilt.rotation.x = fall;
  P.body.rotation.y = heading - fallDir;
  P.body.rotation.z = lean;
  P.arms[1].rotation.set(armR, 0, armRz); P.arms[0].rotation.set(armL, 0, armLz);
  P.legs[0].rotation.x = legSwing; P.legs[1].rotation.x = -legSwing;
  P.neck.rotation.x = headX;
}
function R2(P) { return (P.ph * 1000 | 0) % 3 === 0; }

function updatePeople(t) {
  const hideAll = t > 28.25;
  for (let i = 0; i < people.length; i++) {
    const P = people[i];
    P.root.visible = !hideAll;
    if (hideAll) {
      P.loose.visible = false;
      if (i >= 8 && i < 13 && t > 28.25) {
        // a few silhouettes running through the dust in the distance
        P.root.visible = true;
        const dir = i % 2 ? 1 : -1; const x = -dir * 22 + dir * (t - 28.4 + i * 0.7) * 3.6, z = -26 - i * 3;
        P.root.position.set(x, 0, z); P.fallYaw.rotation.y = 0; P.tilt.rotation.x = 0; P.body.rotation.set(0, dir * Math.PI / 2, 0);
        const s = Math.sin((t + i) * 10); P.legs[0].rotation.x = s * 0.7; P.legs[1].rotation.x = -s * 0.7; P.arms[0].rotation.set(-s * 0.8, 0, 0); P.arms[1].rotation.set(s * 0.8, 0, 0);
        P.phone.visible = false; P.neck.rotation.x = 0.2;
      }
      continue;
    }
    setPerson(P, t);
    const hasPhone = P.kind === 'film';
    const dropped = hasPhone && t > P.dropAt;
    P.phone.visible = hasPhone && !dropped;
    P.glow.material.opacity = t > 7.35 && t < 7.9 ? (Math.floor(t * 20) % 2 ? 0.05 : 0.4) : 0.35;
    if (dropped) {
      if (!P.dropCache) {
        setPerson(P, P.dropAt); P.root.updateMatrixWorld(true);
        P.phone.matrixWorld.decompose(tmpV, tmpQ, tmpS);
        P.dropCache = { p: tmpV.clone(), q: tmpQ.clone(), r: mulberry(P.ph * 1000 | 0) };
        P.dropCache.vx = (P.dropCache.r() - 0.5) * 1.5; P.dropCache.vz = (P.dropCache.r() - 0.5) * 1.5; P.dropCache.face = P.dropCache.r() < 0.5;
        setPerson(P, t);
      }
      const c = P.dropCache; const dt = t - P.dropAt;
      const tFall = Math.sqrt(2 * c.p.y / 9.81);
      const k = Math.min(dt, tFall);
      P.loose.visible = true;
      let px = c.p.x + c.vx * k, pz = c.p.z + c.vz * k, py = Math.max(0.01, c.p.y - 4.9 * k * k);
      const th = waveHit(pz);
      if (t > th) { const d2 = t - th; pz += 12 * (1 - Math.exp(-d2 * 2)); py += Math.max(0, Math.sin(Math.min(d2 * 5, Math.PI)) * 0.8); }
      P.loose.position.set(px, py, pz);
      if (dt < tFall) { P.loose.quaternion.copy(c.q); P.loose.rotateX(dt * 9); P.loose.rotateZ(dt * 5); }
      else { P.loose.rotation.set(c.face ? -Math.PI / 2 : Math.PI / 2, 0, c.vx * 3); }
    } else P.loose.visible = false;
  }
}

function updateWorld(t) {
  // sky / aurora
  skyU.uTime.value = t;
  const aur = 1.0 + 0.55 * sstep(7.6, 10.5, t) + 0.15 * sstep(11, 15, t);
  skyU.uAurora.value = aur * (1 - 0.35 * sstep(16, 17, t) * (1 - sstep(17, 19, t)));
  skyU.uRed.value = sstep(8, 12, t) * 0.7;
  skyU.uCity.value = 1 - sstep(7.4, 8.6, t);
  const flash = t < 16 ? 0 : t < 16.12 ? 6 : 6 * Math.exp(-(t - 16.12) * 2.4);
  skyU.uFlash.value = flash;
  const glow = sstep(16, 16.3, t) * (1.6 - 0.6 * sstep(17, 20, t)) + 0.2 * sstep(20, 30, t);
  skyU.uGlow.value = glow;
  skyU.uDust.value = sstep(T_HIT_CAM - 0.2, T_HIT_CAM + 0.4, t) * 0.55 * (1 - sstep(28.4, 29.6, t)) + sstep(28.4, 34, t) * 0.97 * (t > 28.4 ? 1 : 0);
  skyU.uDust.value = Math.max(skyU.uDust.value, sstep(29.2, 34.0, t) * 0.97, t > 27.5 && t < 29.2 ? 0.32 : 0);
  skyU.uDustCol.value.setRGB(0.21, 0.17, 0.14);

  // fog
  const dust = sstep(T_HIT_CAM - 0.1, T_HIT_CAM + 0.3, t);
  fog.density = lerp(0.0016, 0.035, dust) - 0.012 * sstep(28.2, 29.6, t) + 0.02 * sstep(30, 34, t);
  fog.color.setRGB(lerp(0.027, 0.2, dust), lerp(0.043, 0.16, dust), lerp(0.094, 0.13, dust));
  if (t > 16 && t < T_HIT_CAM) { const k = sstep(16, 16.3, t) * (1 - sstep(24, 26, t) * 0.5); fog.color.setRGB(lerp(0.027, 0.16, k), lerp(0.043, 0.07, k), lerp(0.094, 0.04, k)); }

  // lights
  const aurL = (1 - sstep(16, 16.4, t) * 0.6) * (1 - dust * 0.8);
  hemi.intensity = 0.75 * aurL + 0.15 * sstep(7.6, 10, t) * aurL;
  hemi.color.setHex(0x5fd9b0); if (t > 16) hemi.color.lerp(new THREE.Color(0xff8a4a), sstep(16, 17, t)); if (dust > 0) hemi.color.lerp(new THREE.Color(0x8a7a6a), dust);
  auroraLight.intensity = 0.55 * aur * aurL; pinkLight.intensity = 0.3 * aur * aurL;
  blastLight.intensity = flash * 2.2 + glow * 0.9 * (1 - dust * 0.6);
  blastLight.color.setHex(t < 16.4 ? 0xfff2e0 : 0xff8040);
  const fireOn = sstep(28, 29.5, t);
  fireLight.intensity = fireOn * (14 + noise1(t * 8, 21) * 5); fireLight2.intensity = fireOn * (10 + noise1(t * 9, 22) * 4);

  // lamps: flicker and go out from far to near
  let li = 0;
  const near = [...lamps].sort((a, b) => b.z - a.z);
  for (const L of lamps) {
    const off = 7.25 + (-L.z / 170) * -1 + 1.1 + (L.side > 0 ? 0.08 : 0);
    const tOff = 8.35 - (-L.z / 170) * 1.05 + (L.side > 0 ? 0.06 : 0);
    let on = t < tOff - 0.3 ? 1 : t < tOff ? (hash1(Math.floor(t * 24) + L.seed) > 0.5 ? 1 : 0.15) : 0;
    L.headMat.color.setRGB(on ? 1 : 0.08, on ? 0.76 : 0.07, on ? 0.48 : 0.06);
    L.glow.visible = on > 0.5; L.pool.material.opacity = 0.38 * on;
    L.on = on; void off;
    // tilt during quake / blast
    const q = sstep(20.2, 20.6, t) * (1 - sstep(23.6, 24, t));
    L.g.rotation.z = noise1(t * 5 + L.seed, 31) * 0.05 * q + (t > waveHit(L.z) ? -0.0 : 0);
    L.g.rotation.x = t > waveHit(L.z) ? sstep(waveHit(L.z), waveHit(L.z) + 0.3, t) * (0.5 + hash1(L.seed) * 0.6) : 0;
  }
  for (let i = 0; i < lampLights.length; i++) { const L = near[i]; const l = lampLights[i]; l.position.set(L.side * 11.2, 7.1, L.z); l.intensity = 9 * L.on; }

  // windows: blackout block by block
  const winBase = 1 - 0;
  for (const m of windowMats) { if (m.userData.tOff === undefined) m.userData.tOff = 7.45 + hash1(windowMats.indexOf(m)) * 1.3; m.emissiveIntensity = t < m.userData.tOff ? 1.25 * winBase : t < m.userData.tOff + 0.15 ? (Math.floor(t * 30) % 2 ? 0.8 : 0.1) : 0; }
  for (const o of towers) if (o.userData.blink !== undefined) o.visible = t < 7.6 && Math.floor(t * 1.2 + o.userData.blink * 2) % 2 === 0;

  // trees sway in quake and blast
  for (const T of trees) {
    const q = sstep(20.2, 20.6, t) * (1 - sstep(23.6, 24, t));
    T.g.rotation.z = noise1(t * 4 + T.seed, 41) * 0.06 * q;
    const th = waveHit(T.z); const b = t > th ? sstep(th, th + 0.25, t) : 0;
    T.g.rotation.x = b * (1.1 + hash1(T.seed) * 0.4);
    T.crown.visible = !(t > th + 0.15 && hash1(T.seed + 3) < 0.5);
  }

  // cars
  for (const C of cars) {
    let x = C.x, y = 0, z = C.z, rx = 0, rz = 0, ry = C.ry;
    const q = sstep(20.2, 20.5, t) * (1 - sstep(23.6, 24, t));
    y += Math.abs(noise1(t * 9 + C.seed, 51)) * 0.35 * q; rx += noise1(t * 7 + C.seed, 52) * 0.06 * q; rz += noise1(t * 8 + C.seed, 53) * 0.07 * q;
    const th = waveHit(C.z);
    if (t > th) {
      const dt = t - th; const k = 1 - Math.exp(-dt * 1.7);
      z += 16 * k; x += (C.x > 0 ? 1 : -1) * 2 * k;
      rx += -C.spin * sstep(0, 1.1, dt);
      y += Math.abs(Math.sin(rx)) * 1.3 + Math.max(0, Math.sin(Math.min(dt * 3, Math.PI))) * 2.2;
    }
    C.g.position.set(x, y, z); C.g.rotation.set(0, ry, 0); C.body.rotation.set(rx, 0, rz);
    const haz = t > 20.6 && Math.floor((t + C.seed) * 1.6) % 2 === 0;
    C.hazMat.color.setHex(haz ? 0xffa020 : 0x2a1600);
  }

  // cracks
  for (const c of cracks) {
    const prog = clamp((t - 20.3 - c.delay) / 1.6);
    const n = c.pts.length; const len = prog * (n - 1);
    const widen = c.w0 * (1 + 2.5 * sstep(20.5, 23.5, t)) + 0.15 * sstep(T_HIT_CAM, T_HIT_CAM + 1, t);
    for (let i = 0; i < n; i++) {
      const [px, pz] = c.pts[i]; const w = i <= len ? widen * (0.5 + 0.5 * hash1(i + c.seed)) * Math.min(1, len - i + 1) : 0;
      c.pos.set([px - w, 0.015, pz, px + w, 0.015, pz + w * 0.3], i * 6);
    }
    c.m.geometry.attributes.position.needsUpdate = true; c.m.visible = t > 20.3;
  }

  // meteor
  const mI = sstep(10.9, 11.6, t) * (t < 16 ? 1 : 0);
  meteorHead.visible = trail.visible = mI > 0;
  if (mI > 0) {
    const d = meteorDir(t); const dist = 9000;
    meteorHead.position.copy(camera.position).addScaledVector(d, dist);
    const bright = lerp(0.5, 1.6, sstep(11, 16, t));
    meteorHead.scale.setScalar(lerp(180, 520, sstep(11, 16, t)));
    meteorHead.material.opacity = mI;
    meteorHead.material.color.setRGB(bright, bright, bright * 0.9);
    const pos = trailGeo.attributes.position, a = trailGeo.attributes.a;
    const camPos = camera.position;
    for (let i = 0; i < TRAIL; i++) {
      const tt = t - i * 0.028 * (1 + sstep(11, 16, t));
      const p = meteorDir(Math.max(tt, 10.6)).multiplyScalar(dist).add(camPos);
      const p2 = meteorDir(Math.max(tt - 0.02, 10.6)).multiplyScalar(dist).add(camPos);
      const dir = p2.clone().sub(p).normalize(); const toCam = camPos.clone().sub(p).normalize();
      const side = new THREE.Vector3().crossVectors(dir, toCam).normalize();
      const w = lerp(55, 4, i / TRAIL) * lerp(0.7, 1.6, sstep(11, 16, t));
      pos.setXYZ(i * 2, p.x + side.x * w, p.y + side.y * w, p.z + side.z * w);
      pos.setXYZ(i * 2 + 1, p.x - side.x * w, p.y - side.y * w, p.z - side.z * w);
      const al = Math.pow(1 - i / TRAIL, 1.6); a.setX(i * 2, al); a.setX(i * 2 + 1, al);
    }
    pos.needsUpdate = a.needsUpdate = true;
    trailMat.uniforms.uI.value = mI * lerp(0.9, 2.2, sstep(11, 16, t));
  }

  // fireball / mushroom cloud
  const fT = t - 16;
  fire.visible = fT > 0;
  if (fT > 0) {
    fireU.uTime.value = t; fireU.uHeat.value = Math.exp(-fT * 0.12);
    const rise = 300 + 1500 * (1 - Math.exp(-fT * 0.3)), rad = 380 + 850 * (1 - Math.exp(-fT * 0.25));
    fireBall.position.set(0, rise, 0); fireBall.scale.set(rad * 1.25, rad * 0.8, rad * 1.25); fireBall.rotation.y = fT * 0.05;
    fireStem.position.set(0, rise / 2, 0); fireStem.scale.set(rad * 0.55, rise, rad * 0.55);
    fireSkirt.position.set(0, 60, 0); fireSkirt.scale.set(rad * 1.5, 90, rad * 1.5);
    fireU.uA.value = 1 - 0.85 * sstep(T_HIT_CAM - 0.3, T_HIT_CAM + 0.6, t);
  }

  // shock wave wall
  const zw = waveZ(t);
  const wallOn = t > WAVE_T0 - 0.6 && zw < 8;
  wallLayers.forEach((m, i) => {
    m.visible = wallOn;
    if (!wallOn) return;
    const z = zw - i * 9;
    const far = z < -150;
    const wdt = far ? 380 : 60, hgt = far ? 140 : 70;
    m.position.set(0, hgt / 2 - 2, z); m.scale.set(wdt, hgt, 1);
    m.material.uniforms.uTime.value = t; m.material.uniforms.uA.value = (i === 0 ? 0.75 : 0.9) * sstep(WAVE_T0 - 0.6, WAVE_T0 + 0.3, t);
  });

  // glass shards
  for (let i = 0; i < SHARDS; i++) {
    const s = shardData[i]; const th = waveHit(s.z) - 0.05;
    if (t < th || t > th + 6) { tmpM.makeScale(0, 0, 0); shards.setMatrixAt(i, tmpM); continue; }
    const dt = t - th;
    const drag = (1 - Math.exp(-dt * 1.5)) / 1.5;
    let y = s.y + s.vy * dt - 4.9 * dt * dt; const x = s.x + s.vx * drag, z = s.z + s.vz * drag;
    if (y < 0.02) y = 0.02;
    tmpE.set(s.rx + dt * s.sp, s.ry + dt * s.sp * 0.7, s.rz); tmpQ.setFromEuler(tmpE);
    tmpM.compose(tmpV.set(x, y, z), tmpQ, tmpS.setScalar(s.sc)); shards.setMatrixAt(i, tmpM);
  }
  shards.instanceMatrix.needsUpdate = true;
  shardMat.color.setRGB(0.9, 0.75, 0.6);

  // falling burning debris
  for (let i = 0; i < DEB; i++) {
    const d = debData[i];
    if (t < d.t0) { tmpM.makeScale(0, 0, 0); debris.setMatrixAt(i, tmpM); debTrails.setMatrixAt(i, tmpM); continue; }
    const dt = t - d.t0; let y = d.y0 + d.vy * dt - 2 * dt * dt; const x = d.x + d.vx * dt, z = d.z + d.vz * dt;
    let landed = false; if (y < 0.2) { y = 0.2; landed = true; }
    tmpE.set(dt * d.spin, dt * d.spin * 0.6, 0); tmpQ.setFromEuler(tmpE);
    tmpM.compose(tmpV.set(x, y, z), tmpQ, tmpS.setScalar(d.sc * (landed ? 0.6 : 1))); debris.setMatrixAt(i, tmpM);
    if (landed) { tmpM.makeScale(0, 0, 0); debTrails.setMatrixAt(i, tmpM); continue; }
    const v = new THREE.Vector3(d.vx, d.vy - 4 * dt, d.vz); const L = 3 + v.length() * 0.35;
    tmpQ.setFromUnitVectors(up, v.clone().normalize().negate());
    const c = tmpV.set(x, y, z).addScaledVector(v.clone().normalize(), -L / 2);
    tmpM.compose(c, tmpQ, tmpS.set(d.sc * 1.4, L, d.sc * 1.4)); debTrails.setMatrixAt(i, tmpM);
  }
  debris.instanceMatrix.needsUpdate = debTrails.instanceMatrix.needsUpdate = true;
  debris.visible = debTrails.visible = t > 27.8;

  // dust billows
  for (const D of dusts) {
    const dt = t - D.t0; D.sp.visible = dt > 0;
    if (dt <= 0) continue;
    D.sp.position.set(D.x, D.y0 + D.size * 0.3 + dt * D.rise, D.z + dt * 2);
    const s = D.size * (1 + dt * 0.25); D.sp.scale.set(s, s, 1); D.sp.material.rotation = D.rot + dt * 0.05;
    D.sp.material.opacity = sstep(0, 1.5, dt) * (0.45 + 0.4 * sstep(30, 34, t));
    D.sp.material.color.setRGB(0.42, 0.37, 0.33).multiplyScalar(1 + 0.3 * fireOn);
  }
  // fires
  for (const F of fires) {
    const on = sstep(F.t0, F.t0 + 0.8, t); F.sp.visible = on > 0;
    const fl = 1 + noise1(t * 9 + F.seed, 61) * 0.25;
    F.sp.scale.set(F.s * fl * on, F.s * 2 * fl * on, 1); F.sp.material.opacity = on * (0.8 + 0.2 * noise1(t * 13 + F.seed, 62));
  }

  updatePeople(t);

  // camera
  const P = camPose(t);
  camera.position.set(P.x, P.y, P.z); camera.rotation.set(P.pitch, P.yaw, P.roll);
  camera.updateMatrixWorld(true);

  // your phone in hand
  let hx = 0.068, hy = -0.07, hz = -0.42, hrx = 0.03, hry = -0.12, hrz = 0.04;
  hx += noise1(t * 0.9, 71) * 0.003; hy += noise1(t * 0.8, 72) * 0.003;
  // look-up at the start: phone already pointing up
  if (t > 11.5 && t < 16) { hy += 0.004 * Math.sin(t * 7); }
  const lower = sstep(16.4, 17.6, t);
  hy -= 0.07 * lower; hrx -= 0.35 * lower; hrz += 0.1 * lower;
  const q = sstep(20.0, 20.4, t);
  hx += noise1(t * 12, 73) * 0.012 * q; hy += noise1(t * 14, 74) * 0.012 * q;
  const drop = clamp((t - 21.25) / 0.7);
  if (drop > 0) { hy -= drop * drop * 0.6; hrx += drop * 2.5; hrz -= drop * 1.4; hx += drop * 0.08; }
  handRig.visible = t < 22.2;
  handRig.position.set(hx, hy, hz); handRig.rotation.set(hrx, hry, hrz);
  phoneCam.rotation.set(-hrx * 0.5, -hry, -hrz);
}

// ------------------------------------------------------------------ close-up state (34–42 s)
function updateClose(t) {
  const k = clamp((t - 34) / 8);
  const camH = lerp(0.29, 0.205, easeIO(k)), camZ = lerp(0.2, 0.135, easeIO(k));
  closeCam.position.set(0.012 + noise1(t * 0.3, 81) * 0.003, camH, camZ);
  closeCam.lookAt(0.004, 0, 0.004);
  const pos = ashGeo.attributes.position;
  for (let i = 0; i < ASH; i++) {
    const a = ashData[i]; let y = (a.y0 - (t - 34) * a.sp) % 0.5; if (y < 0) y += 0.5;
    pos.setXYZ(i, a.x + Math.sin(t * 0.8 + a.ph) * 0.01 + (t - 34) * 0.004, y, a.z + Math.cos(t * 0.6 + a.ph) * 0.008);
  }
  pos.needsUpdate = true;
  const on = t < 40.72 ? 1 : t < 41.0 ? (Math.floor(t * 28) % 2 ? 0.25 : 0.85) : 0;
  closeScreenMat.uniforms.uOn.value = on * (t < 34.25 ? sstep(33.9, 34.25, t) : 1);
  closeScreenMat.uniforms.uCrack.value = 1;
  closeScreenMat.uniforms.uAsh.value = 1;
  closeScreenMat.uniforms.uGain.value = 2.8;
  screenGlow.intensity = 0.0025 * on;
  closeKey.intensity = 0.55 + noise1(t * 6, 82) * 0.15;
  drawAsh(t);
}

// ------------------------------------------------------------------ 2D overlay (HUD, captions, cards)
const out = document.getElementById('out');
const ctx = out.getContext('2d');
const grain = [];
for (let i = 0; i < 6; i++) { const c = document.createElement('canvas'); c.width = 540; c.height = 960; const g = c.getContext('2d'); const im = g.createImageData(540, 960); const r = mulberry(70 + i); for (let p = 0; p < im.data.length; p += 4) { const v = r() * 255; im.data[p] = im.data[p + 1] = im.data[p + 2] = v; im.data[p + 3] = 255; } g.putImageData(im, 0, 0); grain.push(c); }

function wrapLines(text, maxW) {
  const words = text.split(' '); const lines = []; let cur = '';
  for (const w of words) { const test = cur ? cur + ' ' + w : w; if (ctx.measureText(test).width > maxW && cur) { lines.push(cur); cur = w; } else cur = test; }
  if (cur) lines.push(cur); return lines;
}
function fadeIn(t, a, b, fi = 0.35, fo = 0.3) { return sstep(a, a + fi, t) * (1 - sstep(b - fo, b, t)); }

function drawHUD(t) {
  const bat = batteryAt(t);
  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,.65)'; ctx.shadowBlur = 18;
  const x = 66;
  const lowCol = bat <= 6 ? '#ff6b5e' : bat <= 19 ? '#ffb27a' : '#ffffff';
  ctx.fillStyle = 'rgba(255,255,255,.88)';
  ctx.font = '400 30px "Playfair SC"'; ctx.letterSpacing = '5px'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  ctx.fillText('Dein Akku', x, 196);
  // continuous drain bar
  const frac = lerp(0.34, 0, clamp(t / 41)) / 0.34;
  ctx.shadowBlur = 0;
  ctx.fillStyle = 'rgba(255,255,255,.22)'; ctx.fillRect(x + 2, 212, 196, 3);
  ctx.fillStyle = lowCol; ctx.fillRect(x + 2, 212, 196 * frac, 3);
  ctx.shadowBlur = 18;
  // big number
  const pulse = bat <= 6 && bat > 0 ? 0.55 + 0.45 * Math.abs(Math.sin(t * 4)) : 1;
  ctx.globalAlpha = pulse;
  ctx.fillStyle = lowCol; ctx.letterSpacing = '0px';
  ctx.font = '500 132px "Playfair"';
  const numStr = String(bat);
  ctx.fillText(numStr, x - 4, 338);
  const nw = ctx.measureText(numStr).width;
  ctx.font = '400 70px "Playfair"'; ctx.fillText('%', x + nw + 8, 338);
  ctx.globalAlpha = 1;
  // second line (changes per scene)
  let line = '', la = 0;
  for (const L of HUD_LINES) if (t >= L.a && t < L.b) { line = typeof L.text === 'function' ? L.text(t) : L.text; la = fadeIn(t, L.a, L.b, 0.3, 0.25); }
  if (line) {
    ctx.globalAlpha = la; ctx.fillStyle = 'rgba(255,255,255,.92)';
    ctx.font = '400 27px "Playfair SC"'; ctx.letterSpacing = '4px';
    const lines = wrapLines(line, 620);
    lines.forEach((l, i) => ctx.fillText(l, x, 388 + i * 36));
    ctx.globalAlpha = 1;
  }
  ctx.restore();
}

function drawCaption(t) {
  for (const T of TEXTS) {
    if (t < T.a || t >= T.b) continue;
    const a = fadeIn(t, T.a, T.b, 0.35, 0.3);
    const rise = (1 - sstep(T.a, T.a + 0.5, t)) * 14;
    ctx.save();
    ctx.globalAlpha = a; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.font = 'italic 400 56px "Playfair Italic"';
    const lines = wrapLines(T.text, 900);
    const lh = 70; const y0 = 1525 - (lines.length - 1) * lh / 2 + rise;
    // soft dark band for legibility
    const grd = ctx.createLinearGradient(0, y0 - 120, 0, y0 + lines.length * lh + 60);
    grd.addColorStop(0, 'rgba(0,0,0,0)'); grd.addColorStop(0.5, 'rgba(0,0,0,.38)'); grd.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grd; ctx.fillRect(0, y0 - 120, W, lines.length * lh + 180);
    ctx.shadowColor = 'rgba(0,0,0,.8)'; ctx.shadowBlur = 16; ctx.fillStyle = '#fbf8f2';
    lines.forEach((l, i) => ctx.fillText(l, W / 2, y0 + i * lh));
    ctx.restore();
  }
}

function drawTitle(t) {
  if (t > TITLE.b) return;
  const a = 1 - sstep(TITLE.b - 0.45, TITLE.b, t);
  ctx.save(); ctx.globalAlpha = a; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.font = '500 92px "Playfair"';
  const lines = wrapLines(TITLE.text, 900); const lh = 112; const y0 = 840 - (lines.length - 1) * lh / 2;
  const grd = ctx.createRadialGradient(W / 2, 840, 50, W / 2, 840, 700); grd.addColorStop(0, 'rgba(0,0,0,.42)'); grd.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = grd; ctx.fillRect(0, 200, W, 1300);
  ctx.shadowColor = 'rgba(0,0,0,.75)'; ctx.shadowBlur = 24; ctx.fillStyle = '#ffffff';
  lines.forEach((l, i) => ctx.fillText(l, W / 2, y0 + i * lh));
  ctx.restore();
}

function drawEndCard(t) {
  const a = sstep(42.0, 42.6, t);
  if (a <= 0) return;
  ctx.save();
  ctx.globalAlpha = a; ctx.fillStyle = '#060607'; ctx.fillRect(0, 0, W, H);
  // drifting ash
  const r = mulberry(5);
  for (let i = 0; i < 90; i++) { const x = (r() * W + t * 8 * (r() - 0.3)) % W, y = (r() * H + (t - 42) * (20 + r() * 30)) % H, s = 1 + r() * 2.5; ctx.fillStyle = `rgba(160,155,150,${0.15 + r() * 0.25})`; ctx.beginPath(); ctx.arc(x, y, s, 0, 7); ctx.fill(); }
  const b = sstep(42.3, 43.0, t);
  ctx.globalAlpha = a * b; ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = '#f4efe6';
  ctx.font = '500 104px "Playfair"'; ctx.fillText('Was wäre, wenn …', W / 2, 880);
  ctx.font = 'italic 400 76px "Playfair Italic"'; ctx.fillStyle = '#d9cfbf'; ctx.fillText('Teil 1', W / 2, 990);
  ctx.globalAlpha = a * b * 0.5; ctx.fillStyle = '#d9cfbf'; ctx.fillRect(W / 2 - 60, 1060, 120, 2);
  const c = sstep(42.8, 43.4, t);
  ctx.globalAlpha = a * c; ctx.fillStyle = '#e8e0d2'; ctx.font = '400 34px "Playfair SC"'; ctx.letterSpacing = '5px';
  ctx.fillText('Teil 2: Die Sonne verschwindet', W / 2, 1150);
  ctx.fillStyle = '#b8ad9c'; ctx.font = '400 30px "Playfair SC"';
  ctx.fillText('· Folge, um es zu sehen ·', W / 2, 1206);
  ctx.restore();
}

function composite(t, mode) {
  ctx.globalAlpha = 1; ctx.filter = 'none';
  if (mode === 'dark') { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); }
  else ctx.drawImage(glCanvas, 0, 0);
  // flash
  const fl = t < 16 ? 0 : t < 16.15 ? 1 : Math.exp(-(t - 16.15) * 2.2);
  if (fl > 0.003 && t < 20) { ctx.fillStyle = `rgba(255,252,244,${fl})`; ctx.fillRect(0, 0, W, H); }
  // shock wave hit: brown-out
  if (t > T_HIT_CAM - 0.25 && t < 31) {
    const a = sstep(T_HIT_CAM - 0.25, T_HIT_CAM + 0.05, t) * (1 - sstep(T_HIT_CAM + 0.5, 30.2, t) * 0.88);
    ctx.fillStyle = `rgba(92,74,58,${a})`; ctx.fillRect(0, 0, W, H);
  }
  // vignette
  const v = ctx.createRadialGradient(W / 2, H / 2, H * 0.28, W / 2, H / 2, H * 0.62);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.5)');
  ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
  // grain
  ctx.globalAlpha = 0.05; ctx.globalCompositeOperation = 'overlay';
  ctx.drawImage(grain[Math.floor(t * 30) % grain.length], 0, 0, W, H);
  ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
  drawTitle(t);
  drawCaption(t);
  drawEndCard(t);
  drawHUD(t);
}

// ------------------------------------------------------------------ frame entry point
let replayT = 0;
function renderFrame(t) {
  const bat = batteryAt(t);
  if (t < 34) {
    updateWorld(t);
    drawPhoneUI(t, 'live', bat, 0);
    myScreenMat.uniforms.uCrack.value = 0; myScreenMat.uniforms.uAsh.value = 0;
    myScreenMat.uniforms.uOn.value = 1; myScreenMat.uniforms.uGain.value = 2.6;
    // phone screen pass (without the phone itself)
    if (handRig.visible) {
      myPhone.g.visible = false;
      phoneCam.updateMatrixWorld(true);
      renderer.setRenderTarget(rtPhone); renderer.render(scene, phoneCam); renderer.setRenderTarget(null);
      myPhone.g.visible = true;
    }
    bloom.strength = 0.85 + 0.6 * sstep(15, 16, t) * (t < 18 ? 1 : 0);
    renderPass.scene = scene; renderPass.camera = camera;
    composer.render();
    composite(t, 'live');
  } else if (t < 42) {
    // replay of the aurora footage on the cracked phone
    replayT = 0.4 + (t - 34) * 0.85;
    updateWorld(2.6 + replayT * 0.62);
    handRig.visible = true; myPhone.g.visible = false;
    camera.updateMatrixWorld(true); phoneCam.updateMatrixWorld(true);
    drawPhoneUI(t, 'replay', bat, replayT);
    if (t < 41.05) { renderer.setRenderTarget(rtPhone); renderer.render(scene, phoneCam); renderer.setRenderTarget(null); }
    updateClose(t);
    bloom.strength = 0.7;
    renderPass.scene = closeScene; renderPass.camera = closeCam;
    composer.render();
    composite(t, 'close');
  } else {
    composite(t, 'dark');
  }
}

async function loadFonts() {
  const faces = [
    new FontFace('Playfair', 'url(/fonts/PlayfairDisplay.ttf)', { weight: '400 900' }),
    new FontFace('Playfair Italic', 'url(/fonts/PlayfairDisplay-Italic.ttf)', { weight: '400 900', style: 'italic' }),
    new FontFace('Playfair SC', 'url(/fonts/PlayfairDisplaySC-Regular.ttf)'),
  ];
  for (const f of faces) { await f.load(); document.fonts.add(f); }
}

window.renderFrame = async (t, quality = 0.93) => {
  renderFrame(t);
  return out.toDataURL('image/jpeg', quality);
};
await loadFonts();
window.ready = true;
