import React, { useEffect, useState, useCallback } from "react";
import { api } from "../api/client";
import SkillCard from "./SkillCard";
import QuizBlock from "./QuizBlock";

function flatSkills(skillsObj) {
  const flat = [];
  if (!skillsObj) return flat;
  for (const [skill, subTopics] of Object.entries(skillsObj)) {
    for (const [subTopic, entry] of Object.entries(subTopics)) {
      flat.push({ skill, subTopic, entry });
    }
  }
  return flat;
}

export default function Dashboard({ activeTab = "dashboard" }) {
  const [skills, setSkills] = useState(null);
  const [skillsLoading, setSkillsLoading] = useState(false);
  const [skillsError, setSkillsError] = useState(null);

  const [cycleResult, setCycleResult] = useState(null);
  const [cycleLoading, setCycleLoading] = useState(false);
  const [cycleError, setCycleError] = useState(null);

  const [answerResults, setAnswerResults] = useState({});
  const [submittingFor, setSubmittingFor] = useState(null);

  const [report, setReport] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState(null);

  const [testHistory, setTestHistory] = useState([]);
  const [testHistoryLoading, setTestHistoryLoading] = useState(false);
  const [testHistoryError, setTestHistoryError] = useState(null);
  const [selectedReportCycle, setSelectedReportCycle] = useState(null);

  const [advanceDays, setAdvanceDays] = useState("30");
  const [advanceLoading, setAdvanceLoading] = useState(false);
  const [advanceResult, setAdvanceResult] = useState(null);
  const [advanceError, setAdvanceError] = useState(null);

  const [skillFilter, setSkillFilter] = useState("all");

  const fetchSkills = useCallback(async () => {
    setSkillsLoading(true);
    setSkillsError(null);
    try {
      const data = await api.getSkills();
      setSkills(data.skills || data);
    } catch (e) {
      setSkillsError(e.message);
    } finally {
      setSkillsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  const handleRunCycle = async () => {
    setCycleLoading(true);
    setCycleError(null);
    setCycleResult(null);
    setAnswerResults({});
    try {
      const data = await api.runCycle();
      setCycleResult(data);
    } catch (e) {
      setCycleError(e.message);
    } finally {
      setCycleLoading(false);
    }
  };

  const handleSubmitAnswer = useCallback(
    async ({ subtopic, question_id, selected_option, cycle_id }) => {
      setSubmittingFor(subtopic);
      try {
        const data = await api.submitAnswer({
          subtopic,
          question_id,
          selected_option,
          cycle_id,
        });
        setAnswerResults((prev) => ({ ...prev, [subtopic]: data }));
        fetchSkills();
      } catch (e) {
        setAnswerResults((prev) => ({ ...prev, [subtopic]: { error: e.message } }));
      } finally {
        setSubmittingFor(null);
      }
    },
    [fetchSkills]
  );

  const handleAdvanceTime = async () => {
    const days = parseFloat(advanceDays);
    if (!days || days <= 0) return;
    setAdvanceLoading(true);
    setAdvanceError(null);
    setAdvanceResult(null);
    try {
      const data = await api.advanceTime(days);
      setAdvanceResult(data);
      await fetchSkills();
    } catch (e) {
      setAdvanceError(e.message);
    } finally {
      setAdvanceLoading(false);
    }
  };

  const fetchTestHistory = useCallback(async () => {
    setTestHistoryLoading(true);
    setTestHistoryError(null);
    try {
      const data = await api.getTestHistory();
      setTestHistory(data.reports || []);
    } catch (e) {
      setTestHistoryError(e.message);
    } finally {
      setTestHistoryLoading(false);
    }
  }, []);

  const handleFetchReport = useCallback(async () => {
    setReportLoading(true);
    setReportError(null);
    try {
      const data = await api.getStrengthReport();
      setReport(data);
    } catch (e) {
      setReportError(e.message);
    } finally {
      setReportLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "insights") {
      fetchTestHistory();
      if (!report) {
        handleFetchReport();
      }
    }
  }, [activeTab, fetchTestHistory, handleFetchReport, report]);



  const allSkills = flatSkills(skills);
  const atRiskSkills = allSkills.filter(
    (s) => s.entry?.escalated || (s.entry?.decay?.decay_score ?? 0) >= 0.7
  );
  const attentionSkills = allSkills.filter(
    (s) =>
      !s.entry?.escalated &&
      (s.entry?.decay?.decay_score ?? 0) >= 0.45 &&
      (s.entry?.decay?.decay_score ?? 0) < 0.7
  );
  const stableSkills = allSkills.filter(
    (s) => !s.entry?.escalated && (s.entry?.decay?.decay_score ?? 0) < 0.45
  );

  const filteredSkills = allSkills.filter((s) => {
    if (skillFilter === "at_risk")
      return s.entry?.escalated || (s.entry?.decay?.decay_score ?? 0) >= 0.7;
    if (skillFilter === "attention")
      return (
        !s.entry?.escalated &&
        (s.entry?.decay?.decay_score ?? 0) >= 0.45 &&
        (s.entry?.decay?.decay_score ?? 0) < 0.7
      );
    if (skillFilter === "stable")
      return !s.entry?.escalated && (s.entry?.decay?.decay_score ?? 0) < 0.45;
    return true;
  });

  const actionResults = cycleResult?.action_results ?? [];
  const activeResults = actionResults.filter((r) => r.action !== "WAIT");
  const waitResults = actionResults.filter((r) => r.action === "WAIT");

  return (
    <div>
      {/* VIEW: DASHBOARD OVERVIEW */}
      {activeTab === "dashboard" && (
        <div className="mon-root">

          {/* Page header */}
          <div className="mon-page-head">
            <div>
              <h1 className="mon-page-title">Monitoring Dashboard</h1>
              <p className="mon-page-sub">Continuous skill telemetry and automated intervention engine</p>
            </div>
            <div className="mon-status-pill">
              <span className="mon-status-dot" />
              Live Monitoring
            </div>
          </div>

          {/* KPI stat strip */}
          <div className="mon-kpi-strip">
            {[
              {
                label: "Monitored Sub-topics",
                value: allSkills.length || 0,
                icon: (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                  </svg>
                ),
                iconBg: "#eff6ff", iconColor: "#2563eb", valColor: "#0f172a",
              },
              {
                label: "At Risk / Escalated",
                value: atRiskSkills.length,
                icon: (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                ),
                iconBg: "#fef2f2", iconColor: "#ef4444", valColor: "#ef4444",
              },
              {
                label: "Needs Attention",
                value: attentionSkills.length,
                icon: (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4M12 17h.01"/>
                  </svg>
                ),
                iconBg: "#fffbeb", iconColor: "#f59e0b", valColor: "#f59e0b",
              },
              {
                label: "Stable Competency",
                value: stableSkills.length,
                icon: (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
                  </svg>
                ),
                iconBg: "#ecfdf5", iconColor: "#10b981", valColor: "#10b981",
              },
            ].map(({ label, value, icon, iconBg, iconColor, valColor }) => (
              <div key={label} className="mon-kpi-card">
                <div className="mon-kpi-icon" style={{ background: iconBg, color: iconColor }}>{icon}</div>
                <div>
                  <div className="mon-kpi-val" style={{ color: valColor }}>{value}</div>
                  <div className="mon-kpi-label">{label}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Decision Engine card */}
          <div className="mon-engine-card">
            <div className="mon-engine-head">
              <div className="mon-engine-icon-wrap">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 010 14.14M4.93 4.93a10 10 0 000 14.14"/>
                  <path d="M22 12a10 10 0 00-10-10M2 12a10 10 0 0010 10"/>
                </svg>
              </div>
              <div className="mon-engine-text">
                <div className="mon-engine-title">Decision Engine Loop</div>
                <div className="mon-engine-sub">
                  Evaluates decay thresholds, triggers active knowledge checks, and generates targeted review guides.
                </div>
              </div>
              <button
                className="mon-run-btn"
                onClick={handleRunCycle}
                disabled={cycleLoading}
              >
                {cycleLoading ? (
                  <svg className="mon-spin-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M21 12a9 9 0 11-6.22-8.56"/>
                  </svg>
                ) : (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <polygon points="5 3 19 12 5 21 5 3"/>
                  </svg>
                )}
                {cycleLoading ? "Running…" : "Run Decision Cycle"}
              </button>
            </div>

            {/* pipeline step pills */}
            <div className="mon-pipeline">
              {[
                { label: "Decay Scan", done: true },
                { label: "BKT Estimate", done: true },
                { label: "Signal Classify", done: !!cycleResult },
                { label: "Action Dispatch", done: !!cycleResult && activeResults.length > 0 },
              ].map(({ label, done }, i, arr) => (
                <React.Fragment key={label}>
                  <div className={`mon-pipe-step ${done ? "mon-pipe-done" : "mon-pipe-pending"}`}>
                    <span className="mon-pipe-dot">{done ? "✓" : String(i + 1)}</span>
                    <span className="mon-pipe-label">{label}</span>
                  </div>
                  {i < arr.length - 1 && <div className="mon-pipe-arrow">→</div>}
                </React.Fragment>
              ))}
            </div>

            {cycleError && (
              <div className="mon-error-banner">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                {cycleError}
              </div>
            )}
          </div>

          {/* Loading */}
          {cycleLoading && (
            <div className="mon-loading">
              <div className="mon-loading-ring" />
              <div>
                <div className="mon-loading-title">Analysing skill signals…</div>
                <div className="mon-loading-sub">Running Bayesian Knowledge Tracing and decay classification</div>
              </div>
            </div>
          )}

          {/* Cycle results */}
          {!cycleLoading && cycleResult && (
            <div>
              <div className="mon-results-header">
                <span className="mon-results-title">Cycle Output</span>
                <span className="mon-results-badge">{activeResults.length} action{activeResults.length !== 1 ? "s" : ""} required</span>
              </div>

              {activeResults.length > 0 ? (
                <div>
                  {activeResults.map((r, i) => (
                    <QuizBlock
                      key={`${r.subtopic}-${i}`}
                      result={r}
                      onSubmitAnswer={handleSubmitAnswer}
                      submitting={submittingFor === r.subtopic}
                      answerResult={answerResults[r.subtopic]}
                    />
                  ))}
                </div>
              ) : (
                <div className="mon-all-ok">
                  <span className="mon-ok-icon">✓</span>
                  All skills are within acceptable retention boundaries — no tests required.
                </div>
              )}

              {waitResults.length > 0 && (
                <div className="mon-stable-section">
                  <div className="mon-stable-label">Stable — Monitoring ({waitResults.length})</div>
                  <div className="mon-stable-pills">
                    {waitResults.map((r) => (
                      <span key={r.subtopic} className="mon-stable-chip">
                        {r.subtopic.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Empty state */}
          {!cycleLoading && !cycleResult && (
            <div className="mon-empty-state">
              <div className="mon-empty-icon-wrap">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 010 14.14M4.93 4.93a10 10 0 000 14.14"/>
                  <path d="M22 12a10 10 0 00-10-10M2 12a10 10 0 0010 10"/>
                </svg>
              </div>
              <div className="mon-empty-title">No active decision cycle</div>
              <p className="mon-empty-sub">
                Trigger a cycle evaluation to process current retention signals through Bayesian Knowledge Tracing and determine action requirements.
              </p>
              <button className="mon-execute-btn" onClick={handleRunCycle} disabled={cycleLoading}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <polygon points="5 3 19 12 5 21 5 3"/>
                </svg>
                Execute Cycle Now
              </button>
            </div>
          )}
        </div>
      )}

      {/* VIEW: SKILLS OVERVIEW */}
      {activeTab === "skills" && (
        <div>
          <div style={{ marginBottom: "2rem" }}>
            <h1 className="page-title">Skills Overview</h1>
            <p className="page-subtitle">Telemetry across individual topics, Bayesian Knowledge Tracing estimates, and decay indicators</p>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem", marginBottom: "1.25rem" }}>
            <div className="filter-bar" style={{ marginBottom: 0 }}>
              <button
                className={`filter-chip ${skillFilter === "all" ? "active" : ""}`}
                onClick={() => setSkillFilter("all")}
              >
                All ({allSkills.length})
              </button>
              <button
                className={`filter-chip ${skillFilter === "at_risk" ? "active" : ""}`}
                onClick={() => setSkillFilter("at_risk")}
              >
                At Risk ({atRiskSkills.length})
              </button>
              <button
                className={`filter-chip ${skillFilter === "attention" ? "active" : ""}`}
                onClick={() => setSkillFilter("attention")}
              >
                Needs Attention ({attentionSkills.length})
              </button>
              <button
                className={`filter-chip ${skillFilter === "stable" ? "active" : ""}`}
                onClick={() => setSkillFilter("stable")}
              >
                Stable ({stableSkills.length})
              </button>
            </div>

            <button
              className="btn btn-secondary"
              onClick={fetchSkills}
              disabled={skillsLoading}
            >
              {skillsLoading ? <span className="spinner" /> : null}
              Refresh Telemetry
            </button>
          </div>

          {skillsError && <div className="alert alert-error">⚠ {skillsError}</div>}

          {skillsLoading && (
            <div className="loading-state">
              <div className="spinner" />
              <span>Fetching skill signals…</span>
            </div>
          )}

          {!skillsLoading && filteredSkills.length > 0 && (
            <div className="card-grid">
              {filteredSkills.map(({ skill, subTopic, entry }) => (
                <SkillCard
                  key={`${skill}/${subTopic}`}
                  skill={skill}
                  subTopic={subTopic}
                  entry={entry}
                />
              ))}
            </div>
          )}

          {!skillsLoading && filteredSkills.length === 0 && (
            <div className="card" style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
              No skills match the selected filter.
            </div>
          )}
        </div>
      )}

      {/* VIEW: INSIGHTS & ALL TEST REPORTS */}
      {activeTab === "insights" && (
        <div className="rep-page-root">
          {/* Header */}
          <div className="rep-header">
            <div>
              <div className="rep-header-badge">
                <span className="rep-pulse-dot" /> Test Telemetry & Diagnostic Reports
              </div>
              <h1 className="rep-page-title">Assessment Reports & Competency Analysis</h1>
              <p className="rep-page-sub">
                Historical record of all diagnostic test cycles with exact dates, times, accuracy scores, and longitudinal mastery trajectories.
              </p>
            </div>
            <div className="rep-actions">
              <button
                className="rep-btn-refresh"
                onClick={() => {
                  fetchTestHistory();
                  handleFetchReport();
                }}
                disabled={testHistoryLoading || reportLoading}
              >
                {(testHistoryLoading || reportLoading) ? "Refreshing..." : "↻ Refresh Reports"}
              </button>
            </div>
          </div>

          {/* KPI Strip for Test Reports */}
          <div className="rep-kpi-grid">
            <div className="rep-kpi-card">
              <div className="rep-kpi-icon-wrap" style={{ background: "#eff6ff", color: "#2563eb" }}>
                📝
              </div>
              <div>
                <div className="rep-kpi-val">{testHistory.length}</div>
                <div className="rep-kpi-label">Tests Completed</div>
              </div>
            </div>

            <div className="rep-kpi-card">
              <div className="rep-kpi-icon-wrap" style={{ background: "#ecfdf5", color: "#059669" }}>
                🎯
              </div>
              <div>
                <div className="rep-kpi-val">
                  {testHistory.length > 0
                    ? Math.round(testHistory.reduce((acc, r) => acc + r.accuracy_pct, 0) / testHistory.length)
                    : 0}%
                </div>
                <div className="rep-kpi-label">Avg Test Accuracy</div>
              </div>
            </div>

            <div className="rep-kpi-card">
              <div className="rep-kpi-icon-wrap" style={{ background: "#fef3c7", color: "#d97706" }}>
                ⚡
              </div>
              <div>
                <div className="rep-kpi-val">
                  {testHistory.reduce((acc, r) => acc + r.total_questions, 0)}
                </div>
                <div className="rep-kpi-label">Questions Evaluated</div>
              </div>
            </div>

            <div className="rep-kpi-card">
              <div className="rep-kpi-icon-wrap" style={{ background: "#f5f3ff", color: "#7c3aed" }}>
                🧠
              </div>
              <div>
                <div className="rep-kpi-val">
                  {testHistory.filter(r => r.mastery_mode === "bkt").length > 0 ? "pyBKT Active" : "Calibrating"}
                </div>
                <div className="rep-kpi-label">Knowledge Engine</div>
              </div>
            </div>
          </div>

          {/* Section 1: All Test Reports with Date & Time */}
          <div className="rep-section">
            <div className="rep-section-head">
              <div className="rep-section-title-wrap">
                <span className="rep-section-icon">📅</span>
                <div>
                  <h2 className="rep-section-title">All Test Reports ({testHistory.length})</h2>
                  <p className="rep-section-sub">Chronological timeline of all assessment sessions taken with date, time, and score</p>
                </div>
              </div>
            </div>

            {testHistoryLoading && testHistory.length === 0 ? (
              <div className="rep-loading-card">
                <div className="spinner" />
                <span>Loading completed test reports...</span>
              </div>
            ) : testHistory.length === 0 ? (
              <div className="rep-empty-card">
                <div className="rep-empty-icon">📋</div>
                <div className="rep-empty-title">No test sessions recorded yet</div>
                <p className="rep-empty-sub">
                  When you take tests from the "Take Test" section or click "Test Now", each completed assessment report with exact date, time, and question breakdown will appear here.
                </p>
              </div>
            ) : (
              <div className="rep-reports-table-wrap">
                <table className="rep-table">
                  <thead>
                    <tr>
                      <th>Date & Time</th>
                      <th>Subject / Domain</th>
                      <th>Sub-Topic</th>
                      <th>Score</th>
                      <th>Accuracy</th>
                      <th>Tracking Mode</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {testHistory.map((item) => {
                      const isPassing = item.accuracy_pct >= 60;
                      return (
                        <tr key={item.cycle_id} className="rep-row">
                          <td className="rep-time-cell">
                            <div className="rep-date-text">{item.date}</div>
                            <div className="rep-time-text">🕒 {item.time}</div>
                          </td>
                          <td>
                            <span className="rep-subject-badge">{item.subject}</span>
                          </td>
                          <td className="rep-subtopic-cell">
                            {item.sub_topic.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
                          </td>
                          <td>
                            <span className="rep-score-pill">
                              {item.correct_count} / {item.total_questions}
                            </span>
                          </td>
                          <td>
                            <div className="rep-acc-box">
                              <span className={`rep-acc-badge ${isPassing ? "pass" : "fail"}`}>
                                {item.accuracy_pct}%
                              </span>
                            </div>
                          </td>
                          <td>
                            <span className={`rep-mode-tag ${item.mastery_mode}`}>
                              {item.mastery_mode.toUpperCase()}
                            </span>
                          </td>
                          <td>
                            <button
                              className="rep-btn-view"
                              onClick={() => setSelectedReportCycle(item)}
                            >
                              View Breakdown →
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Modal / Overlay for selected report details */}
          {selectedReportCycle && (
            <div className="rep-modal-backdrop" onClick={() => setSelectedReportCycle(null)}>
              <div className="rep-modal-card" onClick={(e) => e.stopPropagation()}>
                <div className="rep-modal-header">
                  <div>
                    <span className="rep-subject-badge">{selectedReportCycle.subject}</span>
                    <h3 className="rep-modal-title">
                      {selectedReportCycle.sub_topic.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
                    </h3>
                    <div className="rep-modal-meta">
                      <span>📅 {selectedReportCycle.date}</span>
                      <span>🕒 {selectedReportCycle.time}</span>
                      <span>Cycle ID: <code>{selectedReportCycle.cycle_id.slice(0, 8)}...</code></span>
                    </div>
                  </div>
                  <button className="rep-modal-close" onClick={() => setSelectedReportCycle(null)}>✕</button>
                </div>

                <div className="rep-modal-stats-grid">
                  <div className="rep-m-stat">
                    <div className="rep-m-val">{selectedReportCycle.correct_count} / {selectedReportCycle.total_questions}</div>
                    <div className="rep-m-lbl">Score</div>
                  </div>
                  <div className="rep-m-stat">
                    <div className={`rep-m-val ${selectedReportCycle.accuracy_pct >= 60 ? "text-green" : "text-red"}`}>
                      {selectedReportCycle.accuracy_pct}%
                    </div>
                    <div className="rep-m-lbl">Accuracy</div>
                  </div>
                  <div className="rep-m-stat">
                    <div className="rep-m-val">{selectedReportCycle.mastery_mode.toUpperCase()}</div>
                    <div className="rep-m-lbl">BKT Mode</div>
                  </div>
                  <div className="rep-m-stat">
                    <div className="rep-m-val">
                      {selectedReportCycle.knowledge_probability !== null && selectedReportCycle.knowledge_probability !== undefined
                        ? `${Math.round(selectedReportCycle.knowledge_probability * 100)}%`
                        : "Calibrating"}
                    </div>
                    <div className="rep-m-lbl">Mastery Level</div>
                  </div>
                </div>

                <div className="rep-modal-q-list">
                  <h4 className="rep-modal-q-title">Question Breakdown</h4>
                  {selectedReportCycle.questions_breakdown.map((q, idx) => (
                    <div key={idx} className={`rep-q-row ${q.correct ? "correct" : "incorrect"}`}>
                      <div className="rep-q-icon">{q.correct ? "✓" : "✗"}</div>
                      <div className="rep-q-info">
                        <span className="rep-q-id">Question #{idx + 1} ({q.question_id})</span>
                        <span className="rep-q-verdict">{q.correct ? "Answered Correctly" : "Answered Incorrectly"}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Section 2: AI Diagnostic Summary & Longitudinal Mastery Analysis */}
          <div className="rep-section" style={{ marginTop: "2rem" }}>
            <div className="rep-section-head">
              <div className="rep-section-title-wrap">
                <span className="rep-section-icon">🧠</span>
                <div>
                  <h2 className="rep-section-title">Longitudinal Competency Insights</h2>
                  <p className="rep-section-sub">Synthesized knowledge telemetry across all 5 computer science domains</p>
                </div>
              </div>
              <button
                className="btn btn-secondary"
                onClick={handleFetchReport}
                disabled={reportLoading}
              >
                {reportLoading ? "Analyzing..." : "Re-run Diagnostic Summary"}
              </button>
            </div>

            {report?.ai_summary && (
              <div className="rep-summary-card">
                <div className="rep-summary-badge">🤖 AI Diagnostic Analysis (Featherless)</div>
                <p className="rep-summary-text">{report.ai_summary}</p>
              </div>
            )}

            {/* Domain Mastery Breakdown */}
            {report?.stats?.skills && (
              <div className="rep-domains-grid">
                {Object.entries(report.stats.skills).map(([skillName, sdata]) => {
                  const pct = sdata.mastery_pct ?? 0;
                  const isHigh = pct >= 70;
                  const isMed = pct >= 45 && pct < 70;
                  const statusColor = isHigh ? "#10b981" : isMed ? "#f59e0b" : "#ef4444";

                  return (
                    <div className="rep-domain-card" key={skillName}>
                      <div className="rep-dc-top">
                        <span className="rep-dc-name">{skillName}</span>
                        <span className="rep-dc-val" style={{ color: statusColor }}>{pct}%</span>
                      </div>
                      <div className="rep-dc-bar">
                        <div className="rep-dc-fill" style={{ width: `${pct}%`, backgroundColor: statusColor }} />
                      </div>
                      <div className="rep-dc-subtopics">
                        {Object.entries(report.stats.sub_topics ?? {})
                          .filter(([_, v]) => v.skill === skillName)
                          .map(([subKey, v]) => (
                            <div key={subKey} className="rep-dc-row">
                              <span className="rep-dc-sub-name">{subKey.replace(/_/g, " ")}</span>
                              <div className="rep-dc-sub-right">
                                <span className="rep-dc-sub-pct">{v.mastery_pct}%</span>
                                <span className={`trend-badge trend-${v.trend}`}>
                                  {v.trend === "improving" ? "↑ Up" : v.trend === "declining" ? "↓ Down" : "→ Stable"}
                                </span>
                              </div>
                            </div>
                          ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}


      {/* VIEW: DEVELOPER SETTINGS & TIME SIMULATION */}
      {activeTab === "time" && (
        <div>
          <div style={{ marginBottom: "2rem" }}>
            <h1 className="page-title">Developer Settings</h1>
            <p className="page-subtitle">Simulation controls to test retention decay models and automated cycle triggers</p>
          </div>

          <div className="card" style={{ maxWidth: "540px" }}>
            <h2 style={{ fontSize: "1.05rem", marginBottom: "0.5rem" }}>Simulated Time Advance</h2>
            <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: "1.25rem" }}>
              Simulates the passage of days without modifying actual evaluation records or Bayesian priors, accelerating decay metrics for testing.
            </p>

            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "1rem" }}>
              <input
                id="advance-days-input"
                className="input-text"
                style={{ width: "120px" }}
                type="number"
                min="1"
                max="365"
                value={advanceDays}
                onChange={(e) => setAdvanceDays(e.target.value)}
              />
              <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>days</span>
              <button
                className="btn btn-primary"
                onClick={handleAdvanceTime}
                disabled={advanceLoading}
                id="advance-time-btn"
              >
                {advanceLoading ? <span className="spinner" /> : null}
                Advance Clock
              </button>
            </div>

            <div style={{ marginBottom: "1.5rem" }}>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.5rem", fontWeight: 600 }}>
                Quick Offsets
              </div>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                {[7, 14, 30, 60, 90].map((d) => (
                  <button
                    key={d}
                    className="btn btn-secondary"
                    style={{ fontSize: "0.75rem", padding: "0.25rem 0.6rem" }}
                    onClick={() => setAdvanceDays(String(d))}
                  >
                    +{d} days
                  </button>
                ))}
              </div>
            </div>

            {advanceError && <div className="alert alert-error">⚠ {advanceError}</div>}

            {advanceResult && (
              <div style={{ background: "var(--bg-base)", padding: "0.75rem 1rem", borderRadius: "6px", border: "1px solid var(--border)", fontSize: "0.85rem" }}>
                <div style={{ color: "var(--text-muted)", marginBottom: "0.25rem" }}>New Virtual Date:</div>
                <div style={{ fontWeight: 600, color: "var(--text-primary)", fontFamily: "monospace" }}>
                  {new Date(advanceResult.new_simulated_now).toLocaleString()}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
