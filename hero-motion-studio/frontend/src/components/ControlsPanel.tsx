import { timeline, type SceneId } from "../engine/film";
import { ACCENTS, FONTS, SHAPE_STYLES, STAT_STYLES, THEMES, WORDS_STYLES, type MotionConfig, type MotionText } from "../engine/types";

interface Props {
  cfg: MotionConfig;
  setCfg: (fn: (c: MotionConfig) => MotionConfig) => void;
}

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3 border-t border-neutral-800 pt-4">
      <h2 className="text-xs font-extrabold uppercase tracking-widest text-neutral-400">{title}</h2>
      {children}
    </section>
  );
}

function Choices<T extends string>({ options, value, onChange }: { options: { id: T; name: string; note: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {options.map((o) => (
        <button
          key={o.id}
          className={`rounded-md border p-2 text-left ${value === o.id ? "border-[var(--accent)] bg-neutral-900" : "border-neutral-800 hover:border-neutral-600"}`}
          onClick={() => onChange(o.id)}
        >
          <div className="text-sm font-bold">{o.name}</div>
          <div className="text-xs leading-snug text-neutral-500">{o.note}</div>
        </button>
      ))}
    </div>
  );
}

const SCENE_SWITCHES: { id: SceneId; name: string }[] = [
  { id: "stat", name: "Stat" },
  { id: "shape", name: "Shape" },
  { id: "words", name: "Words" },
  { id: "card", name: "End card" },
];

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-sm text-neutral-300">
        {label} {hint && <span className="text-xs text-neutral-500">· {hint}</span>}
      </span>
      {children}
    </label>
  );
}

export default function ControlsPanel({ cfg, setCfg }: Props) {
  const setText = <K extends keyof MotionText>(k: K, v: MotionText[K]) => setCfg((c) => ({ ...c, text: { ...c.text, [k]: v } }));
  const setStyle = (patch: Partial<MotionConfig["style"]>) => setCfg((c) => ({ ...c, style: { ...c.style, ...patch } }));
  const { text, style } = cfg;
  const show = cfg.scenes.show;
  const setShow = (id: SceneId, on: boolean) => setCfg((c) => ({ ...c, scenes: { ...c.scenes, show: { ...c.scenes.show, [id]: on } } }));
  const natural = Math.round(timeline(cfg).natural * 2) / 2;

  return (
    <>
      <Section title="Text">
        <div className="grid grid-cols-[1fr_2fr] gap-2">
          <Field label="Intro"><input className="input" value={text.intro} maxLength={14} onChange={(e) => setText("intro", e.target.value)} /></Field>
          <Field label="Hero word" hint="an i or j gets the dot"><input className="input" value={text.hero} maxLength={24} onChange={(e) => setText("hero", e.target.value)} /></Field>
        </div>
        <Field label="Stat" hint="graph overshoots by this %"><input className="input" value={text.stat} maxLength={8} onChange={(e) => setText("stat", e.target.value)} /></Field>
        <Field label="Orbit words" hint="comma separated, 3–6">
          <input
            className="input"
            value={text.words.join(", ")}
            onChange={(e) => setText("words", e.target.value.split(",").map((w) => w.trimStart()).slice(0, 6))}
            onBlur={(e) => setText("words", e.target.value.split(",").map((w) => w.trim().toUpperCase()).filter(Boolean).slice(0, 6))}
          />
        </Field>
        <Field label="End card title" hint="blank = hero"><input className="input" value={text.cardTitle} maxLength={24} placeholder={text.hero} onChange={(e) => setText("cardTitle", e.target.value)} /></Field>
        <Field label="End card subtitle"><input className="input" value={text.cardSubtitle} maxLength={44} onChange={(e) => setText("cardSubtitle", e.target.value)} /></Field>
        <Field label="End card footnote"><input className="input" value={text.cardFootnote} maxLength={32} onChange={(e) => setText("cardFootnote", e.target.value)} /></Field>
      </Section>

      <Section title="Scenes">
        <span className="text-sm text-neutral-300">In the loop <span className="text-xs text-neutral-500">· toggle and hero word are always on</span></span>
        <div className="flex flex-wrap gap-2">
          {SCENE_SWITCHES.map((sc) => (
            <button key={sc.id} className={`chip ${show[sc.id] ? "chip-on" : "line-through opacity-60"}`} onClick={() => setShow(sc.id, !show[sc.id])}>
              {show[sc.id] ? "✓ " : ""}{sc.name}
            </button>
          ))}
        </div>
        {show.stat && (
          <>
            <span className="text-sm text-neutral-300">How the stat is shown</span>
            <Choices options={STAT_STYLES} value={cfg.scenes.stat} onChange={(stat) => setCfg((c) => ({ ...c, scenes: { ...c.scenes, stat } }))} />
          </>
        )}
        {show.shape && (
          <>
            <span className="text-sm text-neutral-300">Shape</span>
            <Choices options={SHAPE_STYLES} value={cfg.scenes.shape} onChange={(shape) => setCfg((c) => ({ ...c, scenes: { ...c.scenes, shape } }))} />
          </>
        )}
        {show.words && (
          <>
            <span className="text-sm text-neutral-300">How the words move</span>
            <Choices options={WORDS_STYLES} value={cfg.scenes.words} onChange={(words) => setCfg((c) => ({ ...c, scenes: { ...c.scenes, words } }))} />
          </>
        )}
      </Section>

      <Section title="Style">
        <div className="grid grid-cols-2 gap-2">
          {THEMES.map((th) => (
            <button
              key={th.id}
              className={`flex items-center gap-2 rounded-md border px-2 py-1.5 text-left text-sm ${style.theme === th.id ? "border-[var(--accent)]" : "border-neutral-800 hover:border-neutral-600"}`}
              onClick={() => setStyle({ theme: th.id, paper: th.paper, ink: th.ink })}
            >
              <span className="flex h-5 w-8 overflow-hidden rounded-sm border border-neutral-700">
                <span className="flex-1" style={{ background: th.paper }} />
                <span className="flex-1" style={{ background: th.ink }} />
              </span>
              {th.name}
            </button>
          ))}
        </div>
        <Field label="Accent">
          <div className="flex items-center gap-2">
            {ACCENTS.map((a) => (
              <button
                key={a}
                aria-label={a}
                className={`h-7 w-7 rounded-full border-2 ${style.accent.toLowerCase() === a.toLowerCase() ? "border-white" : "border-transparent"}`}
                style={{ background: a }}
                onClick={() => setStyle({ accent: a })}
              />
            ))}
            <input type="color" className="h-7 w-10 cursor-pointer rounded border border-neutral-700 bg-transparent" value={style.accent} onChange={(e) => setStyle({ accent: e.target.value })} />
          </div>
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Background"><input type="color" className="h-8 w-full cursor-pointer rounded border border-neutral-700 bg-transparent" value={style.paper} onChange={(e) => setStyle({ paper: e.target.value, theme: "custom" })} /></Field>
          <Field label="Ink"><input type="color" className="h-8 w-full cursor-pointer rounded border border-neutral-700 bg-transparent" value={style.ink} onChange={(e) => setStyle({ ink: e.target.value, theme: "custom" })} /></Field>
        </div>
        <Field label="Font">
          <select className="input" value={style.font} onChange={(e) => setStyle({ font: e.target.value })}>
            {FONTS.map((fo) => <option key={fo} value={fo}>{fo}</option>)}
          </select>
        </Field>
      </Section>

      <Section title="Timing">
        <Field label={`Duration · ${cfg.duration.toFixed(1)}s per loop`} hint="all scenes scale together">
          <input type="range" className="accent-[var(--accent)]" min={6} max={30} step={0.5} value={cfg.duration} onChange={(e) => setCfg((c) => ({ ...c, duration: +e.target.value }))} />
        </Field>
        <p className="text-xs text-neutral-500">
          Designed pace for these scenes: {natural.toFixed(1)}s
          {Math.abs(cfg.duration - natural) > 0.25 && (
            <button className="ml-2 text-[var(--accent)] hover:underline" onClick={() => setCfg((c) => ({ ...c, duration: natural }))}>use it</button>
          )}
        </p>
        <div className="flex gap-2">
          {[8, 10, 15, 20].map((d) => (
            <button key={d} className={`chip ${cfg.duration === d ? "chip-on" : ""}`} onClick={() => setCfg((c) => ({ ...c, duration: d }))}>{d}s</button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-neutral-500" title="Sound will be added in a later version">
          <input type="checkbox" disabled checked={cfg.sound.enabled} readOnly /> Sound track <span className="text-xs">(coming later)</span>
        </label>
      </Section>
    </>
  );
}
