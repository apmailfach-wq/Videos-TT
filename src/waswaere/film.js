// "Was wäre, wenn … Teil 1" – 45 s, 1080x1920, low-poly 3D, rendered frame by frame.
// Every visual state is a pure function of the film time t (seconds), so any frame can be rendered alone.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { HUD_LINES, BATTERY, BATTERY_EMPTY_AT, TEXTS, TITLE, END, DURATION } from './timeline.js';
const TL = await (await fetch('/src/waswaere/timeline.json')).json();
// output time u -> story time t (piecewise linear)
function warp(u) {
  const k = TL.warp;
  if (u <= k[0][0]) return k[0][1];
  for (let i = 1; i < k.length; i++) if (u <= k[i][0]) { const [u0, t0] = k[i - 1], [u1, t1] = k[i]; return t0 + (t1 - t0) * (u - u0) / (u1 - u0); }
  return k[k.length - 1][1];
}

const W = 1080, H = 1920;
let RT = 0; // real (output) time: drives oscillations, while t (story time) drives events

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
  uDustCol: { value: new THREE.Color(0x3a332d) }, uStars: { value: 0.6 }, uDusk: { value: 1 },
};
const SKY_GLSL = `  uniform float uTime,uAurora,uRed,uDust,uFlash,uGlow,uCity,uStars,uDusk; uniform vec3 uImpact,uDustCol;
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
  vec3 skyColor(vec3 d){
    float el = d.y;
    // blue hour: deep blue zenith, lighter horizon, last glow of the sunset in the west (left)
    vec3 zen = vec3(.010,.020,.065), hor = vec3(.055,.085,.17);
    vec3 col = mix(hor, zen, pow(clamp(el,0.,1.),.45));
    if(el < 0.) col = hor*.6;
    vec2 wd = normalize(vec2(-.95,-.3));
    float west = pow(max(dot(normalize(d.xz + 1e-5), wd), 0.), 2.5);
    col += uDusk*west*(vec3(.75,.26,.08)*exp(-max(el,0.)*14.) + vec3(.28,.08,.16)*exp(-max(el,0.)*5.));
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
      for(int i=0;i<AUR_STEPS;i++){
        float fi = (float(i)+jit)/float(AUR_STEPS);
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
      acc *= .42*22./float(AUR_STEPS)*uAurora*smoothstep(.015,.12,el)*(.75+.25*smoothstep(.0,.5,el));
    }
    acc = .95*(vec3(1.) - exp(-acc*1.25));   // soft saturation keeps the hue, no white hot spots
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
    return col;
  }
`;
const skyMat = new THREE.ShaderMaterial({
  uniforms: skyU, side: THREE.BackSide, depthWrite: false, fog: false, defines: { AUR_STEPS: 22 },
  vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); vec4 p = projectionMatrix*modelViewMatrix*vec4(position,1.); gl_Position = p.xyww; }`,
  fragmentShader: SKY_GLSL + `varying vec3 vDir; void main(){ gl_FragColor = vec4(skyColor(normalize(vDir)), 1.); }`,
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

// ------------------------------------------------------------------ coast: Kurplatz on the Baltic Sea
// Camera stands on a tiled promenade plaza looking out to sea (-z). The railing/sea wall runs along
// z = RAIL_Z, the lit resort town follows the coastline off to the left, a pier with lamps, a pavilion
// and a Ferris wheel goes out on the right, a lighthouse sweeps on the far headland.
const world = new THREE.Group(); scene.add(world);
const tmpM0 = new THREE.Matrix4();
const SEA_Y = -2.4, RAIL_Z = -14;
const TERRACE = 3.5;   // you stand on the Kurhaus terrace above the plaza
const shoreX = s => -22 - 0.22 * s;          // coastline: x at distance s along the shore
const shoreZ = s => RAIL_Z - 6 - s;
const tileTex = canvasTex(256, 256, (g, w, h) => {
  g.fillStyle = '#6e675e'; g.fillRect(0, 0, w, h); const r = mulberry(44);
  for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) { const v = 150 + r() * 34 | 0; g.fillStyle = `rgb(${v + 8},${v + 2},${v - 10})`; g.fillRect(x * 32 + 1, y * 32 + 1, 30, 30); }
});
tileTex.wrapS = tileTex.wrapT = THREE.RepeatWrapping; tileTex.repeat.set(30, 18);
const plaza = new THREE.Mesh(new THREE.PlaneGeometry(120, 70), flat(0xb8b0a4, { map: tileTex, roughness: 0.6 }));
plaza.rotation.x = -Math.PI / 2; plaza.position.set(-25, 0, RAIL_Z + 35); world.add(plaza);
// land along the coast (left), slightly lower than the plaza
{
  const sh = new THREE.Shape();
  sh.moveTo(-22, -RAIL_Z); sh.lineTo(shoreX(4000), -shoreZ(4000)); sh.lineTo(-6000, -shoreZ(4000)); sh.lineTo(-6000, 200); sh.lineTo(-22, 200); sh.closePath();
  const land = new THREE.Mesh(new THREE.ShapeGeometry(sh), flat(0x22252c));
  land.rotation.x = -Math.PI / 2; land.position.y = -0.05; world.add(land);
}
// the Kurhaus terrace you are standing on
{ const ter = new THREE.Mesh(new THREE.BoxGeometry(90, TERRACE, 45), [flat(0x9a9286), flat(0x9a9286), flat(0xb8b0a4, { map: tileTex }), flat(0x9a9286), flat(0x9a9286), flat(0x9a9286)]);
  ter.position.set(0, TERRACE / 2, -1.2 + 22.5); world.add(ter); }
// sea wall + balustrade
const wallMatC = flat(0x8d857a);
{ const w = new THREE.Mesh(new THREE.BoxGeometry(70, 3.2, 0.8), wallMatC); w.position.set(5, -1.5, RAIL_Z - 0.3); world.add(w); }
{ // slanted sea wall along the coast
  const L = 4000, a = Math.atan2(0.22, 1);
  const w = new THREE.Mesh(new THREE.BoxGeometry(1.2, 3.2, L), wallMatC);
  w.position.set((shoreX(0) + shoreX(L)) / 2, -1.6, (shoreZ(0) + shoreZ(L)) / 2); w.rotation.y = a; world.add(w);
}
const railMat = flat(0xdcd6cc, { roughness: 0.5 });
const railing = new THREE.Group(); world.add(railing);
{ const top = new THREE.Mesh(new THREE.BoxGeometry(31, 0.12, 0.16), railMat); top.position.set(-6.5, 1.05, RAIL_Z); railing.add(top);
  for (let x = -22; x <= 9; x += 1.1) { const p = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.05, 1.0, 5), railMat); p.position.set(x, 0.5, RAIL_Z); railing.add(p); }
  const top2 = new THREE.Mesh(new THREE.BoxGeometry(18, 0.12, 0.16), railMat); top2.position.set(26, 1.05, RAIL_Z); railing.add(top2); }
// seabed: shallow slope out from the wall (exposed when the sea draws back)
const bedY = dz => -Math.min(14, 1.9 + dz * 0.028);
{
  const geo = new THREE.PlaneGeometry(6000, 4000, 2, 80); const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) p.setZ(i, bedY(p.getY(i) + 2000));
  geo.computeVertexNormals();
  const bed = new THREE.Mesh(geo, flat(0x4c4436)); bed.rotation.x = -Math.PI / 2; bed.position.set(0, 0, RAIL_Z - 2000.5); world.add(bed);
  const r = mulberry(55);
  for (let i = 0; i < 24; i++) { const s = 0.4 + r() * 1.3; const m = new THREE.Mesh(new THREE.IcosahedronGeometry(s, 0), flat(0x3a3530)); const dz = 2 + r() * 140; m.position.set(-30 + r() * 70, bedY(dz) + s * 0.3, RAIL_Z - dz); m.rotation.set(r() * 3, r() * 3, 0); world.add(m); }
}

// ------------------------------------------------------------------ sea (reflects the sky)
const seaU = { uFoamZ: { value: -9999 }, uFoamA: { value: 0 }, uChop: { value: 1 }, uSeaDust: { value: 0 }, uFlashS: { value: 0 } };
const seaMat = new THREE.ShaderMaterial({
  uniforms: { ...skyU, ...seaU }, fog: false, defines: { AUR_STEPS: 9 },
  vertexShader: 'varying vec3 vW; void main(){ vec4 w = modelMatrix*vec4(position,1.); vW = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }',
  fragmentShader: SKY_GLSL + `
  varying vec3 vW;
  uniform float uFoamZ,uFoamA,uChop,uSeaDust,uFlashS;
  void main(){
    vec3 V = normalize(vW - cameraPosition);
    float dist = length(vW.xz - cameraPosition.xz);
    vec2 p = vW.xz; float t = uTime;
    float amp = (.10*exp(-dist/380.) + .018)*uChop;
    float gx = cos(p.x*.31 + t*1.1)*.9 + cos(p.x*.11 + p.y*.17 + t*.6)*.6 + cos(p.x*.53 - p.y*.29 + t*1.7)*.4 + (noise(p*.9 + t*.4)-.5)*1.2;
    float gz = cos(p.y*.37 + t*1.3)*.9 + cos(p.y*.13 - p.x*.07 + t*.5)*.6 + cos(p.y*.61 + p.x*.23 - t*1.9)*.4 + (noise(p*.9 - t*.3 + 7.)-.5)*1.2;
    vec3 n = normalize(vec3(gx*amp, 1., gz*amp));
    vec3 Rf = reflect(V, n); Rf.y = max(Rf.y, .012);
    vec3 sk = skyColor(normalize(Rf));
    float fr = .03 + .97*pow(1. - max(dot(-V, n), 0.), 5.);
    vec3 water = vec3(.004,.012,.022) + vec3(.01,.03,.03)*(1. - fr);
    vec3 col = mix(water, sk, clamp(fr*1.1, 0., 1.));
    // pressure wave racing over the water: a bright band of spray, rough water behind it
    float dz = p.y - uFoamZ;
    float band = exp(-dz*dz/60.) * uFoamA;
    float rough = smoothstep(0., -40., dz) * uFoamA;
    col += vec3(.55,.48,.40)*(band*(.6 + .8*noise(p*.35 + t*3.)) + rough*.25*noise(p*.8 + t*2.));
    col += uFlashS*vec3(1.,.95,.88)*.35;
    col = mix(col, uDustCol*.5, uSeaDust);
    gl_FragColor = vec4(col, 1.);
  }`,
});
const sea = new THREE.Mesh(new THREE.PlaneGeometry(40000, 40000), seaMat);
sea.rotation.x = -Math.PI / 2; sea.position.set(0, SEA_Y, RAIL_Z - 20000); world.add(sea);

// ------------------------------------------------------------------ town along the coast
const buildings = []; // {mesh, side, fx (facade x, facing +x / the sea), z, w, h}
const towers = [];    // red warning lights (blink until the blackout)
{
  let s = 30, k = 0;
  while (s < 3400) {
    const far = s > 900;
    const w = (far ? 30 : 16) + R() * (far ? 40 : 18), d = 14 + R() * 10;
    const tall = R() < (far ? 0.25 : 0.12);
    const h = tall ? 35 + R() * 45 : 12 + R() * 14;
    const fx = shoreX(s) - 14 - R() * 6;
    const z = shoreZ(s) - w / 2;
    const col = pick(R, [0xe8e0d0, 0xd8cdb8, 0xc9d3dc, 0xe6d2b5, 0xbfc8c0, 0xf0e8dc]);
    const b = boxWithWindows(d, h, w, facadeTex[k % 3], col, 3.3, 3.0, 500 + k);
    b.position.set(fx - d / 2, h / 2, z); world.add(b);
    if (!tall && R() < 0.55) { const rf = new THREE.Mesh(new THREE.CylinderGeometry(0.01, d * 0.62, 3 + R() * 2, 4, 1), flat(pick(R, [0x8a3b2e, 0x5a4a48, 0x3e4a5a]))); rf.rotation.y = Math.PI / 4; rf.scale.set(1, 1, w / d); rf.position.set(b.position.x, h + 1.5, z); world.add(rf); }
    if (tall) { const red = new THREE.Mesh(new THREE.SphereGeometry(1.2, 6, 4), new THREE.MeshBasicMaterial({ color: 0xff2020 })); red.position.set(b.position.x, h + 1.5, z); red.userData.blink = R(); world.add(red); towers.push(red); }
    buildings.push({ mesh: b, side: -1, fx, z, w, h });
    if (R() < 0.8) { const h2 = 10 + R() * (far ? 40 : 18); const b2 = boxWithWindows(d, h2, w * 0.8, facadeTex[(k + 1) % 3], pick(R, [0xa8a090, 0x9aa3ac, 0xb0a490]), 3.3, 3.0, 800 + k); b2.position.set(fx - d - 10 - R() * 20, h2 / 2, z - R() * 10); world.add(b2); }
    s += w + 2 + R() * 8; k++;
  }
  for (let i = 0; i < 160; i++) { const s2 = 200 + R() * 3200; const x = shoreX(s2) - 60 - R() * 700, z = shoreZ(s2) + R() * 200; const w = 20 + R() * 30, h = 8 + R() * 30; const b = boxWithWindows(w, h, w, facadeTex[i % 3], 0x6a6560, 3.6, 3.2, 1200 + i); b.position.set(x, h / 2, z); world.add(b); }
}

// ------------------------------------------------------------------ lamps, lighthouse, pier, Ferris wheel, festoons
const lamps = [];
const poleMat = flat(0x1f2a2a);
const poolTex = canvasTex(128, 128, (g, w, h) => { const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64); gr.addColorStop(0, 'rgba(255,190,110,1)'); gr.addColorStop(0.5, 'rgba(255,170,90,.35)'); gr.addColorStop(1, 'rgba(255,160,80,0)'); g.fillStyle = gr; g.fillRect(0, 0, w, h); });
const glowTex = canvasTex(128, 128, (g, w, h) => { const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64); gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.2, 'rgba(255,255,255,.55)'); gr.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = gr; g.fillRect(0, 0, w, h); });
const streakTex = canvasTex(32, 256, (g, w, h) => { for (let y = 0; y < h; y++) { const a = Math.pow(1 - y / h, 1.5) * (0.6 + 0.4 * Math.sin(y * 0.9) ** 2); g.fillStyle = `rgba(255,255,255,${a})`; g.fillRect(4 + Math.sin(y * 0.4) * 3, y, w - 8, 1); } });
// lighthouse on the far headland with a sweeping beam
const LH = new THREE.Vector3(shoreX(2650) + 30, 0, shoreZ(2650));
const lighthouse = new THREE.Group(); lighthouse.position.copy(LH); world.add(lighthouse);
{ const t1 = new THREE.Mesh(new THREE.CylinderGeometry(3, 4.5, 36, 8), flat(0xf2eee8)); t1.position.y = 18; lighthouse.add(t1);
  for (const y of [8, 20]) { const band = new THREE.Mesh(new THREE.CylinderGeometry(3.6, 3.9, 4, 8), flat(0xc0302a)); band.position.y = y; lighthouse.add(band); }
  const lamp = new THREE.Mesh(new THREE.CylinderGeometry(2.2, 2.2, 3, 8), new THREE.MeshBasicMaterial({ color: 0xfff2c0 })); lamp.position.y = 38; lighthouse.add(lamp); lighthouse.userData.lamp = lamp; }
const beamMat = new THREE.MeshBasicMaterial({ color: 0xfff0c8, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, fog: false });
const beam = new THREE.Group(); beam.position.set(0, 38, 0); lighthouse.add(beam);
{ const c = new THREE.Mesh(new THREE.ConeGeometry(28, 1300, 10, 1, true), beamMat); c.rotation.z = Math.PI / 2; c.position.x = 650; beam.add(c);
  const c2 = c.clone(); c2.rotation.z = -Math.PI / 2; c2.position.x = -650; beam.add(c2); }
const lhGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0xfff0c0, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false }));
lhGlow.position.set(0, 38, 0); lhGlow.scale.set(40, 40, 1); lighthouse.add(lhGlow);

function makeLamp(x, z, base = 0, overWater = false) {
  const g = new THREE.Group(); g.position.set(x, base, z); world.add(g);
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.12, 4.4, 6), poleMat); pole.position.y = 2.2; g.add(pole);
  const headMat = new THREE.MeshBasicMaterial({ color: 0xffc27a });
  const head = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.14, 0.5, 6), headMat); head.position.set(0, 4.6, 0); g.add(head);
  const cap = new THREE.Mesh(new THREE.ConeGeometry(0.3, 0.25, 6), poleMat); cap.position.y = 4.98; g.add(cap);
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0xffb36b, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending, depthWrite: false }));
  glow.scale.set(2.0, 2.0, 1); glow.position.copy(head.position); g.add(glow);
  const pool = new THREE.Mesh(new THREE.PlaneGeometry(8, 8), new THREE.MeshBasicMaterial({ map: poolTex, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false }));
  pool.rotation.x = -Math.PI / 2; pool.position.set(0, 0.03, 0); g.add(pool);
  let refl = null;
  if (overWater) { refl = new THREE.Sprite(new THREE.SpriteMaterial({ map: streakTex, color: 0xffa860, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false })); refl.center.set(0.5, 1); refl.scale.set(1.0, 14, 1); refl.position.set(x, SEA_Y + 0.05, z); world.add(refl); }
  const L = { g, headMat, glow, pool, refl, z, x, side: x < 3 ? 1 : -1, hx: x, hy: base + 4.6, seed: R() * 100 };
  lamps.push(L); return L;
}
for (let x = -20; x <= 8; x += 7) makeLamp(x, RAIL_Z + 0.6);
for (const x of [18, 25, 32]) makeLamp(x, RAIL_Z + 0.6);
// pier (Seebrücke): segments that can break away during the quake
const PIER_X0 = 10.5, PIER_X1 = 15.5, PIER_LEN = 300;
const pierSegs = [];
const deckMat = flat(0x8a6e52), pileMat = flat(0x3a3230);
for (let z = RAIL_Z; z > RAIL_Z - PIER_LEN; z -= 12) {
  const g = new THREE.Group(); g.position.set((PIER_X0 + PIER_X1) / 2, 0, z - 6); world.add(g);
  const deck = new THREE.Mesh(new THREE.BoxGeometry(PIER_X1 - PIER_X0, 0.35, 12), deckMat); deck.position.y = -0.17; g.add(deck);
  for (const sx of [-1, 1]) { const pile = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.25, 12, 6), pileMat); pile.position.set(sx * 2.2, -6, 5.5); g.add(pile);
    const rl = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.08, 12), railMat); rl.position.set(sx * 2.45, 1.0, 0); g.add(rl); }
  pierSegs.push({ g, z: z - 6, seed: R() * 10, breaks: z < RAIL_Z - 60 && R() < 0.55 });
}
for (let z = RAIL_Z - 10; z > RAIL_Z - PIER_LEN + 10; z -= 16) { makeLamp(PIER_X0 + 0.3, z, 0, true); makeLamp(PIER_X1 - 0.3, z - 8, 0, true); }
// pavilion at the pier head
{ const pz = RAIL_Z - PIER_LEN - 8;
  const plat = new THREE.Mesh(new THREE.BoxGeometry(26, 0.5, 22), deckMat); plat.position.set(13, -0.25, pz); world.add(plat);
  const pav = boxWithWindows(18, 7, 14, facadeTex[1], 0xf0ebe0, 2.2, 3.0, 77); pav.position.set(13, 3.5, pz); world.add(pav);
  const roof = new THREE.Mesh(new THREE.ConeGeometry(13, 6, 8), flat(0x3c5a6a)); roof.position.set(13, 10, pz); world.add(roof);
  buildings.push({ mesh: pav, side: -1, fx: 4, z: pz, w: 14, h: 7 });
}
// Ferris wheel on a platform next to the pier
const WHEEL = { x: 34, z: RAIL_Z - 85, r: 19, cy: 23 };
const wheelRoot = new THREE.Group(); wheelRoot.position.set(WHEEL.x, 0, WHEEL.z); wheelRoot.rotation.y = -0.35; world.add(wheelRoot);
const wheelTilt = new THREE.Group(); wheelRoot.add(wheelTilt);
const wheelRot = new THREE.Group(); wheelRot.position.y = WHEEL.cy; wheelTilt.add(wheelRot);
{ const plat = new THREE.Mesh(new THREE.BoxGeometry(24, 0.5, 16), deckMat); plat.position.set(WHEEL.x, -0.25, WHEEL.z); world.add(plat);
  const steel = flat(0xe8e8ec, { roughness: 0.4 });
  for (const sz of [-1.6, 1.6]) for (const sx of [-1, 1]) { const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.45, 25, 5), steel); leg.position.set(sx * 6, 11.5, sz); leg.rotation.z = -sx * 0.25; wheelTilt.add(leg); }
  for (const sz of [-1.2, 1.2]) { const ring = new THREE.Mesh(new THREE.TorusGeometry(WHEEL.r, 0.28, 4, 36), steel); ring.position.z = sz; wheelRot.add(ring); }
  for (let i = 0; i < 16; i++) { const a = i / 16 * Math.PI * 2; const sp = new THREE.Mesh(new THREE.BoxGeometry(0.15, WHEEL.r, 0.15), steel); sp.position.set(Math.cos(a) * WHEEL.r / 2, Math.sin(a) * WHEEL.r / 2, 0); sp.rotation.z = a - Math.PI / 2; wheelRot.add(sp); }
}
const gondolas = [];
const gondMats = [0xd04a3a, 0x3a7ad0, 0xe0b030, 0x3aa070].map(c => flat(c));
for (let i = 0; i < 16; i++) { const g = new THREE.Mesh(new THREE.BoxGeometry(1.8, 1.6, 1.6), gondMats[i % 4]); wheelRot.add(g); gondolas.push({ g, a: i / 16 * Math.PI * 2, falls: i % 3 === 0, seed: R() * 10 }); }
const WB = 48;
const wheelBulbs = new THREE.InstancedMesh(new THREE.SphereGeometry(0.28, 5, 4), new THREE.MeshBasicMaterial({ color: 0xffffff }), WB);
wheelRot.add(wheelBulbs);
for (let i = 0; i < WB; i++) { const a = i / WB * Math.PI * 2; tmpM0.makeTranslation(Math.cos(a) * WHEEL.r, Math.sin(a) * WHEEL.r, 1.5); wheelBulbs.setMatrixAt(i, tmpM0); wheelBulbs.setColorAt(i, new THREE.Color(1, 1, 1)); }
// festoon string lights between the railing lamps
const FEST_PER = 16;
const festLamps = lamps.filter(L => Math.abs(L.z - (RAIL_Z + 0.6)) < 0.01 && L.x < 9).sort((a, b) => a.x - b.x);
const FEST = (festLamps.length - 1) * FEST_PER;
const festoon = new THREE.InstancedMesh(new THREE.SphereGeometry(0.075, 5, 4), new THREE.MeshBasicMaterial({ color: 0xffffff }), FEST);
const festData = [];
{ let k = 0; const pal = [0xffd28a, 0xff8a6a, 0x8ad0ff, 0xffe6a0, 0xb8ff9a];
  for (let i = 0; i < festLamps.length - 1; i++) { const a = festLamps[i], b = festLamps[i + 1];
    for (let j = 0; j < FEST_PER; j++) { const u = (j + 0.5) / FEST_PER; const x = lerp(a.x, b.x, u), y = 4.3 - Math.sin(u * Math.PI) * 0.9, z = RAIL_Z + 0.6;
      tmpM0.makeTranslation(x, y, z); festoon.setMatrixAt(k, tmpM0); const c = new THREE.Color(pal[(k * 7) % pal.length]); festoon.setColorAt(k, c); festData.push({ c, lamp: a, x, y, z }); k++; } } }
world.add(festoon);
const lampLights = [];
for (let i = 0; i < 4; i++) { const l = new THREE.PointLight(0xffb070, 0, 22, 1.4); scene.add(l); lampLights.push(l); }

const trees = [];

// cars: a food truck on the plaza and a few cars at the edges of the promenade
const cars = [];
function makeCar(color, len = 4.3, hgt = 0.7) {
  const g = new THREE.Group(); const body = new THREE.Group(); g.add(body);
  const m = flat(color, { roughness: 0.6, metalness: 0.2 });
  const lower = new THREE.Mesh(new THREE.BoxGeometry(1.8, hgt, len), m); lower.position.y = 0.25 + hgt / 2; body.add(lower);
  if (hgt < 1) {
    const cab = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.85, 1.75, 4, 1), m); cab.rotation.y = Math.PI / 4; cab.scale.set(1.0, 0.36, 1.3);
    const cabG = new THREE.Group(); cabG.add(cab); cabG.position.set(0, 0.25 + hgt + 0.48, -0.15); cabG.scale.set(1.45, 1, 1.4); body.add(cabG);
    const glass = new THREE.Mesh(new THREE.BoxGeometry(1.62, 0.36, 2.0), flat(0x0e1420, { roughness: 0.2, metalness: 0.6 })); glass.position.set(0, 0.25 + hgt + 0.5, -0.15); body.add(glass);
  }
  const wm = flat(0x111111);
  for (const [x, z] of [[-0.85, len * 0.31], [0.85, len * 0.31], [-0.85, -len * 0.31], [0.85, -len * 0.31]]) { const w = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.34, 0.24, 8), wm); w.rotation.z = Math.PI / 2; w.position.set(x, 0.34, z); body.add(w); }
  const hazMat = new THREE.MeshBasicMaterial({ color: 0x331a00 });
  for (const [x, z] of [[-0.75, len / 2 + 0.01], [0.75, len / 2 + 0.01], [-0.75, -len / 2 - 0.01], [0.75, -len / 2 - 0.01]]) { const h = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.14, 0.05), hazMat); h.position.set(x, 0.78, z); body.add(h); }
  return { g, body, hazMat };
}
for (const [x, z, ry, col, len, hgt, push] of [[-8.5, -11.2, 1.45, 0xe8e2d0, 5.2, 2.0, 0.35], [-16, -6, 0.2, 0x8a1f24, 4.3, 0.7, 1], [-19, -10.5, -0.1, 0x2a3d6b, 4.3, 0.7, 1], [19, -9, 0.4, 0xb8bcc4, 4.3, 0.7, 1], [24, -12, 1.2, 0x355a45, 4.3, 0.7, 1]]) {
  const c = makeCar(col, len, hgt); c.g.position.set(x, 0, z); c.g.rotation.y = ry; world.add(c.g);
  if (hgt > 1) { // food truck: lit serving hatch + awning
    const hatch = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 0.9), new THREE.MeshBasicMaterial({ color: 0xffd9a0 })); hatch.position.set(0.91, 1.6, 0); hatch.rotation.y = Math.PI / 2; c.body.add(hatch); c.hatch = hatch;
    const awn = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.06, 2.6), flat(0xc0392b)); awn.position.set(1.3, 2.25, 0); awn.rotation.z = -0.3; c.body.add(awn); }
  cars.push({ ...c, x, z, ry, seed: R() * 100, spin: Math.PI * (R() < 0.5 ? 1 : -1), push });
}

const hw0 = (c, i, len) => (i <= len ? 0.05 : 0);
// cracks in the plaza (revealed during the quake)
const crackMat = new THREE.MeshBasicMaterial({ color: 0x020203, side: THREE.DoubleSide });
const rimMat = new THREE.MeshBasicMaterial({ color: 0x3a2c24, side: THREE.DoubleSide });
const cracks = [];
function addCrack(pts, delay, w0, seed, dur) {
  const n = pts.length; const pos = new Float32Array(n * 2 * 3);
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const idx = []; for (let i = 0; i < n - 1; i++) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); } geo.setIndex(idx);
  const m = new THREE.Mesh(geo, crackMat); m.frustumCulled = false; world.add(m);
  cracks.push({ m, pts, pos, delay, w0, seed, dur });
}
for (let c = 0; c < 7; c++) {
  const pts = []; let x = -20 + c * 6 + R() * 3, z = RAIL_Z + 0.4;
  const zEnd = -2 - R() * 6;
  while (z < zEnd) { pts.push([x, z]); z += 0.7 + R() * 0.9; x += (R() - 0.5) * 1.8; }
  pts.push([x, z]); addCrack(pts, R() * 0.8, 0.12 + R() * 0.12, R() * 10);
}
{ // the crack that runs right up to your feet
  const pts = []; let x = -3, z = RAIL_Z + 0.4; const r = mulberry(2222);
  while (z < -0.9) { pts.push([x, z]); z += 0.6 + r() * 0.7; x += (r() - 0.5) * 1.0 + (0.3 - x) * 0.15; }
  pts.push([0.3, -0.9]); addCrack(pts, 1.0, 0.2, 7, 1.3);
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
crowdSpots.push([-1.9, -9.8], [2.2, -10.4], [-3.4, -11.6]);
for (let i = 0; i < 58; i++) {
  const z = RAIL_Z + 0.9 + Math.pow(PR(), 1.6) * 8.5;   // dense at the railing
  crowdSpots.push([-12 + PR() * 21 + (PR() < 0.3 ? (PR() - 0.5) * 16 : 0), z]);
}
for (let i = 0; i < 14; i++) crowdSpots.push([PIER_X0 + 0.8 + PR() * 3.4, RAIL_Z - 4 - PR() * 70]);
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
const IMPACT_DIR = new THREE.Vector3(-0.025, 0, -1).normalize();
skyU.uImpact.value.copy(IMPACT_DIR);
const frags = [0, 1, 2].map(() => { const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0xffd8a0, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false })); sp.renderOrder = 5; scene.add(sp); return sp; });
function meteorDir(tt) {
  const k = clamp((tt - 10.6) / 5.4);
  const kk = k * k * 0.25 + k * 0.75;
  const az = lerp(-0.2, Math.atan2(IMPACT_DIR.x, -IMPACT_DIR.z), kk) + Math.sin(k * Math.PI) * 0.04;
  const el = lerp(0.66, 0.0, kk);
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

const plumeMat = new THREE.ShaderMaterial({
  uniforms: { uTime: { value: 0 }, uA: { value: 0 }, uGlowP: { value: 1 } }, fog: false, transparent: true, depthWrite: false, side: THREE.DoubleSide,
  vertexShader: 'varying vec3 vP; varying vec3 vN; void main(){ vP=position; vN=normalize(normalMatrix*normal); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }',
  fragmentShader: `uniform float uTime,uA,uGlowP; varying vec3 vP; varying vec3 vN;
    float h(vec3 p){ return fract(sin(dot(p,vec3(12.9898,78.233,45.164)))*43758.5453); }
    void main(){ float n = h(floor(vP*6. + vec3(0., -uTime*2., 0.)));
      float rim = pow(1.-abs(vN.z), 2.);
      vec3 c = mix(vec3(.85,.88,.9), vec3(.45,.5,.55), n*.5 + rim*.4) + vec3(1.,.45,.15)*uGlowP*(1.-vP.y)*.6;
      gl_FragColor = vec4(c, uA*(.75 + .25*n)*(1. - rim*.5)); }`,
});
const plume = new THREE.Group(); plume.position.copy(IMPACT_DIR).multiplyScalar(6900); plume.position.y = SEA_Y; scene.add(plume);
const plumeCol = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 1, 1, 12, 4, true), plumeMat); plumeCol.position.y = 0.5; plumeCol.renderOrder = 3; plume.add(plumeCol);
const plumeRing = new THREE.Mesh(new THREE.TorusGeometry(1, 0.12, 4, 40), plumeMat); plumeRing.rotation.x = Math.PI / 2; plumeRing.renderOrder = 3; plume.add(plumeRing);
// tsunami: an extruded wave profile across the whole bay
const TSU_W = 3200;
const tsuMat = new THREE.ShaderMaterial({
  uniforms: { uTime: { value: 0 }, uH: { value: 0 }, uGlowT: { value: 0 } }, fog: false, side: THREE.DoubleSide,
  vertexShader: `uniform float uTime; varying vec2 vUv; varying float vY; varying vec3 vN;
    void main(){ vUv = uv; vec3 p = position; p.y *= 1. + .12*sin(p.x*.012 + uTime*.7) + .06*sin(p.x*.05 - uTime);
      vY = uv.y; vN = normalize(normalMatrix*normal); gl_Position = projectionMatrix*modelViewMatrix*vec4(p,1.); }`,
  fragmentShader: `uniform float uTime,uH,uGlowT; varying vec2 vUv; varying float vY; varying vec3 vN;
    float h(vec2 p){ p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y);} 
    float nz(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f); return mix(mix(h(i),h(i+vec2(1,0)),f.x), mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x), f.y);} 
    void main(){
      float n = nz(vec2(vUv.x*900., vY*12. - uTime*3.));
      vec3 deep = vec3(.015,.05,.06), face = vec3(.05,.16,.17);
      vec3 c = mix(deep, face, smoothstep(.2,.8,vY));
      float foam = smoothstep(.86, .97, vY + n*.1);
      c = mix(c, vec3(.5,.55,.55), foam);
      c += vec3(.5,.2,.05)*uGlowT*(.3 + .7*vY);
      c *= .75 + .35*n;
      gl_FragColor = vec4(c, 1.); }`,
});
const tsunami = new THREE.Group(); scene.add(tsunami);
{
  const prof = [[-90, 0], [-55, .2], [-30, .5], [-16, .78], [-7, .95], [-2, 1.03], [1.5, 1.02], [3.5, .9], [4.5, .74], [4.0, .6]];
  const geo = new THREE.BufferGeometry(); const pos = [], uv = [], idx = []; const SEG = 160;
  for (let i = 0; i <= SEG; i++) { const x = -TSU_W / 2 + TSU_W * i / SEG; prof.forEach(([z, y], j) => { pos.push(x, y, z); uv.push(i / SEG, j / (prof.length - 1)); }); }
  const P = prof.length;
  for (let i = 0; i < SEG; i++) for (let j = 0; j < P - 1; j++) { const a = i * P + j, b = (i + 1) * P + j; idx.push(a, b, a + 1, b, b + 1, a + 1); }
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); geo.setIndex(idx); geo.computeVertexNormals();
  const m = new THREE.Mesh(geo, tsuMat); m.frustumCulled = false; tsunami.add(m);
}
const TSU_T0 = 32.0, TSU_HIT = 33.95;
const tsuZ = t => lerp(-1600, 0, clamp((t - TSU_T0) / (TSU_HIT - TSU_T0)) ** 0.85);
const seaDrop = t => 4.6 * sstep(31.7, 32.9, t);

// ------------------------------------------------------------------ ships on the evening sea
// A lit cruise ship crossing the horizon (own generators: stays lit in the blackout), sailing boats with
// mast lights and fishing boats with deck lights. Pressure wave capsizes / darkens them, the receding sea
// strands the fishing boats on the bottom, the tsunami lifts the cruise ship onto its crest.
const shipWinTex = canvasTex(256, 64, (g, w, h) => {
  g.fillStyle = '#000'; g.fillRect(0, 0, w, h); const r = mulberry(606);
  for (let row = 0; row < 3; row++) for (let i = 0; i < 32; i++) if (r() < 0.86) { const v = 0.7 + r() * 0.3; g.fillStyle = `rgb(255,${210 * v | 0},${140 * v | 0})`; g.fillRect(i * 8 + 2, 6 + row * 20, 5, 9); }
});
shipWinTex.wrapS = THREE.RepeatWrapping;
const ships = [];
function lightSprite(color, size, parent, x, y, z) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false }));
  s.scale.set(size, size, 1); s.position.set(x, y, z); parent.add(s); return s;
}
function reflStreak(color, w, h) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: streakTex, color, transparent: true, opacity: 0.6, blending: THREE.AdditiveBlending, depthWrite: false, fog: false }));
  s.center.set(0.5, 1); s.scale.set(w, h, 1); world.add(s); return s;
}
function hullWithBow(len, hgt, wid, color) {
  const grp = new THREE.Group(); const m = flat(color);
  const hull = new THREE.Mesh(new THREE.BoxGeometry(len, hgt, wid), m); hull.position.y = hgt / 2 - hgt * 0.35; grp.add(hull);
  const bow = new THREE.Mesh(new THREE.CylinderGeometry(wid * 0.58, wid * 0.58, hgt, 3), m); bow.rotation.y = Math.PI / 2; bow.scale.set(1, 1, 1.7);
  bow.position.set(len / 2 + wid * 0.29 * 1.7 - 0.5, hgt / 2 - hgt * 0.35, 0); grp.add(bow);
  return grp;
}
{ // cruise ship
  const g = new THREE.Group(); const body = new THREE.Group(); g.add(body); world.add(g);
  body.add(hullWithBow(150, 11, 24, 0x18222f));
  const stripe = new THREE.Mesh(new THREE.BoxGeometry(150.2, 0.8, 24.2), flat(0xd8d8d8)); stripe.position.y = 6.6; body.add(stripe);
  const deckMats = [];
  [[124, 10.5, 20, 0], [104, 14.5, 18, -6], [76, 18.5, 16, -12], [40, 22.5, 14, -6]].forEach(([len, y, wid, x]) => {
    const tex = shipWinTex.clone(); tex.repeat.set(len / 70, 1); tex.needsUpdate = true;
    const side = new THREE.MeshStandardMaterial({ color: 0xf2f0ea, emissive: 0xffffff, emissiveMap: tex, emissiveIntensity: 1.6, flatShading: true, roughness: 0.8 });
    const top = flat(0xe8e6e0); deckMats.push(side);
    const d = new THREE.Mesh(new THREE.BoxGeometry(len, 4, wid), [side, side, top, top, side, side]); d.position.set(x, y, 0); body.add(d);
  });
  const funnel = new THREE.Mesh(new THREE.CylinderGeometry(3.6, 4.2, 9, 8), flat(0xf0f0f0)); funnel.position.set(-40, 28, 0); body.add(funnel);
  const ftop = new THREE.Mesh(new THREE.CylinderGeometry(3.7, 3.7, 2.4, 8), flat(0xb02828)); ftop.position.set(-40, 33.2, 0); body.add(ftop);
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.5, 12, 5), flat(0xdddddd)); mast.position.set(30, 30, 0); body.add(mast);
  const lights = [lightSprite(0xffffff, 7, body, 30, 36.5, 0), lightSprite(0xff3030, 5, body, 92, 8, 9), lightSprite(0x30ff70, 5, body, 92, 8, -9), lightSprite(0xffffff, 5, body, -76, 13, 0)];
  // dressing lights bow -> mast -> stern
  for (let i = 0; i <= 18; i++) { const u = i / 18; lights.push(lightSprite(i % 3 ? 0xffe2a0 : 0xa0d8ff, 2.2, body, lerp(96, 30, u), lerp(9, 36, u), 0)); lights.push(lightSprite(i % 3 ? 0xffe2a0 : 0xffa0c0, 2.2, body, lerp(30, -76, u), lerp(36, 14, u), 0)); }
  const refl = [-60, -40, -20, 0, 20, 40, 60].map(() => reflStreak(0xffb070, 9, 70));
  ships.push({ type: 'cruise', g, body, deckMats, lights, refl, x0: -165, z: -420, vx: 4.5, draft: 3, ph: 0.3, reflX: [-60, -40, -20, 0, 20, 40, 60] });
}
function makeSailboat(x, z, ry, ph) {
  const g = new THREE.Group(); const body = new THREE.Group(); g.add(body); world.add(g);
  body.add(hullWithBow(9, 1.6, 3, 0xe8e4dc));
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 13, 4), flat(0xcccccc)); mast.position.set(0.5, 7, 0); body.add(mast);
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.Float32BufferAttribute([0.6, 1.6, 0, 0.6, 13, 0, -4.2, 1.8, 0, 0.8, 1.6, 0, 0.8, 11, 0, 5.2, 1.6, 0], 3)); sg.computeVertexNormals();
  const sail = new THREE.Mesh(sg, new THREE.MeshStandardMaterial({ color: 0xf4f1ea, side: THREE.DoubleSide, flatShading: true, roughness: 0.9, emissive: 0x222018 })); body.add(sail);
  const lights = [lightSprite(0xffffff, 2.4, body, 0.5, 13.6, 0), lightSprite(0xff3030, 1.6, body, 5, 1.6, 1.2)];
  const refl = [reflStreak(0xfff0d0, 1.2, 18)];
  g.rotation.y = ry;
  ships.push({ type: 'sail', g, body, lights, refl, x0: x, z, vx: 0.6, draft: 0.8, ph, reflX: [0] });
}
makeSailboat(-55, -330, 0.4, 1.1); makeSailboat(-18, -560, -0.3, 2.3); makeSailboat(-140, -700, 0.2, 3.7); makeSailboat(62, -470, 2.6, 4.1); makeSailboat(-95, -420, -0.9, 5.2);
function makeFisher(x, z, ry, ph, col) {
  const g = new THREE.Group(); const body = new THREE.Group(); g.add(body); world.add(g);
  body.add(hullWithBow(12, 2.4, 4, col));
  const cab = new THREE.Mesh(new THREE.BoxGeometry(3.2, 2.6, 3), [flat(0xeeeeee), flat(0xeeeeee), flat(0xdddddd), flat(0xdddddd), new THREE.MeshBasicMaterial({ color: 0xffd9a0 }), flat(0xeeeeee)]); cab.position.set(-1.5, 2.9, 0); body.add(cab);
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 6, 4), flat(0x888888)); mast.position.set(1, 4.5, 0); body.add(mast);
  const lights = [lightSprite(0xffd28a, 7, body, 1, 7, 0), lightSprite(0xffffff, 2, body, 1, 7.6, 0), lightSprite(0x30ff70, 1.4, body, 5.5, 1.6, -1.6)];
  const refl = [reflStreak(0xffc080, 3, 26)];
  g.rotation.y = ry;
  ships.push({ type: 'fish', g, body, lights, refl, x0: x, z, vx: 0, draft: 1.2, ph, reflX: [0], cabMat: cab.material[4] });
}
makeFisher(-35, -135, 0.6, 0.7, 0x8a2a24); makeFisher(-78, -175, -0.4, 2.9, 0x2a4a6a);
const tsuH = t => lerp(12, 50, sstep(TSU_T0, TSU_T0 + 1.5, t));
function updateShips(t) {
  const wl = SEA_Y - seaDrop(t); const chop = seaU.uChop.value;
  for (const S of ships) {
    const th = waveHit(S.z);
    let x = S.x0 + S.vx * Math.min(t, th), z = S.z, y = wl, rx = 0, rz = 0;
    const amp = S.type === 'cruise' ? 0.25 : 0.5;
    y += Math.sin(RT * 0.9 + S.ph) * amp * chop; rx = Math.sin(RT * 0.7 + S.ph * 2) * 0.02 * chop * (S.type === 'cruise' ? 0.3 : 1); rz = Math.sin(RT * 0.6 + S.ph) * 0.015 * chop;
    // pressure wave: boats capsize, the liner lists and is pushed
    if (t > th) { const d = t - th; z += (S.type === 'cruise' ? 25 : 40) * (1 - Math.exp(-d * 1.5));
      rx += (S.type === 'sail' ? 1.45 : S.type === 'fish' ? 0.4 : 0.12) * sstep(0, 0.7, d); }
    // the sea draws back: stranded on the bottom
    const bed = bedY(RAIL_Z - z) + S.draft * 0.5;
    if (y < bed) { y = bed; rx += 0.32 * sstep(0, 1, bed - wl); }
    // the tsunami lifts and carries everything in front of it
    const tz = tsuZ(t);
    if (t > TSU_T0 && t < 34.05 && tz > z - 4) { const crest = SEA_Y - seaDrop(t) - 1 + tsuH(t) * 0.92; const k = sstep(z - 4, z + 30, tz);
      y = lerp(y, crest - (S.type === 'cruise' ? 6 : 1), k); z = lerp(z, tz - 3, k); rx += -0.35 * k; }
    S.g.position.set(x, y, z); S.body.rotation.set(rx, 0, rz);
    // lights: on until the wave hits (ships have their own power), flicker, then a few emergency lights
    const on = t < th ? (t > 16 && t < 16.25 ? 0.4 : 1) : t < th + 0.5 ? (Math.floor(RT * 20) % 2 ? 1 : 0.1) : 0;
    S.lights.forEach((l, i) => { l.visible = on > 0.3 || (i === 0 && S.type === 'cruise' && t > th); l.material.opacity = on > 0.3 ? 1 : 0.6; });
    if (S.deckMats) S.deckMats.forEach(m => { m.emissiveIntensity = 1.6 * on + 0.05; });
    if (S.cabMat) S.cabMat.color.setHex(on > 0.3 ? 0xffd9a0 : 0x222222);
    S.refl.forEach((r, i) => { const rot = S.g.rotation.y; r.visible = on > 0.3 && seaDrop(t) < 0.3; r.position.set(x + S.reflX[i] * Math.cos(rot), wl + 0.05, z - S.reflX[i] * Math.sin(rot)); r.scale.y = (S.type === 'cruise' ? 70 : 20) + Math.sin(RT * 2 + i) * 3; });
  }
}

// ------------------------------------------------------------------ shock wave wall
const wallMat = new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, side: THREE.DoubleSide, fog: false,
  uniforms: { uTime: { value: 0 }, uA: { value: 0 }, uSeed: { value: 0 }, uSX: { value: 1 } },
  vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }',
  fragmentShader: `uniform float uTime,uA,uSeed,uSX; varying vec2 vUv;
    float hash(vec2 p){ p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y);}
    float noise(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f); return mix(mix(hash(i),hash(i+vec2(1,0)),f.x), mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x), f.y);}
    void main(){ vec2 p = vUv*vec2(14.*uSX,6.) + vec2(uSeed, -uTime*1.6);
      float n = noise(p)*.55 + noise(p*2.3+5.)*.3 + noise(p*5.1+1.)*.15;
      float billow = noise(vec2(vUv.x*uSX*9. + uSeed, uTime*.4))*.45 + noise(vec2(vUv.x*uSX*31., uSeed))*.2;
      float top = smoothstep(.98, .25 + billow, vUv.y + n*.12);
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
{ const r = mulberry(4242); const near = buildings.filter(b => b.z > -700);
  for (let i = 0; i < SHARDS; i++) { const b = near[Math.floor(r() * near.length)]; const z = b.z + (r() - 0.5) * b.w; shardData.push({ x: b.fx, y: 2 + r() * (b.h - 3), z, side: -1, vx: (3 + r() * 9), vy: r() * 4, vz: 10 + r() * 30, rx: r() * 6, ry: r() * 6, rz: r() * 6, sp: 4 + r() * 14, sc: (0.4 + r() * 1.3) * (1 + (-b.z) / 120) }); } }

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
  const nearB = buildings.filter(b => b.z > -900);
  for (let i = 0; i < 16; i++) { const b = nearB[Math.floor(r() * nearB.length)]; spots.push([b.fx + 0.5, 3 + r() * (b.h - 5), b.z + (r() - 0.5) * b.w * 0.7, (4 + r() * 6) * (1 + (-b.z) / 300)]); }
  for (const [x, z, sz] of [[-6, -6, 2.4], [5, -9, 2.0], [-4, -11, 2.6], [13, -30, 3.0], [13, RAIL_Z - PIER_LEN - 8, 14], [-2, -12, 1.8], [13, RAIL_Z - 55, 6]]) spots.push([x, 0.9, z, sz]);
  for (const [x, y, z, s] of spots) { const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: flameTex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })); sp.position.set(x, y, z); scene.add(sp); fires.push({ sp, s, seed: r() * 50, t0: 28 + r() * 3 }); } }

// facade chunks falling during the quake
const fallingGond = gondolas.filter(g => g.falls);
fallingGond.forEach((g, i) => { g.t0 = 20.7 + i * 0.45 + g.seed * 0.05; g.clone = new THREE.Mesh(g.g.geometry, g.g.material); g.clone.visible = false; scene.add(g.clone); });
const wheelSpin = t => 0.05 * Math.min(t, 7.6) + 0.05 * (1 - Math.exp(-Math.max(0, t - 7.6) * 0.7)) / 0.7;
function gondolaWorld(gd, t) { // world position of a gondola hanging on the wheel at story time t
  const a = gd.a + wheelSpin(t); const lx = Math.cos(a) * WHEEL.r, ly = WHEEL.cy + Math.sin(a) * WHEEL.r - 1.2;
  const ry = wheelRoot.rotation.y; return new THREE.Vector3(WHEEL.x + lx * Math.cos(ry), ly, WHEEL.z - lx * Math.sin(ry));
}
// debris driven ahead of the pressure wave
const WD = 420;
const wdebris = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(0.22, 0), flat(0x4a3c30), WD); wdebris.frustumCulled = false; scene.add(wdebris);
const wdData = []; { const r = mulberry(717); for (let i = 0; i < WD; i++) wdData.push({ dz: 2 + r() * 45, x: (r() - 0.5) * 44, y: 0.3 + Math.pow(r(), 1.6) * 30, sc: 0.4 + r() * 2.2, sp: 3 + r() * 9, ph: r() * 6 }); }
// exploding car in the aftermath
const EXPLO_T = 31.2;
const KIOSK = new THREE.Vector3(13, 0, RAIL_Z - 55);
{ const k = new THREE.Mesh(new THREE.BoxGeometry(3, 2.6, 3), flat(0xe8d8b0)); k.position.set(KIOSK.x, 1.3, KIOSK.z); world.add(k);
  const r = new THREE.Mesh(new THREE.ConeGeometry(2.6, 1.2, 4), flat(0xb03030)); r.rotation.y = Math.PI / 4; r.position.set(KIOSK.x, 3.2, KIOSK.z); world.add(r); }
const exploSprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: flameTex, color: 0xffb060, transparent: true, depthWrite: false, fog: false }));
exploSprite.renderOrder = 20; scene.add(exploSprite);
const EF = 40;
const efrags = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(0.25, 0), new THREE.MeshBasicMaterial({ color: 0xffb050 }), EF); efrags.frustumCulled = false; scene.add(efrags);
const efData = []; { const r = mulberry(919); for (let i = 0; i < EF; i++) { const a = r() * Math.PI * 2; efData.push({ vx: Math.cos(a) * (3 + r() * 8), vz: Math.sin(a) * (3 + r() * 8), vy: 6 + r() * 14, sc: 0.4 + r() * 1.2 }); } }

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
  const g = new THREE.Mesh(geo, flat(0x5e554b)); g.rotation.x = -Math.PI / 2; closeScene.add(g);
  const pud = new THREE.Mesh(new THREE.CircleGeometry(0.2, 9), new THREE.MeshStandardMaterial({ color: 0x0c1012, roughness: 0.08, metalness: 0.7, transparent: true, opacity: 0.85 }));
  pud.rotation.x = -Math.PI / 2; pud.scale.set(1.6, 0.9, 1); pud.position.set(-0.16, 0.0015, -0.05); closeScene.add(pud);
  const pud2 = pud.clone(); pud2.scale.set(0.8, 0.5, 1); pud2.position.set(0.18, 0.0015, 0.16); closeScene.add(pud2);
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
    const blink = Math.floor(RT * 2) % 2 === 0;
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

function pierDrop(z, t) { // how far a pier segment at z has sunk at story time t
  const sg = pierSegs.find(s => Math.abs(s.z - z) <= 6.01); if (!sg || !sg.breaks) return 0;
  const tb = 20.8 + hash1(sg.seed * 7) * 2.6; return 5.5 * sstep(tb, tb + 1.3, t);
}
// ------------------------------------------------------------------ world state as f(t)
const tmpM = new THREE.Matrix4(), tmpQ = new THREE.Quaternion(), tmpE = new THREE.Euler(), tmpV = new THREE.Vector3(), tmpS = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0);

function camPose(t) {
  // returns {x,y,z,yaw,pitch,roll}
  const sway = (s, f) => noise1(RT * f, s) ;
  let p = { x: 0, y: TERRACE + 1.68, z: 0, yaw: -0.03, pitch: 0.07, roll: 0 };
  // 0–2.9 s: looking up into the aurora, then tilt down to the street
  const tilt = easeIO(clamp((t - 1.55) / 1.45));
  p.pitch = lerp(0.66, 0.07, tilt); p.yaw = lerp(0.3, -0.03, tilt);
  // handheld
  p.yaw += sway(1, 0.35) * 0.012; p.pitch += sway(2, 0.4) * 0.01; p.roll += sway(3, 0.3) * 0.012;
  if (t > 16 && t < 20) { const k = sstep(16, 16.4, t) * (1 - sstep(18, 20, t)); p.z += 0.25 * sstep(16, 17, t); p.pitch -= 0.02 * k; }
  if (t >= 17) p.z += 0.25;
  // quake
  const q = sstep(19.9, 20.4, t) * (1 - sstep(23.6, 24.0, t));
  if (q > 0) { p.x += noise1(RT * 11, 4) * 0.09 * q; p.y += noise1(RT * 13, 5) * 0.08 * q; p.pitch += noise1(RT * 9, 6) * 0.035 * q; p.roll += noise1(RT * 10, 7) * 0.05 * q; p.yaw += noise1(RT * 7, 8) * 0.03 * q; }
  // look down at the crack opening in front of your feet
  p.pitch -= 0.6 * sstep(21.75, 22.25, t) * (1 - sstep(23.0, 23.6, t));
  // car explosion shake
  if (t > 31.2 && t < 32.5) { const e = Math.exp(-(t - 31.2) * 4); p.pitch += noise1(RT * 31, 16) * 0.05 * e; p.roll += noise1(RT * 29, 17) * 0.06 * e; }
  // 24–25 silence: still. wave approaching -> trembling, then hit
  const tr = sstep(25.6, T_HIT_CAM, t) * (t < T_HIT_CAM ? 1 : 0);
  p.pitch += noise1(RT * 25, 9) * 0.012 * tr; p.roll += noise1(RT * 22, 10) * 0.015 * tr;
  if (t >= T_HIT_CAM) {
    const k = easeIO(clamp((t - T_HIT_CAM) / 0.75));
    const shake = Math.exp(-(t - T_HIT_CAM) * 2.5);
    p.x = lerp(p.x, 0.9, k); p.y = lerp(p.y, TERRACE + 0.42, k); p.z = lerp(p.z, 7.5, k);
    p.pitch = lerp(p.pitch, 0.42, k); p.roll = lerp(p.roll, 0.16, k); p.yaw = lerp(p.yaw, 0.06, k);
    p.pitch += noise1(RT * 30, 11) * 0.12 * shake; p.roll += noise1(RT * 27, 12) * 0.2 * shake; p.yaw += noise1(RT * 24, 13) * 0.08 * shake;
    p.pitch += 0.04 * sstep(29, 34, t); p.z -= 0.3 * sstep(29, 34, t);
    p.pitch += noise1(RT * 0.5, 14) * 0.01; p.roll += noise1(RT * 0.4, 15) * 0.012;
    // you get back up and look out to sea: the water draws back, the wave comes
    const up2 = easeIO(clamp((t - 31.4) / 0.9));
    p.y = lerp(p.y, TERRACE + 1.3, up2); p.pitch = lerp(p.pitch, 0.06, up2); p.roll = lerp(p.roll, 0.03, up2); p.yaw = lerp(p.yaw, -0.02, up2); p.z = lerp(p.z, 3.5, up2);
    const tw = sstep(32.6, TSU_HIT, t);
    p.pitch += 0.32 * tw * tw + noise1(RT * 18, 18) * 0.03 * tw; p.roll += noise1(RT * 16, 19) * 0.04 * tw;
  }
  return p;
}

function setPerson(P, t) {
  const { kind } = P;
  let x = P.x, z = P.z, heading = P.heading, y = 0;
  let fallDir = 0, fall = 0;
  let armR = -0.15, armL = 0.15, armRz = 0, armLz = 0, headX = -0.35, legSwing = 0, lean = 0;
  const ph = P.ph;
  if (kind === 'film') { armR = -2.45 + Math.sin(RT * 0.8 + ph) * 0.05; armRz = 0.25; armL = R2(P) ? -2.3 : -0.1; armLz = R2(P) ? -0.35 : 0.1; headX = -0.25; }
  if (kind === 'point') { armL = -2.6 + Math.sin(RT * 0.6 + ph) * 0.15; armLz = -0.2; armR = -0.1; headX = -0.45; }
  if (kind === 'watch') { armR = -0.05 + Math.sin(RT + ph) * 0.03; armL = 0.05; headX = -0.5; }
  // idle sway
  lean = Math.sin(RT * 0.7 + ph) * 0.03;
  // meteor: cheering
  if (t > 11.6 && t < 16.2 && P.cheer) {
    const k = sstep(11.6, 12.2, t) * (1 - sstep(15.9, 16.2, t));
    const pump = Math.sin((RT + ph) * 7.5);
    if (kind === 'film') { armL = lerp(armL, -2.75 + pump * 0.35, k); armLz = lerp(armLz, -0.3, k); }
    else { armR = lerp(armR, -2.8 + pump * 0.3, k); armRz = lerp(armRz, 0.3, k); armL = lerp(armL, -2.7 - pump * 0.3, k); }
    if (P.jump) y += Math.max(0, Math.sin((RT + ph) * 7.5)) * 0.12 * k;
    headX = lerp(headX, -0.55, k);
  }
  // flash: recoil, arms sink; some run away
  if (t > 16.1) {
    const k = sstep(16.1, 16.9, t);
    z += 0.6 * k; headX = lerp(headX, -0.1, k);
    const sh = sstep(16.03, 16.25, t) * (1 - sstep(17.2, 18.0, t));
    if (sh > 0) { armR = lerp(armR, -2.1, sh); armL = lerp(armL, -2.1, sh); armRz = lerp(armRz, -0.55, sh); armLz = lerp(armLz, 0.55, sh); }
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
      legSwing = Math.sin((RT + ph) * 11) * 0.7 * k2; armR = lerp(armR, -Math.sin((RT + ph) * 11) * 0.8, k2); armL = lerp(armL, Math.sin((RT + ph) * 11) * 0.8, k2);
      armRz = armLz = 0;
    }
  }
  // quake: stumble / fall
  if (t > 20.1) {
    const q = sstep(20.1, 20.5, t) * (1 - sstep(23.6, 24, t));
    lean += noise1(RT * 6 + ph, 3) * 0.12 * q; y += Math.abs(noise1(RT * 14 + ph, 2)) * 0.05 * q;
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
        const dir = i % 2 ? 1 : -1; const x = -dir * 22 + dir * (t - 28.4 + i * 0.7) * 3.6, z = -7 - (i - 8) * 1.4;
        P.root.position.set(x, 0, z); P.fallYaw.rotation.y = 0; P.tilt.rotation.x = 0; P.body.rotation.set(0, dir * Math.PI / 2, 0);
        const s = Math.sin((RT + i) * 10); P.legs[0].rotation.x = s * 0.7; P.legs[1].rotation.x = -s * 0.7; P.arms[0].rotation.set(-s * 0.8, 0, 0); P.arms[1].rotation.set(s * 0.8, 0, 0);
        P.phone.visible = false; P.neck.rotation.x = 0.2;
      }
      continue;
    }
    setPerson(P, t);
    const hasPhone = P.kind === 'film';
    const dropped = hasPhone && t > P.dropAt;
    P.phone.visible = hasPhone && !dropped;
    P.glow.material.opacity = t > 7.35 && t < 7.9 ? (Math.floor(RT * 20) % 2 ? 0.05 : 0.4) : 0.35;
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
  skyU.uTime.value = RT;
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
  const clear = sstep(31.3, 32.1, t);
  fog.density = lerp(lerp(0.00045, 0.035, dust) - 0.012 * sstep(28.2, 29.6, t) + 0.02 * sstep(30, 34, t), 0.0011, clear);
  fog.color.setRGB(lerp(0.05, 0.2, dust), lerp(0.075, 0.16, dust), lerp(0.14, 0.13, dust));
  if (t > 16 && t < T_HIT_CAM) { const k = sstep(16, 16.3, t) * (1 - sstep(24, 26, t) * 0.5); fog.color.setRGB(lerp(0.05, 0.16, k), lerp(0.075, 0.07, k), lerp(0.14, 0.04, k)); }
  skyU.uDust.value *= 1 - 0.35 * clear;
  skyU.uDusk.value = 1 - sstep(16, 17, t) * 0.7;

  // lights
  const aurL = (1 - sstep(16, 16.4, t) * 0.6) * (1 - dust * 0.8);
  hemi.intensity = 1.0 * aurL + 0.15 * sstep(7.6, 10, t) * aurL;
  hemi.color.setHex(0x86b8d8); if (t > 16) hemi.color.lerp(new THREE.Color(0xff8a4a), sstep(16, 17, t)); if (dust > 0) hemi.color.lerp(new THREE.Color(0x8a7a6a), dust);
  auroraLight.intensity = 0.55 * aur * aurL; pinkLight.intensity = 0.3 * aur * aurL;
  blastLight.intensity = flash * 2.2 + glow * 0.9 * (1 - dust * 0.6);
  blastLight.color.setHex(t < 16.4 ? 0xfff2e0 : 0xff8040);
  const fireOn = sstep(28, 29.5, t);
  fireLight.intensity = fireOn * (14 + noise1(RT * 8, 21) * 5); fireLight2.intensity = fireOn * (10 + noise1(RT * 9, 22) * 4);

  // lamps: flicker and go out from far to near
  let li = 0;
  const near = [...lamps].sort((a, b) => b.z - a.z);
  for (const L of lamps) {
    const off = 7.25 + (-L.z / 170) * -1 + 1.1 + (L.side > 0 ? 0.08 : 0);
    const tOff = 8.35 - clamp(-L.z / 320) * 1.0 + hash1(L.seed) * 0.12;
    let on = t < tOff - 0.3 ? 1 : t < tOff ? (hash1(Math.floor(RT * 24) + L.seed) > 0.5 ? 1 : 0.15) : 0;
    L.headMat.color.setRGB(on ? 1 : 0.08, on ? 0.76 : 0.07, on ? 0.48 : 0.06);
    L.glow.visible = on > 0.5; L.pool.material.opacity = 0.35 * on;
    if (L.refl) { L.refl.visible = on > 0.5 && seaDrop(t) < 0.4; L.refl.scale.y = 14 + Math.sin(RT * 2 + L.seed) * 1.5; }
    const segDrop = L.z < RAIL_Z - 1 ? pierDrop(L.z, t) : 0; L.g.position.y = -segDrop;
    L.on = on; void off;
    // tilt during quake / blast
    const q = sstep(20.2, 20.6, t) * (1 - sstep(23.6, 24, t));
    const tf = 20.7 + hash1(L.seed + 9) * 2.2;
    const topple = L.z > -60 && hash1(L.seed + 4) < 0.6 ? sstep(tf, tf + 0.6, t) : 0;
    L.g.rotation.z = noise1(RT * 5 + L.seed, 31) * 0.05 * q + L.side * 1.42 * topple * topple;
    L.g.rotation.x = t > waveHit(L.z) ? sstep(waveHit(L.z), waveHit(L.z) + 0.3, t) * (0.5 + hash1(L.seed) * 0.6) : 0;
  }
  for (let i = 0; i < lampLights.length; i++) { const L = near[i]; const l = lampLights[i]; l.position.set(L.hx, L.hy - 0.3, L.z); l.intensity = 9 * L.on; }
  // festoon string lights
  { const dark = new THREE.Color(0x15110c); const gone = t > waveHit(RAIL_Z) + 0.08;
    festoon.visible = !gone;
    festData.forEach((f, k) => { const on = f.lamp.on > 0.5 || (t < 7.0); festoon.setColorAt(k, on ? f.c : dark); });
    festoon.instanceColor.needsUpdate = true;
    const q = sstep(20.2, 20.6, t) * (1 - sstep(23.6, 24, t)); festoon.position.y = noise1(RT * 6, 91) * 0.15 * q; }
  // Ferris wheel: turning, chasing colours, stops in the blackout, rocks in the quake, falls in the blast
  { wheelRot.rotation.z = wheelSpin(t);
    const lightsOn = t < 7.7 ? 1 : t < 7.95 ? (Math.floor(RT * 22) % 2) : 0;
    const col = new THREE.Color();
    for (let i = 0; i < WB; i++) { if (lightsOn) col.setHSL(((i / WB) * 3 + RT * 0.25) % 1, 0.85, 0.62); else col.setRGB(0.06, 0.06, 0.07); wheelBulbs.setColorAt(i, col); }
    wheelBulbs.instanceColor.needsUpdate = true;
    for (const gd of gondolas) { gd.g.rotation.z = -wheelSpin(t); gd.g.position.set(Math.cos(gd.a) * WHEEL.r, Math.sin(gd.a) * WHEEL.r - 1.1, 0); gd.g.visible = !(gd.falls && t > gd.t0); }
    const q = sstep(20.2, 20.6, t) * (1 - sstep(23.6, 24, t));
    const th = waveHit(WHEEL.z);
    wheelTilt.rotation.z = noise1(RT * 3, 92) * 0.05 * q;
    wheelTilt.rotation.x = t > th ? 1.45 * easeIO(clamp((t - th) / 1.6)) : 0;
    for (const gd of fallingGond) {
      const dt = t - gd.t0; gd.clone.visible = dt > 0 && dt < 6;
      if (!gd.clone.visible) continue;
      const p0 = gondolaWorld(gd, gd.t0); const floor = SEA_Y - seaDrop(t) - 0.4;
      gd.clone.position.set(p0.x + dt * 1.2, Math.max(floor, p0.y - 4.9 * dt * dt), p0.z + dt * 0.8);
      gd.clone.rotation.set(dt * 2.1, 0.3, dt * 1.4);
    }
  }
  // lighthouse sweeps until the blackout
  { const on = t < 7.9; beam.visible = on; beam.rotation.y = RT * 0.9;
    const toCam = Math.atan2(-(camera.position.z - LH.z), camera.position.x - LH.x);
    const face = Math.max(Math.cos(RT * 0.9 - toCam), Math.cos(RT * 0.9 + Math.PI - toCam), 0);
    beamMat.opacity = 0.16 * (1 - Math.pow(face, 3)); lhGlow.visible = on; lhGlow.scale.setScalar(30 + 90 * Math.pow(face, 12)); lhGlow.material.opacity = 0.45 + 0.55 * Math.pow(face, 12);
    lighthouse.userData.lamp.material.color.setHex(on ? 0xfff2c0 : 0x202020); }
  // pier segments: some break away and sink during the quake
  for (const sg of pierSegs) { sg.g.position.y = -pierDrop(sg.z, t); sg.g.rotation.x = sg.breaks ? (hash1(sg.seed) - 0.5) * 0.7 * sstep(0, 1, pierDrop(sg.z, t)) : 0;
    const q = sstep(20.2, 20.6, t) * (1 - sstep(23.6, 24, t)); sg.g.position.x = (PIER_X0 + PIER_X1) / 2 + noise1(RT * 7 + sg.seed, 93) * 0.12 * q; }
  // sea: level, chop, foam band of the pressure wave
  { sea.position.y = SEA_Y - seaDrop(t);
    const qq = sstep(20.2, 20.6, t) * (1 - sstep(23.6, 24.2, t));
    seaU.uChop.value = 1 + 2.2 * qq + 2.5 * sstep(waveHit(-400), waveHit(-50), t) + 0.4 * sstep(16, 17, t);
    seaU.uFoamZ.value = waveZ(t); seaU.uFoamA.value = t > WAVE_T0 - 0.3 ? 1 - sstep(T_HIT_CAM, T_HIT_CAM + 2.5, t) : 0;
    seaU.uSeaDust.value = skyU.uDust.value * 0.55; seaU.uFlashS.value = flash / 6; }
  // impact plume of water and steam, and the ring racing out over the sea
  { const fT = t - 16; plume.visible = fT > 0 && fT < 14;
    if (plume.visible) { const H = 2600 * (1 - Math.exp(-fT * 0.9)), rad = 160 + fT * 70;
      plumeCol.scale.set(rad, H, rad); plumeRing.scale.setScalar(250 + fT * 520); plumeRing.position.y = 20;
      plumeMat.uniforms.uTime.value = RT; plumeMat.uniforms.uGlowP.value = Math.exp(-fT * 0.5);
      plumeMat.uniforms.uA.value = sstep(0, 0.25, fT) * (1 - sstep(6, 13, fT)) * (1 - skyU.uDust.value * 0.8); } }
  updateShips(t);
  // the tsunami
  { tsunami.visible = t > TSU_T0 - 0.05 && t < 34.05;
    if (tsunami.visible) { const H = lerp(12, 50, sstep(TSU_T0, TSU_T0 + 1.5, t));
      tsunami.position.set(0, SEA_Y - seaDrop(t) - 1, tsuZ(t)); tsunami.scale.set(1, H, 0.7 + H / 45);
      tsuMat.uniforms.uTime.value = RT; tsuMat.uniforms.uH.value = H; tsuMat.uniforms.uGlowT.value = 0.25 + 0.15 * noise1(RT * 3, 94); } }

  // windows: blackout block by block
  const winBase = 1 - 0;
  for (const m of windowMats) { if (m.userData.tOff === undefined) m.userData.tOff = 7.45 + hash1(windowMats.indexOf(m)) * 1.3; m.emissiveIntensity = t < m.userData.tOff ? 1.25 * winBase : t < m.userData.tOff + 0.15 ? (Math.floor(RT * 30) % 2 ? 0.8 : 0.1) : 0; }
  for (const o of towers) if (o.userData.blink !== undefined) o.visible = t < 7.6 && Math.floor(t * 1.2 + o.userData.blink * 2) % 2 === 0;

  // trees sway in quake and blast
  for (const T of trees) {
    const q = sstep(20.2, 20.6, t) * (1 - sstep(23.6, 24, t));
    T.g.rotation.z = noise1(RT * 4 + T.seed, 41) * 0.06 * q;
    const th = waveHit(T.z); const b = t > th ? sstep(th, th + 0.25, t) : 0;
    T.g.rotation.x = b * (1.1 + hash1(T.seed) * 0.4);
    T.crown.visible = !(t > th + 0.15 && hash1(T.seed + 3) < 0.5);
  }

  // cars
  for (const C of cars) {
    let x = C.x, y = 0, z = C.z, rx = 0, rz = 0, ry = C.ry;
    const q = sstep(20.2, 20.5, t) * (1 - sstep(23.6, 24, t));
    y += Math.abs(noise1(RT * 9 + C.seed, 51)) * 0.35 * q; rx += noise1(RT * 7 + C.seed, 52) * 0.06 * q; rz += noise1(RT * 8 + C.seed, 53) * 0.07 * q;
    const th = waveHit(C.z);
    if (t > th) {
      const dt = t - th; const k = 1 - Math.exp(-dt * 1.7);
      z += 16 * k * C.push; x += (C.x > 0 ? 1 : -1) * 2 * k * C.push;
      rx += -C.spin * sstep(0, 1.1, dt);
      y += Math.abs(Math.sin(rx)) * 1.3 + Math.max(0, Math.sin(Math.min(dt * 3, Math.PI))) * 2.2;
    }
    C.g.position.set(x, y, z); C.g.rotation.set(0, ry, 0); C.body.rotation.set(rx, 0, rz);
    const haz = t > 20.6 && Math.floor((RT + C.seed) * 1.6) % 2 === 0;
    C.hazMat.color.setHex(haz ? 0xffa020 : 0x2a1600);
  }

  // cracks
  for (const c of cracks) {
    const prog = clamp((t - 20.3 - c.delay) / (c.dur || 1.6));
    const n = c.pts.length; const len = prog * (n - 1);
    const widen = c.w0 * (1 + 2.5 * sstep(20.5, 23.5, t)) + 0.15 * sstep(T_HIT_CAM, T_HIT_CAM + 1, t);
    for (let i = 0; i < n; i++) {
      const [px, pz] = c.pts[i]; const w = i <= len ? widen * (0.5 + 0.5 * hash1(i + c.seed)) * Math.min(1, len - i + 1) : 0;
      c.pos.set([px - w, 0.03, pz, px + w, 0.03, pz + w * 0.3], i * 6);
    }
    c.m.geometry.attributes.position.needsUpdate = true; c.m.visible = t > 20.3;
    if (!c.rim) { const g = new THREE.BufferGeometry(); c.rimPos = new Float32Array(c.pos.length); g.setAttribute('position', new THREE.BufferAttribute(c.rimPos, 3)); g.setIndex(c.m.geometry.index); c.rim = new THREE.Mesh(g, rimMat); c.rim.frustumCulled = false; world.add(c.rim); }
    for (let i = 0; i < n; i++) { const cx = (c.pos[i * 6] + c.pos[i * 6 + 3]) / 2, cz = c.pos[i * 6 + 2]; const hw = (c.pos[i * 6 + 3] - c.pos[i * 6]) / 2 * 1.25 + (hw0(c, i, len)); c.rimPos.set([cx - hw, 0.027, cz, cx + hw, 0.027, cz + hw * 0.3], i * 6); }
    c.rim.geometry.attributes.position.needsUpdate = true; c.rim.visible = c.m.visible;
    
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
  // the streak breaks apart shortly before impact
  const fk = clamp((t - 14.5) / 1.5);
  frags.forEach((sp, i) => {
    sp.visible = fk > 0 && t < 16;
    if (!sp.visible) return;
    const d = meteorDir(t - 0.06 * (i + 1)); const side = new THREE.Vector3(-d.z, 0, d.x).normalize();
    d.addScaledVector(side, (i - 1) * 0.03 * fk).addScaledVector(up, (i === 1 ? -1 : 1) * 0.012 * fk).normalize();
    sp.position.copy(camera.position).addScaledVector(d, 9000);
    sp.scale.setScalar(lerp(120, 260, fk) * (0.8 + 0.3 * Math.sin(RT * 30 + i)));
  });

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
    const far = z < RAIL_Z - 10;
    const wdt = far ? 2600 : 90, hgt = far ? 240 : 70;
    m.material.uniforms.uSX.value = far ? 14 : 1;
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

  // debris riding in front of the wave
  const zwf = waveZ(t);
  for (let i = 0; i < WD; i++) {
    const d = wdData[i]; const z = zwf + d.dz;
    if (t < WAVE_T0 || z > 6 || z < -260) { tmpM.makeScale(0, 0, 0); wdebris.setMatrixAt(i, tmpM); continue; }
    tmpE.set(RT * d.sp + d.ph, RT * d.sp * 0.7, d.ph); tmpQ.setFromEuler(tmpE);
    tmpM.compose(tmpV.set(d.x + Math.sin(RT * 3 + d.ph) * 0.8, d.y + Math.sin(RT * 4 + d.ph) * 0.6, z), tmpQ, tmpS.setScalar(d.sc)); wdebris.setMatrixAt(i, tmpM);
  }
  wdebris.instanceMatrix.needsUpdate = true;
  // car explosion
  const ex = t - EXPLO_T; const ec = cars[0];
  exploSprite.visible = ex > 0 && ex < 2.5;
  if (exploSprite.visible) {
    const base = KIOSK;
    exploSprite.position.set(base.x, base.y + 4 + ex * 4, base.z);
    { const sc = 6 + 26 * (1 - Math.exp(-ex * 5)); exploSprite.scale.set(sc, sc * 1.5, 1); }
    exploSprite.material.opacity = Math.min(1, 1.6 * Math.exp(-ex * 1.1)); exploSprite.material.color.setRGB(2.2, 1.0 + 0.8 * Math.exp(-ex * 4), 0.35);
    fireLight2.position.set(base.x, base.y + 2, base.z); fireLight2.intensity += 120 * Math.exp(-ex * 3);
  }
  for (let i = 0; i < EF; i++) {
    const f = efData[i];
    if (ex < 0 || ex > 3) { tmpM.makeScale(0, 0, 0); efrags.setMatrixAt(i, tmpM); continue; }
    const b = KIOSK; const y = Math.max(0.2, b.y + 1 + f.vy * ex - 4.9 * ex * ex);
    tmpM.compose(tmpV.set(b.x + f.vx * ex, y, b.z + f.vz * ex), tmpQ.identity(), tmpS.setScalar(f.sc * Math.max(0.2, 1 - ex / 3))); efrags.setMatrixAt(i, tmpM);
  }
  efrags.instanceMatrix.needsUpdate = true;

  // dust billows
  for (const D of dusts) {
    const dt = t - D.t0; D.sp.visible = dt > 0;
    if (dt <= 0) continue;
    D.sp.position.set(D.x, D.y0 + D.size * 0.3 + dt * D.rise, D.z + dt * 2);
    const s = D.size * (1 + dt * 0.25); D.sp.scale.set(s, s, 1); D.sp.material.rotation = D.rot + dt * 0.05;
    D.sp.material.opacity = sstep(0, 1.5, dt) * (0.45 + 0.4 * sstep(30, 34, t)) * (1 - 0.92 * sstep(31.2, 31.9, t));
    D.sp.material.color.setRGB(0.42, 0.37, 0.33).multiplyScalar(1 + 0.3 * fireOn);
  }
  // fires
  for (const F of fires) {
    const on = sstep(F.t0, F.t0 + 0.8, t); F.sp.visible = on > 0;
    const fl = 1 + noise1(RT * 9 + F.seed, 61) * 0.25;
    F.sp.scale.set(F.s * fl * on, F.s * 2 * fl * on, 1); F.sp.material.opacity = on * (0.8 + 0.2 * noise1(RT * 13 + F.seed, 62));
  }

  updatePeople(t);

  // camera
  const P = camPose(t);
  camera.position.set(P.x, P.y, P.z); camera.rotation.set(P.pitch, P.yaw, P.roll);
  // you zoom in on the streak, the flash snaps the view back
  const zoom = sstep(12.3, 15.3, t) * (1 - sstep(16.0, 16.25, t));
  camera.fov = 68 - 17 * zoom; camera.updateProjectionMatrix();
  phoneCam.fov = 66 - 30 * zoom; phoneCam.updateProjectionMatrix();
  camera.updateMatrixWorld(true);

  // your phone in hand
  let hx = 0.068, hy = -0.07, hz = -0.42, hrx = 0.03, hry = -0.12, hrz = 0.04;
  hx += noise1(RT * 0.9, 71) * 0.003; hy += noise1(RT * 0.8, 72) * 0.003;
  // look-up at the start: phone already pointing up
  if (t > 11.5 && t < 16) { hy += 0.004 * Math.sin(RT * 7); }
  const lower = sstep(16.4, 17.6, t);
  hy -= 0.07 * lower; hrx -= 0.35 * lower; hrz += 0.1 * lower;
  const q = sstep(20.0, 20.4, t);
  hx += noise1(RT * 12, 73) * 0.012 * q; hy += noise1(RT * 14, 74) * 0.012 * q;
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
  closeCam.position.set(0.012 + noise1(RT * 0.3, 81) * 0.003, camH, camZ);
  closeCam.lookAt(0.004, 0, 0.004);
  const pos = ashGeo.attributes.position;
  for (let i = 0; i < ASH; i++) {
    const a = ashData[i]; let y = (a.y0 - (t - 34) * a.sp) % 0.5; if (y < 0) y += 0.5;
    pos.setXYZ(i, a.x + Math.sin(RT * 0.8 + a.ph) * 0.01 + (t - 34) * 0.004, y, a.z + Math.cos(t * 0.6 + a.ph) * 0.008);
  }
  pos.needsUpdate = true;
  const on = t < 40.72 ? 1 : t < 41.0 ? (Math.floor(t * 28) % 2 ? 0.25 : 0.85) : 0;
  closeScreenMat.uniforms.uOn.value = on * (t < 34.25 ? sstep(33.9, 34.25, t) : 1);
  closeScreenMat.uniforms.uCrack.value = 1;
  closeScreenMat.uniforms.uAsh.value = 1;
  closeScreenMat.uniforms.uGain.value = 2.8;
  screenGlow.intensity = 0.0025 * on;
  closeKey.intensity = 0.55 + noise1(RT * 6, 82) * 0.15;
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
  const frac = 1 - clamp(t / BATTERY_EMPTY_AT);
  ctx.shadowBlur = 0;
  ctx.fillStyle = 'rgba(255,255,255,.22)'; ctx.fillRect(x + 2, 212, 196, 3);
  ctx.fillStyle = lowCol; ctx.fillRect(x + 2, 212, 196 * frac, 3);
  ctx.shadowBlur = 18;
  // big number
  const pulse = bat <= 6 && bat > 0 ? 0.55 + 0.45 * Math.abs(Math.sin(RT * 4)) : 1;
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
  const a = sstep(END.a, END.a + 0.6, t);
  if (a <= 0) return;
  ctx.save();
  ctx.globalAlpha = a; ctx.fillStyle = '#060607'; ctx.fillRect(0, 0, W, H);
  // drifting ash
  const r = mulberry(5);
  for (let i = 0; i < 90; i++) { const x = (r() * W + t * 8 * (r() - 0.3)) % W, y = (r() * H + (t - END.a) * (20 + r() * 30)) % H, s = 1 + r() * 2.5; ctx.fillStyle = `rgba(160,155,150,${0.15 + r() * 0.25})`; ctx.beginPath(); ctx.arc(x, y, s, 0, 7); ctx.fill(); }
  const b = sstep(END.text, END.text + 0.7, t);
  ctx.globalAlpha = a * b; ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = '#f4efe6';
  ctx.font = '500 104px "Playfair"'; ctx.fillText('Was wäre, wenn …', W / 2, 880);
  ctx.font = 'italic 400 76px "Playfair Italic"'; ctx.fillStyle = '#d9cfbf'; ctx.fillText('Teil 1', W / 2, 990);
  ctx.globalAlpha = a * b * 0.5; ctx.fillStyle = '#d9cfbf'; ctx.fillRect(W / 2 - 60, 1060, 120, 2);
  const c = sstep(END.sub, END.sub + 0.6, t);
  ctx.globalAlpha = a * c; ctx.fillStyle = '#e8e0d2'; ctx.font = '400 34px "Playfair SC"'; ctx.letterSpacing = '5px';
  ctx.fillText('Teil 2: Die Sonne verschwindet', W / 2, 1150);
  ctx.fillStyle = '#b8ad9c'; ctx.font = '400 30px "Playfair SC"';
  ctx.fillText('· Folge, um es zu sehen ·', W / 2, 1206);
  ctx.restore();
}

function composite(t, u, mode) {
  ctx.globalAlpha = 1; ctx.filter = 'none';
  if (mode === 'dark') { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); }
  else ctx.drawImage(glCanvas, 0, 0);
  // flash
  const fl = t < 16 ? 0 : t < 16.15 ? 1 : Math.exp(-(t - 16.15) * 2.2);
  if (fl > 0.003 && t < 20) { ctx.fillStyle = `rgba(255,252,244,${fl})`; ctx.fillRect(0, 0, W, H); }
  // the tsunami hits: dark water, white foam
  if (t > TSU_HIT - 0.12 && t < 34.1) {
    const a = sstep(TSU_HIT - 0.12, TSU_HIT + 0.02, t);
    ctx.fillStyle = `rgba(8,30,34,${a})`; ctx.fillRect(0, 0, W, H);
    const r = mulberry(Math.floor(RT * 30)); ctx.save(); ctx.filter = 'blur(10px)';
    for (let i = 0; i < 140; i++) { const x = r() * W, y = r() * H, rr = 6 + r() * 60; const g = ctx.createRadialGradient(x, y, 0, x, y, rr); g.addColorStop(0, `rgba(235,245,245,${0.55 * a})`); g.addColorStop(1, 'rgba(235,245,245,0)'); ctx.fillStyle = g; ctx.fillRect(x - rr, y - rr, rr * 2, rr * 2); }
    ctx.restore();
  }
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
  ctx.drawImage(grain[Math.floor(RT * 30) % grain.length], 0, 0, W, H);
  ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
  drawTitle(u);
  drawCaption(u);
  drawEndCard(u);
  drawHUD(u);
}

// ------------------------------------------------------------------ frame entry point
let replayT = 0;
function renderFrame(u) {
  const t = warp(u);
  RT = u;
  const bat = batteryAt(u);
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
    composite(t, u, 'live');
  } else if (t < 42) {
    // replay of the aurora footage on the cracked phone
    replayT = 0.4 + (t - 34) * 0.85;
    RT = 6 + replayT * 1.1;
    updateWorld(2.6 + replayT * 0.62);
    RT = u;
    handRig.visible = true; myPhone.g.visible = false;
    camera.updateMatrixWorld(true); phoneCam.updateMatrixWorld(true);
    drawPhoneUI(t, 'replay', bat, replayT);
    if (t < 41.05) { renderer.setRenderTarget(rtPhone); renderer.render(scene, phoneCam); renderer.setRenderTarget(null); }
    updateClose(t);
    bloom.strength = 0.7;
    renderPass.scene = closeScene; renderPass.camera = closeCam;
    composer.render();
    composite(t, u, 'close');
  } else {
    composite(t, u, 'dark');
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
