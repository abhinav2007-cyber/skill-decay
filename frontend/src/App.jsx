import React, { useState } from "react";
import "./index.css";
import Dashboard from "./components/Dashboard";

export default function App() {
  const [activeTab, setActiveTab] = useState("dashboard");

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-brand">
            Skill Decay Alerts
          </div>
        </div>
        <nav className="sidebar-nav">
          <button 
            className={`nav-item ${activeTab === "dashboard" ? "active" : ""}`}
            onClick={() => setActiveTab("dashboard")}
          >
            Dashboard
          </button>
          <button 
            className={`nav-item ${activeTab === "skills" ? "active" : ""}`}
            onClick={() => setActiveTab("skills")}
          >
            Skills Overview
          </button>
          <button 
            className={`nav-item ${activeTab === "insights" ? "active" : ""}`}
            onClick={() => setActiveTab("insights")}
          >
            Insights
          </button>
          <button 
            className={`nav-item ${activeTab === "time" ? "active" : ""}`}
            onClick={() => setActiveTab("time")}
          >
            Developer Settings
          </button>
        </nav>
        <div className="sidebar-footer">
          SDA v1.0 • Abhinav
        </div>
      </aside>
      
      <main className="main-content">
        <Dashboard activeTab={activeTab} />
      </main>
    </div>
  );
}
