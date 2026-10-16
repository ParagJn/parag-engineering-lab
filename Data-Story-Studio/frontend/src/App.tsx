import { useEffect, useState } from "react";
import { DashboardPage } from "./dashboard/DashboardPage";
import { Spinner } from "./dashboard/icons";
import { api } from "./lib/api";
import type { DatasetSummary } from "./lib/types";
import { Readiness } from "./setup/Readiness";
import { Upload } from "./setup/Upload";

type View = { name: "upload" } | { name: "setup"; id: string } | { name: "dashboard"; id: string };

function parseHash(): View {
  const m = location.hash.match(/^#\/(setup|dashboard)\/([a-f0-9]{12})/);
  return m ? ({ name: m[1], id: m[2] } as View) : { name: "upload" };
}

export default function App() {
  const [view, setView] = useState<View>(parseHash);
  const [ds, setDs] = useState<DatasetSummary | null>(null);
  const [llm, setLlm] = useState<boolean | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.health().then((h) => setLlm(h.llm)).catch(() => setErr("Can't reach the backend — is it running on port 8020?"));
    const onHash = () => setView(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = (v: View) => {
    location.hash = v.name === "upload" ? "" : `#/${v.name}/${v.id}`;
    setView(v);
  };

  useEffect(() => {
    if (view.name === "upload") {
      setDs(null);
      return;
    }
    if (ds?.id === view.id) return;
    api
      .get(view.id)
      .then((d) => {
        setDs(d);
        if (view.name === "dashboard" && !d.scopes.length) go({ name: "setup", id: d.id });
      })
      .catch(() => go({ name: "upload" }));
  }, [view]); // eslint-disable-line react-hooks/exhaustive-deps

  if (err)
    return (
      <div className="mx-auto max-w-[640px] px-4 pt-24">
        <h1 className="text-2xl font-semibold">Backend unavailable</h1>
        <p className="mt-2 text-ink-2">{err}</p>
      </div>
    );

  if (view.name === "upload") return <Upload llm={llm} onLoaded={(id) => go({ name: "setup", id })} onOpen={(id) => go({ name: "dashboard", id })} />;
  if (!ds)
    return (
      <div className="pt-32 grid place-items-center text-muted">
        <Spinner />
      </div>
    );
  if (view.name === "setup")
    return (
      <Readiness
        ds={ds}
        onChange={setDs}
        onBack={() => go({ name: "upload" })}
        onReady={(d) => {
          setDs({ ...d, dashboards: [] });
          go({ name: "dashboard", id: d.id });
        }}
        onView={() => go({ name: "dashboard", id: ds.id })}
      />
    );
  return <DashboardPage key={ds.id + ds.scopes.map((s) => s.id).join()} ds={ds} llm={llm} onHome={() => go({ name: "upload" })} onSetup={() => go({ name: "setup", id: ds.id })} />;
}
