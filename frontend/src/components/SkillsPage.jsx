import React, { useState } from "react";
import AddSkillModal from "./AddSkillModal";
import { api } from "../api/client";

// Fallback meta for custom skills
const SKILL_META = {
  Python:             { color: "#4f8ef7", bg: "#eff6ff", icon: "🐍" },
  Java:               { color: "#f59e0b", bg: "#fffbeb", icon: "☕" },
  DBMS:               { color: "#6366f1", bg: "#eef2ff", icon: "🗄️" },
  "Machine Learning": { color: "#8b5cf6", bg: "#f5f3ff", icon: "🧠" },
  DSA:                { color: "#ef4444", bg: "#fef2f2", icon: "⚡" },
};

function skillMeta(name) {
  if (SKILL_META[name]) return SKILL_META[name];
  const colors = [
    { color: "#0ea5e9", bg: "#e0f2fe", icon: "💡" },
    { color: "#d946ef", bg: "#fdf4ff", icon: "🔧" },
    { color: "#f97316", bg: "#fff7ed", icon: "📦" },
    { color: "#14b8a6", bg: "#f0fdfa", icon: "🌐" },
    { color: "#84cc16", bg: "#f7fee7", icon: "🚀" },
  ];
  const idx = name.charCodeAt(0) % colors.length;
  return colors[idx];
}

export default function SkillsPage({ skillsData, onTestNowClick, onStartBaselineTest, onRefresh, loading }) {
  const [showAddModal, setShowAddModal] = useState(false);
  const [filter, setFilter] = useState("All");
  const [confirmDeleteSkill, setConfirmDeleteSkill] = useState(null); // skill name pending confirm
  const [deletingSkill, setDeletingSkill] = useState(null);           // skill being deleted (loading)
  const [optimisticallyDeleted, setOptimisticallyDeleted] = useState(new Set()); // instantly hidden

  const buildSkillSummaries = () => {
    if (!skillsData) return [];
    const skillsObj = skillsData.skills || skillsData;

    const list = [];
    for (const [skill, subTopics] of Object.entries(skillsObj)) {
      const entries = Object.values(subTopics);
      if (!entries.length) continue;

      const withKP = entries.filter(
        (e) => (e.knowledge_tracking?.knowledge_probability ?? e.knowledge_probability) != null
      );

      const totalObs = entries.reduce(
        (acc, e) => acc + (e.knowledge_tracking?.observation_count ?? e.observation_count ?? 0),
        0
      );

      const isNewSkill = entries.every((e) => {
        const mode = e.knowledge_tracking?.mode ?? e.tracking_mode ?? "cold_start";
        const obs = e.knowledge_tracking?.observation_count ?? e.observation_count ?? 0;
        return mode === "cold_start" && obs === 0;
      });

      const isBaselineEstablished = !isNewSkill && entries.some((e) => {
        const obs = e.knowledge_tracking?.observation_count ?? e.observation_count ?? 0;
        const mode = e.knowledge_tracking?.mode ?? e.tracking_mode;
        return obs > 0 && mode !== "bkt";
      });

      let mastery = 0;
      if (isNewSkill) {
        mastery = 0;
      } else if (withKP.length > 0) {
        mastery = Math.round(
          withKP.reduce(
            (acc, e) => acc + (e.knowledge_tracking?.knowledge_probability ?? e.knowledge_probability) * 100,
            0
          ) / withKP.length
        );
      } else {
        const avgDecay = entries.reduce((acc, e) => acc + (e.decay?.decay_score ?? 0), 0) / entries.length;
        mastery = Math.round((1 - avgDecay) * 100);
      }

      // Determine statuses based on logic
      let status = "Tracked";
      if (isNewSkill) {
        status = "New";
      } else if (entries.some((e) => e.escalated) || (mastery < 50 && !isNewSkill)) {
        status = "Needs Attention";
      } else if (entries.some((e) => (e.decay?.days_since_last_use ?? 0) > 30)) {
        status = "Stale";
      } else if (mastery >= 80) {
        status = "Strong";
      } else if (isBaselineEstablished) {
        status = "Baseline Established";
      }

      // Re-map tracking modes logically for display
      let displayStatus = "";
      if (isNewSkill) {
        displayStatus = "Baseline Pending";
      } else if (isBaselineEstablished) {
        displayStatus = "Baseline Established";
      } else if (status === "Needs Attention") {
        displayStatus = "Needs Attention";
      } else if (status === "Stale") {
        displayStatus = "Refresh Soon";
      } else if (status === "Strong") {
        displayStatus = "Strong Memory";
      } else {
        displayStatus = "Tracked";
      }

      list.push({
        name: skill,
        mastery: Math.max(0, Math.min(100, mastery)),
        isNewSkill,
        subTopicCount: entries.length,
        totalObservations: totalObs,
        status,
        displayStatus,
        subTopics: Object.keys(subTopics),
      });
    }
    return list;
  };

  const skills = buildSkillSummaries();

  const filteredSkills = skills.filter((s) => {
    if (optimisticallyDeleted.has(s.name)) return false; // hide immediately on delete
    if (filter === "All") return true;
    if (filter === "New" && s.status === "New") return true;
    if (filter === "Strong" && s.status === "Strong") return true;
    if (filter === "Needs Attention" && s.status === "Needs Attention") return true;
    if (filter === "Stale" && s.status === "Stale") return true;
    return false;
  });

  const handleSkillAdded = () => {
    if (onRefresh) onRefresh();
  };

  const handleDeleteConfirmed = async (skillName) => {
    // Optimistically hide the card right away
    setOptimisticallyDeleted(prev => new Set(prev).add(skillName));
    setConfirmDeleteSkill(null);
    setDeletingSkill(skillName);
    try {
      await api.deleteSkill(skillName);
      if (onRefresh) onRefresh();
    } catch (err) {
      // Roll back optimistic deletion on error
      setOptimisticallyDeleted(prev => {
        const next = new Set(prev);
        next.delete(skillName);
        return next;
      });
      console.error(`Failed to delete skill: ${err.message || err}`);
    } finally {
      setDeletingSkill(null);
    }
  };

  return (
    <div className="dashboard-view">
      <div className="dash-header-row">
        <div>
          <h1 className="welcome-title">Skills Overview</h1>
          <p className="welcome-subtitle">Track and manage all your learning domains.</p>
        </div>
        <button
          className="btn-add-skill"
          onClick={() => setShowAddModal(true)}
          style={{ height: "40px" }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Add New Skill
        </button>
      </div>

      <div className="filter-tabs" style={{ marginBottom: "2rem", display: "flex", gap: "10px" }}>
        {["All", "Strong", "Needs Attention", "New", "Stale"].map((f) => (
          <button
            key={f}
            className={`ask-example-chip ${filter === f ? "active" : ""}`}
            style={filter === f ? { background: "#6366f1", color: "white", borderColor: "#6366f1" } : {}}
            onClick={() => setFilter(f)}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="skill-summary-grid">
        {filteredSkills.length === 0 ? (
          <div style={{ padding: "2rem", color: "#64748b" }}>No skills found matching this filter.</div>
        ) : (
          filteredSkills.map((skill) => {
            const meta = skillMeta(skill.name);
            const statusStyle = {
              "Baseline Pending": { bg: "#e0f2fe", color: "#0369a1" },
              "Baseline Established": { bg: "#fef3c7", color: "#b45309" },
              "Needs Attention": { bg: "#fee2e2", color: "#b91c1c" },
              "Refresh Soon": { bg: "#ffedd5", color: "#c2410c" },
              "Strong Memory": { bg: "#dcfce7", color: "#15803d" },
              "Tracked": { bg: "#f3e8ff", color: "#7e22ce" },
            }[skill.displayStatus] || { bg: "#f1f5f9", color: "#475569" };

            return (
              <div
                className="compact-skill-card"
                key={skill.name}
                style={{ borderBottom: `3px solid ${meta.color}`, minHeight: "170px" }}
              >
                <div className="csc-head" style={{ justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0, flex: 1 }}>
                    <span className="csc-icon" style={{ background: meta.bg, color: meta.color }}>
                      {meta.icon}
                    </span>
                    <span className="csc-name" title={skill.name}>{skill.name}</span>
                  </div>
                  {confirmDeleteSkill === skill.name ? (
                    <div style={{ display: "flex", alignItems: "center", gap: "4px", flexShrink: 0 }}>
                      <span style={{ fontSize: "11px", color: "#ef4444", fontWeight: 600 }}>Delete?</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteConfirmed(skill.name); }}
                        style={{
                          background: "#ef4444", color: "white", border: "none",
                          borderRadius: "5px", padding: "3px 8px", fontSize: "11px",
                          fontWeight: 600, cursor: "pointer"
                        }}
                      >Yes</button>
                      <button
                        onClick={(e) => { e.stopPropagation(); setConfirmDeleteSkill(null); }}
                        style={{
                          background: "#e2e8f0", color: "#475569", border: "none",
                          borderRadius: "5px", padding: "3px 8px", fontSize: "11px",
                          fontWeight: 600, cursor: "pointer"
                        }}
                      >No</button>
                    </div>
                  ) : (
                    <button
                      className="btn-delete-skill"
                      onClick={(e) => {
                        e.stopPropagation();
                        setConfirmDeleteSkill(skill.name);
                      }}
                      disabled={deletingSkill === skill.name}
                      title={`Delete ${skill.name}`}
                      style={{
                        background: "transparent",
                        border: "none",
                        cursor: deletingSkill === skill.name ? "not-allowed" : "pointer",
                        padding: "5px",
                        borderRadius: "6px",
                        color: "#94a3b8",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        transition: "all 0.15s ease",
                        flexShrink: 0
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.color = "#ef4444";
                        e.currentTarget.style.background = "#fee2e2";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.color = "#94a3b8";
                        e.currentTarget.style.background = "transparent";
                      }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        <line x1="10" y1="11" x2="10" y2="17"></line>
                        <line x1="14" y1="11" x2="14" y2="17"></line>
                      </svg>
                    </button>
                  )}
                </div>

                <div style={{ marginTop: "6px", marginBottom: "6px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "6px" }}>
                  <span style={{
                    fontSize: "11px",
                    fontWeight: "600",
                    padding: "3px 8px",
                    borderRadius: "12px",
                    background: statusStyle.bg,
                    color: statusStyle.color,
                    whiteSpace: "nowrap",
                    flexShrink: 0
                  }}>
                    {skill.displayStatus}
                  </span>
                  <span style={{ fontSize: "11px", color: "#94a3b8", whiteSpace: "nowrap" }}>
                    {skill.subTopicCount} {skill.subTopicCount === 1 ? "topic" : "topics"}
                  </span>
                </div>

                {skill.isNewSkill ? (
                  <>
                    <div className="csc-new-label" style={{ color: "#64748b" }}>New Skill</div>
                    <div className="csc-new-sub">Take a test to establish baseline</div>
                  </>
                ) : (
                  <>
                    <div className="csc-mastery">{skill.mastery}%</div>
                    <div className="csc-label">Mastery</div>
                  </>
                )}

                <div className="compact-progress-track" style={{ marginTop: "10px" }}>
                  <div
                    className="compact-progress-fill"
                    style={{
                      width: skill.isNewSkill ? "4%" : `${skill.mastery}%`,
                      background: skill.isNewSkill ? "#cbd5e1" : meta.color,
                    }}
                  />
                </div>
              </div>
            );
          })
        )}
      </div>

      {showAddModal && (
        <AddSkillModal
          onClose={() => setShowAddModal(false)}
          onSkillAdded={handleSkillAdded}
          onStartBaselineTest={onStartBaselineTest}
        />
      )}
    </div>
  );
}
