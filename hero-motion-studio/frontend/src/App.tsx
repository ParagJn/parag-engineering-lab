import { useEffect, useRef, useState } from "react";
import AiBrief from "./components/AiBrief";
import ControlsPanel from "./components/ControlsPanel";
import ExportPanel from "./components/ExportPanel";
import Preview from "./components/Preview";
import { loadFont } from "./engine/film";
import { DEFAULT_CONFIG, SHAPE_STYLES, SIZES, STAT_STYLES, WORDS_STYLES, type MotionConfig } from "./engine/types";

const STORE_KEY = "hero-motion-studio:v1";

function loadSaved(): { cfg: MotionConfig; sizeId: string; custom: { w: number; h: number } } {
  const fallback = { cfg: DEFAULT_CONFIG, sizeId: "hero", custom: { w: 1600, h: 900 } };
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return fallback;
    const s = JSON.parse(raw);
    const sc = { ...DEFAULT_CONFIG.scenes, ...s.cfg?.scenes, show: { ...DEFAULT_CONFIG.scenes.show, ...s.cfg?.scenes?.show } };
    if (!STAT_STYLES.some((o) => o.id === sc.stat)) sc.stat = DEFAULT_CONFIG.scenes.stat;
    if (!SHAPE_STYLES.some((o) => o.id === sc.shape)) sc.shape = DEFAULT_CONFIG.scenes.shape;
    if (!WORDS_STYLES.some((o) => o.id === sc.words)) sc.words = DEFAULT_CONFIG.scenes.words;
    return {
      cfg: { ...DEFAULT_CONFIG, ...s.cfg, text: { ...DEFAULT_CONFIG.text, ...s.cfg?.text }, style: { ...DEFAULT_CONFIG.style, ...s.cfg?.style }, scenes: sc, sound: { enabled: false } },
      sizeId: SIZES.some((z) => z.id === s.sizeId) ? s.sizeId : "hero",
      custom: s.custom ?? fallback.custom,
    };
  } catch {
    return fallback;
  }
}

const even = (v: number) => Math.max(160, Math.min(4096, Math.round(v / 2) * 2));

export default function App() {
  const saved = useRef(loadSaved()).current;
  const [cfg, setCfg] = useState<MotionConfig>(saved.cfg);
  const [sizeId, setSizeId] = useState(saved.sizeId);
  const [custom, setCustom] = useState(saved.custom);
  const [fontVersion, setFontVersion] = useState(0);
  const timeRef = useRef(0);

  useEffect(() => {
    try { localStorage.setItem(STORE_KEY, JSON.stringify({ cfg, sizeId, custom })); } catch { /* storage unavailable */ }
  }, [cfg, sizeId, custom]);

  useEffect(() => {
    let live = true;
    loadFont(cfg.style.font).then(() => live && setFontVersion((v) => v + 1));
    return () => { live = false; };
  }, [cfg.style.font]);

  const size = SIZES.find((z) => z.id === sizeId)!;
  const w = sizeId === "custom" ? even(custom.w) : size.w;
  const h = sizeId === "custom" ? even(custom.h) : size.h;

  return (
    <div className="min-h-screen" style={{ ["--accent" as string]: cfg.style.accent }}>
      <header className="flex items-center gap-3 border-b border-neutral-800 px-5 py-3">
        <span className="h-4 w-4 rounded-full" style={{ background: cfg.style.accent }} />
        <h1 className="text-base font-extrabold tracking-tight">Hero Motion Studio</h1>
        <span className="text-sm text-neutral-500">Animated hero images for presentations</span>
        <button className="btn ml-auto text-xs" onClick={() => { setCfg(DEFAULT_CONFIG); setSizeId("hero"); }}>Reset</button>
      </header>

      <div className="grid gap-6 p-5 lg:grid-cols-[380px_1fr]">
        <aside className="flex flex-col gap-4 lg:max-h-[calc(100vh-90px)] lg:overflow-y-auto lg:pr-2">
          <AiBrief setCfg={setCfg} />
          <ControlsPanel cfg={cfg} setCfg={setCfg} />
        </aside>

        <main className="flex min-w-0 flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            {SIZES.map((z) => (
              <button
                key={z.id}
                title={z.note}
                className={`rounded-md border px-3 py-1.5 text-left ${sizeId === z.id ? "border-[var(--accent)] bg-neutral-900" : "border-neutral-800 hover:border-neutral-600"}`}
                onClick={() => setSizeId(z.id)}
              >
                <div className="text-sm font-bold">{z.name}</div>
                <div className="text-xs text-neutral-500 tabular-nums">{z.id === "custom" ? `${w}×${h}` : `${z.w}×${z.h}`} · {z.note}</div>
              </button>
            ))}
          </div>
          {sizeId === "custom" && (
            <div className="flex items-center gap-2 text-sm">
              <input className="input w-24" type="number" min={160} max={4096} step={2} value={custom.w} onChange={(e) => setCustom({ ...custom, w: +e.target.value })} />
              <span className="text-neutral-500">×</span>
              <input className="input w-24" type="number" min={160} max={4096} step={2} value={custom.h} onChange={(e) => setCustom({ ...custom, h: +e.target.value })} />
              <span className="text-xs text-neutral-500">px, even numbers, up to 4096</span>
            </div>
          )}

          <Preview cfg={cfg} w={w} h={h} fontVersion={fontVersion} timeRef={timeRef} />
          <ExportPanel cfg={cfg} w={w} h={h} sizeId={sizeId} timeRef={timeRef} />
        </main>
      </div>
    </div>
  );
}
