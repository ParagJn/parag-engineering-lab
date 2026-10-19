import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { DeckChoice, DeckDesign, DeckOptions, DeckPalette } from "../lib/types";
import { IconCheck, IconDownload, IconX, Spinner } from "./icons";

type Colors = DeckPalette["colors"];
const hex = (h: string) => `#${h}`;
const serif = (d: DeckDesign) => `${d.font}, ${d.font === "Cambria" ? "Georgia, serif" : "sans-serif"}`;

/** A bar chart in miniature; the first bar is the highlighted one. */
function Bars({ c, tall = true }: { c: Colors; tall?: boolean }) {
  const hs = tall ? [0.9, 0.62, 0.45, 0.3] : [0.7, 0.45, 0.55, 0.3, 0.4];
  return (
    <div className="h-full w-full flex items-end gap-[3px]">
      {hs.map((b, i) => (
        <span key={i} className="flex-1 rounded-t-[1px]" style={{ height: `${b * 100}%`, background: hex(i === 0 ? c.accent : c.bar_soft) }} />
      ))}
    </div>
  );
}

const Line = ({ color, w = "100%", o = 1 }: { color: string; w?: string; o?: number }) => (
  <span className="block h-[2px] rounded-full" style={{ background: hex(color), width: w, opacity: o }} />
);

/** Title slide + content slide of a design, painted in the given palette. Mirrors the layouts in backend/deck.py. */
function DesignPreview({ d, c }: { d: DeckDesign; c: Colors }) {
  const head = { fontFamily: serif(d) };
  const frame = "relative flex-1 aspect-[16/9] rounded-md overflow-hidden border border-black/10";

  if (d.id === "editorial") {
    return (
      <div className="flex gap-2">
        <div className={frame} style={{ background: hex(c.page) }}>
          <div className="absolute left-3 top-3 text-[4px] font-bold tracking-widest" style={{ color: hex(c.accent) }}>EXECUTIVE BRIEFING</div>
          <div className="absolute left-3 top-[18px] text-[13px] font-bold leading-[1]" style={{ ...head, color: hex(c.ink) }}>Dashboard<br />title</div>
          <div className="absolute left-3 bottom-3 w-3/5 space-y-[3px]"><Line color={c.muted} /><Line color={c.muted} w="70%" /></div>
        </div>
        <div className={`${frame} p-2`} style={{ background: hex(c.page) }}>
          <div className="text-[6px] font-bold leading-tight" style={{ ...head, color: hex(c.ink) }}>A headline that states the point</div>
          <div className="mt-1.5 flex gap-2 h-[calc(100%-16px)]">
            <div className="flex-[1.8]"><Bars c={c} /></div>
            <div className="flex-1 space-y-1"><Line color={c.accent} w="40%" /><Line color={c.muted} /><Line color={c.muted} w="80%" /></div>
          </div>
        </div>
      </div>
    );
  }

  if (d.id === "split") {
    return (
      <div className="flex gap-2">
        <div className={`${frame} flex`} style={{ background: hex(c.page) }}>
          <div className="relative w-[48%] overflow-hidden" style={{ background: hex(c.dark) }}>
            <span className="absolute -bottom-3 -right-3 w-9 h-9 rounded-full" style={{ background: hex(c.deco1) }} />
            <span className="absolute bottom-0 right-0 w-5 h-5 rounded-full" style={{ background: hex(c.deco2) }} />
            <div className="absolute left-2 top-3 text-[10px] font-bold leading-[1]" style={{ ...head, color: hex(c.dark_ink) }}>Dashboard<br />title</div>
          </div>
          <div className="flex-1 p-2 pt-4 space-y-[3px]"><Line color={c.ink} /><Line color={c.ink} w="80%" /><Line color={c.muted} w="60%" /></div>
        </div>
        <div className={`${frame} flex`} style={{ background: hex(c.page) }}>
          <div className="w-[34%] p-1.5" style={{ background: hex(c.dark) }}>
            <div className="text-[5px] font-bold leading-tight" style={{ ...head, color: hex(c.dark_ink) }}>A headline that states the point</div>
            <div className="mt-1.5 space-y-[3px]"><Line color={c.dark_text} /><Line color={c.dark_text} w="80%" /></div>
          </div>
          <div className="flex-1 p-1.5">
            <div className="h-full rounded-[3px] border p-1" style={{ background: hex(c.surface), borderColor: hex(c.hair) }}><Bars c={c} /></div>
          </div>
        </div>
      </div>
    );
  }

  if (d.id === "focus") {
    return (
      <div className="flex gap-2">
        <div className={`${frame} text-center`} style={{ background: hex(c.dark) }}>
          <span className="absolute -bottom-4 -left-4 w-12 h-12 rounded-full" style={{ background: hex(c.deco1) }} />
          <span className="absolute -top-4 -right-3 w-10 h-10 rounded-full" style={{ background: hex(c.deco2) }} />
          <div className="absolute inset-x-0 top-[34%] text-[11px] font-bold leading-[1]" style={{ ...head, color: hex(c.dark_ink) }}>Dashboard title</div>
          <div className="absolute inset-x-6 bottom-3 space-y-[3px]"><Line color={c.dark_ink} w="100%" o={0.7} /><Line color={c.dark_ink} w="60%" o={0.4} /></div>
        </div>
        <div className={`${frame} p-2 flex flex-col`} style={{ background: hex(c.page) }}>
          <div className="text-[6px] font-bold leading-tight" style={{ ...head, color: hex(c.ink) }}>A headline that states the point</div>
          <div className="mt-1 flex-1 rounded-[3px] border p-1" style={{ background: hex(c.surface), borderColor: hex(c.hair) }}><Bars c={c} tall={false} /></div>
          <div className="mt-1 grid grid-cols-3 gap-1 h-[22%]">
            <Line color={c.muted} w="90%" /><Line color={c.muted} w="90%" />
            <span className="rounded-[2px]" style={{ background: hex(c.accent_soft) }} />
          </div>
        </div>
      </div>
    );
  }

  // classic
  return (
    <div className="flex gap-2">
      <div className={frame} style={{ background: hex(c.dark) }}>
        <span className="absolute -top-5 -right-5 w-14 h-14 rounded-full" style={{ background: hex(c.deco1) }} />
        <span className="absolute -top-2 -right-2 w-8 h-8 rounded-full" style={{ background: hex(c.deco2) }} />
        <div className="absolute left-2.5 top-3 text-[4px] font-bold tracking-widest" style={{ color: hex(c.accent_light) }}>EXECUTIVE BRIEFING</div>
        <div className="absolute left-2.5 top-[20px] text-[11px] font-bold leading-[1.05]" style={{ ...head, color: hex(c.dark_ink) }}>Dashboard title</div>
        <div className="absolute left-2.5 bottom-3 w-3/5 space-y-[3px]"><Line color={c.dark_ink} o={0.85} /><Line color={c.dark_ink} w="70%" o={0.5} /></div>
      </div>
      <div className={`${frame} p-2`} style={{ background: hex(c.page) }}>
        <div className="text-[6px] font-bold leading-tight" style={{ ...head, color: hex(c.ink) }}>A headline that states the point</div>
        <div className="mt-1.5 flex gap-1.5 h-[calc(100%-16px)]">
          <div className="flex-[1.6] rounded-[3px] border p-1" style={{ background: hex(c.surface), borderColor: hex(c.hair) }}><Bars c={c} /></div>
          <div className="flex-1 flex flex-col gap-1">
            <Line color={c.muted} /><Line color={c.muted} w="80%" />
            <span className="mt-auto rounded-[3px] h-[40%]" style={{ background: hex(c.accent_soft) }} />
          </div>
        </div>
      </div>
    </div>
  );
}

function Swatches({ p }: { p: DeckPalette }) {
  const c = p.colors;
  return (
    <div className="flex h-9 rounded-md overflow-hidden border border-black/10">
      {[c.dark, c.accent, c.accent_light, c.bar_soft, c.page].map((col, i) => (
        <span key={i} className="flex-1" style={{ background: hex(col) }} />
      ))}
    </div>
  );
}

const Check = () => (
  <span className="w-5 h-5 rounded-full bg-accent text-white inline-flex items-center justify-center shrink-0">
    <IconCheck className="w-3 h-3" />
  </span>
);

const store = {
  get(k: string): string | null {
    try {
      return localStorage.getItem(k);
    } catch {
      return null;
    }
  },
  set(k: string, v: string) {
    try {
      localStorage.setItem(k, v);
    } catch {
      /* storage blocked */
    }
  },
};

/** Pick a design (slide layout) and a palette (colours) for the executive deck, then download it. */
export function DeckThemePicker({
  dsId,
  scope,
  busy,
  onChoose,
  onClose,
}: {
  dsId: string;
  scope: string;
  busy: boolean;
  onChoose: (c: DeckChoice) => void;
  onClose: () => void;
}) {
  const [opts, setOpts] = useState<DeckOptions | null>(null);
  const [design, setDesign] = useState("");
  const [palette, setPalette] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api
      .deckOptions()
      .then((o) => {
        if (!live) return;
        setOpts(o);
        const d = store.get("dss-deck-design");
        const p = store.get("dss-deck-palette");
        setDesign(o.designs.some((x) => x.id === d) ? d! : o.default_design);
        setPalette(o.palettes.some((x) => x.id === p) ? p! : o.default_palette);
      })
      .catch((e) => live && setErr(e.message));
    return () => {
      live = false;
    };
  }, [dsId, scope]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, busy]);

  const pal = opts?.palettes.find((p) => p.id === palette);

  const go = (regenerate = false) => {
    store.set("dss-deck-design", design);
    store.set("dss-deck-palette", palette);
    onChoose({ design, palette, regenerate });
  };

  const optionCls = (on: boolean) =>
    `text-left rounded-xl p-3 border transition-colors ${on ? "border-accent bg-accent-soft/60 ring-2 ring-accent/30" : "border-hair bg-surface hover:border-line"}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div role="dialog" aria-modal="true" aria-label="Choose a presentation design and colours" className="card w-full max-w-[820px] max-h-[94vh] overflow-auto p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-[17px] font-semibold text-ink">Executive presentation</h2>
            <p className="text-[13px] text-ink-2 mt-0.5">Pick a design and a colour palette. Slides are saved after the first build; use Regenerate slides to have the model write them again.</p>
          </div>
          <button onClick={onClose} disabled={busy} className="p-1.5 rounded-lg text-ink-2 hover:bg-sunken" aria-label="Close">
            <IconX />
          </button>
        </div>

        {err && <p className="mt-4 text-[13px] text-bad">Couldn't load the options: {err}</p>}
        {!opts && !err && (
          <div className="py-16 flex justify-center text-muted">
            <Spinner />
          </div>
        )}

        {opts && pal && (
          <>
            <div className="mt-5 text-[11px] font-semibold tracking-wider text-muted">1 · DESIGN</div>
            <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-3" role="radiogroup" aria-label="Design">
              {opts.designs.map((d) => (
                <button key={d.id} role="radio" aria-checked={d.id === design} onClick={() => setDesign(d.id)} disabled={busy} className={optionCls(d.id === design)}>
                  <DesignPreview d={d} c={pal.colors} />
                  <div className="mt-2.5 flex items-center justify-between gap-2">
                    <div>
                      <div className="text-[13.5px] font-semibold text-ink">{d.name}</div>
                      <div className="text-[12px] text-ink-2">{d.blurb}</div>
                    </div>
                    {d.id === design && <Check />}
                  </div>
                </button>
              ))}
            </div>

            <div className="mt-5 text-[11px] font-semibold tracking-wider text-muted">2 · COLOURS</div>
            <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-3" role="radiogroup" aria-label="Colour palette">
              {opts.palettes.map((p) => (
                <button key={p.id} role="radio" aria-checked={p.id === palette} onClick={() => setPalette(p.id)} disabled={busy} className={optionCls(p.id === palette)}>
                  <Swatches p={p} />
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-[13px] font-semibold text-ink">{p.name}</div>
                      <div className="text-[11.5px] text-ink-2 truncate">{p.blurb}</div>
                    </div>
                    {p.id === palette && <Check />}
                  </div>
                </button>
              ))}
            </div>
          </>
        )}

        <div className="mt-5 flex items-center justify-end gap-2">
          <button onClick={onClose} disabled={busy} className="px-3 py-2 rounded-lg text-[13px] text-ink-2 hover:bg-sunken">
            Cancel
          </button>
          <button
            onClick={() => go(true)}
            disabled={busy || !opts || !design || !palette}
            title="Ask the model to write the slides again instead of reusing the saved ones"
            className="px-3 py-2 rounded-lg text-[13px] text-ink-2 border border-hair hover:bg-sunken disabled:opacity-60"
          >
            Regenerate slides
          </button>
          <button
            onClick={() => go(false)}
            disabled={busy || !opts || !design || !palette}
            className="px-4 py-2 rounded-lg text-[13px] font-medium bg-accent text-white hover:opacity-90 disabled:opacity-60 inline-flex items-center gap-2"
          >
            {busy ? <Spinner className="w-3.5 h-3.5" /> : <IconDownload className="w-3.5 h-3.5" />}
            {busy ? "Building your deck…" : "Download PPTX"}
          </button>
        </div>
      </div>
    </div>
  );
}
