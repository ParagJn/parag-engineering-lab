import { isStory, PROBLEM_T1, sceneOn, timeline } from "./film";
import type { MotionConfig, SoundPreset } from "./types";

/**
 * Procedural soundtrack for the film. No samples and no models: every sound is synthesised with the
 * Web Audio API and placed on the film's own event times (via the same timing map as the visuals),
 * so hits land exactly on the dot's moves at any duration or with scenes switched off.
 *
 * The loop is rendered offline into an AudioBuffer exactly `duration` long. Sounds that ring past the
 * loop point are folded back onto the start, so the buffer loops seamlessly like the video.
 */

interface Synth { ac: BaseAudioContext; out: AudioNode; noise: AudioBuffer }

// Deterministic noise so every export of the same config sounds identical.
function makeNoise(ac: BaseAudioContext) {
  const buf = ac.createBuffer(1, ac.sampleRate, ac.sampleRate), d = buf.getChannelData(0);
  let s = 0x2f6b4e1d;
  for (let i = 0; i < d.length; i++) { s = (s * 1664525 + 1013904223) >>> 0; d[i] = s / 2147483648 - 1; }
  return buf;
}

function env(g: GainNode, T: number, peak: number, decay: number, attack = 0.004) {
  g.gain.setValueAtTime(0.0001, T);
  g.gain.exponentialRampToValueAtTime(Math.max(0.0002, peak), T + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, T + decay);
}
function noiseSrc(c: Synth, T: number) {
  const s = c.ac.createBufferSource();
  s.buffer = c.noise;
  return { s, offset: (T * 7.919) % 0.5 };
}

const kick = (c: Synth, T: number, v: number) => {
  const o = c.ac.createOscillator(), g = c.ac.createGain();
  o.frequency.setValueAtTime(150, T); o.frequency.exponentialRampToValueAtTime(42, T + 0.12);
  env(g, T, v, 0.38); o.connect(g).connect(c.out); o.start(T); o.stop(T + 0.4);
};
const hat = (c: Synth, T: number, v: number) => {
  const { s, offset } = noiseSrc(c, T), f = c.ac.createBiquadFilter(), g = c.ac.createGain();
  f.type = "highpass"; f.frequency.value = 7500; env(g, T, v, 0.05);
  s.connect(f).connect(g).connect(c.out); s.start(T, offset); s.stop(T + 0.06);
};
const clap = (c: Synth, T: number, v: number) => {
  const { s, offset } = noiseSrc(c, T), f = c.ac.createBiquadFilter(), g = c.ac.createGain();
  f.type = "bandpass"; f.frequency.value = 1600; f.Q.value = 0.8; env(g, T, v, 0.16);
  s.connect(f).connect(g).connect(c.out); s.start(T, offset); s.stop(T + 0.2);
};
const tick = (c: Synth, T: number, v: number, freq = 2400) => {
  const o = c.ac.createOscillator(), g = c.ac.createGain();
  o.type = "square"; o.frequency.value = freq; env(g, T, v, 0.03);
  o.connect(g).connect(c.out); o.start(T); o.stop(T + 0.05);
};
const tone = (c: Synth, T: number, freq: number, v: number, dur = 0.25, type: OscillatorType = "triangle") => {
  const o = c.ac.createOscillator(), g = c.ac.createGain();
  o.type = type; o.frequency.value = freq; env(g, T, v, dur);
  o.connect(g).connect(c.out); o.start(T); o.stop(T + dur + 0.05);
};
// Soft plucked note: triangle through a closing low-pass.
const pluck = (c: Synth, T: number, freq: number, v: number) => {
  const o = c.ac.createOscillator(), f = c.ac.createBiquadFilter(), g = c.ac.createGain();
  o.type = "triangle"; o.frequency.value = freq;
  f.type = "lowpass"; f.frequency.setValueAtTime(freq * 6, T); f.frequency.exponentialRampToValueAtTime(freq * 1.2, T + 0.3);
  env(g, T, v, 0.4); o.connect(f).connect(g).connect(c.out); o.start(T); o.stop(T + 0.45);
};
// Pitch glide, used for rises and drops (a negative stat glides down).
const glide = (c: Synth, T: number, from: number, to: number, v: number, dur: number) => {
  const o = c.ac.createOscillator(), g = c.ac.createGain();
  o.type = "sine"; o.frequency.setValueAtTime(from, T); o.frequency.exponentialRampToValueAtTime(to, T + dur);
  env(g, T, v, dur + 0.15, 0.02); o.connect(g).connect(c.out); o.start(T); o.stop(T + dur + 0.2);
};
const thump = (c: Synth, T: number, freq: number, v: number) => {
  const o = c.ac.createOscillator(), g = c.ac.createGain();
  o.type = "sine"; o.frequency.setValueAtTime(freq * 2, T); o.frequency.exponentialRampToValueAtTime(freq, T + 0.08);
  env(g, T, v, 0.5); o.connect(g).connect(c.out); o.start(T); o.stop(T + 0.55);
};
const stab = (c: Synth, T: number, freqs: number[], v: number, dur = 0.45) => freqs.forEach((fq) => tone(c, T, fq, v / freqs.length, dur));
const pad = (c: Synth, T: number, freqs: number[], v: number, dur: number) => {
  freqs.forEach((fq) => {
    const o = c.ac.createOscillator(), f = c.ac.createBiquadFilter(), g = c.ac.createGain();
    o.type = "sawtooth"; o.frequency.value = fq; f.type = "lowpass"; f.frequency.value = 900;
    g.gain.setValueAtTime(0.0001, T); g.gain.linearRampToValueAtTime(v / freqs.length, T + dur * 0.3);
    g.gain.linearRampToValueAtTime(0.0001, T + dur);
    o.connect(f).connect(g).connect(c.out); o.start(T); o.stop(T + dur + 0.05);
  });
};
const bass = (c: Synth, T: number, freq: number, v: number) => {
  const o = c.ac.createOscillator(), f = c.ac.createBiquadFilter(), g = c.ac.createGain();
  o.type = "sawtooth"; o.frequency.value = freq; f.type = "lowpass"; f.frequency.value = 500;
  env(g, T, v, 0.22); o.connect(f).connect(g).connect(c.out); o.start(T); o.stop(T + 0.25);
};
// Filtered-noise whoosh; `up` sweeps the band upward.
const sweep = (c: Synth, T: number, dur: number, v: number, up = true) => {
  const { s } = noiseSrc(c, T), f = c.ac.createBiquadFilter(), g = c.ac.createGain();
  f.type = "bandpass"; f.Q.value = 2;
  f.frequency.setValueAtTime(up ? 400 : 6000, T); f.frequency.exponentialRampToValueAtTime(up ? 6000 : 400, T + dur);
  g.gain.setValueAtTime(0.0001, T); g.gain.exponentialRampToValueAtTime(v, T + dur * 0.85); g.gain.exponentialRampToValueAtTime(0.0001, T + dur);
  s.loop = true; s.connect(f).connect(g).connect(c.out); s.start(T); s.stop(T + dur + 0.02);
};

const PENTA = [440, 523.25, 587.33, 659.25, 783.99, 880, 1046.5];

/** Sound events for this config: `t` in real seconds within the loop. */
export function soundEvents(cfg: MotionConfig) {
  const tl = timeline(cfg), at = (u: number) => tl.toSeconds(u);
  const ev: { t: number; play: (c: Synth, T: number) => void }[] = [];
  const push = (u: number, play: (c: Synth, T: number) => void) => ev.push({ t: at(u), play });
  const negative = /^[^\d]*[-−–↓]/.test(cfg.text.stat.trim());

  // Opening: the click, the dot landing on the i, the jump.
  push(1.0, (c, T) => tick(c, T, 0.22));
  push(2.3, (c, T) => pluck(c, T, 1318.5, 0.2));
  push(3.0, (c, T) => sweep(c, T, 0.18, 0.06));

  if (sceneOn(cfg, "stat")) {
    const style = cfg.scenes.stat;
    if (style === "spring") {
      push(3.5, (c, T) => thump(c, T, 220, 0.35));
      push(4.0, (c, T) => tone(c, T, negative ? 523.25 : 987.77, 0.18, 0.3));
      push(5.0, (c, T) => stab(c, T, negative ? [440, 523.25, 659.25] : [659.25, 830.6, 987.77], 0.22));
    } else if (style === "bars") {
      [3.5, 3.8, 4.1, 4.4].forEach((u, i) => push(u, (c, T) => pluck(c, T, PENTA[i], 0.18)));
      push(4.7, (c, T) => thump(c, T, 165, 0.3));
      if (negative) push(5.0, (c, T) => glide(c, T, 660, 330, 0.12, at(5.5) - at(5.0)));
      else push(4.7, (c, T) => glide(c, T, 330, 660, 0.1, at(5.4) - at(4.7)));
      push(5.0, (c, T) => stab(c, T, negative ? [440, 523.25, 659.25] : [659.25, 830.6, 987.77], 0.2));
    } else {
      // counter / ring: ticks that follow the count (dense at first, then slowing), rising or falling in pitch
      for (let i = 0; i < 10; i++) {
        const u = 3.5 + 2 * (i / 10) ** 2;
        push(u, (c, T) => tick(c, T, 0.1, negative ? 2600 - i * 120 : 1500 + i * 120));
      }
      push(5.5, (c, T) => tone(c, T, negative ? 659.25 : 1318.5, 0.16, 0.5));
    }
    push(5.95, (c, T) => sweep(c, T, at(6.45) - at(5.95), 0.12));
  }

  if (sceneOn(cfg, "shape")) {
    push(6.5, (c, T) => sweep(c, T, at(7.0) - at(6.5), 0.14));
    push(7.0, (c, T) => { thump(c, T, 110, 0.45); tone(c, T, 110, 0.12, 0.6, "sawtooth"); });
    push(7.75, (c, T) => pluck(c, T, 880, 0.16));
    push(8.5, (c, T) => sweep(c, T, at(9.0) - at(8.5), 0.12, false));
  }

  if (isStory(cfg)) {
    // Problem: the dot jumps in, types, stalls three times, the line is struck through and crumbles.
    push(15.0, (c, T) => sweep(c, T, 0.18, 0.06));
    if (cfg.story?.problem.trim()) {
      for (let i = 0; i < 10; i++) push(15.45 + (0.85 * i) / 9, (c, T) => tick(c, T, 0.07, 2900 + (i % 3) * 140));
      for (let k = 0; k < 3; k++) push(16.3 + k * 0.18 + 0.08, (c, T) => thump(c, T, 140, 0.16));
      push(16.5, (c, T) => sweep(c, T, at(16.85) - at(16.5), 0.06));
      push(16.9, (c, T) => sweep(c, T, at(17.3) - at(16.9), 0.08, false));
    }
    if (sceneOn(cfg, "shape") && (cfg.story?.solution.trim() || cfg.story?.lead.trim())) push(7.95, (c, T) => stab(c, T, [523.25, 659.25, 783.99], 0.24));
    push(PROBLEM_T1, (c, T) => sweep(c, T, 0.3, 0.07));
  }

  if (!isStory(cfg) && sceneOn(cfg, "words")) {
    const n = Math.max(1, cfg.text.words.filter((w) => w.trim()).length), step = Math.min(0.25, 1 / n);
    for (let k = 0; k < n; k++) push(9 + k * step, (c, T) => pluck(c, T, PENTA[k % PENTA.length], 0.15));
    push(10.75, (c, T) => sweep(c, T, at(11.4) - at(10.75), 0.13));
  }

  if (sceneOn(cfg, "card")) {
    push(12.0, (c, T) => thump(c, T, 110, 0.35));
    push(12.5, (c, T) => stab(c, T, [440, 554.37, 659.25, 880], 0.24));
  }

  // Return trip and ending.
  push(13.55, (c, T) => tone(c, T, 1318.5, 0.1, 0.15));
  push(13.95, (c, T) => tone(c, T, 987.77, 0.1, 0.15));
  if (cfg.outro?.mode === "logo" && cfg.outro.logo) {
    push(14.45, (c, T) => sweep(c, T, at(14.85) - at(14.45), 0.1));
    push(14.85, (c, T) => pad(c, T, [261.63, 329.63, 392], 0.12, Math.max(0.4, cfg.duration - at(14.85))));
  } else {
    push(14.92, (c, T) => tick(c, T, 0.18));
  }
  return ev;
}

/** Beat bed: an exact number of beats per loop (~120 BPM) so the beat loops with the film. */
function bed(c: Synth, preset: SoundPreset, L: number) {
  if (preset !== "minimal" && preset !== "pulse") return;
  const n = Math.max(4, Math.round(L * 2)), beat = L / n, full = preset === "pulse";
  const roots = [55, 55, 65.41, 49, 55, 73.42, 65.41, 55];
  for (let b = 0; b < n; b++) {
    const T = b * beat;
    kick(c, T, full ? 0.75 : 0.45);
    hat(c, T + beat / 2, full ? 0.1 : 0.06);
    if (!full) continue;
    if (b % 2 === 1) clap(c, T, 0.2);
    bass(c, T + beat / 2, roots[Math.floor(b / 4) % roots.length], 0.2);
    if (b % 4 === 0) pad(c, T, [220, 261.63, 329.63], 0.05, beat * 4);
  }
}

/** Render one seamless loop. Returns null when sound is off. */
export async function renderSoundtrack(cfg: MotionConfig, sampleRate = 48000): Promise<AudioBuffer | null> {
  const preset = cfg.sound?.preset ?? "off";
  if (preset === "off") return null;
  const L = cfg.duration, tail = 1.5;
  const len = Math.round(L * sampleRate), total = Math.round((L + tail) * sampleRate);
  const ac = new OfflineAudioContext(2, total, sampleRate);
  const comp = ac.createDynamicsCompressor();
  comp.threshold.value = -14; comp.ratio.value = 3;
  const master = ac.createGain();
  master.gain.value = Math.max(0, Math.min(1, cfg.sound.volume ?? 0.8)) * (preset === "subtle" ? 1.2 : 1);
  master.connect(comp).connect(ac.destination);
  const c: Synth = { ac, out: master, noise: makeNoise(ac) };

  bed(c, preset, L);
  for (const e of soundEvents(cfg)) if (e.t >= 0 && e.t < L) e.play(c, e.t);

  const rendered = await ac.startRendering();
  // Fold the tail that rings past the loop point back onto the start.
  const out = new AudioBuffer({ length: len, numberOfChannels: 2, sampleRate });
  for (let ch = 0; ch < 2; ch++) {
    const src = rendered.getChannelData(ch), dst = out.getChannelData(ch);
    dst.set(src.subarray(0, len));
    for (let i = len; i < total; i++) dst[(i - len) % len] += src[i];
  }
  return out;
}

/** 16-bit PCM WAV of a rendered loop, for dropping the sound into a deck separately. */
export function bufferToWav(buf: AudioBuffer): Blob {
  const ch = buf.numberOfChannels, n = buf.length, bytes = 44 + n * ch * 2;
  const v = new DataView(new ArrayBuffer(bytes));
  const str = (o: number, s: string) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  str(0, "RIFF"); v.setUint32(4, bytes - 8, true); str(8, "WAVE"); str(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, ch, true);
  v.setUint32(24, buf.sampleRate, true); v.setUint32(28, buf.sampleRate * ch * 2, true);
  v.setUint16(32, ch * 2, true); v.setUint16(34, 16, true); str(36, "data"); v.setUint32(40, n * ch * 2, true);
  const data = Array.from({ length: ch }, (_, i) => buf.getChannelData(i));
  let o = 44;
  for (let i = 0; i < n; i++) for (let c = 0; c < ch; c++) {
    const x = Math.max(-1, Math.min(1, data[c][i]));
    v.setInt16(o, x < 0 ? x * 0x8000 : x * 0x7fff, true); o += 2;
  }
  return new Blob([v.buffer], { type: "audio/wav" });
}
