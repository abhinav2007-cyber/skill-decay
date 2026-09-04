import React from "react";

export default function SkillCard({ skill, subTopic, entry }) {
  const decay = entry?.decay?.decay_score ?? 0;
  const days = entry?.decay?.days_since_last_use ?? 0;
  const mode = entry?.knowledge_tracking?.mode ?? "cold_start";
  const kp = entry?.knowledge_tracking?.knowledge_probability;
  const acc = entry?.quiz?.recent_accuracy;
  const obs = entry?.knowledge_tracking?.observation_count ?? 0;
  const lastAction = entry?.last_decision_action;
  const escalated = entry?.escalated;

  const displayName = subTopic.replace(/_/g, " ");

  // Determine status color based on decay
  let statusColor = "bg-green";
  let statusText = "Stable";
  if (escalated || decay >= 0.7) {
    statusColor = "bg-red";
    statusText = escalated ? "Escalated" : "At Risk";
  } else if (decay >= 0.45) {
    statusColor = "bg-amber";
    statusText = "Needs Attention";
  }

  return (
    <div className="skill-card">
      <div className="skill-header">
        <div>
          <div className="skill-name">{displayName}</div>
          <div className="skill-topic">{skill}</div>
        </div>
        <div className="status-indicator">
          <span className={`status-dot ${statusColor}`}></span>
          <span className={`color-${statusColor.replace('bg-', '')}`}>{statusText}</span>
        </div>
      </div>

      <div className="metrics-row">
        <div className="metric">
          <div className="metric-label">Estimated Knowledge</div>
          <div className="metric-value">
            {kp !== null && kp !== undefined ? `${(kp * 100).toFixed(0)}%` : "N/A"}
          </div>
        </div>
        <div className="metric">
          <div className="metric-label">Last Used</div>
          <div className="metric-value">
            {days > 0 ? `${days.toFixed(0)} days ago` : "Today"}
          </div>
        </div>
        <div className="metric">
          <div className="metric-label">Recent Accuracy</div>
          <div className="metric-value">
            {acc !== null && acc !== undefined ? `${(acc * 100).toFixed(0)}%` : "N/A"}
          </div>
        </div>
      </div>

      <div className="progress-container">
        <div className="progress-labels">
          <span>Decay</span>
          <span>{(decay * 100).toFixed(1)}%</span>
        </div>
        <div className="progress-track">
          <div
            className={`progress-fill ${statusColor}`}
            style={{ width: `${decay * 100}%` }}
          />
        </div>
      </div>

      <div className="mt-4 flex-row">
        {mode === "bkt" && <span className="badge-outline">BKT Model</span>}
        {mode === "decay_fallback" && <span className="badge-outline">Decay Proxy</span>}
        {mode === "cold_start" && <span className="badge-outline">Cold Start</span>}
        {obs > 0 && <span className="badge-outline">{obs} observations</span>}
      </div>
    </div>
  );
}
