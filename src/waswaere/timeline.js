// Script of "Was wäre, wenn … Teil 1" (all times in seconds).
export const DURATION = 45;

export const TITLE = { a: 0, b: 2.15, text: 'Was wäre, wenn der schönste Himmel deines Lebens der letzte wäre?' };

// battery value from scene start (ticks down over 0.7 s)
export const BATTERY = [
  [0, 34], [2, 34], [7, 31], [11, 28], [16, 24], [20, 19], [24, 13], [29, 6], [34, 1], [41.0, 0],
];

// second HUD line (small caps), changes per scene
export const HUD_LINES = [
  { a: 2.0, b: 7.0, text: 'Stärkster Sturm seit 1859' },
  { a: 7.0, b: 11.0, text: 'Kein Netz' },
  { a: 11.0, b: 16.0, text: t => `Zeit bis zum Einschlag ${Math.max(1, Math.ceil(16 - t))} s` },
  { a: 16.0, b: 20.0, text: 'Mehr Energie als alle Atomwaffen der Welt' },
  { a: 20.0, b: 24.0, text: 'Bodenwelle · 20 s nach dem Einschlag' },
  { a: 24.0, b: 29.0, text: '5 Minuten nach dem Einschlag' },
  { a: 29.0, b: 34.0, text: 'Staub verdunkelt den Himmel' },
  { a: 34.0, b: 41.0, text: 'Letzte Aufnahme' },
  { a: 41.0, b: 45.0, text: 'Akku leer' },
];

// lower-third captions (italic serif, "du" form)
export const TEXTS = [
  { a: 2.35, b: 6.85, text: 'Ein Sonnensturm trifft die Erde. Polarlichter über Frankfurt.' },
  { a: 7.2, b: 10.85, text: 'Der Sturm legt Satelliten und Stromnetze lahm.' },
  { a: 11.3, b: 15.85, text: 'Deshalb warnt dich niemand.' },
  { a: 16.6, b: 19.85, text: 'Ein Asteroid schlägt 100 Kilometer entfernt ein.' },
  { a: 20.3, b: 23.85, text: 'Zuerst kommt das Erdbeben.' },
  { a: 24.15, b: 28.85, text: 'Dann die Druckwelle.' },
  { a: 29.2, b: 31.0, text: 'Millionen Menschen lebten hier.' },
  { a: 31.15, b: 33.9, text: 'Der schönste Himmel deines Lebens verschwindet.' },
  { a: 35.2, b: 41.7, text: 'Es war das Letzte, was du gefilmt hast.' },
];

export const TIMELINE = { DURATION };
