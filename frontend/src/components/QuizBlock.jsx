import React, { useState } from "react";

export default function QuizBlock({ result, onSubmitAnswer, submitting, answerResult }) {
  const { subtopic, skill, reason, quiz, cycle_id, action } = result;
  const [selected, setSelected] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  if (action === "WAIT") return null;

  const displayName = subtopic ? subtopic.replace(/_/g, " ") : "";

  if (action === "RECOMMEND") {
    return (
      <div className="action-block">
        <div className="action-header">
          <div>
            <div className="skill-name">{displayName}</div>
            <div className="skill-topic">{skill}</div>
          </div>
          <span className="badge-outline color-blue" style={{ borderColor: "var(--accent)" }}>RECOMMEND</span>
        </div>
        
        {reason && (
          <div className="reasoning-box">
            <strong>System Rationale:</strong> {reason}
          </div>
        )}

        {result.recommendation && (
          <div className="card" style={{ background: "var(--bg-base)", border: "1px solid var(--border)", marginTop: "1rem" }}>
            <div style={{ fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: "0.5rem" }}>
              Suggested Review Material
            </div>
            <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
              {result.recommendation}
            </p>
          </div>
        )}
      </div>
    );
  }

  if (action === "ESCALATE") {
    return (
      <div className="action-block" style={{ borderLeft: "3px solid var(--danger)" }}>
        <div className="action-header">
          <div>
            <div className="skill-name">{displayName}</div>
            <div className="skill-topic">{skill}</div>
          </div>
          <span className="badge-outline color-red" style={{ borderColor: "var(--danger)" }}>ESCALATE</span>
        </div>

        <div className="alert alert-error" style={{ margin: "0.75rem 0" }}>
          <strong>Critical Decay Warning:</strong> Severe retention decline detected without recent practice. Priority revision advised.
        </div>

        {reason && (
          <div className="reasoning-box">
            <strong>Observation:</strong> {reason}
          </div>
        )}
      </div>
    );
  }

  if (action === "TEST_NOW" && quiz && quiz.length > 0) {
    const q = quiz[0];
    const isAnswered = submitted && answerResult;
    const isCorrect = isAnswered && answerResult.grade_result?.correct;

    const handleSubmit = async () => {
      if (!selected || submitted) return;
      setSubmitted(true);
      await onSubmitAnswer({
        subtopic,
        question_id: q.question_id,
        selected_option: selected,
        cycle_id,
      });
    };

    return (
      <div className="action-block">
        <div className="action-header">
          <div>
            <div className="skill-name">{displayName}</div>
            <div className="skill-topic">{skill}</div>
          </div>
          <span className="badge-outline color-amber" style={{ borderColor: "var(--warning)" }}>TEST REQUIRED</span>
        </div>

        {reason && (
          <div className="reasoning-box">
            <strong>Diagnosis:</strong> {reason}
          </div>
        )}

        <div style={{ marginTop: "1rem" }}>
          <div style={{ fontSize: "0.9rem", fontWeight: 500, marginBottom: "0.75rem", color: "var(--text-primary)" }}>
            {q.question}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {Object.entries(q.options || {}).map(([key, val]) => {
              let optionClass = "quiz-option";
              if (isAnswered) {
                const correctKey = answerResult?.grade_result?.correct_answer;
                if (key === correctKey) optionClass += " correct";
                else if (key === selected) optionClass += " wrong";
              } else if (selected === key) {
                optionClass += " selected";
              }

              return (
                <div
                  key={key}
                  className={optionClass}
                  onClick={() => !submitted && setSelected(key)}
                  style={{ cursor: submitted ? "default" : "pointer" }}
                >
                  <div className="radio-circle" />
                  <span style={{ fontWeight: 600, minWidth: "1.5rem" }}>{key}.</span>
                  <span>{val}</span>
                </div>
              );
            })}
          </div>

          {isAnswered ? (
            <div className={`alert ${isCorrect ? "alert-success" : "alert-error"}`} style={{ marginTop: "1rem" }}>
              <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>
                {isCorrect ? "✓ Correct evaluation" : `✗ Incorrect — Correct answer was (${answerResult?.grade_result?.correct_answer})`}
              </div>
              {answerResult?.grade_result?.explanation && (
                <div style={{ fontSize: "0.85rem", opacity: 0.9 }}>
                  {answerResult.grade_result.explanation}
                </div>
              )}
            </div>
          ) : (
            <div style={{ marginTop: "1rem" }}>
              <button
                className="btn btn-primary"
                onClick={handleSubmit}
                disabled={!selected || submitting}
              >
                {submitting ? <span className="spinner" /> : null}
                Submit Evaluation
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Fallback for TEST_NOW without quiz data or errors
  return (
    <div className="action-block">
      <div className="action-header">
        <div>
          <div className="skill-name">{displayName}</div>
          <div className="skill-topic">{skill}</div>
        </div>
        <span className="badge-outline">TEST NOW</span>
      </div>
      {reason && <div className="reasoning-box">{reason}</div>}
      {result.error && <div className="alert alert-error">⚠ {result.error}</div>}
    </div>
  );
}
