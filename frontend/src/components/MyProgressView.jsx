import React, { useState, useMemo } from "react";

// ── domain meta ──────────────────────────────────────────────────────────────
const DOMAIN_META = {
  "Python":           { icon: "🐍", color: "#4f8ef7", bg: "#eff6ff" },
  "Java":             { icon: "☕", color: "#f59e0b", bg: "#fffbeb" },
  "DBMS":             { icon: "🗄️", color: "#6366f1", bg: "#eef2ff" },
  "Machine Learning": { icon: "🧠", color: "#10b981", bg: "#ecfdf5" },
  "DSA":              { icon: "⚡", color: "#ef4444", bg: "#fef2f2" },
};
function dmeta(skill) {
  return DOMAIN_META[skill] || { icon: "💻", color: "#64748b", bg: "#f8fafc" };
}
function statusOf(item) {
  const d = item.decay?.decay_score ?? 0;
  if (item.escalated || d >= 0.7) return "danger";
  if (d >= 0.45) return "warning";
  return "success";
}
const STATUS_LABEL = { danger: "At Risk", warning: "Attention", success: "Healthy" };

// ── tiny decay heat bar (7 segments) ────────────────────────────────────────
function DecayHeatBar({ score }) {
  const segs   = 7;
  const filled = Math.round(score * segs);
  const segColor = score >= 0.7 ? "#ef4444" : score >= 0.45 ? "#f59e0b" : "#10b981";
  return (
    <div style={{ display: "flex", gap: "2px" }}>
      {Array.from({ length: segs }).map((_, i) => (
        <div
          key={i}
          style={{
            width: "10px", height: "6px", borderRadius: "2px",
            background: i < filled ? segColor : "#e2e8f0",
          }}
        />
      ))}
    </div>
  );
}

// ── mini SVG ring gauge ──────────────────────────────────────────────────────
function MiniRing({ pct, color }) {
  const r = 18, circ = 2 * Math.PI * r;
  return (
    <svg width="44" height="44" viewBox="0 0 44 44">
      <circle cx="22" cy="22" r={r} fill="none" stroke="#e2e8f0" strokeWidth="4" />
      <circle
        cx="22" cy="22" r={r} fill="none" stroke={color} strokeWidth="4"
        strokeDasharray={`${circ * pct / 100} ${circ}`}
        strokeLinecap="round" transform="rotate(-90 22 22)"
      />
      <text x="22" y="26" textAnchor="middle" fontSize="10" fontWeight="700" fill="#0f172a">
        {pct}%
      </text>
    </svg>
  );
}

// ── domain summary card ──────────────────────────────────────────────────────
function DomainCard({ skill, items }) {
  const meta   = dmeta(skill);
  const avg    = items.length
    ? Math.round(items.reduce((a, s) => a + (1 - (s.decay?.decay_score || 0)) * 100, 0) / items.length)
    : 0;
  const danger = items.filter(s => statusOf(s) === "danger").length;
  const warn   = items.filter(s => statusOf(s) === "warning").length;
  const ringColor = avg >= 65 ? "#10b981" : avg >= 45 ? "#f59e0b" : "#ef4444";
  return (
    <div className="dom-card" style={{ borderTop: `3px solid ${meta.color}` }}>
      <div className="dom-card-head">
        <span className="dom-icon" style={{ background: meta.bg, color: meta.color }}>{meta.icon}</span>
        <div>
          <div className="dom-title">{skill}</div>
          <div className="dom-count">{items.length} topics</div>
        </div>
      </div>
      <MiniRing pct={avg} color={ringColor} />
      <div className="dom-pills">
        {danger > 0 && <span className="dom-pill dom-pill-r">{danger} risk</span>}
        {warn   > 0 && <span className="dom-pill dom-pill-w">{warn} attn</span>}
        {danger === 0 && warn === 0 && <span className="dom-pill dom-pill-g">All healthy</span>}
      </div>
    </div>
  );
}

// ── KPI icon colours ─────────────────────────────────────────────────────────
const KPI_COLORS = { blue: "#2563eb", green: "#10b981", amber: "#f59e0b", red: "#ef4444", teal: "#0d9488" };

// ── main view ────────────────────────────────────────────────────────────────
export default function MyProgressView({ skillsData, onTestNow, onRefresh, loading }) {
  const [activeFilter, setActiveFilter] = useState("all");
  const [search,       setSearch]       = useState("");
  const [sortBy,       setSortBy]       = useState("status");

  const list = useMemo(() => {
    if (!skillsData) return [];
    const out = [];
    for (const [skill, subs] of Object.entries(skillsData)) {
      for (const [key, data] of Object.entries(subs)) {
        if (data && typeof data === "object" && !data.error) {
          out.push({ skill, subtopicKey: key, ...data });
        }
      }
    }
    return out;
  }, [skillsData]);

  const byDomain = useMemo(() => {
    const m = {};
    for (const item of list) {
      (m[item.skill] = m[item.skill] || []).push(item);
    }
    return m;
  }, [list]);

  const atRiskList    = list.filter(s => statusOf(s) === "danger");
  const attentionList = list.filter(s => statusOf(s) === "warning");
  const healthyList   = list.filter(s => statusOf(s) === "success");
  const avgRet        = list.length
    ? Math.round(list.reduce((a, s) => a + (1 - (s.decay?.decay_score || 0)) * 100, 0) / list.length)
    : 65;

  const filtered = useMemo(() => {
    let out = list.filter(item => {
      const st = statusOf(item);
      if (activeFilter === "at_risk"   && st !== "danger")  return false;
      if (activeFilter === "attention" && st !== "warning")  return false;
      if (activeFilter === "healthy"   && st !== "success")  return false;
      if ((activeFilter === "procedural" || activeFilter === "conceptual") && item.category !== activeFilter) return false;
      if (search.trim()) {
        const q = search.toLowerCase();
        if (!item.skill.toLowerCase().includes(q) && !item.subtopicKey.toLowerCase().includes(q)) return false;
      }
      return true;
    });
    if (sortBy === "status") {
      const ord = { danger: 0, warning: 1, success: 2 };
      out = [...out].sort((a, b) => ord[statusOf(a)] - ord[statusOf(b)]);
    } else if (sortBy === "retention") {
      out = [...out].sort((a, b) => (a.decay?.decay_score || 0) - (b.decay?.decay_score || 0));
    } else if (sortBy === "recent") {
      out = [...out].sort((a, b) => (a.decay?.days_since_last_use ?? 0) - (b.decay?.days_since_last_use ?? 0));
    }
    return out;
  }, [list, activeFilter, search, sortBy]);

  const FILTERS = [
    { id: "all",       label: `All (${list.length})` },
    { id: "at_risk",   label: `At Risk (${atRiskList.length})` },
    { id: "attention", label: `Attention (${attentionList.length})` },
    { id: "healthy",   label: `Healthy (${healthyList.length})` },
  ];

  // inline svg helper
  const Svg = ({ d, vb = "0 0 24 24" }) => (
    <svg width="15" height="15" viewBox={vb} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );

  return (
    <div className="mpv-root">

      {/* HEADER */}
      <div className="mpv-header">
        <div>
          <h1 className="mpv-title">My Progress</h1>
          <p className="mpv-subtitle">Bayesian Knowledge Tracing · retention decay · adaptive urgency signals</p>
        </div>
        <button className="mpv-refresh-btn" onClick={onRefresh} disabled={loading}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {/* KPI STRIP */}
      <div className="mpv-kpi-strip">
        {[
          { label: "Tracked Topics", val: list.length || 10, col: "blue",  path: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
          { label: "Avg Retention",  val: `${avgRet}%`,      col: "green", path: "M22 12h-4l-3 9L9 3l-3 9H2" },
          { label: "Need Attention", val: attentionList.length, col: "amber", path: "M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4M12 17h.01" },
          { label: "At Risk",        val: atRiskList.length,   col: "red",   path: "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM12 8v4M12 16h.01" },
          { label: "Healthy",        val: healthyList.length,  col: "teal",  path: "M22 11.08V12a10 10 0 11-5.93-9.14M22 4L12 14.01l-3-3" },
        ].map(({ label, val, col, path }) => (
          <div key={label} className="mpv-kpi-card">
            <div className="mpv-kpi-icon" style={{ background: `${KPI_COLORS[col]}18`, color: KPI_COLORS[col] }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d={path} />
              </svg>
            </div>
            <div>
              <div className="mpv-kpi-val" style={{ color: col === "blue" ? "#0f172a" : KPI_COLORS[col] }}>{val}</div>
              <div className="mpv-kpi-label">{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* DOMAIN STRIP */}
      {Object.keys(byDomain).length > 0 && (
        <div className="mpv-section">
          <div className="mpv-section-hd">Domain Overview</div>
          <div className="mpv-domain-row">
            {Object.entries(byDomain).map(([skill, items]) => (
              <DomainCard key={skill} skill={skill} items={items} />
            ))}
          </div>
        </div>
      )}

      {/* TOOLBAR */}
      <div className="mpv-toolbar">
        <div className="mpv-filters">
          {FILTERS.map(f => (
            <button
              key={f.id}
              className={`mpv-fbtn ${activeFilter === f.id ? "mpv-fbtn-active" : ""}`}
              onClick={() => setActiveFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="mpv-toolbar-right">
          <div className="mpv-search-wrap">
            <svg className="mpv-search-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2.5" strokeLinecap="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              type="text"
              className="mpv-search-input"
              placeholder="Search topic…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <select className="mpv-sort-sel" value={sortBy} onChange={e => setSortBy(e.target.value)}>
            <option value="status">Sort: Urgency</option>
            <option value="retention">Sort: Retention ↑</option>
            <option value="recent">Sort: Last Tested</option>
          </select>
        </div>
      </div>

      <div className="mpv-result-line">
        {filtered.length} sub-topic{filtered.length !== 1 ? "s" : ""} shown
      </div>

      {/* GRID */}
      {filtered.length === 0 ? (
        <div className="mpv-empty">
          <div className="mpv-empty-icon">🔍</div>
          <div className="mpv-empty-title">No sub-topics match your filter</div>
          <div className="mpv-empty-sub">Try adjusting the search or filter selection</div>
        </div>
      ) : (
        <div className="mpv-grid">
          {filtered.map(item => {
            const meta       = dmeta(item.skill);
            const status     = statusOf(item);
            const decay      = item.decay?.decay_score || 0;
            const daysSince  = item.decay?.days_since_last_use ?? 0;
            const kp         = item.knowledge_tracking?.knowledge_probability;
            const acc        = item.quiz?.recent_accuracy;
            const obsCount   = item.knowledge_tracking?.observation_count || 0;
            const mode       = item.knowledge_tracking?.mode || "cold_start";
            const urgency    = item.urgency?.urgency_score ?? decay;

            const retPct = Math.round((1 - decay) * 100);
            const kpPct  = kp  != null ? Math.round(kp  * 100) : null;
            const accPct = acc != null ? Math.round(acc * 100) : null;
            const urgPct = Math.round(urgency * 100);

            const modeTag = mode === "bkt" ? "pyBKT" : mode === "decay_fallback" ? "Decay" : "Cold Start";
            const cleanName = item.subtopicKey.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());

            const SC = {
              danger:  { border: "#fca5a5", badgeBg: "#fef2f2", badgeText: "#b91c1c", retFill: "#ef4444", urgFill: "#ef4444" },
              warning: { border: "#fcd34d", badgeBg: "#fffbeb", badgeText: "#b45309", retFill: "#f59e0b", urgFill: "#f59e0b" },
              success: { border: "#6ee7b7", badgeBg: "#ecfdf5", badgeText: "#047857", retFill: "#10b981", urgFill: "#10b981" },
            }[status];

            return (
              <div
                key={`${item.skill}-${item.subtopicKey}`}
                className="mpv-card"
                style={{ borderLeft: `3px solid ${SC.border}` }}
              >
                {/* HEAD */}
                <div className="mpv-card-head">
                  <div className="mpv-card-id">
                    <span className="mpv-card-di" style={{ background: meta.bg, color: meta.color }}>{meta.icon}</span>
                    <div>
                      <div className="mpv-card-title">{cleanName}</div>
                      <span className="mpv-card-dtag" style={{ color: meta.color, background: meta.bg, border: `1px solid ${meta.color}40` }}>
                        {item.skill}
                      </span>
                    </div>
                  </div>
                  <span className="mpv-status-chip" style={{ background: SC.badgeBg, color: SC.badgeText }}>
                    <span className="mpv-sdot" style={{ background: SC.badgeText }} />
                    {STATUS_LABEL[status]}
                  </span>
                </div>

                {/* RETENTION */}
                <div className="mpv-ret-block">
                  <div className="mpv-ret-hd">
                    <span className="mpv-ret-lbl">Retention</span>
                    <span className="mpv-ret-num">{retPct}%</span>
                  </div>
                  <div className="mpv-ret-track">
                    <div className="mpv-ret-fill" style={{ width: `${retPct}%`, background: SC.retFill }} />
                  </div>
                  <div className="mpv-decay-row">
                    <span className="mpv-decay-lbl">Decay pressure</span>
                    <DecayHeatBar score={decay} />
                  </div>
                </div>

                {/* METRICS 2×2 */}
                <div className="mpv-metrics">
                  {[
                    { label: "pyBKT Knowledge", val: kpPct != null ? `${kpPct}%` : `~${retPct}%`, mono: false },
                    { label: "Last Tested",      val: daysSince > 0 ? `${Math.round(daysSince)}d ago` : "Today", mono: false },
                    { label: "Quiz Accuracy",    val: accPct != null ? `${accPct}%` : "—",          mono: false },
                    { label: "Model",            val: modeTag,                                       mono: true, col: meta.color },
                  ].map(({ label, val, mono, col }) => (
                    <div key={label} className="mpv-mc">
                      <div className="mpv-mc-lbl">{label}</div>
                      <div className="mpv-mc-val" style={mono ? { color: col || "#2563eb", fontWeight: 700 } : {}}>
                        {val}
                      </div>
                    </div>
                  ))}
                </div>

                {/* URGENCY BAR */}
                <div className="mpv-urg-row">
                  <span className="mpv-urg-lbl">Urgency</span>
                  <div className="mpv-urg-track">
                    <div className="mpv-urg-fill" style={{ width: `${urgPct}%`, background: SC.urgFill }} />
                  </div>
                  <span className="mpv-urg-pct">{urgPct}%</span>
                </div>

                {/* FOOTER */}
                <div className="mpv-card-foot">
                  <span className="mpv-obs">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                      <path d="M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>
                    </svg>
                    {obsCount} obs.
                  </span>
                  <button className="mpv-test-btn" onClick={() => onTestNow(item.skill, item.subtopicKey)}>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                      <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                    Test Now
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
