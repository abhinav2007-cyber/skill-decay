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

export default function Dashboard() {
  const [tab, setTab] = useState("skills");
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

  const [advanceDays, setAdvanceDays] = useState("30");
  const [advanceLoading, setAdvanceLoading] = useState(false);
  const [advanceResult, setAdvanceResult] = useState(null);
  const [advanceError, setAdvanceError] = useState(null);

  const fetchSkills = useCallback(async () => {
    setSkillsLoading(true);
    setSkillsError(null);
    try {
      const data = await api.getSkills();
      setSkills(data.skills);
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
      setTab("cycle");
    } catch (e) {
      setCycleError(e.message);
    } finally {
      setCycleLoading(false);
    }
  };

  const handleSubmitAnswer = useCallback(async ({ subtopic, question_id, selected_option, cycle_id }) => {
    setSubmittingFor(subtopic);
    try {
      const data = await api.submitAnswer({ subtopic, question_id, selected_option, cycle_id });
      setAnswerResults(prev => ({ ...prev, [subtopic]: data }));
      // Refresh skills after answer
      fetchSkills();
    } catch (e) {
      setAnswerResults(prev => ({ ...prev, [subtopic]: { error: e.message } }));
    } finally {
      setSubmittingFor(null);
    }
  }, [fetchSkills]);

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

  const handleFetchReport = async () => {
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
  };

  const skillList = flatSkills(skills);
  const actionResults = cycleResult?.action_results ?? [];
  const activeResults = actionResults.filter(r => r.action !== "WAIT");
  const waitResults = actionResults.filter(r => r.action === "WAIT");

  return (
    <div>
      <div className="tabs">
        <button className={`tab${tab === "skills" ? " active" : ""}`} onClick={() => setTab("skills")}>Skills</button>
        <button className={`tab${tab === "cycle" ? " active" : ""}`} onClick={() => setTab("cycle")}>Cycle</button>
        <button className={`tab${tab === "report" ? " active" : ""}`} onClick={() => setTab("report")}>Strength Report</button>
        <button className={`tab${tab === "time" ? " active" : ""}`} onClick={() => setTab("time")}>Time Control</button>
      </div>

      {/* SKILLS TAB */}
      {tab === "skills" && (
        <div>
          <div className="page-header">
            <h1 className="page-title">Skill Dashboard</h1>
            <p className="page-subtitle">Live decay signals across all 10 sub-topics</p>
          </div>
          <div className="action-bar">
            <button className="btn btn-primary" onClick={handleRunCycle} disabled={cycleLoading}>
              {cycleLoading ? <span className="spinner" /> : "▶"}
              Run Decision Cycle
            </button>
            <button className="btn btn-secondary" onClick={fetchSkills} disabled={skillsLoading}>
              {skillsLoading ? <span className="spinner" /> : "↻"} Refresh
            </button>
          </div>
          {cycleError && <div className="alert alert-error">⚠ {cycleError}</div>}
          {skillsError && <div className="alert alert-error">⚠ {skillsError}</div>}
          {skillsLoading && <div className="loading-state"><div className="spinner" /><span>Loading signals…</span></div>}
          {!skillsLoading && skillList.length > 0 && (
            <div className="card-grid">
              {skillList.map(({ skill, subTopic, entry }) => (
                <SkillCard key={`${skill}/${subTopic}`} skill={skill} subTopic={subTopic} entry={entry} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* CYCLE TAB */}
      {tab === "cycle" && (
        <div>
          <div className="page-header">
            <h1 className="page-title">Decision Cycle</h1>
            <p className="page-subtitle">Agent decisions and actions from the last cycle run</p>
          </div>
          <div className="action-bar">
            <button className="btn btn-primary" onClick={handleRunCycle} disabled={cycleLoading}>
              {cycleLoading ? <span className="spinner" /> : "▶"}
              {cycleResult ? "Re-run Cycle" : "Run Cycle"}
            </button>
          </div>
          {cycleError && <div className="alert alert-error">⚠ {cycleError}</div>}
          {cycleLoading && <div className="loading-state"><div className="spinner" /><span>Running decision cycle…</span></div>}
          {!cycleLoading && !cycleResult && (
            <div className="card" style={{ textAlign: "center", color: "var(--text-muted)" }}>
              <p>No cycle run yet. Click "Run Cycle" to start.</p>
            </div>
          )}
          {cycleResult && !cycleLoading && (
            <div className="cycle-results fade-in">
              {cycleResult.workflow_status === "error" && (
                <div className="alert alert-error">⚠ {cycleResult.error_information}</div>
              )}
              {activeResults.length > 0 && (
                <>
                  <div className="section-label">Actions Required</div>
                  {activeResults.map((r, i) => (
                    <QuizBlock
                      key={`${r.subtopic}-${i}`}
                      result={r}
                      onSubmitAnswer={handleSubmitAnswer}
                      submitting={submittingFor === r.subtopic}
                      answerResult={answerResults[r.subtopic]}
                    />
                  ))}
                </>
              )}
              {waitResults.length > 0 && (
                <>
                  <div className="divider" />
                  <div className="section-label">No Action Needed ({waitResults.length} sub-topics)</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                    {waitResults.map(r => (
                      <span key={r.subtopic} className="badge badge-wait">{r.subtopic.replace(/_/g, " ")}</span>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* REPORT TAB */}
      {tab === "report" && (
        <div>
          <div className="page-header">
            <h1 className="page-title">Strength Report</h1>
            <p className="page-subtitle">Per-skill mastery analysis + AI-powered insights</p>
          </div>
          <div className="action-bar">
            <button className="btn btn-primary" onClick={handleFetchReport} disabled={reportLoading}>
              {reportLoading ? <span className="spinner" /> : "📊"}
              {report ? "Refresh Report" : "Generate Report"}
            </button>
          </div>
          {reportError && <div className="alert alert-error">⚠ {reportError}</div>}
          {reportLoading && <div className="loading-state"><div className="spinner" /><span>Generating report with AI analysis…</span></div>}
          {report && !reportLoading && (
            <div className="fade-in">
              <div className="section-label">Skill Mastery</div>
              <div className="report-grid">
                {Object.entries(report.stats?.skills ?? {}).map(([skill, sdata]) => {
                  const pct = sdata.mastery_pct ?? 0;
                  const color = pct >= 70 ? "#10b981" : pct >= 45 ? "#f59e0b" : "#ef4444";
                  return (
                    <div className="report-card" key={skill}>
                      <div className="report-skill">
                        <span style={{ color }}>{pct >= 70 ? "✓" : pct >= 45 ? "~" : "✗"}</span>
                        {skill}
                      </div>
                      <div style={{ display: "flex", alignItems: "baseline", gap: "0.375rem" }}>
                        <span className="mastery-pct" style={{ color }}>{pct}%</span>
                        <span className="mastery-sub">mastery</span>
                      </div>
                      <div className="decay-bar-track" style={{ marginTop: "0.75rem" }}>
                        <div className="decay-bar-fill" style={{ width: `${pct}%`, background: color }} />
                      </div>
                      {/* Sub-topic breakdown */}
                      <div style={{ marginTop: "0.875rem" }}>
                        {Object.entries(report.stats?.sub_topics ?? {})
                          .filter(([k]) => k.startsWith(`${skill}/`))
                          .map(([k, v]) => {
                            const trend = v.trend;
                            const trendEl = trend === "improving"
                              ? <span className="trend trend-up">↑ improving</span>
                              : trend === "declining"
                                ? <span className="trend trend-down">↓ declining</span>
                                : <span className="trend trend-stable">→ {trend}</span>;
                            return (
                              <div key={k} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.8rem", padding: "0.3rem 0", borderBottom: "1px solid var(--border)" }}>
                                <span style={{ color: "var(--text-secondary)" }}>{v.sub_topic.replace(/_/g, " ")}</span>
                                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                                  <span style={{ fontWeight: 600, fontFamily: "JetBrains Mono, monospace" }}>{v.mastery_pct}%</span>
                                  {trendEl}
                                </div>
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  );
                })}
              </div>
              {report.ai_summary && (
                <div className="ai-summary">
                  <div className="ai-label">AI Analysis</div>
                  <p className="ai-text">{report.ai_summary}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TIME TAB */}
      {tab === "time" && (
        <div>
          <div className="page-header">
            <h1 className="page-title">Time Control</h1>
            <p className="page-subtitle">Advance the simulated clock to observe skill decay in action</p>
          </div>
          <div className="card" style={{ maxWidth: 480 }}>
            <div className="section-label">Advance Simulated Time</div>
            <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginBottom: "1.25rem", lineHeight: 1.6 }}>
              Moving time forward increases decay scores without altering quiz history or BKT knowledge estimates.
              Watch decay bars change after advancing.
            </p>
            <div className="time-control">
              <input
                id="advance-days-input"
                className="time-input"
                type="number"
                min="1"
                max="365"
                value={advanceDays}
                onChange={e => setAdvanceDays(e.target.value)}
              />
              <span className="time-label">days</span>
              <button
                className="btn btn-primary"
                onClick={handleAdvanceTime}
                disabled={advanceLoading}
                id="advance-time-btn"
              >
                {advanceLoading ? <span className="spinner" /> : "⏩"}
                Advance Time
              </button>
            </div>
            {advanceError && <div className="alert alert-error" style={{ marginTop: "1rem" }}>⚠ {advanceError}</div>}
            {advanceResult && (
              <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
                <span className="time-label">New simulated time:</span>
                <span className="time-result">{new Date(advanceResult.new_simulated_now).toLocaleDateString()}</span>
              </div>
            )}
          </div>

          <div className="card" style={{ maxWidth: 480, marginTop: "1rem" }}>
            <div className="section-label">Quick Presets</div>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              {[7, 14, 30, 60, 90].map(d => (
                <button key={d} className="btn btn-secondary btn-sm" onClick={() => setAdvanceDays(String(d))}>
                  +{d}d
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
