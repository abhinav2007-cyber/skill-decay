import React from "react";
import "./index.css";
import Dashboard from "./components/Dashboard";

export default function App() {
  return (
    <div className="app">
      <nav className="nav">
        <div className="nav-brand">
          <span className="nav-brand-dot" />
          Skill Decay Alerts
        </div>
        <div className="nav-time">
          <span>SDA</span>
          <span style={{ color: "var(--border)", marginInline: "0.25rem" }}>·</span>
          <span>v1.0</span>
        </div>
      </nav>
      <main className="page">
        <Dashboard />
      </main>
    </div>
  );
}
