import React, { useState } from "react";
import AddSkillModal from "./AddSkillModal";

// ── Default meta for built-in skills ─────────────────────────────────────────
const SKILL_META = {
  Python:             { color: "#4f8ef7", bg: "#eff6ff", icon: "🐍", urgency: "High",     urgClass: "rec-urg-high" },
  Java:               { color: "#f59e0b", bg: "#fffbeb", icon: "☕", urgency: "Medium",   urgClass: "rec-urg-med"  },
  DBMS:               { color: "#6366f1", bg: "#eef2ff", icon: "🗄️", urgency: "Medium",   urgClass: "rec-urg-med"  },
  "Machine Learning": { color: "#8b5cf6", bg: "#f5f3ff", icon: "🧠", urgency: "High",     urgClass: "rec-urg-high" },
  DSA:                { color: "#ef4444", bg: "#fef2f2", icon: "⚡", urgency: "Critical", urgClass: "rec-urg-crit" },
};

// Fallback meta for custom skills
function skillMeta(name) {
  if (SKILL_META[name]) return SKILL_META[name];
  // Deterministic color from name
  const colors = [
    { color: "#0ea5e9", bg: "#e0f2fe", icon: "💡" },
    { color: "#d946ef", bg: "#fdf4ff", icon: "🔧" },
    { color: "#f97316", bg: "#fff7ed", icon: "📦" },
    { color: "#14b8a6", bg: "#f0fdfa", icon: "🌐" },
    { color: "#84cc16", bg: "#f7fee7", icon: "🚀" },
  ];
  const idx = name.charCodeAt(0) % colors.length;
  return { ...colors[idx], urgency: "Medium", urgClass: "rec-urg-med" };
}

// ── Build skill summaries from live API data ──────────────────────────────────
function buildSkillSummaries(skillsData) {
  if (!skillsData) return null;
  const skillsObj = skillsData.skills || skillsData;

  const bySkill = {};
  for (const [skill, subTopics] of Object.entries(skillsObj)) {
    const entries = Object.values(subTopics);
    if (!entries.length) continue;

    // Check knowledge tracking mode and observation count
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

    let mastery;
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
      // Decay fallback / baseline established
      const avgDecay = entries.reduce((acc, e) => acc + (e.decay?.decay_score ?? 0), 0) / entries.length;
      mastery = Math.round((1 - avgDecay) * 100);
    }

    bySkill[skill] = {
      name: skill,
      mastery: Math.max(0, Math.min(100, mastery)),
      isNewSkill,
    };
  }
  return bySkill;
}

// ── Recommended tests (static seed, sorted by urgency) ────────────────────────
const RECOMMENDED_TESTS = [
  { subject: "Python",           subTopicKey: "oop_and_design_patterns",         label: "OOP & Design Patterns",        decay: 68 },
  { subject: "Java",             subTopicKey: "oop_and_jvm_concepts",             label: "OOP & JVM Concepts",           decay: 52 },
  { subject: "DBMS",             subTopicKey: "sql_queries_and_joins",            label: "SQL Queries & Joins",          decay: 47 },
  { subject: "Machine Learning", subTopicKey: "algorithms_and_theory",           label: "Algorithms & Theory",          decay: 73 },
  { subject: "DSA",              subTopicKey: "complexity_and_problem_solving",   label: "Complexity & Problem Solving", decay: 81 },
];

const CORE_SKILL_NAMES = ["Python", "Java", "DBMS", "Machine Learning", "DSA"];

// ── Component ─────────────────────────────────────────────────────────────────
export default function HomeDashboard({ skillsData, onTestNowClick, onStartBaselineTest, loading, onRefresh, navigate }) {
  const [showAddModal, setShowAddModal] = useState(false);

  // Build live summaries from API data
  const liveSummaries = buildSkillSummaries(skillsData);

  // Skill list — use live data if available, else show static defaults
  const allCards = liveSummaries
    ? Object.values(liveSummaries)
    : [
        { name: "Python",           mastery: 62, isNewSkill: false },
        { name: "Java",             mastery: 48, isNewSkill: false },
        { name: "DBMS",             mastery: 55, isNewSkill: false },
        { name: "Machine Learning", mastery: 44, isNewSkill: false },
        { name: "DSA",              mastery: 38, isNewSkill: false },
      ];

  // On the homepage, display only the 5 Core domain skills
  const coreCards = allCards.filter(s => CORE_SKILL_NAMES.includes(s.name));
  const skillCards = coreCards.length > 0 ? coreCards : allCards.slice(0, 5);

  const handleSkillAdded = (skillName) => {
    if (onRefresh) onRefresh();
  };

  return (
    <div className="dashboard-view">
      <div className="dash-header-row">
        <div>
          <h1 className="welcome-title">Welcome back, Rudra!</h1>
          <p className="welcome-subtitle">Your personalized learning journey continues. Stay consistent, stay ahead.</p>
        </div>
        <div className="sda-status-card">
          <span className="sda-status-title">SDA Status</span>
          <div className="sda-status-pill">
            <span className="status-dot-green">●</span>
            <span className="status-text">On Track</span>
          </div>
        </div>
      </div>

      {/* ── Skill Mastery Strip ── */}
      <div className="section-block">
        <div className="skill-strip-header">
          <div className="skill-strip-title-row">
            <h2 className="skill-strip-title">Core Domain Skill Standing</h2>
            <span className="skill-strip-badge">Core 5 Domains</span>
            {navigate && (
              <button 
                className="view-all-link"
                style={{ background: "none", border: "none", cursor: "pointer", padding: "0 8px", fontSize: "13px", fontWeight: "600", color: "#6366f1" }}
                onClick={() => navigate("/skills")}
              >
                View all skills in Skills tab ({allCards.length}) →
              </button>
            )}
          </div>
          <button
            className="btn-add-skill"
            onClick={() => setShowAddModal(true)}
            title="Add a new skill to track"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19"/>
              <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            Add New Skill
          </button>
        </div>

        <div className="skill-summary-grid">
          {skillCards.map((skill) => {
            const meta = skillMeta(skill.name);
            return (
              <div
                className="compact-skill-card"
                key={skill.name}
                style={{ borderBottom: `3px solid ${meta.color}` }}
              >
                <div className="csc-head">
                  <span className="csc-icon" style={{ background: meta.bg, color: meta.color }}>
                    {meta.icon}
                  </span>
                  <span className="csc-name">{skill.name}</span>
                </div>

                {skill.isNewSkill ? (
                  <>
                    <div className="csc-new-label">New Skill</div>
                    <div className="csc-new-sub">Take a test to establish your baseline</div>
                  </>
                ) : (
                  <>
                    <div className="csc-mastery">{skill.mastery}%</div>
                    <div className="csc-label">Mastery</div>
                  </>
                )}

                <div className="compact-progress-track">
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
          })}
        </div>
      </div>

      {/* ── Recommended Tests ── */}
      <div className="section-block" style={{ marginTop: "2.5rem" }}>
        <div className="recommended-header">
          <div>
            <h3 className="rec-section-title">Recommended Tests</h3>
            <p className="rec-section-sub">Prioritised by your SDA signal engine — highest urgency first</p>
          </div>
          <span
            className="view-all-link"
            onClick={() => navigate && navigate("/recommendations")}
            title="Go to Recommendations"
          >
            View All →
          </span>
        </div>

        <div className="recommended-grid">
          {RECOMMENDED_TESTS.map((rec) => {
            const meta = skillMeta(rec.subject);
            const retention = 100 - rec.decay;
            return (
              <div
                className="rec-card"
                key={rec.subject}
                style={{ borderTop: `3px solid ${meta.color}` }}
              >
                {/* card head */}
                <div className="rec-card-head">
                  <span className="rec-icon-badge" style={{ background: meta.bg, color: meta.color }}>
                    {meta.icon}
                  </span>
                  <span className={`rec-urgency-chip ${meta.urgClass}`}>{meta.urgency}</span>
                </div>

                {/* subject + topic */}
                <div className="rec-card-body">
                  <div className="rec-subject">{rec.subject}</div>
                  <div className="rec-topic-chip">{rec.label}</div>
                </div>

                {/* retention mini bar */}
                <div className="rec-ret-block">
                  <div className="rec-ret-labels">
                    <span className="rec-ret-lbl">Retention</span>
                    <span className="rec-ret-val">{retention}%</span>
                  </div>
                  <div className="rec-ret-track">
                    <div
                      className="rec-ret-fill"
                      style={{
                        width: `${retention}%`,
                        background: retention < 40 ? "#ef4444" : retention < 60 ? "#f59e0b" : "#10b981"
                      }}
                    />
                  </div>
                </div>

                {/* action button */}
                <button
                  className="btn-rec-test-now"
                  style={{ "--btn-color": meta.color }}
                  onClick={() => onTestNowClick(rec.subject, rec.subTopicKey)}
                  disabled={loading}
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <polygon points="5 3 19 12 5 21 5 3"/>
                  </svg>
                  Test Now
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Add Skill Modal ── */}
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
