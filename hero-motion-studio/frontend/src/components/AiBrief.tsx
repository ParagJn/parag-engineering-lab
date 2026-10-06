import { useEffect, useState } from "react";
import type { MotionConfig } from "../engine/types";
import { getHealth, suggest, type Health } from "../lib/api";
import { Section } from "./ControlsPanel";

interface Props {
  setCfg: (fn: (c: MotionConfig) => MotionConfig) => void;
}

const TONES = ["confident", "playful", "executive", "technical", "bold"];

export default function AiBrief({ setCfg }: Props) {
  const [health, setHealth] = useState<Health | null | undefined>(undefined);
  const [brief, setBrief] = useState("");
  const [tone, setTone] = useState("confident");
  const [useAccent, setUseAccent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { getHealth().then(setHealth); }, []);

  const run = async () => {
    setBusy(true);
    setError("");
    try {
      const s = await suggest(brief, tone);
      setCfg((c) => ({
        ...c,
        text: { intro: s.intro, hero: s.hero, stat: s.stat, words: s.words, cardTitle: s.card_title, cardSubtitle: s.card_subtitle, cardFootnote: s.card_footnote },
        style: useAccent && s.accent ? { ...c.style, accent: s.accent } : c.style,
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const status =
    health === undefined ? "checking…" : health === null ? "backend offline" : health.ai_configured ? health.model : "IBM ICA not configured";
  const ready = !!health?.ai_configured;

  return (
    <Section title="Write it with AI">
      <textarea
        className="input min-h-[84px] resize-y"
        placeholder="What's the slide about? e.g. “Kickoff deck for our Q3 cloud migration, cut infra cost by 30%”"
        value={brief}
        maxLength={2000}
        onChange={(e) => setBrief(e.target.value)}
      />
      <div className="flex flex-wrap items-center gap-2">
        <select className="input w-auto" value={tone} onChange={(e) => setTone(e.target.value)}>
          {TONES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <label className="flex items-center gap-1.5 text-sm text-neutral-400">
          <input type="checkbox" checked={useAccent} onChange={(e) => setUseAccent(e.target.checked)} /> AI accent colour
        </label>
        <button className="btn btn-primary ml-auto" disabled={!ready || busy || brief.trim().length < 3} onClick={run}>
          {busy ? "Writing…" : "Generate copy"}
        </button>
      </div>
      <p className="text-xs text-neutral-500">
        <span className={`mr-1 inline-block h-2 w-2 rounded-full ${ready ? "bg-green-500" : "bg-neutral-600"}`} />
        {status}
      </p>
      {error && <p className="rounded-md border border-red-900 bg-red-950/40 p-2 text-xs text-red-300">{error}</p>}
    </Section>
  );
}
