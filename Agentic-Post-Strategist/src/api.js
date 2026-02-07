export async function fetchOperations() {
  const res = await fetch("/api/operations");
  if (!res.ok) {
    throw new Error(`Failed to load operations: ${res.status}`);
  }
  return res.json();
}

export async function generateContent(payload) {
  const res = await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `Generation failed: ${res.status}`);
  }

  return res.json();
}
