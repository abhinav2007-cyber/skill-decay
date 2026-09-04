import React from "react";

export default function FeatherlessDecision({ agentDecision, onGoToNextTest }) {
  const action = agentDecision?.action || "TEST_NOW";
  const targetSubtopic = agentDecision?.targetSubtopic || "DSA — Complexity & Problem Solving";
  const reason = agentDecision?.reason || "Your performance in OOP improved, but DSA complexity shows low mastery (42%) and high urgency (68%). A targeted test will help validate your current state and guide the next steps.";
  const overallMastery = 56;

  return (
    <div className="decision-page-wrapper">
      <div className="decision-top-banner">
        <div className="agent-robot-icon-wrap">
          🤖
        </div>
        <div>
          <h1 className="decision-main-title">New Decision from Featherless Agent</h1>
          <p className="decision-main-sub">Based on your updated signals, here's the next best action.</p>
        </div>
      </div>

      <div className="agent-action-box">
        <div className="action-tag-pill">
          <span className="action-tag-icon">📋</span>
          <span className="action-tag-text">Action: <strong>{action}</strong></span>
        </div>

        <div className="agent-detail-section">
          <div className="agent-label">Target Sub-topic</div>
          <div className="agent-subtopic-name">{targetSubtopic}</div>
        </div>

        <div className="agent-detail-section">
          <div className="agent-label">Reason</div>
          <p className="agent-reason-paragraph">{reason}</p>
        </div>
      </div>

      <div className="decision-two-cards-row">
        {/* Current Overall Status */}
        <div className="card-half">
          <h3 className="card-half-title">Current Overall Status</h3>
          <div className="overall-ring-center">
            <div className="overall-ring-gauge">
              <span className="overall-gauge-num">{overallMastery}%</span>
            </div>
          </div>
          <div className="overall-gauge-text-center">
            <div className="gauge-title-dark">Overall Mastery</div>
            <div className="gauge-subtitle-muted">(Across All Skills)</div>
          </div>
        </div>

        {/* Next Steps checklist */}
        <div className="card-half">
          <h3 className="card-half-title">Next Steps</h3>
          <ul className="decision-checklist">
            <li className="item-done">
              <span className="check-bullet">☑</span>
              <span>Take the recommended test</span>
            </li>
            <li className="item-pending">
              <span className="check-bullet">○</span>
              <span>Complete the quiz</span>
            </li>
            <li className="item-pending">
              <span className="check-bullet">○</span>
              <span>View updated report</span>
            </li>
            <li className="item-pending">
              <span className="check-bullet">○</span>
              <span>Continue learning</span>
            </li>
          </ul>
        </div>
      </div>

      <div className="decision-action-bottom">
        <button className="btn-go-next-test" onClick={onGoToNextTest}>
          Go to Next Test →
        </button>
      </div>
    </div>
  );
}
