export const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const prog = (t: number, a: number, b: number) => clamp((t - a) / (b - a));
export const eio = (p: number) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
export const ein = (p: number) => p * p * p;
export const eout = (p: number) => 1 - Math.pow(1 - p, 3);
export const einBack = (p: number) => {
  const c = 1.70158;
  return (c + 1) * p * p * p - c * p * p;
};
export const smooth = (a: number, b: number, x: number) => {
  const t = clamp((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};
export const expLerp = (a: number, b: number, p: number) => a * Math.pow(b / a, p);

// Closed-form underdamped spring step response.
export function springStep(x: number, z: number, wn: number) {
  const wd = wn * Math.sqrt(1 - z * z);
  return 1 - Math.exp(-z * wn * x) * (Math.cos(wd * x) + ((z * wn) / wd) * Math.sin(wd * x));
}
// Normalised spring on p in [0,1]; residual at p=1 is sub-pixel, so we snap.
export const sp = (p: number, z = 0.6, wn = 14) => (p <= 0 ? 0 : p >= 1 ? 1 : springStep(p, z, wn));

// One dot pulse after a landing: positive = squash.
export function squash(t: number, t0: number, dur = 0.3, amt = 0.32) {
  const l = prog(t, t0, t0 + dur);
  return l <= 0 || l >= 1 ? 0 : Math.sin(l * Math.PI * 2) * Math.exp(-l * 3) * amt;
}

export function mixHex(a: string, b: string, t: number) {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return "#" + pa.map((v, i) => Math.round(lerp(v, pb[i], t)).toString(16).padStart(2, "0")).join("");
}
