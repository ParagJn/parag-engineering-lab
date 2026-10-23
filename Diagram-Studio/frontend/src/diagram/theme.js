// A theme is a plain object of resolved colours + fonts, so the same renderer can draw the on-screen
// diagram and the exported SVG/PNG. More styles (draw.io, Visio, blueprint...) later = more theme objects
// plus shape tweaks keyed on theme.style.

export const FONT = {
  sans: "Geist, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif",
  serif: "'Instrument Serif', ui-serif, Georgia, serif",
  mono: "'Geist Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
}

export const TYPE = {
  title: 30,
  subtitle: 13,
  kicker: 10,
  node: 13,
  sub: 10.5,
  edge: 10.5,
  group: 10,
}

// Line heights for text inside nodes
export const LINE = { label: 16, sub: 14 }

const editorial = { style: 'editorial', fonts: FONT, radius: 8 }

export const THEMES = {
  light: {
    ...editorial,
    id: 'light',
    label: 'Light',
    paper: '#faf7f2',
    panel: '#f2eee6',
    ink: '#1c1a17',
    muted: '#6f695f',
    rule: '#ddd6ca',
    line: '#a39b8d',
    accent: '#b4532f',
    accentSoft: '#f6e6dd',
  },
  dark: {
    ...editorial,
    id: 'dark',
    label: 'Dark',
    paper: '#15130f',
    panel: '#1d1b16',
    ink: '#f1ede4',
    muted: '#a29b8e',
    rule: '#37332c',
    line: '#6d675c',
    accent: '#e0795a',
    accentSoft: '#3a231b',
  },
}

export const TYPE_LABELS = {
  architecture: 'Architecture',
  flowchart: 'Flowchart',
  state: 'State',
  sequence: 'Sequence',
  timeline: 'Timeline',
  quadrant: 'Quadrant',
}
