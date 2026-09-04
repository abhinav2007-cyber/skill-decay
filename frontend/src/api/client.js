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
  getTestCatalog: () => apiFetch("/test/catalog"),
  getTestQuestions: (subject, subtopic) =>
    apiFetch(`/test/questions?subject=${encodeURIComponent(subject)}&subtopic=${encodeURIComponent(subtopic)}`),
  submitTest: (body) =>
    apiFetch("/test/submit", { method: "POST", body: JSON.stringify(body) }),
  advanceTime: (days) =>
    apiFetch("/advance_time", { method: "POST", body: JSON.stringify({ days }) }),
  getStrengthReport: () => apiFetch("/strength-report"),
  getTestHistory: () => apiFetch("/test/history"),
  getCalendar: () => apiFetch("/calendar"),
  generateCalendarPlan: () => apiFetch("/calendar/generate-plan", { method: "POST" }),
  recalculateCalendarPlan: () => apiFetch("/calendar/recalculate", { method: "POST" }),
  completeCalendarEvent: (id) => apiFetch(`/calendar/events/${id}/complete`, { method: "POST" }),
  startCalendarTest: (id) => apiFetch(`/calendar/events/${id}/start-test`, { method: "POST" }),
  // ── Add New Skill ───────────────────────────────────────────────────────────
  analyzeSkill: (skillName) =>
    apiFetch("/skills/analyze", { method: "POST", body: JSON.stringify({ skill_name: skillName }) }),
  addSkill: (body) =>
    apiFetch("/skills/add", { method: "POST", body: JSON.stringify(body) }),
  generateBaseline: (body) =>
    apiFetch("/skills/baseline/generate", { method: "POST", body: JSON.stringify(body) }),
  deleteSkill: (skillName) =>
    apiFetch(`/skills/${encodeURIComponent(skillName)}`, { method: "DELETE" }),
};

