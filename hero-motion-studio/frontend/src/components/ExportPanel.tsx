import { useRef, useState, type MutableRefObject } from "react";
import { sceneOn, timeline } from "../engine/film";
import { KEY_MOMENTS, type MotionConfig } from "../engine/types";
import { exportGif, exportMp4, exportPng, exportPptx, saveBlob, type ExportJob } from "../export/exporters";

interface Props {
  cfg: MotionConfig;
  w: number;
  h: number;
  sizeId: string;
  timeRef: MutableRefObject<number>;
}

type Format = "png" | "mp4" | "gif" | "pptx";

const FORMATS: { id: Format; name: string; note: string }[] = [
  { id: "png", name: "PNG still", note: "Static hero image" },
  { id: "mp4", name: "MP4 video", note: "Plays inline in PowerPoint & Keynote" },
  { id: "gif", name: "GIF", note: "Google Slides, email" },
  { id: "pptx", name: "PPTX slide", note: "Ready-made slide" },
];

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "hero";

export default function ExportPanel({ cfg, w, h, sizeId, timeRef }: Props) {
  const [format, setFormat] = useState<Format>("mp4");
  const [frame, setFrame] = useState("current");
  const [fps, setFps] = useState(60);
  const [gifFps, setGifFps] = useState(20);
  const [gifWidth, setGifWidth] = useState(960);
  const [pptMode, setPptMode] = useState<"video" | "image">("video");
  const [progress, setProgress] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  const moments = KEY_MOMENTS.filter((k) => !k.scene || sceneOn(cfg, k.scene));
  const frameSeconds = () => (frame === "current" ? timeRef.current : timeline(cfg).toSeconds((moments.find((k) => k.id === frame) ?? moments[moments.length - 1]).t));
  const base = `${slug(cfg.text.hero)}-${sizeId}-${w}x${h}`;

  const run = async () => {
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setProgress(0);
    setMessage("");
    const job: ExportJob = { cfg, w, h, signal: ctrl.signal, onProgress: setProgress };
    const started = performance.now();
    try {
      let blob: Blob, name: string;
      if (format === "png") { blob = await exportPng(job, frameSeconds()); name = `${base}.png`; }
      else if (format === "mp4") { blob = await exportMp4(job, fps); name = `${base}-${fps}fps.mp4`; }
      else if (format === "gif") { blob = await exportGif(job, gifFps, gifWidth); name = `${base}.gif`; }
      else { blob = await exportPptx(job, { mode: pptMode, posterSeconds: frameSeconds(), fps }); name = `${base}.pptx`; }
      saveBlob(blob, name);
      setMessage(`Saved ${name} · ${(blob.size / 1e6).toFixed(1)} MB · ${((performance.now() - started) / 1000).toFixed(1)}s`);
    } catch (e) {
      setMessage(e instanceof DOMException && e.name === "AbortError" ? "Export cancelled." : `Export failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setProgress(null);
      abortRef.current = null;
    }
  };

  const needsFrame = format === "png" || format === "pptx";
  const busy = progress !== null;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-neutral-800 bg-neutral-950 p-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-xs font-extrabold uppercase tracking-widest text-neutral-400">Export</h2>
        <span className="text-xs text-neutral-500 tabular-nums">{w}×{h}</span>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {FORMATS.map((fo) => (
          <button
            key={fo.id}
            className={`rounded-md border p-2 text-left ${format === fo.id ? "border-[var(--accent)] bg-neutral-900" : "border-neutral-800 hover:border-neutral-600"}`}
            onClick={() => setFormat(fo.id)}
          >
            <div className="text-sm font-bold">{fo.name}</div>
            <div className="text-xs text-neutral-500">{fo.note}</div>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        {format === "pptx" && (
          <select className="input w-auto" value={pptMode} onChange={(e) => setPptMode(e.target.value as "video" | "image")}>
            <option value="video">Animated video + poster</option>
            <option value="image">Still image only</option>
          </select>
        )}
        {needsFrame && (
          <label className="flex items-center gap-2">
            <span className="text-neutral-400">{format === "pptx" ? "Poster frame" : "Frame"}</span>
            <select className="input w-auto" value={frame} onChange={(e) => setFrame(e.target.value)}>
              <option value="current">Current preview frame</option>
              {moments.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
            </select>
          </label>
        )}
        {(format === "mp4" || (format === "pptx" && pptMode === "video")) && (
          <label className="flex items-center gap-2">
            <span className="text-neutral-400">Frame rate</span>
            <select className="input w-auto" value={fps} onChange={(e) => setFps(+e.target.value)}>
              <option value={30}>30 fps</option>
              <option value={60}>60 fps</option>
            </select>
          </label>
        )}
        {format === "gif" && (
          <>
            <label className="flex items-center gap-2">
              <span className="text-neutral-400">Frame rate</span>
              <select className="input w-auto" value={gifFps} onChange={(e) => setGifFps(+e.target.value)}>
                {[15, 20, 25].map((v) => <option key={v} value={v}>{v} fps</option>)}
              </select>
            </label>
            <label className="flex items-center gap-2">
              <span className="text-neutral-400">Max width</span>
              <select className="input w-auto" value={gifWidth} onChange={(e) => setGifWidth(+e.target.value)}>
                {[480, 720, 960, 1280].map((v) => <option key={v} value={v}>{v}px</option>)}
              </select>
            </label>
          </>
        )}
        <div className="ml-auto flex gap-2">
          {busy && <button className="btn" onClick={() => abortRef.current?.abort()}>Cancel</button>}
          <button className="btn btn-primary" disabled={busy} onClick={run}>
            {busy ? `Rendering ${Math.round((progress ?? 0) * 100)}%` : "Export"}
          </button>
        </div>
      </div>

      {busy && (
        <div className="h-1.5 overflow-hidden rounded bg-neutral-800">
          <div className="h-full bg-[var(--accent)] transition-[width]" style={{ width: `${(progress ?? 0) * 100}%` }} />
        </div>
      )}
      {message && <p className="text-xs text-neutral-400">{message}</p>}
      {format === "gif" && <p className="text-xs text-neutral-500">GIFs are large and limited to 256 colours; prefer MP4 for PowerPoint and Keynote.</p>}
    </div>
  );
}
