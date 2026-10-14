import { applyPalette, GIFEncoder, quantize } from "gifenc";
import { ArrayBufferTarget, Muxer } from "mp4-muxer";
import pptxgen from "pptxgenjs";
import { createFilm, prepareAssets } from "../engine/film";
import { renderSoundtrack } from "../engine/sound";
import type { MotionConfig } from "../engine/types";

export interface ExportJob {
  cfg: MotionConfig;
  w: number;
  h: number;
  onProgress?: (p: number) => void;
  onNote?: (msg: string) => void;
  signal?: AbortSignal;
}

const tick = () => new Promise((r) => setTimeout(r, 0));
const checkAbort = (signal?: AbortSignal) => {
  if (signal?.aborted) throw new DOMException("Export cancelled", "AbortError");
};

function frameCanvas(w: number, h: number) {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  return { canvas, g: canvas.getContext("2d", { willReadFrequently: true })! };
}

export function saveBlob(blob: Blob, name: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
}

const blobToDataUrl = (blob: Blob) =>
  new Promise<string>((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result as string);
    r.onerror = () => reject(r.error);
    r.readAsDataURL(blob);
  });

// ------------------------------------------------------------ PNG
export async function exportPng(job: ExportJob, seconds: number): Promise<Blob> {
  await prepareAssets(job.cfg);
  const { canvas, g } = frameCanvas(job.w, job.h);
  createFilm(job.cfg, job.w, job.h).seek(g, seconds);
  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("PNG encode failed"))), "image/png"));
}

// ------------------------------------------------------------ MP4 (WebCodecs, faster than real time)
const AVC_CODECS = ["avc1.640034", "avc1.640033", "avc1.640028", "avc1.4d0028", "avc1.42001f"];

export async function exportMp4(job: ExportJob, fps: number): Promise<Blob> {
  if (typeof VideoEncoder === "undefined") throw new Error("MP4 export needs a browser with WebCodecs (Chrome, Edge, or Safari 17+).");
  const w = job.w - (job.w % 2), h = job.h - (job.h % 2); // H.264 needs even dimensions
  const bitrate = Math.min(60e6, Math.round(w * h * fps * 0.1));
  let codec = "";
  for (const c of AVC_CODECS) {
    const { supported } = await VideoEncoder.isConfigSupported({ codec: c, width: w, height: h, bitrate, framerate: fps });
    if (supported) { codec = c; break; }
  }
  if (!codec) throw new Error(`This browser cannot encode H.264 at ${w}×${h}.`);

  await prepareAssets(job.cfg);
  const audio = await audioTrack(job);
  const film = createFilm(job.cfg, w, h);
  const { canvas, g } = frameCanvas(w, h);
  const muxer = new Muxer({
    target: new ArrayBufferTarget(),
    video: { codec: "avc", width: w, height: h, frameRate: fps },
    audio: audio ? { codec: "aac", numberOfChannels: audio.buffer.numberOfChannels, sampleRate: audio.buffer.sampleRate } : undefined,
    fastStart: "in-memory",
  });
  let failure: unknown = null;
  const encoder = new VideoEncoder({ output: (chunk, meta) => muxer.addVideoChunk(chunk, meta), error: (e) => (failure = e) });
  encoder.configure({ codec, width: w, height: h, bitrate, framerate: fps });

  const total = Math.round(job.cfg.duration * fps);
  try {
    for (let i = 0; i < total; i++) {
      checkAbort(job.signal);
      if (failure) throw failure;
      film.seek(g, i / fps);
      const frame = new VideoFrame(canvas, { timestamp: Math.round((i * 1e6) / fps), duration: Math.round(1e6 / fps) });
      encoder.encode(frame, { keyFrame: i % (fps * 2) === 0 });
      frame.close();
      while (encoder.encodeQueueSize > 8) await new Promise((r) => setTimeout(r, 2));
      if (i % 6 === 0) { job.onProgress?.(i / total); await tick(); }
    }
    await encoder.flush();
    if (failure) throw failure;
    if (audio) await encodeAudio(audio, muxer, job.signal);
  } finally {
    if (encoder.state !== "closed") encoder.close();
  }
  muxer.finalize();
  job.onProgress?.(1);
  return new Blob([muxer.target.buffer], { type: "video/mp4" });
}

// AAC soundtrack for the MP4, when sound is on and the browser can encode it.
const AAC = "mp4a.40.2";
async function audioTrack(job: ExportJob) {
  if ((job.cfg.sound?.preset ?? "off") === "off") return null;
  if (typeof AudioEncoder === "undefined") { job.onNote?.("This browser can't encode audio, so the MP4 is silent."); return null; }
  const buffer = await renderSoundtrack(job.cfg, 48000);
  if (!buffer) return null;
  const config: AudioEncoderConfig = { codec: AAC, sampleRate: buffer.sampleRate, numberOfChannels: buffer.numberOfChannels, bitrate: 160_000 };
  if (!(await AudioEncoder.isConfigSupported(config)).supported) { job.onNote?.("This browser can't encode AAC audio, so the MP4 is silent."); return null; }
  return { buffer, config };
}

async function encodeAudio(audio: { buffer: AudioBuffer; config: AudioEncoderConfig }, muxer: Muxer<ArrayBufferTarget>, signal?: AbortSignal) {
  const { buffer } = audio, ch = buffer.numberOfChannels, sr = buffer.sampleRate, block = 4800;
  let failure: unknown = null;
  const enc = new AudioEncoder({ output: (chunk, meta) => muxer.addAudioChunk(chunk, meta), error: (e) => (failure = e) });
  enc.configure(audio.config);
  try {
    const chans = Array.from({ length: ch }, (_, i) => buffer.getChannelData(i));
    for (let off = 0; off < buffer.length; off += block) {
      checkAbort(signal);
      if (failure) throw failure;
      const n = Math.min(block, buffer.length - off), planar = new Float32Array(n * ch);
      chans.forEach((d, i) => planar.set(d.subarray(off, off + n), i * n));
      const data = new AudioData({ format: "f32-planar", sampleRate: sr, numberOfFrames: n, numberOfChannels: ch, timestamp: Math.round((off / sr) * 1e6), data: planar });
      enc.encode(data);
      data.close();
    }
    await enc.flush();
    if (failure) throw failure;
  } finally {
    if (enc.state !== "closed") enc.close();
  }
}

// ------------------------------------------------------------ GIF
export async function exportGif(job: ExportJob, fps: number, maxWidth: number): Promise<Blob> {
  const scale = Math.min(1, maxWidth / job.w);
  const w = Math.round(job.w * scale), h = Math.round(job.h * scale);
  await prepareAssets(job.cfg);
  const film = createFilm(job.cfg, w, h);
  const { g } = frameCanvas(w, h);
  const gif = GIFEncoder();
  const total = Math.round(job.cfg.duration * fps), delay = Math.round(1000 / fps);
  for (let i = 0; i < total; i++) {
    checkAbort(job.signal);
    film.seek(g, i / fps);
    const { data } = g.getImageData(0, 0, w, h);
    const palette = quantize(data, 256);
    gif.writeFrame(applyPalette(data, palette), w, h, { palette, delay, repeat: 0 });
    if (i % 3 === 0) { job.onProgress?.(i / total); await tick(); }
  }
  gif.finish();
  job.onProgress?.(1);
  return new Blob([gif.bytes()], { type: "image/gif" });
}

// ------------------------------------------------------------ PPTX
const SLIDE_W = 13.333, SLIDE_H = 7.5; // LAYOUT_WIDE, inches

export async function exportPptx(job: ExportJob, opts: { mode: "video" | "image"; posterSeconds: number; fps: number }): Promise<Blob> {
  const pptx = new pptxgen();
  pptx.layout = "LAYOUT_WIDE";
  const slide = pptx.addSlide();
  slide.background = { color: job.cfg.style.paper.slice(1) };

  // Fit the asset inside the slide, centred; 16:9 sizes fill it edge to edge.
  const a = job.w / job.h;
  const w = a >= SLIDE_W / SLIDE_H ? SLIDE_W : SLIDE_H * a;
  const h = w / a;
  const pos = { x: (SLIDE_W - w) / 2, y: (SLIDE_H - h) / 2, w, h };

  const posterJob = { ...job, onProgress: undefined };
  const poster = (await blobToDataUrl(await exportPng(posterJob, opts.posterSeconds))).replace(/^data:/, "");
  if (opts.mode === "video") {
    const mp4 = await exportMp4({ ...job, onProgress: (p) => job.onProgress?.(p * 0.95) }, opts.fps);
    const data = (await blobToDataUrl(mp4)).replace(/^data:/, "");
    slide.addMedia({ type: "video", data, cover: poster, extn: "mp4", ...pos });
  } else {
    slide.addImage({ data: poster, ...pos });
  }
  checkAbort(job.signal);
  const out = (await pptx.write({ outputType: "blob" })) as Blob;
  job.onProgress?.(1);
  return out;
}
