export interface Health {
  ok: boolean;
  ai_configured: boolean;
  model: string;
}

export interface Suggestion {
  intro: string;
  ending: string;
  hero: string;
  stat: string;
  words: string[];
  card_title: string;
  card_subtitle: string;
  card_footnote: string;
  problem: string;
  lead: string;
  solution: string;
  proof_label: string;
  accent: string | null;
  stat_from_brief: boolean;
  notes: string[];
  model: string;
}

async function errorText(res: Response) {
  try {
    const body = await res.json();
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

export async function getHealth(): Promise<Health | null> {
  try {
    const res = await fetch("/api/health");
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function suggest(brief: string, tone: string): Promise<Suggestion> {
  const res = await fetch("/api/suggest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ brief, tone }),
  });
  if (!res.ok) throw new Error(await errorText(res));
  return res.json();
}
