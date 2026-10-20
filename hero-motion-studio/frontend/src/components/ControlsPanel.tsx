import { useState } from "react";
import { timeline, type SceneId } from "../engine/film";
import { bufferToWav, renderSoundtrack } from "../engine/sound";
import { saveBlob } from "../export/exporters";
import { ACCENTS, FEEL_OPTIONS, FILM_OPTIONS, FONTS, REVEAL_STYLES, SHAPE_STYLES, SOUND_PRESETS, STAT_STYLES, THEMES, WORDS_STYLES, type MotionConfig, type MotionText } from "../engine/types";

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
  const { text, style, outro } = cfg;
  const story = cfg.film === "story";
  const setStory = <K extends keyof MotionConfig["story"]>(k: K, v: string) => setCfg((c) => ({ ...c, story: { ...c.story, [k]: v } }));
  const [logoError, setLogoError] = useState("");
  const [wavBusy, setWavBusy] = useState(false);
  const downloadWav = async () => {
    setWavBusy(true);
    try {
      const buf = await renderSoundtrack(cfg);
      if (buf) saveBlob(bufferToWav(buf), `${(text.hero || "hero").toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${cfg.sound.preset}.wav`);
    } finally { setWavBusy(false); }
  };
  const setOutro = (patch: Partial<MotionConfig["outro"]>) => setCfg((c) => ({ ...c, outro: { ...c.outro, ...patch } }));
  const onLogo = (file: File | undefined) => {
    setLogoError("");
    if (!file) return;
    if (file.size > 2_000_000) { setLogoError("Logo is over 2 MB — please use an SVG or a smaller PNG."); return; }
    const r = new FileReader();
    r.onload = () => setOutro({ logo: String(r.result), logoName: file.name });
    r.onerror = () => setLogoError("Could not read that file.");
    r.readAsDataURL(file);
  };
  const show = cfg.scenes.show;
  const setShow = (id: SceneId, on: boolean) => setCfg((c) => ({ ...c, scenes: { ...c.scenes, show: { ...c.scenes.show, [id]: on } } }));
  const natural = timeline(cfg).natural;
  const setMotion = (patch: Partial<MotionConfig["motion"]>) => setCfg((c) => ({ ...c, motion: { ...c.motion, ...patch } }));

  return (
    <>
      <Section title="Film">
        <Choices options={FILM_OPTIONS} value={cfg.film} onChange={(film) => setCfg((c) => ({ ...c, film }))} />
        {story && (
          <div className="flex flex-col gap-2 rounded-md border border-neutral-800 p-2.5">
            <p className="text-xs text-neutral-500">
              <b className="text-neutral-300">Hook</b> = intro + hero word · <b className="text-neutral-300">Proof</b> = your stat ·{" "}
              <b className="text-neutral-300">Close</b> = end card (or logo sweep)
            </p>
            <Field label="Problem" hint="the pain, one line">
              <input className="input" value={cfg.story.problem} maxLength={60} placeholder="e.g. Month-end reports take three days." onChange={(e) => setStory("problem", e.target.value)} />
            </Field>
            <div className="grid grid-cols-[1fr_2fr] gap-2">
              <Field label="Lead-in"><input className="input" value={cfg.story.lead} maxLength={20} placeholder="Introducing" onChange={(e) => setStory("lead", e.target.value)} /></Field>
              <Field label="Solution" hint="on the badge"><input className="input" value={cfg.story.solution} maxLength={28} onChange={(e) => setStory("solution", e.target.value)} /></Field>
            </div>
            <Field label="Proof caption" hint="what the stat means">
              <input className="input" value={cfg.story.proofLabel} maxLength={40} placeholder="e.g. faster month-end close" onChange={(e) => setStory("proofLabel", e.target.value)} />
            </Field>
          </div>
        )}
      </Section>

      <Section title="Text">
        <div className="grid grid-cols-[1fr_2fr] gap-2">
          <Field label="Intro"><input className="input" value={text.intro} maxLength={14} onChange={(e) => setText("intro", e.target.value)} /></Field>
          <Field label="Hero word" hint="an i or j gets the dot"><input className="input" value={text.hero} maxLength={24} onChange={(e) => setText("hero", e.target.value)} /></Field>
        </div>
        <div className="flex flex-col gap-2 rounded-md border border-neutral-800 p-2.5">
          <span className="text-sm text-neutral-300">Ending <span className="text-xs text-neutral-500">· the last frame</span></span>
          <div className="flex gap-2">
            {(["toggle", "logo"] as const).map((m) => (
              <button key={m} className={`chip ${outro.mode === m ? "chip-on" : ""}`} onClick={() => setOutro({ mode: m })}>
                {m === "toggle" ? "Toggle row" : "Logo sweep"}
              </button>
            ))}
          </div>
          {outro.mode === "toggle" ? (
            <Field label="Ending word" hint="ending + hero word · blank = loops back to intro">
              <input className="input" value={text.ending} maxLength={16} placeholder={text.intro || "e.g. Thank you"} onChange={(e) => setText("ending", e.target.value)} />
            </Field>
          ) : (
            <>
              <p className="text-xs text-neutral-500">Your logo is revealed left to right by a data sweep, then holds, 1.5 × 1.5 in at slide centre. Use an official file you are authorised to use (SVG or transparent PNG).</p>
              <div className="flex items-center gap-2">
                <label className="btn cursor-pointer">
                  {outro.logo ? "Replace logo" : "Upload logo"}
                  <input type="file" accept="image/svg+xml,image/png,image/webp,image/jpeg" className="hidden" onChange={(e) => onLogo(e.target.files?.[0])} />
                </label>
                {outro.logo && (
                  <>
                    <img src={outro.logo} alt="" className="h-8 max-w-24 rounded bg-neutral-200 object-contain p-1" />
                    <span className="min-w-0 flex-1 truncate text-xs text-neutral-400">{outro.logoName}</span>
                    <button className="text-xs text-neutral-500 hover:text-neutral-300" onClick={() => setOutro({ logo: "", logoName: "" })}>Remove</button>
                  </>
                )}
              </div>
              {logoError && <p className="text-xs text-red-400">{logoError}</p>}
              {!outro.logo && <p className="text-xs text-amber-400/80">Until a logo is uploaded, the film ends on the toggle row.</p>}
            </>
          )}
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
          {SCENE_SWITCHES.filter((sc) => !(story && sc.id === "words")).map((sc) => (
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
        {show.shape && !story && (
          <>
            <span className="text-sm text-neutral-300">Shape</span>
            <Choices options={SHAPE_STYLES} value={cfg.scenes.shape} onChange={(shape) => setCfg((c) => ({ ...c, scenes: { ...c.scenes, shape } }))} />
          </>
        )}
        {show.words && !story && (
          <>
            <span className="text-sm text-neutral-300">How the words move</span>
            <Choices options={WORDS_STYLES} value={cfg.scenes.words} onChange={(words) => setCfg((c) => ({ ...c, scenes: { ...c.scenes, words } }))} />
          </>
        )}
        {show.card && (
          <>
            <span className="text-sm text-neutral-300">End-card reveal</span>
            <Choices options={REVEAL_STYLES} value={cfg.scenes.reveal} onChange={(reveal) => setCfg((c) => ({ ...c, scenes: { ...c.scenes, reveal } }))} />
          </>
        )}
      </Section>

      <Section title="Motion">
        <span className="text-sm text-neutral-300">Feel</span>
        <Choices options={FEEL_OPTIONS} value={cfg.motion.feel} onChange={(feel) => setMotion({ feel })} />
        <label className="flex items-start gap-2 text-sm text-neutral-300">
          <input type="checkbox" className="mt-1" checked={cfg.motion.readable} onChange={(e) => setMotion({ readable: e.target.checked })} />
          <span>Readable holds <span className="block text-xs text-neutral-500">Text stays on screen long enough to read: longer for more words</span></span>
        </label>
        <label className="flex items-start gap-2 text-sm text-neutral-300">
          <input type="checkbox" className="mt-1" checked={cfg.motion.camera} onChange={(e) => setMotion({ camera: e.target.checked })} />
          <span>Camera glide <span className="block text-xs text-neutral-500">A near-invisible push-in that adds depth; loops seamlessly</span></span>
        </label>
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
        <Field label={`Duration · ${(cfg.autoDuration ? natural : cfg.duration).toFixed(1)}s per loop${cfg.autoDuration ? " (auto)" : ""}`} hint="all scenes scale together">
          <input type="range" className="accent-[var(--accent)]" min={6} max={30} step={0.5} value={cfg.autoDuration ? natural : cfg.duration} onChange={(e) => setCfg((c) => ({ ...c, duration: +e.target.value, autoDuration: false }))} />
        </Field>
        <p className="text-xs text-neutral-500">
          {cfg.autoDuration ? "Auto follows the designed pace, including reading holds." : `Designed pace for these scenes: ${natural.toFixed(1)}s`}
        </p>
        <div className="flex flex-wrap gap-2">
          <button className={`chip ${cfg.autoDuration ? "chip-on" : ""}`} onClick={() => setCfg((c) => ({ ...c, autoDuration: true }))}>Auto</button>
          {[8, 10, 15, 20].map((d) => (
            <button key={d} className={`chip ${!cfg.autoDuration && cfg.duration === d ? "chip-on" : ""}`} onClick={() => setCfg((c) => ({ ...c, duration: d, autoDuration: false }))}>{d}s</button>
          ))}
        </div>
      </Section>

      <Section title="Sound">
        <Choices options={SOUND_PRESETS} value={cfg.sound.preset} onChange={(preset) => setCfg((c) => ({ ...c, sound: { ...c.sound, preset } }))} />
        {cfg.sound.preset !== "off" && (
          <>
            <Field label={`Volume · ${Math.round(cfg.sound.volume * 100)}%`}>
              <input type="range" className="accent-[var(--accent)]" min={0} max={1} step={0.05} value={cfg.sound.volume} onChange={(e) => setCfg((c) => ({ ...c, sound: { ...c.sound, volume: +e.target.value } }))} />
            </Field>
            <div className="flex items-center gap-2">
              <button className="btn text-xs" disabled={wavBusy} onClick={downloadWav}>{wavBusy ? "Rendering…" : "Download WAV"}</button>
              <span className="text-xs text-neutral-500">Plays in the preview and is embedded in MP4 / PPTX. GIFs are silent.</span>
            </div>
          </>
        )}
      </Section>
    </>
  );
}
