const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  getSkills: () => apiFetch("/skills"),
  runCycle: () => apiFetch("/cycle", { method: "POST" }),
  submitAnswer: (body) =>
    apiFetch("/answer", { method: "POST", body: JSON.stringify(body) }),
  advanceTime: (days) =>
    apiFetch("/advance_time", { method: "POST", body: JSON.stringify({ days }) }),
  getStrengthReport: () => apiFetch("/strength-report"),
};
