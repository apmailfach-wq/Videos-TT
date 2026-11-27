// Wird im Browser ausgeführt: rendert die komplette Tonspur mit der Web Audio API (OfflineAudioContext).
async function renderSoundtrack() {
  const SR = 48000, DUR = 45.5;
  const ctx = new OfflineAudioContext(2, Math.ceil(SR * DUR), SR);
  const master = ctx.createDynamicsCompressor();
  master.threshold.value = -18; master.ratio.value = 3; master.attack.value = 0.01; master.release.value = 0.3;
  const out = ctx.createGain(); out.gain.value = 0.9;
  master.connect(out); out.connect(ctx.destination);

  // Hall (synthetische Impulsantwort)
  const rev = ctx.createConvolver();
  const irLen = SR * 3.2, ir = ctx.createBuffer(2, irLen, SR);
  let seed = 11; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647) * 2 - 1;
  for (let c = 0; c < 2; c++) { const d = ir.getChannelData(c); for (let i = 0; i < irLen; i++) d[i] = rnd() * Math.pow(1 - i / irLen, 3.2); }
  rev.buffer = ir; const revGain = ctx.createGain(); revGain.gain.value = 0.28; rev.connect(revGain); revGain.connect(master);
  const bus = (g) => { const n = ctx.createGain(); n.gain.value = g; n.connect(master); n.connect(rev); return n; };

  const noiseBuf = ctx.createBuffer(1, SR * 4, SR);
  { const d = noiseBuf.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = rnd(); }

  // --- Ambient-Pad: ruhige Akkorde (Dmaj9 -> Bm9 -> Gmaj7 -> A6)
  const pad = bus(0.05);
  const chords = [[0, [146.83, 220, 277.18, 329.63, 369.99]], [11.25, [123.47, 185, 220, 293.66, 277.18 * 2]], [22.5, [98, 146.83, 196, 246.94, 369.99]], [33.75, [110, 164.81, 220, 277.18, 369.99]]];
  chords.forEach(([t0, notes], ci) => {
    const t1 = t0 + 11.25 + 2.5;
    notes.forEach((f, ni) => {
      [-4, 4].forEach((det) => {
        const o = ctx.createOscillator(); o.type = ni === 0 ? 'sine' : 'triangle'; o.frequency.value = f; o.detune.value = det;
        const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 900; lp.Q.value = 0.3;
        const g = ctx.createGain(); g.gain.setValueAtTime(0, t0);
        g.gain.linearRampToValueAtTime(ni === 0 ? 0.5 : 0.22, t0 + 2.5);
        g.gain.setValueAtTime(ni === 0 ? 0.5 : 0.22, t1 - 2.5);
        g.gain.linearRampToValueAtTime(0, Math.min(t1, DUR));
        const pan = ctx.createStereoPanner(); pan.pan.value = det > 0 ? 0.35 : -0.35;
        o.connect(lp); lp.connect(g); g.connect(pan); pan.connect(pad);
        o.start(t0); o.stop(Math.min(t1, DUR));
      });
    });
  });
  // sanftes Ausblenden am Ende
  pad.gain.setValueAtTime(0.05, 41); pad.gain.linearRampToValueAtTime(0, 45.3);

  // --- UI-Klick: kurzer, hoher Sinus-Tick + weiches Rauschen
  const clickBus = bus(0.5);
  function click(t, f = 2200, vol = 0.35, pan = 0) {
    const o = ctx.createOscillator(); o.type = 'sine'; o.frequency.setValueAtTime(f, t); o.frequency.exponentialRampToValueAtTime(f * 0.6, t + 0.05);
    const g = ctx.createGain(); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vol, t + 0.002); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.09);
    const p = ctx.createStereoPanner(); p.pan.value = pan;
    o.connect(g); g.connect(p); p.connect(clickBus); o.start(t); o.stop(t + 0.12);
    const n = ctx.createBufferSource(); n.buffer = noiseBuf;
    const hp = ctx.createBiquadFilter(); hp.type = 'bandpass'; hp.frequency.value = 5000; hp.Q.value = 1.5;
    const ng = ctx.createGain(); ng.gain.setValueAtTime(vol * 0.5, t); ng.gain.exponentialRampToValueAtTime(0.0001, t + 0.025);
    n.connect(hp); hp.connect(ng); ng.connect(p); n.start(t, 0.5); n.stop(t + 0.04);
  }
  function chime(t, notes, vol = 0.12) {
    notes.forEach((f, i) => {
      const o = ctx.createOscillator(); o.type = 'sine'; o.frequency.value = f;
      const g = ctx.createGain(); const s = t + i * 0.09;
      g.gain.setValueAtTime(0, s); g.gain.linearRampToValueAtTime(vol, s + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, s + 1.6);
      o.connect(g); g.connect(clickBus); o.start(s); o.stop(s + 1.7);
    });
  }
  const clicks = [
    [0.25, 2400], [0.45, 1800, 0.2], [1.6, 2000, 0.25, -0.4], [5.0, 2400], [5.4, 1600, 0.22], [5.8, 1600, 0.18, -0.5],
    [8.6, 2000, 0.25, 0.4], [16.0, 2400], [18.2, 2000, 0.25, 0.4], [18.8, 2000, 0.22, -0.4], [19.6, 2000, 0.22, -0.4],
    [24.2, 2400], [26.4, 1300, 0.3], [28.8, 1500, 0.25, 0.4], [31.0, 2400], [33.6, 1800, 0.22], [34.4, 1800, 0.22],
    [38.2, 2400], [40.8, 1800, 0.2], [41.25, 1900, 0.2], [41.7, 2000, 0.2], [42.6, 2200, 0.2],
  ];
  clicks.forEach(([t, f, v = 0.32, p = 0]) => click(t, f, v, p));
  // leise Daten-Ticks während der Messung (wie ein Messgerät)
  for (let t = 6.5; t < 28; t += 0.5) if (t < 17.4 || t > 24) click(t, 3200, 0.05, (Math.round(t * 2) % 2) ? 0.3 : -0.3);
  chime(37.6, [880, 1108.73, 1318.5], 0.1); // Erfolg: 3-m-Tisch
  chime(42.6, [587.33, 739.99, 880], 0.07);

  // --- Zeitlupen-Rauschen: gefiltertes Rauschen, das den Fall begleitet
  function airBed(t0, t1, fromHz, toHz, vol, dips = []) {
    const n = ctx.createBufferSource(); n.buffer = noiseBuf; n.loop = true;
    const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.Q.value = 0.7;
    lp.frequency.setValueAtTime(fromHz, t0); lp.frequency.exponentialRampToValueAtTime(toHz, t1);
    const g = ctx.createGain(); g.gain.setValueAtTime(0, t0); g.gain.linearRampToValueAtTime(vol, t0 + 1.5);
    dips.forEach(([a, b, v]) => { g.gain.setValueAtTime(vol, a); g.gain.linearRampToValueAtTime(v, a + 0.8); g.gain.setValueAtTime(v, b); g.gain.linearRampToValueAtTime(vol, b + 1.0); });
    g.gain.setValueAtTime(vol, t1 - 0.4); g.gain.linearRampToValueAtTime(0, t1 + 0.3);
    n.connect(lp); lp.connect(g); g.connect(master); n.start(t0); n.stop(t1 + 0.4);
  }
  airBed(5.2, 28.5, 260, 900, 0.16, [[17.0, 23.2, 0.06]]);
  // tiefes, langsames Brummen (Zeitlupen-Gefühl)
  { const o = ctx.createOscillator(); o.type = 'sine'; o.frequency.setValueAtTime(55, 5.2); o.frequency.linearRampToValueAtTime(48, 28.5);
    const g = ctx.createGain(); g.gain.setValueAtTime(0, 5.2); g.gain.linearRampToValueAtTime(0.12, 8); g.gain.setValueAtTime(0.12, 27.8); g.gain.linearRampToValueAtTime(0, 28.6);
    o.connect(g); g.connect(master); o.start(5.2); o.stop(29); }
  // Bullet-Time: weicher "Reverse"-Swell
  { const n = ctx.createBufferSource(); n.buffer = noiseBuf; const bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 2;
    bp.frequency.setValueAtTime(3000, 16.6); bp.frequency.exponentialRampToValueAtTime(300, 17.8);
    const g = ctx.createGain(); g.gain.setValueAtTime(0, 16.6); g.gain.linearRampToValueAtTime(0.18, 17.6); g.gain.linearRampToValueAtTime(0, 18.4);
    n.connect(bp); bp.connect(g); g.connect(master); g.connect(rev); n.start(16.6); n.stop(18.5); }
  // Landung: weicher, gedämpfter Aufprall (kein Stress)
  { const t = 28.5; const o = ctx.createOscillator(); o.type = 'sine'; o.frequency.setValueAtTime(120, t); o.frequency.exponentialRampToValueAtTime(42, t + 0.35);
    const g = ctx.createGain(); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.55, t + 0.008); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.9);
    o.connect(g); g.connect(master); g.connect(rev); o.start(t); o.stop(t + 1);
    const n = ctx.createBufferSource(); n.buffer = noiseBuf; const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 700;
    const ng = ctx.createGain(); ng.gain.setValueAtTime(0.3, t); ng.gain.exponentialRampToValueAtTime(0.0001, t + 0.35);
    n.connect(lp); lp.connect(ng); ng.connect(master); n.start(t); n.stop(t + 0.4); }
  // 3-m-Fall: langer Whoosh
  airBed(33.2, 37.6, 400, 2200, 0.1);

  const buf = await ctx.startRendering();
  return [Array.from(buf.getChannelData(0)), Array.from(buf.getChannelData(1))];
}
