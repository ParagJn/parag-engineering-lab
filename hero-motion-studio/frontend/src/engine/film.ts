import { clamp, ein, einBack, eio, eout, expLerp, lerp, mixHex, prog, smooth, sp, springStep, squash } from "./math";
import type { MotionConfig, MotionFeel } from "./types";

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
 * Scene segments on the internal timeline. `pace` > 1 plays a stretch slower than the base timeline.
 * Holds (`hold`) are the stretches where text sits still on screen; with readable holds on they are
 * stretched to the reading time of that text. A switched-off scene collapses to its scene's `skip`
 * units (shared across its stretches), where the dot makes a short bridging move.
 * The toggle/hero opening and the return trip are always on so the loop closes.
 */
export type SceneId = "stat" | "shape" | "words" | "card";
type HoldId = "hero" | "stat" | "words" | "card" | "problem" | "badge";
const SEGMENTS: { scene?: SceneId; a: number; b: number; pace: number; hold?: HoldId; outro?: true }[] = [
  { a: 0, b: 2.4, pace: 1 },
  { a: 2.4, b: 3.0, pace: 1, hold: "hero" },
  { scene: "stat", a: 3.0, b: 5.45, pace: 1.25 },
  { scene: "stat", a: 5.45, b: 5.95, pace: 1.25, hold: "stat" },
  { scene: "stat", a: 5.95, b: 6.5, pace: 1.25 },
  { scene: "shape", a: 6.5, b: 9.0, pace: 1 },
  { scene: "words", a: 9.0, b: 10.75, pace: 1.35, hold: "words" },
  { scene: "card", a: 10.75, b: 12.7, pace: 1 },
  { scene: "card", a: 12.7, b: 13.5, pace: 1, hold: "card" },
  { scene: "card", a: 13.5, b: 13.55, pace: 1 },
  { a: 13.55, b: 14.3, pace: 1 },
  // Toggle-row ending at base pace; the logo outro is stretched so the sweep runs ~1.2s and then holds.
  { a: 14.3, b: TIMELINE, pace: 1, outro: true },
];
/**
 * Story mode replays the same scenes in story order (Hook → Problem → Reveal → Proof → Close).
 * The Problem scene and the paper-wipe bridge into the proof live past the showcase timeline (15+),
 * so every scene keeps its own internal times and the dot path stays continuous.
 */
export const PROBLEM_T0 = 15, PROBLEM_T1 = 17.5, BRIDGE_T1 = 17.75;
const STORY_SEGMENTS: typeof SEGMENTS = [
  { a: 0, b: 2.4, pace: 1 },
  { a: 2.4, b: 3.0, pace: 1, hold: "hero" },
  { a: 15.0, b: 16.3, pace: 1 },
  { a: 16.3, b: 16.9, pace: 1, hold: "problem" },
  { a: 16.9, b: 17.5, pace: 1 },
  { scene: "shape", a: 6.5, b: 8.2, pace: 1 },
  { scene: "shape", a: 8.2, b: 8.5, pace: 1, hold: "badge" },
  { scene: "shape", a: 8.5, b: 9.0, pace: 1 },
  { a: 17.5, b: 17.75, pace: 1 },
  { scene: "stat", a: 3.0, b: 5.45, pace: 1.25 },
  { scene: "stat", a: 5.45, b: 5.95, pace: 1.25, hold: "stat" },
  { scene: "stat", a: 5.95, b: 6.5, pace: 1.25 },
  { scene: "card", a: 10.75, b: 12.7, pace: 1 },
  { scene: "card", a: 12.7, b: 13.5, pace: 1, hold: "card" },
  { scene: "card", a: 13.5, b: 13.55, pace: 1 },
  { a: 13.55, b: 14.3, pace: 1 },
  { a: 14.3, b: TIMELINE, pace: 1, outro: true },
];
export const isStory = (cfg: MotionConfig) => cfg.film === "story";

const SCENE_SPAN: Record<SceneId, [number, number, number]> = { stat: [3.0, 6.5, 0.8], shape: [6.5, 9.0, 0.9], words: [9.0, 10.75, 0.25], card: [10.75, 13.55, 0.6] };
const LOGO_OUTRO_PACE = 3.2;

/**
 * Motion feel: spring damping per element class (higher = less overshoot), how much the dot
 * squashes on landings, and how much longer text holds.
 */
export const FEELS: Record<MotionFeel, { ui: number; text: number; shape: number; data: number; dot: number; squash: number; hold: number }> = {
  precise: { ui: 0.9, text: 0.88, shape: 0.78, data: 0.75, dot: 0.82, squash: 0.35, hold: 1 },
  lively: { ui: 0.55, text: 0.6, shape: 0.55, data: 0.42, dot: 0.6, squash: 1, hold: 1 },
  bold: { ui: 0.62, text: 0.8, shape: 0.4, data: 0.38, dot: 0.5, squash: 1.4, hold: 1.3 },
};
export const feelOf = (cfg: MotionConfig) => FEELS[cfg.motion?.feel ?? "lively"] ?? FEELS.lively;

const countWords = (s: string) => s.trim().split(/\s+/).filter(Boolean).length;

/** How much a hold stretches so its text can be read (≈ reading time / designed hold time). */
function holdPace(cfg: MotionConfig, id: HoldId, base: number) {
  if (cfg.motion?.readable === false) return base;
  const mul = feelOf(cfg).hold, len = { hero: 0.6, stat: 0.5, words: 1.75, card: 0.8, problem: 0.6, badge: 0.3 }[id];
  const words = cfg.text.words.filter((w) => w.trim()).length;
  const cardWords = countWords([cfg.text.cardTitle || cfg.text.hero, cfg.text.cardSubtitle, cfg.text.cardFootnote].join(" "));
  const st = cfg.story ?? { problem: "", lead: "", solution: "", proofLabel: "" };
  const need = {
    hero: 0.35 + 0.25 * countWords(cfg.text.hero), stat: 0.9 + (isStory(cfg) ? 0.25 * countWords(st.proofLabel) : 0),
    words: 0.8 + 0.4 * words, card: 0.5 + 0.3 * cardWords,
    problem: 0.5 + 0.3 * countWords(st.problem), badge: 0.5 + 0.3 * countWords(`${st.lead} ${st.solution}`),
  }[id];
  return Math.min(4, Math.max(base, need / len)) * mul;
}

export function sceneOn(cfg: MotionConfig, id: SceneId) {
  return cfg.scenes.show?.[id] !== false;
}

/** Maps real seconds onto the internal timeline (and back), honouring pace, reading holds and switched-off scenes. */
export function timeline(cfg: MotionConfig) {
  const logoOutro = cfg.outro?.mode === "logo" && !!cfg.outro.logo;
  const segs = (isStory(cfg) ? STORY_SEGMENTS : SEGMENTS).map((s) => {
    if (s.scene && !sceneOn(cfg, s.scene)) {
      const [a, b, skip] = SCENE_SPAN[s.scene];
      return { ...s, len: (skip * (s.b - s.a)) / (b - a) };
    }
    const pace = s.outro ? (logoOutro ? LOGO_OUTRO_PACE : 1) : s.hold ? holdPace(cfg, s.hold, s.pace) : s.pace;
    return { ...s, len: (s.b - s.a) * pace };
  });
  const natural = segs.reduce((n, s) => n + s.len, 0);
  const duration = cfg.autoDuration ? natural : cfg.duration;
  return {
    /** Loop length in seconds at the designed pace. */
    natural,
    /** Loop length actually used: the designed pace when Auto is on. */
    duration,
    toInternal(seconds: number) {
      let tau = ((((seconds / duration) % 1) + 1) % 1) * natural;
      for (const s of segs) {
        if (tau <= s.len) return s.len > 0 ? s.a + ((s.b - s.a) * tau) / s.len : s.b;
        tau -= s.len;
      }
      return TIMELINE;
    },
    toSeconds(t: number) {
      let acc = 0;
      for (const s of segs) {
        // segments play in list order (story mode reorders them), so find the one containing t
        if (t >= s.a && t <= s.b) return ((acc + (clamp((t - s.a) / (s.b - s.a)) * s.len)) / natural) * duration;
        acc += s.len;
      }
      return duration;
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
  const story = isStory(cfg);
  const showStat = sceneOn(cfg, "stat"), showShape = sceneOn(cfg, "shape"), showWords = !story && sceneOn(cfg, "words"), showCard = sceneOn(cfg, "card");
  const storyText = cfg.story ?? { problem: "", lead: "", solution: "", proofLabel: "" };
  const tl = timeline(cfg);
  const FEEL = feelOf(cfg);
  const springOf = (z: number) => (p: number) => sp(p, Math.min(0.95, z), z < 0.5 ? 16 : 15);
  const spUI = springOf(FEEL.ui), spText = springOf(FEEL.text), spShape = springOf(FEEL.shape), spData = springOf(FEEL.data), spDot = springOf(FEEL.dot);
  const sq = (t: number, t0: number) => squash(t, t0, 0.3, 0.32 * FEEL.squash);
  const PAPER = style.paper, INK = style.ink, ACCENT = style.accent, MUTE = mixHex(PAPER, INK, 0.12);
  const FONT = `"${style.font}", "Helvetica Neue", Arial, sans-serif`;
  const f = (w: number, s: number) => `${w} ${s}px ${FONT}`;

  const hero = cfg.text.hero.trim() || "Hello";
  const intro = cfg.text.intro.trim();
  const label = intro ? `${intro} ${hero}` : hero;
  // The film ends on the toggle row again. A custom ending replaces the intro word there;
  // left blank, the last frame matches the first so the loop is seamless.
  const ending = (cfg.text.ending ?? "").trim();
  const endLabel = ending ? `${ending} ${hero}` : label;
  const words = cfg.text.words.map((w) => w.trim()).filter(Boolean);
  if (!words.length) words.push("MOTION");
  const stat = cfg.text.stat.trim() || "+22%";
  // "+22%" -> prefix "+", 22, suffix "%": counters animate the number and keep the rest.
  const sm = stat.match(/^(.*?)(\d+(?:\.\d+)?)(.*)$/);
  const statNum = sm ? { prefix: sm[1], num: parseFloat(sm[2]), dec: (sm[2].split(".")[1] || "").length, suffix: sm[3] } : null;
  const fmtStat = (k: number) => {
    if (!statNum) return stat;
    const v = (statNum.num * Math.max(0, k)).toFixed(statNum.dec);
    const prefix = Number(v) === 0 ? statNum.prefix.replace(/[-\u2212\u2013\u2193+\u2191]/g, "") : statNum.prefix;
    return prefix + v + statNum.suffix;
  };
  // A negative stat (e.g. a saving: "-40%", "−12%", "↓8%") is shown as a drop below the baseline in every style.
  const negative = /[-\u2212\u2013\u2193]/.test(statNum ? statNum.prefix : stat);
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
  // Small text never renders below ~13 real pixels, so tiles and small GIFs stay readable.
  const legible = (size: number) => Math.max(size, 13 / u);
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

  const UP = negative ? 1 : -1; // screen direction of "more of the stat"
  const GW = 980, GH = Math.min(400, 560 / (1 + OS));
  const G0: Pt = { x: 340, y: negative ? 340 : 800 };
  const gY = (x: number) => G0.y + UP * gy(x) * GH;
  const E: Pt = { x: G0.x + GW, y: gY(1) };
  const P1: Pt = { x: 520, y: 800 }, P2: Pt = { x: P1.x + 640, y: P1.y - 220 * gy(1) };
  const BIG = halfDiag + 150; // clears all four corners of any output aspect

  // ------------------------------------------------------------ stat scene variants
  // Each variant says where the dot lands (3.5), how it moves until 5.5, and where it rests before shooting to centre.
  // Counter and ring read the number and the dot from the same spring.
  const statSpring = (t: number) => { const tau = prog(t, 3.5, 5.5); return tau <= 0 ? 0 : tau >= 1 ? 1 : springStep(tau, 0.45, 14); };

  const BW = 120, BGAP = 70, BX0 = 360, BASE = 800, H5 = 440;
  const lift = clamp(percent / 100, 0.05, 1.5);
  const BREF = 400, cut = clamp(percent / 100, 0.05, 0.9);
  const barHs = negative
    ? [0.7, 0.95, 0.85, 1].map((k) => k * BREF).concat(BREF * (1 - cut))
    : [0.55, 0.78, 0.66, 1].map((k) => (k * H5) / (1 + lift)).concat(H5);
  const heroBarH = (t: number) =>
    negative
      ? t < 5.0 ? BREF * spData(prog(t, 4.7, 5.0)) : lerp(BREF, barHs[4], spData(prog(t, 5.0, 5.5)))
      : H5 * spData(prog(t, 4.7, 5.4));
  const barX = (i: number) => BX0 + i * (BW + BGAP) + BW / 2;
  const barH = (i: number, t: number) =>
    i < 4 ? barHs[i] * spData(prog(t, 3.15 + i * 0.12, 3.6 + i * 0.12)) : heroBarH(t);
  const barTop = (i: number, t: number): Pt => ({ x: barX(i), y: BASE - (i < 4 ? barH(i, t) : 0) - DR });

  const TX0 = 460, TX1 = 1460, TY = 780;
  const CT0 = negative ? TX1 : TX0, CT1 = negative ? TX0 : TX1; // where the count starts and ends
  const ringFrac = isPercent ? clamp(percent / 100, 0.04, 1) : 0.72;
  const RGX = CX, RGY = CY, RGR = 280;
  const ringAng = (k: number) => -Math.PI / 2 - UP * 2 * Math.PI * ringFrac * k;
  const ringPt = (k: number): Pt => ({ x: RGX + RGR * Math.cos(ringAng(k)), y: RGY + RGR * Math.sin(ringAng(k)) });

  const STATS: Record<string, { land: Pt; end: Pt; dot: (t: number) => Dot }> = {
    spring: {
      land: G0,
      end: E,
      dot: (t) => { const tau = prog(t, 3.5, 5.5), s = sq(t, 3.5); return { x: G0.x + tau * GW, y: gY(tau), r: DR, sx: 1 + s, sy: 1 - s }; },
    },
    bars: {
      land: barTop(0, 3.5),
      end: { x: barX(4), y: BASE - barHs[4] - DR },
      dot: (t) => {
        if (t < 4.7) {
          const h = Math.min(3, Math.floor((t - 3.5) / 0.3)), e = prog(t, 3.5 + h * 0.3, 3.8 + h * 0.3);
          const A = barTop(h, t), B = barTop(h + 1, t), s = sq(t, 3.5 + h * 0.3);
          return { x: lerp(A.x, B.x, e), y: lerp(A.y, B.y, e) - 4 * 110 * e * (1 - e), r: DR, sx: 1 + s, sy: 1 - s };
        }
        const s = sq(t, 4.7);
        return { x: barX(4), y: BASE - barH(4, t) - DR, r: DR, sx: 1 + s, sy: 1 - s };
      },
    },
    counter: {
      land: { x: CT0, y: TY },
      end: { x: CT1, y: TY },
      dot: (t) => { const s = sq(t, 3.5); return { x: lerp(CT0, CT1, statSpring(t)), y: TY, r: DR, sx: 1 + s, sy: 1 - s }; },
    },
    ring: {
      land: ringPt(0),
      end: ringPt(1),
      dot: (t) => { const s = sq(t, 3.5); return { ...ringPt(statSpring(t)), r: DR, sx: 1 + s, sy: 1 - s }; },
    },
  };
  const statStyle = STATS[cfg.scenes.stat] ? cfg.scenes.stat : "spring";
  const statScene = STATS[statStyle];
  const SE = statScene.end;

  const cRest: Pt = { x: knobOn.x + 230, y: CY + 190 };
  const endX0 = (DW - (TW + GAP + textW(endLabel, LS, 800))) / 2;
  const endTrack = { ...track, cx: endX0 + TW / 2 };
  const endKnob: Pt = { x: endX0 + 40, y: CY };
  const endL = lineLayout(endLabel, LS, 800, endX0 + TW + GAP, CY + 0.36 * LS);
  const endDot = endLabel.length - hero.length + heroDot.k;
  const endRest: Pt = { x: endX0 + TW - 40 + 230, y: CY + 190 };

  // Logo outro: the uploaded logo fitted inside a 1.5in square at slide centre
  // (1.5 / 13.333in of a 16:9 slide's width = 216 design px).
  const logo = cfg.outro?.mode === "logo" ? getLogo(cfg.outro.logo) : null;
  const LOGO_BOX = (1920 * 1.5) / 13.333;
  const logoW = logo ? (logo.aspect >= 1 ? LOGO_BOX : LOGO_BOX * logo.aspect) : 0;
  const logoH = logo ? logoW / logo.aspect : 0;
  const logoX = CX - logoW / 2, logoY = CY - logoH / 2, sweepBand = logoW * 0.18;
  const sweepAt = (t: number) => { const p = prog(t, 14.45, 14.85); return 1 - (1 - p) * (1 - p); }; // slight ease-out
  const sweepFront = (t: number) => logoX + (logoW + sweepBand) * sweepAt(t);
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
    const e = spText(prog(t, 9.0 + k * wordStep, 9.5 + k * wordStep)), by = Math.sin(t * 2 + k * 1.3) * 8 * clamp(e);
    return { x: lerp(C.x, tags[k].cx, e), y: lerp(C.y, tags[k].cy, e) + by, e };
  };

  // Story mode always uses the pill: it becomes the solution's badge.
  const shapeStyle = story ? "pill" : ["pill", "triangle", "star", "blob"].includes(cfg.scenes.shape) ? cfg.scenes.shape : "pill";

  // ---- story layouts
  const probText = storyText.problem.trim();
  const PS = probText ? Math.min(92, (92 * 1400) / textW(probText, 92, 800)) : 92;
  const probW = probText ? textW(probText, PS, 800) : 0;
  const probX0 = (DW - probW) / 2, probX1 = probX0 + probW;
  const probL = probText ? lineLayout(probText, PS, 800, probX0, CY + 0.36 * PS) : [];
  // each letter appears as the typing cursor (the dot) passes its right edge, so it is set just behind the dot
  const typeAt = (x: number) => 15.45 + 0.85 * clamp((x - (probX0 - 26)) / Math.max(1, probW + 44));
  const solution = storyText.solution.trim(), lead = storyText.lead.trim();
  const BS = solution ? Math.min(84, (84 * 1250) / textW(solution, 84, 800)) : 84;
  const badgeW = solution ? Math.min(1500, Math.max(700, textW(solution, BS, 800) + 200)) : 700;
  const proofLabel = storyText.proofLabel.trim();
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
    const p = spDot(prog(t, t0, t0 + hop)), s = sq(t, t0 + hop);
    return { x: lerp(from.x, to.x, p), y: lerp(from.y, to.y, p) - Math.sin(Math.PI * clamp(p)) * 40, r: Math.min(DR, listSize * 0.22), sx: 1 + s, sy: 1 - s };
  }

  const c1 = Math.min(170, (170 * 1500) / textW(cardText[0], 170, 800));
  // Subtitle and footnote are kept legible in small outputs but never wider than the title area.
  const fitLine = (str: string, size: number, weight: number) => Math.min(size, (size * 1500) / Math.max(1, textW(str, size, weight)));
  const cardSpec: [string, number, number, number][] = [
    [cardText[0], c1, 800, 470],
    [cardText[1], fitLine(cardText[1], legible(60), 500), 500, 590],
    [cardText[2], fitLine(cardText[2], legible(38), 500), 500, 676],
  ];
  const card = cardSpec.map(
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
    if (k < 0) {
      const j = exitOrder[i], q = ein(prog(t, 1.45 + j * 0.05, 1.85 + j * 0.05));
      return { x: x - 40 * q, y: y + 100 * q, size, rot: -0.9 * q, a: 1 - q };
    }
    const B = heroL[k], p = spText(prog(t, 1.7 + k * 0.03, 2.35 + k * 0.03));
    x = lerp(c.x, B.x, p); y = lerp(c.y, B.y, p); size = lerp(LS, HS, p);
    rot = Math.sin(Math.PI * clamp(p)) * 0.14 * (k % 2 ? 1 : -1);
    const q = ein(prog(t, 3.0 + k * 0.025, 3.4 + k * 0.025));
    return { x, y: y + 180 * q, size, rot: rot + 0.4 * q * (k % 2 ? 1 : -1), a: 1 - q };
  }
  // Return: the ending row's letters rise into place.
  function endXf(i: number, t: number): Xf {
    const c = endL[i], r = spText(prog(t, 14.45 + i * 0.017, 14.7 + i * 0.017));
    return { x: c.x, y: c.y + (1 - r) * 56, size: LS, rot: 0, a: clamp(r * 1.6) };
  }
  const heroTittle = (t: number) => tittleAt(labelXf(labelDot, t), labelL[labelDot].u, heroDot.spec);

  const CARD_START = [12.35, 12.5, 12.62], CARD_STAG = [0.02, 0.01, 0.012];
  function cardXf(li: number, k: number, t: number): Xf {
    const l = card[li].letters[k];
    const a = spText(prog(t, CARD_START[li] + k * CARD_STAG[li], CARD_START[li] + k * CARD_STAG[li] + 0.4));
    const q = ein(prog(t, 13.5 + l.gi * 0.008, 13.85 + l.gi * 0.008));
    return { x: l.x, y: l.y + (1 - a) * 50 + 120 * q, size: card[li].size, rot: 0.3 * q * (l.gi % 2 ? 1 : -1), a: clamp(a * 1.6) * (1 - q) };
  }
  const cardTittle = (t: number) => tittleAt(cardXf(0, cardDot.k, t), card[0].letters[cardDot.k].u, cardDot.spec);

  // The accent dot: one continuous path through every scene.
  // Story: the dot jumps in, types the problem line as a cursor, stalls against an invisible wall,
  // then drops to the centre for the reveal. The bridge holds it at the centre during the paper wipe.
  function storyDot(t: number): Dot {
    const S = heroTittle(3.0), start: Pt = { x: probX0 - 26, y: CY }, rest: Pt = { x: probX1 + 18, y: CY }, r = DR * 0.8;
    if (t >= PROBLEM_T1) return { x: C.x, y: C.y, r: DR, sx: 1, sy: 1 };
    if (!probText) {
      const e = eio(prog(t, 15.0, 17.45));
      return { x: lerp(S.x, C.x, e), y: lerp(S.y, C.y, e) - Math.sin(Math.PI * e) * 220, r: DR, sx: 1, sy: 1 };
    }
    if (t < 15.45) {
      const e = eio(prog(t, 15.0, 15.45));
      return { x: lerp(S.x, start.x, e), y: lerp(S.y, start.y, e) - Math.sin(Math.PI * e) * 200, r: lerp(DR, r, e), sx: 1, sy: 1 };
    }
    if (t < 16.3) {
      const s = sq(t, 15.45);
      return { x: lerp(start.x, rest.x, prog(t, 15.45, 16.3)), y: CY, r, sx: 1 + s, sy: 1 - s };
    }
    if (t < 16.9) {
      // three lunges at a wall that isn't there
      let x = rest.x, s = 0;
      for (let k = 0; k < 3; k++) {
        const b0 = 16.3 + k * 0.18, l = prog(t, b0, b0 + 0.16);
        if (l > 0 && l < 1) x = rest.x + 26 * Math.sin(Math.PI * l);
        s += sq(t, b0 + 0.16);
      }
      return { x, y: CY, r, sx: 1 - s, sy: 1 + s };
    }
    const p = spDot(prog(t, 17.0, 17.45));
    return { x: lerp(rest.x, C.x, p), y: lerp(rest.y, C.y, p) - Math.sin(Math.PI * clamp(p)) * 160, r: lerp(r, DR, clamp(p)), sx: 1, sy: 1 };
  }

  function dotAt(t: number): Dot {
    let x: number, y: number, r: number, sx = 1, sy = 1;
    if (t >= PROBLEM_T0) return storyDot(t);
    if (t < 1.0) { x = knobOff.x; y = knobOff.y; r = KR; }
    else if (t < 1.6) {
      const p = spUI(prog(t, 1.0, 1.6)), v = Math.sin(Math.PI * prog(t, 1.0, 1.35));
      x = lerp(knobOff.x, knobOn.x, p); y = knobOn.y; r = KR; sx = 1 + 0.28 * v; sy = 1 - 0.18 * v;
    } else if (t < 2.3) {
      const T = heroTittle(t), e = eio(prog(t, 1.6, 2.3));
      x = lerp(knobOn.x, T.x, e); y = lerp(knobOn.y, T.y, e) - Math.sin(Math.PI * e) * 220; r = lerp(KR, DR, e);
    } else if (t < 3.0) {
      const T = heroTittle(t), s = sq(t, 2.3), a = eio(prog(t, 2.78, 3.0));
      r = DR; x = T.x; y = T.y + r * 0.3 * a; sx = (1 + s) * (1 + 0.2 * a); sy = (1 - s) * (1 - 0.3 * a);
    } else if (t < 6.45 && !showStat) {
      // stat off: hop straight from the hero's i to the centre (story: the dot is already there)
      const S = story ? C : heroTittle(3.0), e = eio(prog(t, 3.0, 6.45)), v = Math.sin(Math.PI * e);
      x = lerp(S.x, C.x, e); y = lerp(S.y, C.y, e) - v * 220; r = DR; sx = 1 + 0.4 * v; sy = 1 - 0.2 * v;
    } else if (t < 3.5) {
      const S = story ? C : heroTittle(3.0), L = statScene.land, e = prog(t, 3.0, 3.5), v = Math.sin(Math.PI * e);
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
      const s = sq(t, 9.0);
      x = C.x; y = C.y; r = DR * (1 + pulse); sx = 1 + s; sy = 1 - s;
    } else if (t < 12.75) {
      const T = cardTittle(t), e = eio(prog(t, 12.25, 12.75));
      x = lerp(C.x, T.x, e); y = lerp(C.y, T.y, e) - Math.sin(Math.PI * e) * 170; r = lerp(DR, DR2, e);
    } else if (t < 13.55) {
      const T = cardTittle(t), s = sq(t, 12.75), a = eio(prog(t, 13.35, 13.55));
      r = DR2; x = T.x; y = T.y + r * 0.3 * a; sx = (1 + s) * (1 + 0.2 * a); sy = (1 - s) * (1 - 0.3 * a);
    } else if (t < 13.95) {
      const S = showCard ? cardTittle(13.55) : C, e = prog(t, 13.55, 13.95);
      x = lerp(S.x, P1.x, e); y = lerp(S.y, P1.y, e) - 4 * 200 * e * (1 - e); r = lerp(showCard ? DR2 : DR, DR, e);
    } else if (t < 14.35) {
      const tau = prog(t, 13.95, 14.35), s = sq(t, 13.95);
      x = P1.x + tau * 640; y = P1.y - gy(tau) * 220; r = DR; sx = 1 + s; sy = 1 - s;
    } else if (logo) {
      if (t < 14.45) {
        const e = eio(prog(t, 14.35, 14.45));
        x = lerp(P2.x, logoX, e); y = lerp(P2.y, CY, e) - Math.sin(Math.PI * e) * 120; r = lerp(DR, 9, e);
      } else {
        x = Math.min(sweepFront(t), logoX + logoW); y = CY; r = 9 * (1 - prog(t, 14.8, 14.88));
      }
    } else if (t < 14.92) {
      const p = spDot(prog(t, 14.35, 14.92));
      x = lerp(P2.x, endKnob.x, p); y = lerp(P2.y, endKnob.y, p) - Math.sin(Math.PI * clamp(p)) * 180; r = lerp(DR, KR, clamp(p));
    } else { x = endKnob.x; y = endKnob.y; r = KR; }
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
    if (t < 14.35 || t >= PROBLEM_T0 || logo) return null;
    const e = eout(prog(t, 14.35, 14.95));
    return { x: lerp(cOff.x, endRest.x, e), y: lerp(cOff.y, endRest.y, e), s: 1 };
  }

  // ------------------------------------------------------------ scenes
  function drawTrack(g: CanvasRenderingContext2D, t: number) {
    let s: number, col = MUTE;
    if (t < 2.0) { col = mixHex(MUTE, INK, prog(t, 1.0, 1.18)); s = 1 - einBack(prog(t, 1.55, 1.95)); }
    else if (t >= 14.5 && t < PROBLEM_T0 && !logo) s = spUI(prog(t, 14.5, 14.9));
    else return;
    const tr = t >= 14.5 ? endTrack : track;
    shapeState(g, { x: tr.cx, y: tr.cy, w: tr.w * s, h: tr.h * s, rad: Infinity }, col);
  }

  function drawLabel(g: CanvasRenderingContext2D, t: number) {
    const atEnd = t >= 14.4, row = atEnd ? endL : labelL, dotIdx = atEnd ? endDot : labelDot;
    row.forEach((c, i) => {
      const xf = atEnd ? endXf(i, t) : labelXf(i, t), isDot = i === dotIdx && heroDot.real;
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
    const c = spText(prog(t, 5.0, 5.45)) * (1 - einBack(prog(t, 6.0, 6.3)));
    if (c <= 0.001) return;
    const size = 130;
    g.save(); g.translate(x, y); g.scale(c, c);
    g.font = f(800, size); g.fillStyle = INK; g.fillText(stat, 0, 0.36 * size); g.restore();
  }

  // Story: a short caption that says what the number means.
  function drawCaption(g: CanvasRenderingContext2D, t: number, x: number, y: number, align: CanvasTextAlign, t0: number) {
    if (!story || !proofLabel) return;
    const a = eout(prog(t, t0, t0 + 0.4)) * (1 - prog(t, 6.0, 6.3));
    if (a <= 0.003) return;
    const size = Math.min(legible(40), (legible(40) * 900) / textW(proofLabel, legible(40), 500));
    g.save(); g.globalAlpha = 0.75 * a; g.textAlign = align; g.font = f(500, size); g.fillStyle = INK;
    g.fillText(proofLabel, x, y + (1 - a) * 16); g.restore();
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
    if (negative) {
      // indicative baseline (the previous level) and a dashed ghost of what was saved
      const b = eout(prog(t, 4.95, 5.25)), top = BASE - BREF, h = barH(4, t);
      if (b > 0) {
        g.save(); g.setLineDash([12, 10]); g.strokeStyle = INK; g.lineWidth = 3; g.globalAlpha = 0.45;
        line(g, barX(3) - BW / 2, top, lerp(barX(3) - BW / 2, barX(4) + BW / 2 + 30, b), top);
        if (h < BREF - 2 && t >= 5.0) { g.beginPath(); g.rect(barX(4) - BW / 2, top, BW, BREF - h - 3); g.stroke(); }
        g.restore();
      }
    }
    drawCallout(g, t, barX(4) + BW / 2 + 50, BASE - (negative ? BREF : H5) + 40);
    drawCaption(g, t, barX(4) + BW / 2 + 54, BASE - (negative ? BREF : H5) + 40 + 105, "left", 5.1);
  }

  function drawCounter(g: CanvasRenderingContext2D, t: number) {
    const a = eout(prog(t, 3.0, 3.45)), k = statSpring(t), q = eio(prog(t, 6.0, 6.35));
    g.save();
    wipeClip(g, t, TX0 - 60, TX1 - TX0 + 200);
    g.lineCap = "round"; g.lineWidth = 8;
    g.strokeStyle = mixHex(PAPER, INK, 0.18); line(g, TX0, TY, lerp(TX0, TX1, a), TY);
    if (t >= 3.5) { g.strokeStyle = INK; line(g, CT0, TY, lerp(CT0, CT1, k), TY); }
    g.font = f(500, legible(26)); g.fillStyle = INK; g.globalAlpha = 0.5 * a;
    g.textAlign = "left"; g.fillText(negative ? fmtStat(1) : "0", TX0 - 8, TY + 52);
    g.textAlign = "right"; g.fillText(negative ? "0" : fmtStat(1), TX1 + 8, TY + 52);
    g.restore();

    const pop = spText(prog(t, 3.35, 3.75));
    if (pop <= 0.001 || q >= 1) return;
    const size = Math.min(300, (300 * 1300) / textW(fmtStat(1), 300, 800));
    g.save(); g.globalAlpha = 1 - q; g.translate(CX, TY - 110 + 60 * q); g.scale(pop, pop);
    g.font = f(800, size); g.fillStyle = INK; g.textAlign = "center"; g.fillText(fmtStat(k), 0, 0); g.restore();
    drawCaption(g, t, CX, TY + 125, "center", 3.8);
  }

  function drawProgressRing(g: CanvasRenderingContext2D, t: number) {
    const a = eout(prog(t, 3.0, 3.5)), k = statSpring(t), q = eio(prog(t, 6.0, 6.35));
    if (q >= 1) return;
    g.save(); g.globalAlpha = 1 - q;
    g.translate(RGX, RGY); g.scale(1 - 0.3 * q, 1 - 0.3 * q); g.translate(-RGX, -RGY);
    g.lineCap = "round"; g.lineWidth = 22;
    g.strokeStyle = mixHex(PAPER, INK, 0.14);
    g.beginPath(); g.arc(RGX, RGY, RGR, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * a); g.stroke();
    if (t >= 3.5 && k > 0.001) { g.strokeStyle = INK; g.beginPath(); g.arc(RGX, RGY, RGR, -Math.PI / 2, ringAng(k), negative); g.stroke(); }
    const pop = spText(prog(t, 3.35, 3.75));
    if (pop > 0.001) {
      const size = Math.min(150, (150 * 400) / textW(fmtStat(1), 150, 800));
      g.translate(RGX, RGY); g.scale(pop, pop);
      g.font = f(800, size); g.fillStyle = INK; g.textAlign = "center"; g.fillText(fmtStat(k), 0, 0.36 * size);
    }
    g.restore();
    drawCaption(g, t, CX, RGY + RGR + 95, "center", 3.8);
  }

  function drawSpring(g: CanvasRenderingContext2D, t: number) {
    const a = eout(prog(t, 3.0, 3.45));
    g.save();
    wipeClip(g, t, G0.x - 60, GW + 200);
    g.lineCap = "round"; g.strokeStyle = INK; g.lineWidth = 5;
    line(g, G0.x, G0.y, G0.x, G0.y + UP * GH * 1.5 * a);
    line(g, G0.x, G0.y, G0.x + (GW + 40) * a, G0.y);
    const tp = eio(prog(t, 3.25, 3.7));
    if (tp > 0) { g.save(); g.setLineDash([14, 14]); g.globalAlpha = 0.4; g.lineWidth = 3; line(g, G0.x, G0.y + UP * GH, G0.x + (GW + 40) * tp, G0.y + UP * GH); g.restore(); }
    g.save(); g.globalAlpha = a; g.font = f(500, legible(26)); g.fillStyle = INK; g.textAlign = "right";
    g.fillText(negative ? "\u22121.0" : "1.0", G0.x - 22, G0.y + UP * GH + 9); g.fillText("0", G0.x - 22, G0.y + 9); g.restore();

    // Curve: drawn from the exact function that moves the dot.
    const tau = prog(t, 3.5, 5.5);
    if (tau > 0) {
      g.lineWidth = 6; g.lineJoin = "round"; g.beginPath();
      const N = Math.ceil(260 * tau) + 1;
      for (let i = 0; i <= N; i++) { const x = (tau * i) / N, px = G0.x + x * GW, py = gY(x); if (i) g.lineTo(px, py); else g.moveTo(px, py); }
      g.stroke();
    }
    if (t >= 4.0) {
      const pk = { x: G0.x + 0.25 * GW, y: G0.y + UP * (1 + OS) * GH }, p = prog(t, 4.0, 4.4);
      g.save(); g.setLineDash([6, 10]); g.globalAlpha = 0.3; g.lineWidth = 3;
      line(g, pk.x, pk.y, lerp(pk.x, G0.x, eout(prog(t, 4.0, 4.3))), pk.y); g.restore();
      if (p < 1) { g.save(); g.globalAlpha = 1 - p; g.lineWidth = 3; g.beginPath(); g.arc(pk.x, pk.y, 20 + 60 * eout(p), 0, Math.PI * 2); g.stroke(); g.restore(); }
    }
    g.restore();
    drawCallout(g, t, E.x + 70, E.y);
    drawCaption(g, t, E.x + 74, E.y + 105, "left", 5.1);
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
    const s1 = spShape(prog(t, 7.0, 7.45));
    const k1 = eio(prog(t, 7.05, 7.5)); // circle -> shape A
    const st = spShape(prog(t, 7.75, 8.25)); // shape A -> shape B
    const spin = spShape(prog(t, 7.0, 8.1));
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
      const w = lerp(280, story ? badgeW : 700, st) * s1 * k, h = lerp(280, 220, st) * s1 * k;
      shapeState(g, { x: C.x, y: C.y, w, h, rad: Math.min(w, h) * lerp(cf, 0.5, clamp(st)), rot: Math.PI * spin }, INK);
      if (story && (solution || lead)) {
        // the pill becomes the solution's badge; the lead-in sits above it on the accent field
        const a = eout(prog(t, 7.95, 8.2)) * (1 - prog(t, 8.5, 8.6));
        if (a > 0.003) {
          g.save(); g.globalAlpha = a; g.textAlign = "center";
          if (solution) { g.font = f(800, BS * k); g.fillStyle = PAPER; g.fillText(solution, C.x, C.y + 0.36 * BS * k + (1 - a) * 20); }
          if (lead) { g.font = f(500, legible(44) * k); g.fillStyle = INK; g.fillText(lead, C.x, C.y - h / 2 - 40 * k); }
          g.restore();
        }
      }
    }
  }

  // Word glyphs before the open-out: centre position, rotation, size, alpha, and open-out delay.
  interface Glyph { ch: string; x: number; y: number; rot: number; size: number; a: number; d: number }

  function wordGlyphs(t: number): Glyph[] {
    const out: Glyph[] = [];
    if (wordsStyle === "orbit") {
      const rotA = -0.32 * (t - 9) - 1.4 * ein(prog(t, 10.75, 11.5));
      for (const ch of ring) {
        const t0 = 9.0 + ch.w * wordStep + ch.c * 0.012, e = spText(prog(t, t0, t0 + 0.45));
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
          const t0 = 9.0 + k * wordStep + j * 0.012, e = spText(prog(t, t0, t0 + 0.5));
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
          const e = spText(prog(t, t0 + 0.05 + j * 0.01, t0 + 0.5 + j * 0.01));
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

  // End-card reveal: cover the frame in paper, then uncover to ink for the card.
  function drawReveal(g: CanvasRenderingContext2D, t: number) {
    const style = cfg.scenes.reveal ?? "halftone";
    if (style === "halftone") return drawHalftone(g, t);
    if (t < 10.85 || t >= 12.6) return;
    const W = V.x1 - V.x0, H = V.y1 - V.y0;
    const cover = t < 11.8, p1 = eio(prog(t, 10.85, 11.75)), p2 = eio(prog(t, 11.8, 12.55));
    if (style === "iris") {
      if (cover) circle(g, C.x, C.y, (halfDiag + 60) * p1, PAPER);
      else { g.fillStyle = PAPER; g.fillRect(V.x0, V.y0, W, H); circle(g, C.x, C.y, (halfDiag + 60) * p2, INK); }
    } else if (style === "stripes") {
      // eight bars sweep left to right, echoing the data lines of the logo sweep
      const rows = 8, rh = H / rows;
      if (!cover) { g.fillStyle = PAPER; g.fillRect(V.x0, V.y0, W, H); }
      g.fillStyle = cover ? PAPER : INK;
      for (let r = 0; r < rows; r++) {
        const pr = cover ? eio(prog(t, 10.85 + r * 0.05, 11.45 + r * 0.05)) : eio(prog(t, 11.8 + r * 0.04, 12.25 + r * 0.04));
        if (pr > 0) g.fillRect(V.x0, V.y0 + r * rh, W * pr, rh + 1);
      }
    } else {
      // slide: a paper panel pushes in from the right, then an ink panel over it
      if (cover) { g.fillStyle = PAPER; g.fillRect(lerp(V.x1, V.x0, p1), V.y0, W, H); }
      else { g.fillStyle = PAPER; g.fillRect(V.x0, V.y0, W, H); g.fillStyle = INK; g.fillRect(lerp(V.x1, V.x0, p2), V.y0, W, H); }
    }
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

  // Data sweep: left of the band the logo is solid; inside it the logo forms out of horizontal
  // data lines that thicken away from the front; short accent streaks run just ahead of it.
  function drawLogo(g: CanvasRenderingContext2D, t: number) {
    if (!logo) return;
    const front = sweepFront(t), rows = 8, pitch = logoH / rows;
    const reveal = (x0: number, x1: number, thick: number) => {
      x0 = Math.max(x0, logoX); x1 = Math.min(x1, logoX + logoW);
      if (x1 <= x0) return;
      g.save(); g.beginPath();
      if (thick >= 1) g.rect(x0, logoY, x1 - x0, logoH);
      else for (let r = 0; r < rows; r++) g.rect(x0, logoY + (r + (1 - thick) / 2) * pitch, x1 - x0, pitch * thick);
      g.clip(); g.drawImage(logo.img, logoX, logoY, logoW, logoH); g.restore();
    };
    reveal(logoX, front - sweepBand, 1);
    [0.25, 0.45, 0.65, 0.85].forEach((k, i) => reveal(front - ((i + 1) * sweepBand) / 4, front - (i * sweepBand) / 4, k));

    const active = Math.sin(Math.PI * sweepAt(t));
    if (active <= 0.01) return;
    g.save(); g.strokeStyle = ACCENT; g.lineCap = "round"; g.lineWidth = 2;
    for (let r = 0; r < rows; r++) for (let k = 0; k < 2; k++) {
      const h = Math.abs(Math.sin((r * 7 + k * 13 + 1) * 12.9898) * 43758.5453) % 1;
      const x = front + 6 + h * 110, len = 10 + ((h * 7.3) % 1) * 36;
      g.globalAlpha = 0.55 * (1 - h) * active;
      line(g, x, logoY + (r + 0.5) * pitch, x + len, logoY + (r + 0.5) * pitch);
    }
    g.restore();
  }

  // Story problem: typed by the dot, dimmed and struck through while it stalls, then it crumbles.
  function drawProblem(g: CanvasRenderingContext2D, t: number) {
    if (!probText || t < 15.4 || t >= PROBLEM_T1) return;
    const dim = 1 - 0.45 * eio(prog(t, 16.35, 16.75));
    probL.forEach((l, j) => {
      const t0 = typeAt(l.x + l.u * PS), e = spText(prog(t, t0, t0 + 0.25));
      const q = ein(prog(t, 16.9 + j * 0.012, 17.25 + j * 0.012));
      drawGlyph(g, l.ch, { x: l.x, y: l.y + (1 - e) * 24 + 160 * q, size: PS, rot: 0.4 * q * (j % 2 ? 1 : -1), a: clamp(e * 2) * dim * (1 - q) }, l.u, 800, INK);
    });
    const sp1 = eio(prog(t, 16.5, 16.85)), fade = 1 - prog(t, 16.9, 17.1);
    if (sp1 > 0 && fade > 0) {
      g.save(); g.strokeStyle = INK; g.lineWidth = 6; g.lineCap = "round"; g.globalAlpha = fade;
      line(g, probX0 - 10, CY, lerp(probX0 - 10, probX1 + 10, sp1), CY); g.restore();
    }
  }

  function bgAt(t: number) {
    if (t >= PROBLEM_T1) return INK; // bridge: the paper wipe grows over the ink from the reveal
    if (t >= PROBLEM_T0) return PAPER;
    if (story && !showCard && t >= 10.75 && t < 14.65) return PAPER; // no end card: stay on paper into the return
    if (story && t >= 10.75 && t < 12.6) return PAPER; // proof was on paper; the reveal flips to ink
    return t >= 7.0 && t < 14.65 ? INK : PAPER;
  }

  // Pure function of t: no state carried between frames.
  function draw(g: CanvasRenderingContext2D, t: number) {
    g.textAlign = "left"; g.textBaseline = "alphabetic";
    g.fillStyle = bgAt(t);
    g.fillRect(V.x0, V.y0, V.x1 - V.x0, V.y1 - V.y0);
    if (showCard) drawReveal(g, t);
    drawEcho(g, t);
    drawWipe(g, t);
    drawTrack(g, t);
    if (t >= PROBLEM_T1) circle(g, C.x, C.y, (halfDiag + 60) * ein(prog(t, PROBLEM_T1, PROBLEM_T1 + 0.22)), PAPER);
    if (story && t >= PROBLEM_T0 && t < 15.6) drawLabel(g, 3.0 + (t - PROBLEM_T0)); // hero word drops out as the problem begins
    else if ((story ? t < 3.0 : t < 3.7) || (t >= 14.4 && t < PROBLEM_T0 && !logo)) drawLabel(g, t);
    drawProblem(g, t);
    if (logo && t >= 14.45 && t < PROBLEM_T0) drawLogo(g, t);
    if (showStat && t >= 3.0 && t < 6.5) drawStat(g, t);
    if (showWords) drawWords(g, t);
    if (showCard) drawCard(g, t);
    const D = dotAt(t);
    shapeState(g, { x: D.x, y: D.y, w: 2 * D.r * D.sx, h: 2 * D.r * D.sy, rad: Infinity }, ACCENT);
    if (showShape) drawInner(g, t);
    drawCursor(g, t);
  }

  return {
    width, height, duration: tl.duration,
    seek(g, seconds) {
      const t = tl.toInternal(seconds);
      g.save();
      g.setTransform(u, 0, 0, u, ox, oy);
      if (cfg.motion?.camera) {
        // Near-invisible push-in that peaks mid-film and is exactly 1x at the loop point.
        const k = 1 + 0.035 * (1 - Math.cos((2 * Math.PI * t) / TIMELINE)) / 2;
        g.translate(CX, CY); g.scale(k, k); g.translate(-CX, -CY);
      }
      draw(g, t);
      g.restore();
    },
  };
}

// Uploaded logos (data URLs), decoded once and shared by the preview and every export.
interface Logo { img: HTMLImageElement; aspect: number }
const logoCache = new Map<string, Logo>();
export const getLogo = (src: string | undefined) => (src ? logoCache.get(src) ?? null : null);

/** Decode a logo data URL; SVGs without width/height get them from their viewBox so they draw at full size. */
export async function loadLogo(src: string | undefined) {
  if (!src || logoCache.has(src)) return;
  let url = src, aspect = 0;
  if (src.startsWith("data:image/svg+xml")) {
    try {
      const comma = src.indexOf(","), body = src.slice(comma + 1);
      const text = src.slice(0, comma).includes(";base64") ? decodeURIComponent(escape(atob(body))) : decodeURIComponent(body);
      const doc = new DOMParser().parseFromString(text, "image/svg+xml"), svg = doc.documentElement;
      const vb = (svg.getAttribute("viewBox") || "").split(/[\s,]+/).map(Number);
      const w = parseFloat(svg.getAttribute("width") || "") || vb[2], h = parseFloat(svg.getAttribute("height") || "") || vb[3];
      if (w > 0 && h > 0) {
        aspect = w / h;
        svg.setAttribute("width", String(w * 10)); svg.setAttribute("height", String(h * 10));
        url = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(svg));
      }
    } catch { /* fall back to the raw data URL */ }
  }
  const img = new Image();
  img.src = url;
  try { await img.decode(); } catch { return; }
  aspect = aspect || (img.naturalWidth && img.naturalHeight ? img.naturalWidth / img.naturalHeight : 1);
  logoCache.set(src, { img, aspect });
}

/** Everything a frame needs before it can be drawn: web fonts and the uploaded logo. */
export async function prepareAssets(cfg: MotionConfig) {
  await Promise.all([loadFont(cfg.style.font), loadLogo(cfg.outro?.mode === "logo" ? cfg.outro.logo : undefined)]);
}

/** Wait for the chosen font so glyph metrics and tittle detection are right. */
export async function loadFont(font: string) {
  try {
    await Promise.all([document.fonts.load(`800 100px "${font}"`), document.fonts.load(`500 100px "${font}"`)]);
  } catch {
    // fall back to system fonts
  }
}
