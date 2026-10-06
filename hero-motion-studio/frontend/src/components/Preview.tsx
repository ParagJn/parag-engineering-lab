import { useEffect, useMemo, useRef, useState, type MutableRefObject } from "react";
import { createFilm, sceneOn, timeline } from "../engine/film";
import { KEY_MOMENTS, type MotionConfig } from "../engine/types";

interface Props {
  cfg: MotionConfig;
  w: number;
  h: number;
  fontVersion: number;
  timeRef: MutableRefObject<number>;
}

const PREVIEW_MAX = { w: 1280, h: 720 };

export default function Preview({ cfg, w, h, fontVersion, timeRef }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [playing, setPlaying] = useState(true);
  const [t, setT] = useState(0);

  // Preview renders at a capped resolution; exports always use the full size.
  const s = Math.min(1, PREVIEW_MAX.w / w, PREVIEW_MAX.h / h);
  const pw = Math.max(2, Math.round(w * s)), ph = Math.max(2, Math.round(h * s));
  // fontVersion forces a re-layout once a web font finishes loading.
  const film = useMemo(() => createFilm(cfg, pw, ph), [cfg, pw, ph, fontVersion]);

  const filmRef = useRef(film);
  const playRef = useRef({ playing, base: performance.now() - timeRef.current * 1000 });
  filmRef.current = film;

  useEffect(() => {
    let raf = 0;
    const loop = () => {
      const p = playRef.current, dur = filmRef.current.duration;
      if (p.playing) timeRef.current = (((performance.now() - p.base) / 1000) % dur + dur) % dur;
      const g = canvasRef.current?.getContext("2d");
      if (g) filmRef.current.seek(g, timeRef.current);
      setT(timeRef.current);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [timeRef]);

  const seekTo = (sec: number) => {
    const dur = film.duration;
    timeRef.current = ((sec % dur) + dur) % dur;
    playRef.current.base = performance.now() - timeRef.current * 1000;
  };
  const toggle = () => {
    playRef.current.playing = !playRef.current.playing;
    playRef.current.base = performance.now() - timeRef.current * 1000;
    setPlaying(playRef.current.playing);
  };
  const pause = () => { playRef.current.playing = false; setPlaying(false); };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.code === "Space") { e.preventDefault(); toggle(); }
      else if (e.key === "ArrowRight") { pause(); seekTo(timeRef.current + 1 / 60); }
      else if (e.key === "ArrowLeft") { pause(); seekTo(timeRef.current - 1 / 60); }
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  });

  const tl = timeline(cfg);

  return (
    <div className="flex flex-col gap-3">
      <div className="checker flex items-center justify-center rounded-lg border border-neutral-800 p-4" style={{ minHeight: 320 }}>
        <canvas
          ref={canvasRef}
          width={pw}
          height={ph}
          className="block max-h-[62vh] max-w-full shadow-2xl"
          style={{ aspectRatio: `${w} / ${h}` }}
        />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button className="btn w-24" onClick={toggle}>{playing ? "❚❚ Pause" : "▶ Play"}</button>
        <input
          type="range"
          className="min-w-[200px] flex-1 accent-[var(--accent)]"
          min={0}
          max={film.duration}
          step={1 / 60}
          value={t}
          onChange={(e) => { pause(); seekTo(+e.target.value); }}
        />
        <span className="w-28 text-right text-sm tabular-nums text-neutral-400">
          {t.toFixed(2)}s / {film.duration.toFixed(1)}s
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {KEY_MOMENTS.filter((k) => !k.scene || sceneOn(cfg, k.scene)).map((k) => (
          <button key={k.id} className="chip" onClick={() => { pause(); seekTo(tl.toSeconds(k.t)); }}>
            {k.name}
          </button>
        ))}
        <span className="self-center text-xs text-neutral-500">Space play/pause · ←/→ one frame</span>
      </div>
    </div>
  );
}
