import * as echarts from "echarts";

// Map boundaries by key ("world", "states-US", …). Exported reports seed them from the embedded JSON;
// the live app fetches each set once from the API.
const loaded = new Set<string>();
const pending = new Map<string, Promise<void>>();

export function seedMaps(geo: Record<string, any> | undefined) {
  for (const [key, json] of Object.entries(geo ?? {})) {
    echarts.registerMap(key, json);
    loaded.add(key);
  }
}

export const mapReady = (key: string) => loaded.has(key);

export function loadMap(key: string): Promise<void> {
  if (loaded.has(key)) return Promise.resolve();
  let p = pending.get(key);
  if (!p) {
    p = fetch(`/api/geo/${encodeURIComponent(key)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`Map boundaries unavailable (${r.status})`);
        return r.json();
      })
      .then((json) => {
        echarts.registerMap(key, json);
        loaded.add(key);
      })
      .finally(() => pending.delete(key));
    pending.set(key, p);
  }
  return p;
}
