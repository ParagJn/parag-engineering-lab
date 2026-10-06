import { clamp, ein, einBack, eio, eout, expLerp, lerp, mixHex, prog, smooth, sp, springStep, squash } from "./math";
import type { MotionConfig } from "./types";

/**
 * The orange-dot film as a pure function of time.
 *
 * Everything is laid out in a 1920x1080 design space on a fixed 15-unit timeline.
 * `seek` maps real seconds onto that timeline and scales the design space into
 * any output size; full-frame effects (background, halftone, fills) cover the
 * whole visible rectangle so non-16:9 outputs still bleed edge to edge.
 */
export const TIMELINE = 15;
const DW = 1920, DH = 1080, CX = DW / 2, CY = DH / 2;

export interface Film {
  width: number;
  height: number;
  duration: number;
  seek(g: CanvasRenderingContext2D, seconds: number): void;
}

/**
 * Scene segments on the internal timeline. `pace` > 1 plays a scene slower than the base timeline;
 * a scene that is switched off collapses to `skip` units, where the dot makes a short bridging move.
 * The toggle/hero opening and the return trip are always on so the loop closes.
 */
export type SceneId = "stat" | "shape" | "words" | "card";
const SEGMENTS: { id: "open" | SceneId | "return"; a: number; b: number; pace: number; skip: number }[] = [
  { id: "open", a: 0, b: 3.0, pace: 1, skip: 0 },
  { id: "stat", a: 3.0, b: 6.5, pace: 1.25, skip: 0.8 },
  { id: "shape", a: 6.5, b: 9.0, pace: 1, skip: 0.9 },
  { id: "words", a: 9.0, b: 10.75, pace: 1.35, skip: 0.25 },
  { id: "card", a: 10.75, b: 13.55, pace: 1, skip: 0.6 },
  { id: "return", a: 13.55, b: TIMELINE, pace: 1, skip: 0 },
];

export function sceneOn(cfg: MotionConfig, id: SceneId) {
  return cfg.scenes.show?.[id] !== false;
}

/** Maps real seconds onto the internal timeline (and back), honouring pace and switched-off scenes. */
export function timeline(cfg: MotionConfig) {
  const segs = SEGMENTS.map((s) => ({ ...s, len: s.id !== "open" && s.id !== "return" && !sceneOn(cfg, s.id) ? s.skip : (s.b - s.a) * s.pace }));
  const natural = segs.reduce((n, s) => n + s.len, 0);
  return {
    /** Loop length in seconds at the designed pace. */
    natural,
    toInternal(seconds: number) {
      let tau = ((((seconds / cfg.duration) % 1) + 1) % 1) * natural;
      for (const s of segs) {
        if (tau <= s.len) return s.len > 0 ? s.a + ((s.b - s.a) * tau) / s.len : s.b;
        tau -= s.len;
      }
      return TIMELINE;
    },
    toSeconds(t: number) {
      let acc = 0;
      for (const s of segs) {
        if (t <= s.b) return ((acc + (clamp((t - s.a) / (s.b - s.a)) * s.len)) / natural) * cfg.duration;
        acc += s.len;
      }
      return cfg.duration;
    },
  };
}

interface Pt { x: number; y: number }
interface Xf { x: number; y: number; size: number; rot: number; a: number }
interface Letter { ch: string; dl: string; x: number; y: number; u: number; gi: number }
interface Spec { x: number; y: number; r: number }
interface DotSpec { k: number; spec: Spec; real: boolean }
interface Dot { x: number; y: number; r: number; sx: number; sy: number }

const DOTLESS: Record<string, string> = { i: "ı", j: "ȷ" };
const tittleCache = new Map<string, Record<string, Spec>>();
let scratch: CanvasRenderingContext2D | null = null;

function scratchCtx() {
  if (!scratch) scratch = document.createElement("canvas").getContext("2d", { willReadFrequently: true })!;
  return scratch;
}

// Find the tittle of i / j by rasterising the glyph: top blob above the first empty row.
function measureTittle(ch: string, fontOf: (w: number, s: number) => string): Spec {
  const c = document.createElement("canvas");
  c.width = c.height = 400;
  const g = c.getContext("2d", { willReadFrequently: true })!;
  g.font = fontOf(800, 200);
  g.fillStyle = "#000";
  g.fillText(ch, 100, 300);
  const d = g.getImageData(0, 0, 400, 400).data;
  let top = -1, bot = -1, minx = 1e9, maxx = -1;
  for (let y = 0; y < 400; y++) {
    let any = false;
    for (let x = 0; x < 400; x++) {
      if (d[(y * 400 + x) * 4 + 3] > 128) { any = true; minx = Math.min(minx, x); maxx = Math.max(maxx, x); }
    }
    if (any && top < 0) top = y;
    if (!any && top >= 0) { bot = y - 1; break; }
  }
  if (top < 0 || bot < 0 || bot > 270) return { x: 0.3, y: 0.72, r: 0.075 };
  return { x: ((minx + maxx) / 2 - 100) / 200, y: (300 - (top + bot) / 2) / 200, r: Math.max(maxx - minx, bot - top) / 400 };
}

export function createFilm(cfg: MotionConfig, width: number, height: number): Film {
  const { style } = cfg;
  const showStat = sceneOn(cfg, "stat"), showShape = sceneOn(cfg, "shape"), showWords = sceneOn(cfg, "words"), showCard = sceneOn(cfg, "card");
  const tl = timeline(cfg);
  const PAPER = style.paper, INK = style.ink, ACCENT = style.accent, MUTE = mixHex(PAPER, INK, 0.12);
  const FONT = `"${style.font}", "Helvetica Neue", Arial, sans-serif`;
  const f = (w: number, s: number) => `${w} ${s}px ${FONT}`;

  const hero = cfg.text.hero.trim() || "Hello";
  const intro = cfg.text.intro.trim();
  const label = intro ? `${intro} ${hero}` : hero;
  const words = cfg.text.words.map((w) => w.trim()).filter(Boolean);
  if (!words.length) words.push("MOTION");
  const stat = cfg.text.stat.trim() || "+22%";
  // "+22%" -> prefix "+", 22, suffix "%": counters animate the number and keep the rest.
  const sm = stat.match(/^(.*?)(\d+(?:\.\d+)?)(.*)$/);
  const statNum = sm ? { prefix: sm[1], num: parseFloat(sm[2]), dec: (sm[2].split(".")[1] || "").length, suffix: sm[3] } : null;
  const fmtStat = (k: number) => (statNum ? statNum.prefix + (statNum.num * Math.max(0, k)).toFixed(statNum.dec) + statNum.suffix : stat);
  const percent = statNum?.num ?? 22;
  const isPercent = !!statNum && statNum.suffix.includes("%");
  const cardText = [cfg.text.cardTitle.trim() || hero, cfg.text.cardSubtitle.trim(), cfg.text.cardFootnote.trim()];

  // Graph spring: damping solved so the overshoot equals the stat,
  // and the peak lands at x = 0.25 of the graph (one beat after landing).
  const OS = clamp(percent / 100, 0.02, 0.8);
  const GZ = -Math.log(OS) / Math.sqrt(Math.PI ** 2 + Math.log(OS) ** 2);
  const GWN = (4 * Math.PI) / Math.sqrt(1 - GZ * GZ);
  const gy = (x: number) => springStep(x, GZ, GWN);

  // Design space -> output transform, and the visible design-space rectangle.
  const u = Math.min(width / 1600, height / 1080);
  const ox = width / 2 - CX * u, oy = height / 2 - CY * u;
  const V = { x0: -ox / u, y0: -oy / u, x1: (width - ox) / u, y1: (height - oy) / u };
  const halfDiag = Math.hypot(V.x1 - V.x0, V.y1 - V.y0) / 2;
  const cornerDist = (p: Pt) => Math.max(...[[V.x0, V.y0], [V.x1, V.y0], [V.x0, V.y1], [V.x1, V.y1]].map(([x, y]) => Math.hypot(x - p.x, y - p.y)));

  // ------------------------------------------------------------ layout
  const m = scratchCtx();
  const textW = (s: string, size: number, weight: number) => { m.font = f(weight, size); return m.measureText(s).width; };
  const lineLayout = (str: string, size: number, weight: number, x0: number, base: number): Letter[] =>
    [...str].map((ch, i, arr) => {
      m.font = f(weight, size);
      const x = x0 + m.measureText(arr.slice(0, i).join("")).width;
      m.font = f(weight, 100);
      return { ch, dl: DOTLESS[ch] || ch, x, y: base, u: m.measureText(ch).width / 100, gi: 0 };
    });
  const dotIndex = (s: string) => { const k = s.lastIndexOf("i"); return k >= 0 ? k : s.lastIndexOf("j"); };

  let TT = tittleCache.get(style.font);
  if (!TT) {
    TT = { i: measureTittle("i", f), j: measureTittle("j", f) };
    if (document.fonts.check(`800 100px "${style.font}"`)) tittleCache.set(style.font, TT);
  }
  const dotSpec = (letters: Letter[], k: number): DotSpec => {
    if (k >= 0) return { k, spec: TT![letters[k].ch], real: true };
    const last = letters.length - 1;
    return { k: last, spec: { x: letters[last].u + 0.1, y: 0.09, r: 0.085 }, real: false };
  };

  const C: Pt = { x: CX, y: CY };
  const TW = 150, TH = 80, GAP = 44, LS = 64, KR = 30;
  const rowX0 = (DW - (TW + GAP + textW(label, LS, 800))) / 2;
  const track = { cx: rowX0 + TW / 2, cy: CY, w: TW, h: TH };
  const knobOff: Pt = { x: rowX0 + 40, y: CY }, knobOn: Pt = { x: rowX0 + TW - 40, y: CY };
  const labelL = lineLayout(label, LS, 800, rowX0 + TW + GAP, CY + 0.36 * LS);
  const h0 = label.length - hero.length;
  let ex = 0;
  const exitOrder = labelL.map((_, i) => (i < h0 ? ex++ : -1));

  const HS = Math.min(220, (220 * 1500) / textW(hero, 220, 800));
  const heroL = lineLayout(hero, HS, 800, (DW - textW(hero, HS, 800)) / 2, CY + 0.36 * HS);
  const heroDot = dotSpec(heroL, dotIndex(hero));
  const labelDot = h0 + heroDot.k;
  const DR = heroDot.spec.r * HS * 1.15;

  const G0: Pt = { x: 340, y: 800 }, GW = 980, GH = 400;
  const E: Pt = { x: G0.x + GW, y: G0.y - GH * gy(1) };
  const P1: Pt = { x: 520, y: 800 }, P2: Pt = { x: P1.x + 640, y: P1.y - 220 * gy(1) };
  const BIG = halfDiag + 150; // clears all four corners of any output aspect

  // ------------------------------------------------------------ stat scene variants
  // Each variant says where the dot lands (3.5), how it moves until 5.5, and where it rests before shooting to centre.
  // Counter and ring read the number and the dot from the same spring.
  const statSpring = (t: number) => { const tau = prog(t, 3.5, 5.5); return tau <= 0 ? 0 : tau >= 1 ? 1 : springStep(tau, 0.45, 14); };

  const BW = 120, BGAP = 70, BX0 = 360, BASE = 800, H5 = 440;
  const lift = clamp(percent / 100, 0.05, 1.5);
  const barHs = [0.55, 0.78, 0.66, 1].map((k) => (k * H5) / (1 + lift)).concat(H5);
  const barX = (i: number) => BX0 + i * (BW + BGAP) + BW / 2;
  const barH = (i: number, t: number) =>
    i < 4 ? barHs[i] * sp(prog(t, 3.15 + i * 0.12, 3.6 + i * 0.12), 0.6, 14) : barHs[4] * sp(prog(t, 4.7, 5.4), 0.42, 15);
  const barTop = (i: number, t: number): Pt => ({ x: barX(i), y: BASE - (i < 4 ? barH(i, t) : 0) - DR });

  const TX0 = 460, TX1 = 1460, TY = 780;
  const ringFrac = isPercent ? clamp(percent / 100, 0.04, 1) : 0.72;
  const RGX = CX, RGY = CY, RGR = 280;
  const ringAng = (k: number) => -Math.PI / 2 + 2 * Math.PI * ringFrac * k;
  const ringPt = (k: number): Pt => ({ x: RGX + RGR * Math.cos(ringAng(k)), y: RGY + RGR * Math.sin(ringAng(k)) });

  const STATS: Record<string, { land: Pt; end: Pt; dot: (t: number) => Dot }> = {
    spring: {
      land: G0,
      end: E,
      dot: (t) => { const tau = prog(t, 3.5, 5.5), s = squash(t, 3.5); return { x: G0.x + tau * GW, y: G0.y - gy(tau) * GH, r: DR, sx: 1 + s, sy: 1 - s }; },
    },
    bars: {
      land: barTop(0, 3.5),
      end: { x: barX(4), y: BASE - H5 - DR },
      dot: (t) => {
        if (t < 4.7) {
          const h = Math.min(3, Math.floor((t - 3.5) / 0.3)), e = prog(t, 3.5 + h * 0.3, 3.8 + h * 0.3);
          const A = barTop(h, t), B = barTop(h + 1, t), s = squash(t, 3.5 + h * 0.3);
          return { x: lerp(A.x, B.x, e), y: lerp(A.y, B.y, e) - 4 * 110 * e * (1 - e), r: DR, sx: 1 + s, sy: 1 - s };
        }
        const s = squash(t, 4.7);
        return { x: barX(4), y: BASE - barH(4, t) - DR, r: DR, sx: 1 + s, sy: 1 - s };
      },
    },
    counter: {
      land: { x: TX0, y: TY },
      end: { x: TX1, y: TY },
      dot: (t) => { const s = squash(t, 3.5); return { x: lerp(TX0, TX1, statSpring(t)), y: TY, r: DR, sx: 1 + s, sy: 1 - s }; },
    },
    ring: {
      land: ringPt(0),
      end: ringPt(1),
      dot: (t) => { const s = squash(t, 3.5); return { ...ringPt(statSpring(t)), r: DR, sx: 1 + s, sy: 1 - s }; },
    },
  };
  const statStyle = STATS[cfg.scenes.stat] ? cfg.scenes.stat : "spring";
  const statScene = STATS[statStyle];
  const SE = statScene.end;

  const cRest: Pt = { x: knobOn.x + 230, y: CY + 190 };
  const cClick: Pt = { x: track.cx, y: track.cy };
  const cOff: Pt = { x: Math.max(V.x1, cRest.x) + 80, y: Math.max(V.y1, cRest.y) + 80 };

  const wordStep = Math.min(0.25, 1.0 / words.length);
  // Letters of a word laid out horizontally around a centre x: glyph centres relative to it.
  const rowLetters = (s: string, size: number) => {
    const total = textW(s, size, 800);
    let x = -total / 2;
    return { total, letters: [...s].map((ch) => { const w = textW(ch, size, 800); const c = { ch, dx: x + w / 2 }; x += w; return c; }) };
  };

  // Orbit: one ring of text around the dot.
  const RR = 330;
  const ringText = words.join(" · ") + " · ";
  const FS = Math.min(80, (100 * 2 * Math.PI * RR * 0.97) / textW(ringText, 100, 800));
  const ringK = (2 * Math.PI) / textW(ringText, FS, 800);
  const ring: { ch: string; w: number; c: number; i: number; a: number; sep: boolean }[] = [];
  let cum = 0, ri = 0;
  words.forEach((w, wi) => {
    [...(w + " · ")].forEach((ch, ci) => {
      const cw = textW(ch, FS, 800);
      ring.push({ ch, w: wi, c: ci, i: ri++, a: -Math.PI / 2 + (cum + cw / 2) * ringK, sep: ci >= w.length });
      cum += cw;
    });
  });

  // Floating: words scattered on an ellipse around the dot, drifting.
  const floatWords = words.map((w, k) => {
    const size = Math.min(k % 2 ? 50 : 62, ((k % 2 ? 50 : 62) * 520) / textW(w, k % 2 ? 50 : 62, 800));
    const th = -Math.PI / 2 + 0.3 + (k * 2 * Math.PI) / words.length, s = k % 2 ? 0.82 : 1;
    return { size, x: CX + 480 * s * Math.cos(th), y: CY + 300 * s * Math.sin(th), ...rowLetters(w, size) };
  });
  const floatCount = floatWords.reduce((n, w) => n + w.letters.length, 0);

  // List: words stacked as bullet points; the dot hops down as the bullet.
  const listSize = Math.min(68, (68 * 760) / Math.max(...words.map((w) => textW(w, 68, 800))));
  const listGap = Math.min(96, 600 / Math.max(1, words.length - 1));
  const listW = Math.max(...words.map((w) => textW(w, listSize, 800)));
  const listX = CX - listW / 2 + 36; // text left edge; bullets sit to its left
  const listRows = words.map((w, k) => {
    const row = rowLetters(w, listSize), y = CY + (k - (words.length - 1) / 2) * listGap;
    return { y, letters: row.letters.map((l) => ({ ch: l.ch, dx: l.dx + row.total / 2 })), bullet: { x: listX - 56, y } };
  });

  // Tags: words as rounded chips in two rows, above and below the dot.
  const buildTags = (size: number) => {
    const pad = size * 0.68, gap = size * 0.52, topN = Math.ceil(words.length / 2);
    return [words.slice(0, topN), words.slice(topN)].map((row, ri) => {
      const ws = row.map((w) => textW(w, size, 800) + pad * 2);
      const total = ws.reduce((a, b) => a + b, 0) + gap * (row.length - 1);
      let x = CX - total / 2;
      const chips = row.map((w, j) => { const cx = x + ws[j] / 2; x += ws[j] + gap; return { cx, cy: CY + (ri === 0 ? -1 : 1) * size * 2.6, w: ws[j], h: size * 1.76, letters: rowLetters(w, size).letters }; });
      return { total, chips };
    });
  };
  const tagProbe = buildTags(50);
  const tagSize = 50 * Math.min(1, 1400 / Math.max(...tagProbe.map((r) => r.total)));
  const tags = buildTags(tagSize).flatMap((r) => r.chips);
  const tagAt = (k: number, t: number) => {
    const e = sp(prog(t, 9.0 + k * wordStep, 9.5 + k * wordStep), 0.6, 13), by = Math.sin(t * 2 + k * 1.3) * 8 * clamp(e);
    return { x: lerp(C.x, tags[k].cx, e), y: lerp(C.y, tags[k].cy, e) + by, e };
  };

  const shapeStyle = ["pill", "triangle", "star", "blob"].includes(cfg.scenes.shape) ? cfg.scenes.shape : "pill";
  const wordsStyle = ["orbit", "float", "list", "tags"].includes(cfg.scenes.words) ? cfg.scenes.words : "orbit";

  // List: the dot springs to each bullet as its word arrives, then back to centre for the halftone.
  function hopDot(pts: Pt[], t: number): Dot {
    const last = pts.length - 1;
    let from: Pt, to: Pt, t0: number;
    if (t >= 10.75) { from = pts[last]; to = C; t0 = 10.75; }
    else {
      const k = clamp(Math.floor((t - 9) / wordStep), 0, last);
      from = k ? pts[k - 1] : C; to = pts[k]; t0 = 9 + k * wordStep;
    }
    const hop = t >= 10.75 ? 0.3 : Math.min(0.3, wordStep);
    const p = sp(prog(t, t0, t0 + hop), 0.6, 15), s = squash(t, t0 + hop);
    return { x: lerp(from.x, to.x, p), y: lerp(from.y, to.y, p) - Math.sin(Math.PI * clamp(p)) * 40, r: Math.min(DR, listSize * 0.22), sx: 1 + s, sy: 1 - s };
  }

  const c1 = Math.min(170, (170 * 1500) / textW(cardText[0], 170, 800));
  const card = ([[cardText[0], c1, 800, 470], [cardText[1], 60, 500, 590], [cardText[2], 38, 500, 676]] as const).map(
    ([s, size, weight, base]) => ({ size, weight, letters: lineLayout(s, size, weight, (DW - textW(s, size, weight)) / 2, base) }),
  );
  const cardDot = dotSpec(card[0].letters, dotIndex(cardText[0]));
  const DR2 = cardDot.spec.r * c1 * 1.15;
  let n = 0;
  card.forEach((line) => line.letters.forEach((l) => (l.gi = n++)));

  // ------------------------------------------------------------ glyph helpers
  const glyphPivot = (xf: Xf, uu: number) => { const w = uu * xf.size; return { cx: xf.x + w / 2, cy: xf.y - 0.36 * xf.size, w }; };
  function drawGlyph(g: CanvasRenderingContext2D, ch: string, xf: Xf, uu: number, weight: number, color: string) {
    if (xf.a <= 0.003 || ch === " ") return;
    const P = glyphPivot(xf, uu);
    g.save(); g.globalAlpha *= clamp(xf.a); g.translate(P.cx, P.cy); g.rotate(xf.rot);
    g.font = f(weight, xf.size); g.fillStyle = color; g.fillText(ch, -P.w / 2, 0.36 * xf.size);
    g.restore();
  }
  function tittleAt(xf: Xf, uu: number, spec: Spec): Dot {
    const P = glyphPivot(xf, uu);
    const lx = spec.x * xf.size - P.w / 2, ly = -spec.y * xf.size + 0.36 * xf.size;
    const c = Math.cos(xf.rot), s = Math.sin(xf.rot);
    return { x: P.cx + lx * c - ly * s, y: P.cy + lx * s + ly * c, r: spec.r * xf.size, sx: 1, sy: 1 };
  }
  function circle(g: CanvasRenderingContext2D, x: number, y: number, r: number, color: string, a = 1) {
    if (r <= 0 || a <= 0) return;
    g.save(); g.globalAlpha *= clamp(a); g.fillStyle = color; g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill(); g.restore();
  }
  // The single shape primitive: dot, frame-filling circle, rounded square and pill are all states of this.
  function shapeState(g: CanvasRenderingContext2D, s: { x: number; y: number; w: number; h: number; rad: number; rot?: number }, color: string) {
    const w = Math.max(0, s.w), h = Math.max(0, s.h);
    if (w < 0.1 || h < 0.1) return;
    const r = Math.min(s.rad, w / 2, h / 2);
    g.save(); g.translate(s.x, s.y); g.rotate(s.rot || 0); g.fillStyle = color;
    g.beginPath();
    g.moveTo(-w / 2 + r, -h / 2);
    g.arcTo(w / 2, -h / 2, w / 2, h / 2, r); g.arcTo(w / 2, h / 2, -w / 2, h / 2, r);
    g.arcTo(-w / 2, h / 2, -w / 2, -h / 2, r); g.arcTo(-w / 2, -h / 2, w / 2, -h / 2, r);
    g.closePath(); g.fill(); g.restore();
  }
  function line(g: CanvasRenderingContext2D, x1: number, y1: number, x2: number, y2: number) {
    g.beginPath(); g.moveTo(x1, y1); g.lineTo(x2, y2); g.stroke();
  }
  function forGrid(step: number, fn: (x: number, y: number) => number, g: CanvasRenderingContext2D) {
    const gx0 = CX - Math.ceil((CX - V.x0) / step) * step, gy0 = CY - Math.ceil((CY - V.y0) / step) * step;
    g.beginPath();
    for (let x = gx0; x <= V.x1 + step; x += step) for (let y = gy0; y <= V.y1 + step; y += step) {
      const r = fn(x, y);
      if (r > 0.3) { g.moveTo(x + r, y); g.arc(x, y, r, 0, Math.PI * 2); }
    }
    g.fill();
  }

  // ------------------------------------------------------------ element timelines
  function labelXf(i: number, t: number): Xf {
    const c = labelL[i], k = i - h0;
    let x = c.x, y = c.y, size = LS, rot = 0;
    if (t >= 14.4) {
      const r = sp(prog(t, 14.45 + i * 0.017, 14.7 + i * 0.017), 0.6, 15);
      return { x, y: y + (1 - r) * 56, size, rot, a: clamp(r * 1.6) };
    }
    if (k < 0) {
      const j = exitOrder[i], q = ein(prog(t, 1.45 + j * 0.05, 1.85 + j * 0.05));
      return { x: x - 40 * q, y: y + 100 * q, size, rot: -0.9 * q, a: 1 - q };
    }
    const B = heroL[k], p = sp(prog(t, 1.7 + k * 0.03, 2.35 + k * 0.03), 0.6, 14);
    x = lerp(c.x, B.x, p); y = lerp(c.y, B.y, p); size = lerp(LS, HS, p);
    rot = Math.sin(Math.PI * clamp(p)) * 0.14 * (k % 2 ? 1 : -1);
    const q = ein(prog(t, 3.0 + k * 0.025, 3.4 + k * 0.025));
    return { x, y: y + 180 * q, size, rot: rot + 0.4 * q * (k % 2 ? 1 : -1), a: 1 - q };
  }
  const heroTittle = (t: number) => tittleAt(labelXf(labelDot, t), labelL[labelDot].u, heroDot.spec);

  const CARD_START = [12.35, 12.5, 12.62], CARD_STAG = [0.02, 0.01, 0.012];
  function cardXf(li: number, k: number, t: number): Xf {
    const l = card[li].letters[k];
    const a = sp(prog(t, CARD_START[li] + k * CARD_STAG[li], CARD_START[li] + k * CARD_STAG[li] + 0.4), 0.6, 14);
    const q = ein(prog(t, 13.5 + l.gi * 0.008, 13.85 + l.gi * 0.008));
    return { x: l.x, y: l.y + (1 - a) * 50 + 120 * q, size: card[li].size, rot: 0.3 * q * (l.gi % 2 ? 1 : -1), a: clamp(a * 1.6) * (1 - q) };
  }
  const cardTittle = (t: number) => tittleAt(cardXf(0, cardDot.k, t), card[0].letters[cardDot.k].u, cardDot.spec);

  // The accent dot: one continuous path through every scene.
  function dotAt(t: number): Dot {
    let x: number, y: number, r: number, sx = 1, sy = 1;
    if (t < 1.0) { x = knobOff.x; y = knobOff.y; r = KR; }
    else if (t < 1.6) {
      const p = sp(prog(t, 1.0, 1.6), 0.55, 15), v = Math.sin(Math.PI * prog(t, 1.0, 1.35));
      x = lerp(knobOff.x, knobOn.x, p); y = knobOn.y; r = KR; sx = 1 + 0.28 * v; sy = 1 - 0.18 * v;
    } else if (t < 2.3) {
      const T = heroTittle(t), e = eio(prog(t, 1.6, 2.3));
      x = lerp(knobOn.x, T.x, e); y = lerp(knobOn.y, T.y, e) - Math.sin(Math.PI * e) * 220; r = lerp(KR, DR, e);
    } else if (t < 3.0) {
      const T = heroTittle(t), s = squash(t, 2.3), a = eio(prog(t, 2.78, 3.0));
      r = DR; x = T.x; y = T.y + r * 0.3 * a; sx = (1 + s) * (1 + 0.2 * a); sy = (1 - s) * (1 - 0.3 * a);
    } else if (t < 6.45 && !showStat) {
      // stat off: hop straight from the hero's i to the centre
      const S = heroTittle(3.0), e = eio(prog(t, 3.0, 6.45)), v = Math.sin(Math.PI * e);
      x = lerp(S.x, C.x, e); y = lerp(S.y, C.y, e) - v * 220; r = DR; sx = 1 + 0.4 * v; sy = 1 - 0.2 * v;
    } else if (t < 3.5) {
      const S = heroTittle(3.0), L = statScene.land, e = prog(t, 3.0, 3.5), v = Math.sin(Math.PI * e);
      x = lerp(S.x, L.x, e); y = lerp(S.y, L.y, e) - 4 * 260 * e * (1 - e); r = DR; sy = 1 + 0.25 * v; sx = 1 - 0.15 * v;
    } else if (t < 5.5) {
      return statScene.dot(t);
    } else if (t < 6.0) {
      const a = eio(prog(t, 5.8, 6.0));
      x = SE.x; y = SE.y; r = DR; sx = 1 - 0.25 * a; sy = 1 + 0.15 * a;
    } else if (t < 6.45) {
      const e = eio(prog(t, 6.0, 6.45)), v = Math.sin(Math.PI * e);
      x = lerp(SE.x, C.x, e); y = lerp(SE.y, C.y, e); r = DR; sx = 1 + 0.8 * v; sy = 1 - 0.3 * v;
    } else if (t < 9.0) {
      x = C.x; y = C.y;
      r = t < 6.5 ? DR : t < 7.0 ? expLerp(DR, BIG, eio(prog(t, 6.5, 7.0))) : t < 8.5 ? BIG : expLerp(BIG, DR, eio(prog(t, 8.5, 9.0)));
    } else if (t >= 9.0 && t < 13.55 && ((!showCard && t >= (wordsStyle === "list" && showWords ? 11.05 : 10.75)) || (!showWords && t < 10.75))) {
      // switched-off words / end card: the dot simply waits at the centre
      x = C.x; y = C.y; r = DR;
    } else if (t < 11.05 && wordsStyle === "list" && showWords) {
      return hopDot(listRows.map((r) => r.bullet), t);
    } else if (t < 12.25) {
      let pulse = 0;
      for (let j = 0; j < words.length; j++) pulse += Math.sin(Math.PI * prog(t, 9 + j * wordStep, 9.2 + j * wordStep)) * 0.18;
      const s = squash(t, 9.0);
      x = C.x; y = C.y; r = DR * (1 + pulse); sx = 1 + s; sy = 1 - s;
    } else if (t < 12.75) {
      const T = cardTittle(t), e = eio(prog(t, 12.25, 12.75));
      x = lerp(C.x, T.x, e); y = lerp(C.y, T.y, e) - Math.sin(Math.PI * e) * 170; r = lerp(DR, DR2, e);
    } else if (t < 13.55) {
      const T = cardTittle(t), s = squash(t, 12.75), a = eio(prog(t, 13.35, 13.55));
      r = DR2; x = T.x; y = T.y + r * 0.3 * a; sx = (1 + s) * (1 + 0.2 * a); sy = (1 - s) * (1 - 0.3 * a);
    } else if (t < 13.95) {
      const S = showCard ? cardTittle(13.55) : C, e = prog(t, 13.55, 13.95);
      x = lerp(S.x, P1.x, e); y = lerp(S.y, P1.y, e) - 4 * 200 * e * (1 - e); r = lerp(showCard ? DR2 : DR, DR, e);
    } else if (t < 14.35) {
      const tau = prog(t, 13.95, 14.35), s = squash(t, 13.95);
      x = P1.x + tau * 640; y = P1.y - gy(tau) * 220; r = DR; sx = 1 + s; sy = 1 - s;
    } else if (t < 14.92) {
      const p = sp(prog(t, 14.35, 14.92), 0.6, 15);
      x = lerp(P2.x, knobOff.x, p); y = lerp(P2.y, knobOff.y, p) - Math.sin(Math.PI * clamp(p)) * 180; r = lerp(DR, KR, clamp(p));
    } else { x = knobOff.x; y = knobOff.y; r = KR; }
    return { x, y, r, sx, sy };
  }

  function cursorAt(t: number): (Pt & { s: number }) | null {
    if (t < 0.2) return { ...cRest, s: 1 };
    if (t < 0.85) {
      const e = eio(prog(t, 0.2, 0.85)), bow = Math.sin(Math.PI * e) * 40;
      return { x: lerp(cRest.x, cClick.x, e) - bow * 0.4, y: lerp(cRest.y, cClick.y, e) + bow, s: 1 };
    }
    if (t < 1.0) return { ...cClick, s: 1 - 0.12 * eout(prog(t, 0.85, 1.0)) };
    if (t < 1.3) return { ...cClick, s: lerp(0.88, 1, eout(prog(t, 1.0, 1.15))) };
    if (t < 1.9) { const e = ein(prog(t, 1.3, 1.9)); return { x: lerp(cClick.x, cOff.x, e), y: lerp(cClick.y, cOff.y, e), s: 1 }; }
    if (t < 14.35) return null;
    const e = eout(prog(t, 14.35, 14.95));
    return { x: lerp(cOff.x, cRest.x, e), y: lerp(cOff.y, cRest.y, e), s: 1 };
  }

  // ------------------------------------------------------------ scenes
  function drawTrack(g: CanvasRenderingContext2D, t: number) {
    let s: number, col = MUTE;
    if (t < 2.0) { col = mixHex(MUTE, INK, prog(t, 1.0, 1.18)); s = 1 - einBack(prog(t, 1.55, 1.95)); }
    else if (t >= 14.5) s = sp(prog(t, 14.5, 14.9), 0.6, 15);
    else return;
    shapeState(g, { x: track.cx, y: track.cy, w: track.w * s, h: track.h * s, rad: Infinity }, col);
  }

  function drawLabel(g: CanvasRenderingContext2D, t: number) {
    labelL.forEach((c, i) => {
      const xf = labelXf(i, t), isDot = i === labelDot && heroDot.real;
      drawGlyph(g, isDot ? c.dl : c.ch, xf, c.u, 800, INK);
      if (isDot) {
        const s = t < 3.7 ? 1 - prog(t, 2.22, 2.32) : 1; // ink tittle hands over to the accent dot
        if (s > 0) { const T = tittleAt(xf, c.u, heroDot.spec); circle(g, T.x, T.y, T.r * s, INK, xf.a); }
      }
    });
  }

  // Exit wipe for the chart styles: clips away from the left as the dot leaves.
  function wipeClip(g: CanvasRenderingContext2D, t: number, x0: number, span: number) {
    const er = eio(prog(t, 6.0, 6.4));
    if (er > 0) { const cx = x0 + er * span; g.beginPath(); g.rect(cx, V.y0, V.x1 - cx, V.y1 - V.y0); g.clip(); }
  }
  function drawCallout(g: CanvasRenderingContext2D, t: number, x: number, y: number) {
    const c = sp(prog(t, 5.0, 5.45), 0.5, 15) * (1 - einBack(prog(t, 6.0, 6.3)));
    if (c <= 0.001) return;
    const size = 130;
    g.save(); g.translate(x, y); g.scale(c, c);
    g.font = f(800, size); g.fillStyle = INK; g.fillText(stat, 0, 0.36 * size); g.restore();
  }

  function drawStat(g: CanvasRenderingContext2D, t: number) {
    if (statStyle === "bars") drawBars(g, t);
    else if (statStyle === "counter") drawCounter(g, t);
    else if (statStyle === "ring") drawProgressRing(g, t);
    else drawSpring(g, t);
    // The line the dot shoots across.
    const lp = eio(prog(t, 5.8, 6.05)), tail = eio(prog(t, 6.0, 6.45));
    if (lp > tail) {
      g.save(); g.strokeStyle = INK; g.lineWidth = 3; g.lineCap = "round";
      line(g, lerp(SE.x, C.x, tail), lerp(SE.y, C.y, tail), lerp(SE.x, C.x, lp), lerp(SE.y, C.y, lp)); g.restore();
    }
  }

  function drawBars(g: CanvasRenderingContext2D, t: number) {
    const a = eout(prog(t, 3.0, 3.45)), right = barX(4) + BW / 2 + 40;
    g.save();
    wipeClip(g, t, BX0 - 60, right - BX0 + 200);
    g.lineCap = "round"; g.strokeStyle = INK; g.lineWidth = 5;
    line(g, BX0 - 40, BASE, lerp(BX0 - 40, right, a), BASE);
    for (let i = 0; i < 5; i++) {
      const h = barH(i, t);
      if (h > 0.5) shapeState(g, { x: barX(i), y: BASE - h / 2 - 3, w: BW, h, rad: 12 }, i < 4 ? mixHex(PAPER, INK, 0.22) : INK);
    }
    g.restore();
    drawCallout(g, t, barX(4) + BW / 2 + 50, BASE - H5 + 40);
  }

  function drawCounter(g: CanvasRenderingContext2D, t: number) {
    const a = eout(prog(t, 3.0, 3.45)), k = statSpring(t), q = eio(prog(t, 6.0, 6.35));
    g.save();
    wipeClip(g, t, TX0 - 60, TX1 - TX0 + 200);
    g.lineCap = "round"; g.lineWidth = 8;
    g.strokeStyle = mixHex(PAPER, INK, 0.18); line(g, TX0, TY, lerp(TX0, TX1, a), TY);
    if (t >= 3.5) { g.strokeStyle = INK; line(g, TX0, TY, lerp(TX0, TX1, k), TY); }
    g.font = f(500, 26); g.fillStyle = INK; g.globalAlpha = 0.5 * a;
    g.textAlign = "left"; g.fillText("0", TX0 - 8, TY + 52);
    g.textAlign = "right"; g.fillText(fmtStat(1), TX1 + 8, TY + 52);
    g.restore();

    const pop = sp(prog(t, 3.35, 3.75), 0.55, 14);
    if (pop <= 0.001 || q >= 1) return;
    const size = Math.min(300, (300 * 1300) / textW(fmtStat(1), 300, 800));
    g.save(); g.globalAlpha = 1 - q; g.translate(CX, TY - 110 + 60 * q); g.scale(pop, pop);
    g.font = f(800, size); g.fillStyle = INK; g.textAlign = "center"; g.fillText(fmtStat(k), 0, 0); g.restore();
  }

  function drawProgressRing(g: CanvasRenderingContext2D, t: number) {
    const a = eout(prog(t, 3.0, 3.5)), k = statSpring(t), q = eio(prog(t, 6.0, 6.35));
    if (q >= 1) return;
    g.save(); g.globalAlpha = 1 - q;
    g.translate(RGX, RGY); g.scale(1 - 0.3 * q, 1 - 0.3 * q); g.translate(-RGX, -RGY);
    g.lineCap = "round"; g.lineWidth = 22;
    g.strokeStyle = mixHex(PAPER, INK, 0.14);
    g.beginPath(); g.arc(RGX, RGY, RGR, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * a); g.stroke();
    if (t >= 3.5 && k > 0.001) { g.strokeStyle = INK; g.beginPath(); g.arc(RGX, RGY, RGR, -Math.PI / 2, ringAng(k)); g.stroke(); }
    const pop = sp(prog(t, 3.35, 3.75), 0.55, 14);
    if (pop > 0.001) {
      const size = Math.min(150, (150 * 400) / textW(fmtStat(1), 150, 800));
      g.translate(RGX, RGY); g.scale(pop, pop);
      g.font = f(800, size); g.fillStyle = INK; g.textAlign = "center"; g.fillText(fmtStat(k), 0, 0.36 * size);
    }
    g.restore();
  }

  function drawSpring(g: CanvasRenderingContext2D, t: number) {
    const a = eout(prog(t, 3.0, 3.45));
    g.save();
    wipeClip(g, t, G0.x - 60, GW + 200);
    g.lineCap = "round"; g.strokeStyle = INK; g.lineWidth = 5;
    line(g, G0.x, G0.y, G0.x, G0.y - GH * 1.5 * a);
    line(g, G0.x, G0.y, G0.x + (GW + 40) * a, G0.y);
    const tp = eio(prog(t, 3.25, 3.7));
    if (tp > 0) { g.save(); g.setLineDash([14, 14]); g.globalAlpha = 0.4; g.lineWidth = 3; line(g, G0.x, G0.y - GH, G0.x + (GW + 40) * tp, G0.y - GH); g.restore(); }
    g.save(); g.globalAlpha = a; g.font = f(500, 26); g.fillStyle = INK; g.textAlign = "right";
    g.fillText("1.0", G0.x - 22, G0.y - GH + 9); g.fillText("0", G0.x - 22, G0.y + 9); g.restore();

    // Curve: drawn from the exact function that moves the dot.
    const tau = prog(t, 3.5, 5.5);
    if (tau > 0) {
      g.lineWidth = 6; g.lineJoin = "round"; g.beginPath();
      const N = Math.ceil(260 * tau) + 1;
      for (let i = 0; i <= N; i++) { const x = (tau * i) / N, px = G0.x + x * GW, py = G0.y - gy(x) * GH; if (i) g.lineTo(px, py); else g.moveTo(px, py); }
      g.stroke();
    }
    if (t >= 4.0) {
      const pk = { x: G0.x + 0.25 * GW, y: G0.y - (1 + OS) * GH }, p = prog(t, 4.0, 4.4);
      g.save(); g.setLineDash([6, 10]); g.globalAlpha = 0.3; g.lineWidth = 3;
      line(g, pk.x, pk.y, lerp(pk.x, G0.x, eout(prog(t, 4.0, 4.3))), pk.y); g.restore();
      if (p < 1) { g.save(); g.globalAlpha = 1 - p; g.lineWidth = 3; g.beginPath(); g.arc(pk.x, pk.y, 20 + 60 * eout(p), 0, Math.PI * 2); g.stroke(); g.restore(); }
    }
    g.restore();
    drawCallout(g, t, E.x + 70, E.y);
  }

  // Polar outlines for the shape scene: radius as a function of angle, so any two can be blended.
  const TAU = Math.PI * 2;
  const polygon = (n: number) => (th: number) => { const s = TAU / n, ph = ((th % s) + s) % s; return Math.cos(Math.PI / n) / Math.cos(ph - Math.PI / n); };
  const starOf = (n: number, inner: number) => (th: number) => { const s = TAU / n, ph = (((th % s) + s) % s) / s; return 1 - (1 - inner) * (1 - Math.abs(2 * ph - 1)); };
  const soften = (fn: (th: number) => number, k: number) => (th: number) => lerp(fn(th), 1, k);
  const triA = soften(polygon(3), 0.1), starA = soften(starOf(5, 0.5), 0.05), starB = starOf(5, 0.22);

  function polarShape(g: CanvasRenderingContext2D, R: number, rot: number, fn: (th: number) => number) {
    if (R < 0.1) return;
    g.save(); g.translate(C.x, C.y); g.rotate(rot); g.fillStyle = INK; g.beginPath();
    for (let i = 0; i <= 180; i++) {
      const th = (i / 180) * TAU, r = R * fn(th);
      if (i) g.lineTo(r * Math.cos(th), r * Math.sin(th)); else g.moveTo(r, 0);
    }
    g.closePath(); g.fill(); g.restore();
  }

  // Inner shape: grows out of the centre as a circle, becomes shape A, then morphs to shape B.
  function drawInner(g: CanvasRenderingContext2D, t: number) {
    if (t < 7.0 || t >= 9.0) return;
    const s1 = sp(prog(t, 7.0, 7.45), 0.55, 14);
    const k1 = eio(prog(t, 7.05, 7.5)); // circle -> shape A
    const st = sp(prog(t, 7.75, 8.25), 0.55, 14); // shape A -> shape B
    const spin = sp(prog(t, 7.0, 8.1), 0.5, 14);
    const k = t >= 8.5 ? (dotAt(t).r - DR) / (BIG - DR) : 1; // contracts with the accent field
    const R = 140 * s1 * k;
    const blend = (a: (th: number) => number, b: (th: number) => number) => (th: number) => lerp(1, lerp(a(th), b(th), st), k1);

    if (shapeStyle === "triangle") {
      polarShape(g, R, -Math.PI / 2 + (TAU / 3) * spin, blend((th) => triA(th) * 1.45, () => 1.25));
    } else if (shapeStyle === "star") {
      polarShape(g, R, -Math.PI / 2 + (TAU / 5) * spin, blend((th) => starA(th) * 1.3, (th) => starB(th) * 1.8));
    } else if (shapeStyle === "blob") {
      const wob = (a3: number, a5: number) => (th: number) => 1 + a3 * Math.sin(3 * th + t * 5) + a5 * Math.sin(5 * th - t * 4);
      polarShape(g, R, t * 0.6, blend(wob(0.12, 0.06), (th) => 1.25 * wob(0.05, 0.14)(th)));
    } else {
      const cf = lerp(0.5, 0.2, k1); // circle -> rounded square -> pill
      const w = lerp(280, 700, st) * s1 * k, h = lerp(280, 220, st) * s1 * k;
      shapeState(g, { x: C.x, y: C.y, w, h, rad: Math.min(w, h) * lerp(cf, 0.5, clamp(st)), rot: Math.PI * spin }, INK);
    }
  }

  // Word glyphs before the open-out: centre position, rotation, size, alpha, and open-out delay.
  interface Glyph { ch: string; x: number; y: number; rot: number; size: number; a: number; d: number }

  function wordGlyphs(t: number): Glyph[] {
    const out: Glyph[] = [];
    if (wordsStyle === "orbit") {
      const rotA = -0.32 * (t - 9) - 1.4 * ein(prog(t, 10.75, 11.5));
      for (const ch of ring) {
        const t0 = 9.0 + ch.w * wordStep + ch.c * 0.012, e = sp(prog(t, t0, t0 + 0.45), 0.6, 14);
        if (e <= 0) continue;
        const ang = ch.a + rotA;
        out.push({ ch: ch.ch, x: C.x + RR * e * Math.cos(ang), y: C.y + RR * e * Math.sin(ang), rot: ang + Math.PI / 2,
          size: FS * lerp(0.5, 1, clamp(e)), a: clamp(e * 2) * (ch.sep ? 0.45 : 1), d: Math.min(0.18, ch.i * 0.004) });
      }
    } else if (wordsStyle === "float") {
      let gi = 0;
      floatWords.forEach((w, k) => {
        const bx = Math.cos(t * 1.5 + k * 2.1) * 10, by = Math.sin(t * 2.2 + k * 1.7) * 14, rot = Math.sin(t * 1.3 + k) * 0.06;
        w.letters.forEach((l, j) => {
          const t0 = 9.0 + k * wordStep + j * 0.012, e = sp(prog(t, t0, t0 + 0.5), 0.6, 13);
          const d = (gi++ / floatCount) * 0.18;
          if (e <= 0) return;
          out.push({ ch: l.ch, x: C.x + (w.x + l.dx * Math.cos(rot) - C.x) * e + bx * clamp(e), y: C.y + (w.y + l.dx * Math.sin(rot) - C.y) * e + by * clamp(e),
            rot, size: w.size * lerp(0.4, 1, clamp(e)), a: clamp(e * 2), d });
        });
      });
    } else if (wordsStyle === "list") {
      listRows.forEach((row, k) => {
        const t0 = 9.0 + k * wordStep;
        row.letters.forEach((l, j) => {
          const e = sp(prog(t, t0 + 0.05 + j * 0.01, t0 + 0.5 + j * 0.01), 0.6, 14);
          if (e <= 0) return;
          out.push({ ch: l.ch, x: lerp(row.bullet.x, listX + l.dx, e), y: row.y, rot: 0, size: listSize * lerp(0.6, 1, clamp(e)), a: clamp(e * 2), d: (k / words.length) * 0.15 });
        });
      });
    } else {
      tags.forEach((tag, k) => {
        const p = tagAt(k, t);
        if (p.e <= 0) return;
        tag.letters.forEach((l) => out.push({ ch: l.ch, x: p.x + l.dx * p.e, y: p.y, rot: 0, size: tagSize * clamp(p.e, 0, 1.2), a: clamp(p.e * 2), d: (k / words.length) * 0.15 }));
      });
    }
    return out;
  }

  // Every word style hands over to the halftone the same way: letters fly outward and shrink into dots.
  function drawWords(g: CanvasRenderingContext2D, t: number) {
    if (t < 9.0 || t > 11.7) return;
    const fade = 1 - eio(prog(t, 10.75, 11.05));
    if (wordsStyle === "list" && fade > 0) {
      // bullets the dot has already visited stay behind as small marks
      listRows.forEach((row, k) => { if (t >= 9.0 + (k + 1) * wordStep) circle(g, row.bullet.x, row.bullet.y, 7 * fade, PAPER, fade); });
    }
    if (wordsStyle === "tags" && fade > 0) {
      g.save(); g.strokeStyle = PAPER; g.lineWidth = 3;
      tags.forEach((tag, k) => {
        const p = tagAt(k, t), s = clamp(p.e, 0, 1.2);
        if (s <= 0.01) return;
        g.globalAlpha = clamp(p.e * 2) * fade * 0.7;
        g.beginPath(); g.roundRect(p.x - (tag.w * s) / 2, p.y - (tag.h * s) / 2, tag.w * s, tag.h * s, (tag.h * s) / 2); g.stroke();
      });
      g.restore();
    }
    g.save(); g.textAlign = "center";
    for (const gl of wordGlyphs(t)) {
      const o = ein(prog(t, 10.75 + gl.d, 11.35 + gl.d));
      let dx = gl.x - C.x, dy = gl.y - C.y;
      const len = Math.hypot(dx, dy);
      if (len < 1) { dx = Math.cos(gl.d * 50); dy = Math.sin(gl.d * 50); } else { dx /= len; dy /= len; }
      const px = gl.x + dx * 760 * o, py = gl.y + dy * 760 * o;
      if (o > 0 && o < 1) circle(g, px, py, 4.5, PAPER, Math.sin(Math.PI * o));
      const a = gl.a * (1 - o);
      if (gl.ch === " " || a <= 0.003) continue;
      const size = gl.size * (1 - o * 0.85);
      g.save(); g.globalAlpha = a; g.translate(px, py); g.rotate(gl.rot);
      g.font = f(800, size); g.fillStyle = PAPER; g.fillText(gl.ch, 0, 0.36 * size); g.restore();
    }
    g.restore();
  }

  function drawHalftone(g: CanvasRenderingContext2D, t: number) {
    const step = 30;
    if (t >= 10.85 && t < 12.0) {
      const Rw = lerp(140, halfDiag + 420, eio(prog(t, 10.85, 12.0)));
      const mr = lerp(3.5, step * 0.76, ein(prog(t, 11.3, 12.0)));
      const rip = 0.15 * (1 - prog(t, 11.4, 11.9)), hole = 1 - prog(t, 11.6, 12.0);
      const D = dotAt(t);
      g.fillStyle = PAPER;
      forGrid(step, (x, y) => {
        const d = Math.hypot(x - CX, y - CY);
        const r = mr * clamp((Rw - d) / 420) * smooth(D.r + 8 * hole, D.r + 110 * hole + 1, Math.hypot(x - D.x, y - D.y));
        return r * (1 - rip + rip * Math.cos(d / 38 - t * 14));
      }, g);
    } else if (t >= 12.0 && t < 12.6) {
      // flip to the ink side from the centre
      g.fillStyle = PAPER; g.fillRect(V.x0, V.y0, V.x1 - V.x0, V.y1 - V.y0);
      const Rw = lerp(0, halfDiag + 300, eio(prog(t, 12.0, 12.55)));
      g.fillStyle = INK;
      forGrid(step, (x, y) => step * 0.76 * clamp((Rw - Math.hypot(x - CX, y - CY)) / 300), g);
    }
  }

  function drawCard(g: CanvasRenderingContext2D, t: number) {
    if (t < 12.3 || t > 14.3) return;
    card.forEach((ln, li) => {
      const alpha = [1, 0.9, 0.55][li];
      ln.letters.forEach((l, k) => {
        const xf = cardXf(li, k, t);
        xf.a *= alpha;
        const isDot = li === 0 && k === cardDot.k && cardDot.real;
        drawGlyph(g, isDot ? l.dl : l.ch, xf, l.u, ln.weight, PAPER);
        if (isDot) {
          const s = 1 - prog(t, 12.66, 12.76);
          if (s > 0) { const T = tittleAt(xf, l.u, cardDot.spec); circle(g, T.x, T.y, T.r * s, PAPER, xf.a); }
        }
      });
    });
  }

  function drawEcho(g: CanvasRenderingContext2D, t: number) {
    if (t >= 13.55 && t < 13.95) {
      // halftone echo around the moving dot
      const env = Math.sin(Math.PI * prog(t, 13.55, 13.95)), D = dotAt(t);
      g.fillStyle = PAPER;
      forGrid(30, (x, y) => 8 * env * clamp(1 - Math.hypot(x - D.x, y - D.y) / 320), g);
    }
    if (t >= 13.95 && t < 14.45) {
      // graph echo, same spring
      const tau = prog(t, 13.95, 14.35), fade = 1 - prog(t, 14.3, 14.45), t0 = Math.max(0, tau - 0.45);
      if (tau <= t0) return;
      g.save(); g.globalAlpha = fade; g.strokeStyle = PAPER; g.lineWidth = 5; g.lineCap = "round"; g.beginPath();
      for (let i = 0; i <= 80; i++) { const x = lerp(t0, tau, i / 80), px = P1.x + x * 640, py = P1.y - gy(x) * 220; if (i) g.lineTo(px, py); else g.moveTo(px, py); }
      g.stroke(); g.restore();
    }
  }

  function drawWipe(g: CanvasRenderingContext2D, t: number) {
    if (t < 14.3 || t >= 14.65) return;
    const D = dotAt(t);
    circle(g, D.x, D.y, (cornerDist(D) + 20) * ein(prog(t, 14.3, 14.65)), PAPER);
  }

  function drawCursor(g: CanvasRenderingContext2D, t: number) {
    const p = prog(t, 1.0, 1.4);
    if (p > 0 && p < 1) {
      g.save(); g.globalAlpha = 0.45 * (1 - p); g.strokeStyle = INK; g.lineWidth = 3;
      g.beginPath(); g.arc(cClick.x, cClick.y, 50 + 50 * eout(p), 0, Math.PI * 2); g.stroke(); g.restore();
    }
    const c = cursorAt(t);
    if (!c) return;
    g.save(); g.translate(c.x, c.y); g.scale(1.7 * c.s, 1.7 * c.s);
    g.beginPath(); g.moveTo(0, 0); g.lineTo(0, 34); g.lineTo(8, 26); g.lineTo(13.5, 38); g.lineTo(19, 35.5); g.lineTo(13.5, 24); g.lineTo(24, 24); g.closePath();
    g.lineJoin = "round"; g.lineWidth = 2.5; g.strokeStyle = PAPER; g.stroke(); g.fillStyle = INK; g.fill();
    g.restore();
  }

  // Pure function of t: no state carried between frames.
  function draw(g: CanvasRenderingContext2D, t: number) {
    g.textAlign = "left"; g.textBaseline = "alphabetic";
    g.fillStyle = t >= 7.0 && t < 14.65 ? INK : PAPER;
    g.fillRect(V.x0, V.y0, V.x1 - V.x0, V.y1 - V.y0);
    if (showCard) drawHalftone(g, t);
    drawEcho(g, t);
    drawWipe(g, t);
    drawTrack(g, t);
    if (t < 3.7 || t >= 14.4) drawLabel(g, t);
    if (showStat && t >= 3.0 && t < 6.5) drawStat(g, t);
    if (showWords) drawWords(g, t);
    if (showCard) drawCard(g, t);
    const D = dotAt(t);
    shapeState(g, { x: D.x, y: D.y, w: 2 * D.r * D.sx, h: 2 * D.r * D.sy, rad: Infinity }, ACCENT);
    if (showShape) drawInner(g, t);
    drawCursor(g, t);
  }

  return {
    width, height, duration: cfg.duration,
    seek(g, seconds) {
      const t = tl.toInternal(seconds);
      g.save();
      g.setTransform(u, 0, 0, u, ox, oy);
      draw(g, t);
      g.restore();
    },
  };
}

/** Wait for the chosen font so glyph metrics and tittle detection are right. */
export async function loadFont(font: string) {
  try {
    await Promise.all([document.fonts.load(`800 100px "${font}"`), document.fonts.load(`500 100px "${font}"`)]);
  } catch {
    // fall back to system fonts
  }
}
