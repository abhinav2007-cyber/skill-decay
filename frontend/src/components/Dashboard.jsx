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
        <div>
          <div style={{ marginBottom: "2rem" }}>
            <h1 className="page-title">Monitoring Dashboard</h1>
            <p className="page-subtitle">Continuous skill telemetry and automated intervention engine</p>
          </div>

          <div className="stats-grid">
            <div className="stat-box">
              <div className="stat-box-label">Monitored Sub-topics</div>
              <div className="stat-box-value">{allSkills.length}</div>
            </div>
            <div className="stat-box">
              <div className="stat-box-label">At Risk / Escalated</div>
              <div className="stat-box-value color-red">{atRiskSkills.length}</div>
            </div>
            <div className="stat-box">
              <div className="stat-box-label">Needs Attention</div>
              <div className="stat-box-value color-amber">{attentionSkills.length}</div>
            </div>
            <div className="stat-box">
              <div className="stat-box-label">Stable Competency</div>
              <div className="stat-box-value color-green">{stableSkills.length}</div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: "2rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
              <div>
                <h2 style={{ fontSize: "1.1rem", marginBottom: "0.25rem" }}>Decision Engine Loop</h2>
                <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                  Evaluate decay thresholds, trigger active knowledge checks, or generate review guides.
                </p>
              </div>
              <button
                className="btn btn-primary"
                onClick={handleRunCycle}
                disabled={cycleLoading}
              >
                {cycleLoading ? <span className="spinner" /> : null}
                Run Decision Cycle
              </button>
            </div>

            {cycleError && (
              <div className="alert alert-error" style={{ marginTop: "1rem" }}>
                ⚠ {cycleError}
              </div>
            )}
          </div>

          {cycleLoading && (
            <div className="loading-state">
              <div className="spinner" />
              <span>Analyzing decay models and generating questions…</span>
            </div>
          )}

          {!cycleLoading && cycleResult && (
            <div>
              <div className="section-title">Cycle Output ({activeResults.length} Actions Required)</div>
              
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
                <div className="card" style={{ marginBottom: "1.5rem", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                  All skills are currently within acceptable retention boundaries. No tests or escalations required.
                </div>
              )}

              {waitResults.length > 0 && (
                <div style={{ marginTop: "1.5rem" }}>
                  <div className="section-title">Stable Skills — Monitoring ({waitResults.length})</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                    {waitResults.map((r) => (
                      <span key={r.subtopic} className="badge-outline">
                        {r.subtopic.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {!cycleLoading && !cycleResult && (
            <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem", color: "var(--text-secondary)" }}>
              <div style={{ fontWeight: 500, color: "var(--text-primary)", marginBottom: "0.5rem" }}>
                No active decision cycle
              </div>
              <p style={{ fontSize: "0.875rem", maxWidth: "420px", margin: "0 auto 1.5rem auto" }}>
                Trigger a cycle evaluation to process current retention signals through Bayesian Knowledge Tracing and determine action requirements.
              </p>
              <button
                className="btn btn-secondary"
                onClick={handleRunCycle}
                disabled={cycleLoading}
              >
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

      {/* VIEW: INSIGHTS & STRENGTH REPORT */}
      {activeTab === "insights" && (
        <div>
          <div style={{ marginBottom: "2rem" }}>
            <h1 className="page-title">Competency Insights</h1>
            <p className="page-subtitle">Longitudinal mastery analysis and diagnostic observations</p>
          </div>

          <div className="card" style={{ marginBottom: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
              <div>
                <h2 style={{ fontSize: "1.05rem", marginBottom: "0.25rem" }}>Report Generation</h2>
                <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                  Aggregates all subtopic performance metrics and compiles structured diagnostic insights.
                </p>
              </div>
              <button
                className="btn btn-primary"
                onClick={handleFetchReport}
                disabled={reportLoading}
              >
                {reportLoading ? <span className="spinner" /> : null}
                {report ? "Refresh Analysis" : "Generate Report"}
              </button>
            </div>

            {reportError && <div className="alert alert-error" style={{ marginTop: "1rem" }}>⚠ {reportError}</div>}
          </div>

          {reportLoading && (
            <div className="loading-state">
              <div className="spinner" />
              <span>Compiling mastery insights…</span>
            </div>
          )}

          {report && !reportLoading && (
            <div>
              {report.ai_summary && (
                <div className="card" style={{ marginBottom: "1.5rem" }}>
                  <div className="section-title">Diagnostic Summary</div>
                  <p className="insight-text" style={{ fontSize: "0.95rem", whiteSpace: "pre-line" }}>
                    {report.ai_summary}
                  </p>
                </div>
              )}

              <div className="section-title">Domain Mastery Breakdown</div>
              <div className="report-grid">
                {Object.entries(report.stats?.skills ?? {}).map(([skillName, sdata]) => {
                  const pct = sdata.mastery_pct ?? 0;
                  const isHigh = pct >= 70;
                  const isMedium = pct >= 45 && pct < 70;
                  const statusColor = isHigh ? "var(--success)" : isMedium ? "var(--warning)" : "var(--danger)";

                  return (
                    <div className="report-card" key={skillName}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "0.75rem" }}>
                        <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>{skillName}</h3>
                        <span style={{ fontSize: "1.1rem", fontWeight: 600, color: statusColor }}>
                          {pct}%
                        </span>
                      </div>

                      <div className="progress-track" style={{ marginBottom: "1rem" }}>
                        <div
                          className="progress-fill"
                          style={{
                            width: `${pct}%`,
                            backgroundColor: statusColor,
                          }}
                        />
                      </div>

                      <div>
                        {Object.entries(report.stats?.sub_topics ?? {})
                          .filter(([k]) => k.startsWith(`${skillName}/`))
                          .map(([k, v]) => {
                            const trend = v.trend;
                            return (
                              <div key={k} className="insight-item">
                                <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                                  {v.sub_topic.replace(/_/g, " ")}
                                </span>
                                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                  <span style={{ fontSize: "0.8rem", fontWeight: 500, fontFamily: "monospace" }}>
                                    {v.mastery_pct}%
                                  </span>
                                  <span className={`trend-badge trend-${trend}`}>
                                    {trend === "improving" ? "↑ Up" : trend === "declining" ? "↓ Down" : "→ Stable"}
                                  </span>
                                </div>
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {!report && !reportLoading && (
            <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem", color: "var(--text-secondary)" }}>
              <div style={{ fontWeight: 500, color: "var(--text-primary)", marginBottom: "0.5rem" }}>
                No report compiled yet
              </div>
              <p style={{ fontSize: "0.875rem", maxWidth: "420px", margin: "0 auto 1.5rem auto" }}>
                Click "Generate Report" above to review aggregate trends, domain mastery calculations, and diagnostic analysis.
              </p>
            </div>
          )}
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
