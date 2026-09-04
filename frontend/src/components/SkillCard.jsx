import React from "react";

function decayColor(score) {
  if (score >= 0.7) return "#ef4444";
  if (score >= 0.45) return "#f59e0b";
  return "#10b981";
}

function trackingBadge(mode) {
  if (mode === "bkt") return <span className="badge badge-bkt">BKT</span>;
  if (mode === "decay_fallback") return <span className="badge badge-decay">Decay</span>;
  return <span className="badge badge-cold">Cold Start</span>;
}

function actionBadge(action) {
  if (!action) return null;
  const cls = {
    TEST_NOW: "badge-test",
    RECOMMEND: "badge-recommend",
    ESCALATE: "badge-escalate",
    WAIT: "badge-wait",
  }[action] || "badge-wait";
  return <span className={`badge ${cls}`}>{action}</span>;
}

export default function SkillCard({ skill, subTopic, entry }) {
  const decay = entry?.decay?.decay_score ?? 0;
  const days = entry?.decay?.days_since_last_use ?? 0;
  const mode = entry?.knowledge_tracking?.mode ?? "cold_start";
  const kp = entry?.knowledge_tracking?.knowledge_probability;
  const acc = entry?.quiz?.recent_accuracy;
  const obs = entry?.knowledge_tracking?.observation_count ?? 0;
  const lastAction = entry?.last_decision_action;
  const cat = entry?.category ?? "conceptual";
  const escalated = entry?.escalated;
  const color = decayColor(decay);

  const displayName = subTopic.replace(/_/g, " ");

  return (
    <div className={`skill-card fade-in${escalated ? " escalated" : ""}`}
      style={escalated ? { borderColor: "rgba(239,68,68,0.4)" } : {}}>
      <div className="skill-header">
        <div>
          <div className="skill-name">{displayName}</div>
          <div className="skill-sub">{skill}</div>
        </div>
        <span className={`badge badge-${cat}`}>{cat}</span>
      </div>

      <div className="decay-bar-wrap">
        <div className="decay-label">
          <span>Decay</span>
          <span style={{ color }}>{(decay * 100).toFixed(1)}%</span>
        </div>
        <div className="decay-bar-track">
          <div
            className="decay-bar-fill"
            style={{ width: `${decay * 100}%`, background: color }}
          />
        </div>
      </div>

      <div className="signal-row">
        <div className="signal-item">
          <div className="signal-label">Days ago</div>
          <div className="signal-value" style={{ color: days > 30 ? "#ef4444" : "#f1f5f9" }}>{days.toFixed(0)}</div>
        </div>
        {kp !== null && kp !== undefined ? (
          <div className="signal-item">
            <div className="signal-label">P(Know)</div>
            <div className="signal-value" style={{ color: kp > 0.6 ? "#10b981" : "#f59e0b" }}>{(kp * 100).toFixed(0)}%</div>
          </div>
        ) : null}
        {acc !== null && acc !== undefined ? (
          <div className="signal-item">
            <div className="signal-label">Accuracy</div>
            <div className="signal-value">{(acc * 100).toFixed(0)}%</div>
          </div>
        ) : null}
        <div className="signal-item">
          <div className="signal-label">Obs.</div>
          <div className="signal-value">{obs}</div>
        </div>
      </div>

      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.875rem", flexWrap: "wrap", alignItems: "center" }}>
        {trackingBadge(mode)}
        {escalated && <span className="badge badge-escalate">⚠ Escalated</span>}
        {lastAction && actionBadge(lastAction)}
      </div>
    </div>
  );
}
