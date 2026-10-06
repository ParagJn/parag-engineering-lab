export interface MotionText {
  intro: string; // shown before the hero on the toggle, then bends away
  hero: string;
  stat: string; // e.g. "+22%": the spring graph overshoots by this amount
  words: string[]; // orbit the dot in the kinetic-type scene
  cardTitle: string; // empty = hero
  cardSubtitle: string;
  cardFootnote: string;
}

export interface MotionStyle {
  theme: string;
  accent: string;
  paper: string;
  ink: string;
  font: string;
}

export type StatStyle = "spring" | "bars" | "counter" | "ring";
export type ShapeStyle = "pill" | "triangle" | "star" | "blob";
export type WordsStyle = "orbit" | "float" | "list" | "tags";

export interface MotionConfig {
  text: MotionText;
  style: MotionStyle;
  scenes: { stat: StatStyle; shape: ShapeStyle; words: WordsStyle; show: Record<"stat" | "shape" | "words" | "card", boolean> };
  duration: number; // seconds for one full loop
  sound: { enabled: boolean }; // reserved: not wired into exports yet
}

export interface OutputSize {
  id: string;
  name: string;
  w: number;
  h: number;
  note: string;
}

export const DEFAULT_CONFIG: MotionConfig = {
  text: {
    intro: "Meet",
    hero: "Parag Jain",
    stat: "+22%",
    words: ["SPRINGS", "EASING", "KINETIC TYPE", "3D", "SOUND"],
    cardTitle: "",
    cardSubtitle: "Built by Opus 5.5.",
    cardFootnote: "0 keyframes",
  },
  style: { theme: "paper", accent: "#FF5A1F", paper: "#F3EEE4", ink: "#0E0E0E", font: "Inter Tight" },
  scenes: { stat: "spring", shape: "pill", words: "orbit", show: { stat: true, shape: true, words: true, card: true } },
  duration: 16.5,
  sound: { enabled: false },
};

export const THEMES = [
  { id: "paper", name: "Warm paper", paper: "#F3EEE4", ink: "#0E0E0E" },
  { id: "night", name: "Night", paper: "#0E0E0E", ink: "#F3EEE4" },
  { id: "cool", name: "Cool grey", paper: "#E9ECEF", ink: "#111827" },
  { id: "navy", name: "Navy", paper: "#0B1B33", ink: "#EAF0FA" },
];

export const STAT_STYLES: { id: StatStyle; name: string; note: string }[] = [
  { id: "spring", name: "Spring graph", note: "Dot traces a curve that overshoots" },
  { id: "bars", name: "Bar chart", note: "Dot hops the bars, the last one lifts it" },
  { id: "counter", name: "Counter", note: "Big number counts up as the dot runs" },
  { id: "ring", name: "Progress ring", note: "Dot draws the arc round the number" },
];

export const WORDS_STYLES: { id: WordsStyle; name: string; note: string }[] = [
  { id: "orbit", name: "Orbit", note: "Words circle the dot" },
  { id: "float", name: "Floating", note: "Words drift around the dot" },
  { id: "list", name: "List", note: "One word per line, dot as the bullet" },
  { id: "tags", name: "Tags", note: "Words as chips above and below the dot" },
];

export const SHAPE_STYLES: { id: ShapeStyle; name: string; note: string }[] = [
  { id: "pill", name: "Square → pill", note: "Rounded square spins, stretches to a pill" },
  { id: "triangle", name: "Triangle → circle", note: "Triangle spins, puffs into a circle" },
  { id: "star", name: "Star burst", note: "Star spins, points shoot out sharper" },
  { id: "blob", name: "Blob", note: "Soft organic shape that wobbles" },
];

export const ACCENTS = ["#FF5A1F", "#0F62FE", "#24A148", "#8A3FFC", "#F1C21B", "#E5007E"];

export const FONTS = ["Inter Tight", "Archivo", "Manrope", "Sora", "Plus Jakarta Sans", "Outfit"];

export const SIZES: OutputSize[] = [
  { id: "hero", name: "Full slide 16:9", w: 1920, h: 1080, note: "Title or hero slide" },
  { id: "hero4k", name: "Full slide 16:9 · 4K", w: 3840, h: 2160, note: "Big screens, crisp stills" },
  { id: "classic", name: "Classic slide 4:3", w: 1440, h: 1080, note: "Older 4:3 decks" },
  { id: "half", name: "Half slide 8:9", w: 960, h: 1080, note: "One side of a split layout" },
  { id: "square", name: "Square 1:1", w: 1080, h: 1080, note: "Content block beside text" },
  { id: "banner", name: "Banner 32:9", w: 1920, h: 540, note: "Section header strip" },
  { id: "tile", name: "Tile 4:3", w: 800, h: 600, note: "Small card in a grid" },
  { id: "custom", name: "Custom", w: 1600, h: 900, note: "Your own width × height" },
];

// Key moments on the internal 15-unit timeline; `scene` hides a moment when that scene is off.
export const KEY_MOMENTS: { id: string; name: string; t: number; scene?: "stat" | "shape" | "words" | "card" }[] = [
  { id: "toggle", name: "Toggle", t: 0.95 },
  { id: "hero", name: "Hero word", t: 2.7 },
  { id: "stat", name: "Stat", t: 5.3, scene: "stat" },
  { id: "shape", name: "Shape", t: 7.6, scene: "shape" },
  { id: "type", name: "Words", t: 10.4, scene: "words" },
  { id: "card", name: "End card", t: 13.2, scene: "card" },
];
