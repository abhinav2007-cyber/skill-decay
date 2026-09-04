import React from "react";

export default function TopHeader({ onSimulateClock }) {
  return (
    <header className="top-header">
      <div className="header-actions">
        {onSimulateClock && (
          <button className="btn-clock-sim" onClick={onSimulateClock} title="Simulate 14 days clock advance">
            <span>⏱️ +14 Days Virtual Clock</span>
          </button>
        )}
        <div className="icon-bell-wrap" title="Notifications">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
          </svg>
        </div>
        <div className="user-top-avatar">
          <span>R</span>
        </div>
      </div>
    </header>
  );
}
