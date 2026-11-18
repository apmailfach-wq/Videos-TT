// Script of "Was wäre, wenn … Teil 1" in output time (seconds). The 3D world runs on its own
// "story time"; timeline.json maps output time -> story time (warp) and places the narration.
export const DURATION = 68;

export const TITLE = { a: 0, b: 4.95, text: 'Was wäre, wenn der schönste Himmel deines Lebens der letzte wäre?' };

// battery value from scene start (ticks down over 0.7 s)
export const BATTERY = [
  [0, 34], [5, 34], [13.5, 31], [18, 28], [26.5, 24], [34.5, 19], [40.5, 13], [46.5, 6], [53, 1], [60.6, 0],
];
export const BATTERY_EMPTY_AT = 60.6;

// second HUD line (small caps), changes per scene
export const HUD_LINES = [
  { a: 5.0, b: 13.5, text: 'Stärkster Sturm seit 1859' },
  { a: 13.5, b: 18.0, text: 'Kein Netz' },
  { a: 18.0, b: 26.5, text: t => `Zeit bis zum Einschlag ${Math.max(1, Math.ceil(26.5 - t))} s` },
  { a: 26.5, b: 34.5, text: 'Mehr Energie als alle Atomwaffen der Welt' },
  { a: 34.5, b: 40.5, text: 'Bodenwelle · 20 s nach dem Einschlag' },
  { a: 40.5, b: 46.5, text: '5 Minuten nach dem Einschlag' },
  { a: 46.5, b: 53.0, text: 'Staub verdunkelt den Himmel' },
  { a: 53.0, b: 60.6, text: 'Letzte Aufnahme' },
  { a: 60.6, b: 68.0, text: 'Akku leer' },
];

// lower-third captions (italic serif, "du" form)
export const TEXTS = [
  { a: 5.6, b: 13.3, text: 'Ein Sonnensturm trifft die Erde. Polarlichter über Frankfurt.' },
  { a: 14.0, b: 17.8, text: 'Der Sturm legt Satelliten und Stromnetze lahm.' },
  { a: 18.4, b: 26.3, text: 'Deshalb warnt dich niemand.' },
  { a: 27.7, b: 34.3, text: 'Ein Asteroid schlägt 100 Kilometer entfernt ein.' },
  { a: 34.9, b: 40.3, text: 'Zuerst kommt das Erdbeben.' },
  { a: 40.6, b: 46.3, text: 'Dann die Druckwelle.' },
  { a: 46.8, b: 49.3, text: 'Millionen Menschen lebten hier.' },
  { a: 49.4, b: 52.8, text: 'Der schönste Himmel deines Lebens verschwindet.' },
  { a: 54.9, b: 60.9, text: 'Es war das Letzte, was du gefilmt hast.' },
];

export const END = { a: 62.0, text: 62.3, sub: 62.8 };
