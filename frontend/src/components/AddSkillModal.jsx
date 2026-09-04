import React, { useState, useRef, useEffect } from "react";
import { api } from "../api/client";

// ── Category badge ────────────────────────────────────────────────────────────
function CategoryBadge({ category }) {
  const isProc = category === "procedural";
  return (
    <span className={`ask-cat-badge ${isProc ? "proc" : "conc"}`}>
      {isProc ? "Procedural" : "Conceptual"}
    </span>
  );
}

// ── States ────────────────────────────────────────────────────────────────────
const STATE = { 
  INPUT: "input", 
  ANALYZING: "analyzing", 
  SUGGESTIONS: "suggestions", 
  SAVING: "saving",
  BASELINE_INTRO: "baseline_intro",
  GENERATING_BASELINE: "generating_baseline",
  SUCCESS: "success" 
};

export default function AddSkillModal({ onClose, onSkillAdded, onStartBaselineTest }) {
  const [phase, setPhase] = useState(STATE.INPUT);
  const [skillInput, setSkillInput] = useState("");
  const [analysis, setAnalysis] = useState(null);     // AI response
  const [selected, setSelected] = useState([]);        // which sub-topics are checked
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  // Auto-focus input on open
  useEffect(() => {
    if (phase === STATE.INPUT && inputRef.current) {
      inputRef.current.focus();
    }
  }, [phase]);

  // Close on Escape
  useEffect(() => {
    const handle = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [onClose]);

  // ── Phase 1: Analyze ──────────────────────────────────────────────────────
  const handleAnalyze = async () => {
    const trimmed = skillInput.trim();
    if (!trimmed) { setError("Please enter a skill name."); return; }
    if (trimmed.length > 100) { setError("Skill name is too long (max 100 characters)."); return; }

    setError("");
    setPhase(STATE.ANALYZING);
    try {
      const result = await api.analyzeSkill(trimmed);
      setAnalysis(result);
      setSelected(result.sub_topics.map((_, i) => i)); // select all by default
      setPhase(STATE.SUGGESTIONS);
    } catch (e) {
      setError(e.message || "Analysis failed. Please try again.");
      setPhase(STATE.INPUT);
    }
  };

  // ── Phase 2: Confirm & Save ──────────────────────────────────────────────
  const handleAddSkill = async () => {
    if (!analysis) return;
    const chosenTopics = analysis.sub_topics.filter((_, i) => selected.includes(i));
    if (chosenTopics.length === 0) { setError("Select at least one sub-topic."); return; }

    setError("");
    setPhase(STATE.SAVING);
    try {
      await api.addSkill({
        skill: analysis.normalized_name,
        sub_topics: chosenTopics,
      });
      setPhase(STATE.BASELINE_INTRO);
    } catch (e) {
      setError(e.message || "Failed to save skill. Please try again.");
      setPhase(STATE.SUGGESTIONS);
    }
  };

  // ── Phase 3: Generate Baseline ───────────────────────────────────────────
  const handleGenerateBaseline = async () => {
    if (!analysis) return;
    const chosenTopics = analysis.sub_topics.filter((_, i) => selected.includes(i));
    
    setError("");
    setPhase(STATE.GENERATING_BASELINE);
    try {
      const res = await api.generateBaseline({
        skill: analysis.normalized_name,
        sub_topics: chosenTopics,
      });
      // Route immediately to Take Test
      onClose();
      if (onStartBaselineTest) {
        onStartBaselineTest(res.subject, res.cycle_id, res.questions);
      }
    } catch (e) {
      setError(e.message || "Failed to generate baseline assessment. Please try again.");
      setPhase(STATE.BASELINE_INTRO);
    }
  };

  const toggleTopic = (i) => {
    setSelected((prev) =>
      prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]
    );
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && phase === STATE.INPUT) handleAnalyze();
  };

  return (
    <div className="ask-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="ask-modal" role="dialog" aria-modal="true" aria-label="Add New Skill">

        {/* ── Header ── */}
        <div className="ask-modal-header">
          <div className="ask-header-left">
            <div className="ask-header-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2.5" strokeLinecap="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="16"/>
                <line x1="8" y1="12" x2="16" y2="12"/>
              </svg>
            </div>
            <div>
              <div className="ask-header-title">Add New Skill</div>
              <div className="ask-header-sub">AI-powered sub-topic suggestion via Featherless</div>
            </div>
          </div>
          <button className="ask-close-btn" onClick={onClose} aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {/* ── Body ── */}
        <div className="ask-modal-body">

          {/* STATE: INPUT */}
          {phase === STATE.INPUT && (
            <div className="ask-input-phase">
              <label className="ask-label" htmlFor="skill-name-input">
                What skill do you want to track?
              </label>
              <p className="ask-hint">
                Enter any skill in natural language — e.g. "Advanced SQL", "React.js", "System Design", "TensorFlow"
              </p>
              <div className="ask-input-row">
                <input
                  id="skill-name-input"
                  ref={inputRef}
                  className="ask-text-input"
                  type="text"
                  placeholder="e.g. Advanced SQL, AWS, Docker..."
                  value={skillInput}
                  onChange={(e) => { setSkillInput(e.target.value); setError(""); }}
                  onKeyDown={handleKeyDown}
                  maxLength={100}
                />
                <button
                  className="ask-analyze-btn"
                  onClick={handleAnalyze}
                  disabled={!skillInput.trim()}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <circle cx="11" cy="11" r="8"/>
                    <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                  </svg>
                  Analyze
                </button>
              </div>
              {error && <div className="ask-error-msg">{error}</div>}
              <div className="ask-examples">
                <span className="ask-examples-lbl">Try:</span>
                {["Docker & Kubernetes", "React.js", "System Design", "Cloud Computing"].map((ex) => (
                  <button
                    key={ex}
                    className="ask-example-chip"
                    onClick={() => { setSkillInput(ex); setError(""); }}
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* STATE: ANALYZING */}
          {phase === STATE.ANALYZING && (
            <div className="ask-analyzing-phase">
              <div className="ask-spinner-wrap">
                <div className="ask-spinner" />
              </div>
              <div className="ask-analyzing-title">Analyzing your skill…</div>
              <div className="ask-analyzing-sub">
                Featherless AI is identifying relevant sub-topics and assessment areas for
                <strong> "{skillInput}"</strong>
              </div>
              <div className="ask-pipeline-steps">
                {["Understanding context", "Classifying sub-topics", "Suggesting assessments"].map((step, i) => (
                  <div key={i} className="ask-step">
                    <div className="ask-step-dot active" />
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* STATE: SUGGESTIONS */}
          {phase === STATE.SUGGESTIONS && analysis && (
            <div className="ask-suggestions-phase">
              {/* Skill name header */}
              <div className="ask-skill-header">
                <div className="ask-skill-name-badge">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2.5" strokeLinecap="round">
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                  </svg>
                  {analysis.normalized_name}
                </div>
                {analysis.ai_generated && (
                  <span className="ask-ai-tag">✦ AI Suggested</span>
                )}
              </div>

              {/* Explanation */}
              {analysis.explanation && (
                <p className="ask-explanation">{analysis.explanation}</p>
              )}

              {/* Sub-topics checklist */}
              <div className="ask-subtopics-section">
                <div className="ask-section-title">
                  Sub-topics to track
                  <span className="ask-section-hint">({selected.length} of {analysis.sub_topics.length} selected)</span>
                </div>
                <div className="ask-subtopics-list">
                  {analysis.sub_topics.map((st, i) => (
                    <label key={i} className={`ask-topic-row ${selected.includes(i) ? "checked" : ""}`}>
                      <input
                        type="checkbox"
                        className="ask-topic-checkbox"
                        checked={selected.includes(i)}
                        onChange={() => toggleTopic(i)}
                      />
                      <span className="ask-topic-label">{st.label}</span>
                      <CategoryBadge category={st.category} />
                    </label>
                  ))}
                </div>
              </div>

              {/* Assessment areas */}
              {analysis.assessment_areas && analysis.assessment_areas.length > 0 && (
                <div className="ask-assessment-section">
                  <div className="ask-section-title">Assessment areas</div>
                  <div className="ask-assessment-tags">
                    {analysis.assessment_areas.map((area, i) => (
                      <span key={i} className="ask-assessment-chip">{area}</span>
                    ))}
                  </div>
                </div>
              )}

              {error && <div className="ask-error-msg">{error}</div>}
            </div>
          )}

          {/* STATE: SAVING */}
          {phase === STATE.SAVING && (
            <div className="ask-analyzing-phase">
              <div className="ask-spinner-wrap">
                <div className="ask-spinner save" />
              </div>
              <div className="ask-analyzing-title">Saving skill…</div>
              <div className="ask-analyzing-sub">
                Creating sub-topic state and registering with the Signal Engine
              </div>
            </div>
          )}

          {/* STATE: SUCCESS */}
          {phase === STATE.SUCCESS && (
            <div className="ask-success-phase">
              <div className="ask-success-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/>
                  <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
              </div>
              <div className="ask-success-title">Skill Added!</div>
              <div className="ask-success-sub">
                <strong>{analysis?.normalized_name}</strong> is now tracked by the SDA Signal Engine.
              </div>
            </div>
          )}

          {/* STATE: BASELINE_INTRO */}
          {phase === STATE.BASELINE_INTRO && (
            <div className="ask-success-phase">
              <div className="ask-success-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="16" x2="12" y2="12" />
                  <line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
              </div>
              <div className="ask-success-title">Skill Initialized</div>
              <div className="ask-success-sub" style={{ marginBottom: '20px' }}>
                We need to establish your baseline proficiency for <strong>{analysis?.normalized_name}</strong>.
              </div>
              <p className="ask-hint" style={{ fontSize: '14px', lineHeight: '1.5' }}>
                SDA will generate a short 6-question diagnostic test based on the sub-topics you selected.
                Your answers will set the initial state for the Signal Engine.
              </p>
              {error && <div className="ask-error-msg">{error}</div>}
            </div>
          )}

          {/* STATE: GENERATING_BASELINE */}
          {phase === STATE.GENERATING_BASELINE && (
            <div className="ask-analyzing-phase">
              <div className="ask-spinner-wrap">
                <div className="ask-spinner" />
              </div>
              <div className="ask-analyzing-title">Generating Diagnostic...</div>
              <div className="ask-analyzing-sub">
                AI is crafting 6 targeted questions to assess your baseline.
              </div>
            </div>
          )}
        </div>

        {/* ── Footer ── */}
        {(phase === STATE.INPUT || phase === STATE.SUGGESTIONS || phase === STATE.BASELINE_INTRO) && (
          <div className="ask-modal-footer">
            <button className="ask-cancel-btn" onClick={onClose}>
              Cancel
            </button>
            {phase === STATE.INPUT && (
              <button
                className="ask-primary-btn"
                onClick={handleAnalyze}
                disabled={!skillInput.trim()}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <circle cx="11" cy="11" r="8"/>
                  <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
                Analyze Skill
              </button>
            )}
            {phase === STATE.SUGGESTIONS && (
              <>
                <button
                  className="ask-back-btn"
                  onClick={() => { setPhase(STATE.INPUT); setError(""); }}
                >
                  ← Edit
                </button>
                <button
                  className="ask-primary-btn"
                  onClick={handleAddSkill}
                  disabled={selected.length === 0}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <line x1="12" y1="5" x2="12" y2="19"/>
                    <line x1="5" y1="12" x2="19" y2="12"/>
                  </svg>
                  Confirm Sub-Topics
                </button>
              </>
            )}
            {phase === STATE.BASELINE_INTRO && (
              <button
                className="ask-primary-btn"
                onClick={handleGenerateBaseline}
              >
                Start Baseline Assessment →
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
