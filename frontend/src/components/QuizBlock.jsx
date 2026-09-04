import React, { useState } from "react";

export default function QuizBlock({ result, onSubmitAnswer, submitting, answerResult }) {
  const { subtopic, skill, reason, quiz, cycle_id, action } = result;
  const [selected, setSelected] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  if (action === "WAIT") return null;

  if (action === "RECOMMEND") {
    return (
      <div className="cycle-item fade-in">
        <div className="cycle-item-header">
          <div>
            <div className="cycle-item-skill">{skill}</div>
            <div className="cycle-item-name">{subtopic.replace(/_/g, " ")}</div>
          </div>
          <span className="badge badge-recommend">RECOMMEND</span>
        </div>
        <div className="cycle-reason">{reason}</div>
        {result.recommendation && (
          <div className="rec-panel" style={{ marginTop: "0.75rem" }}>
            <div className="section-label" style={{ marginBottom: "0.5rem" }}>📚 Refresher</div>
            <p className="rec-text">{result.recommendation}</p>
          </div>
        )}
      </div>
    );
  }

  if (action === "ESCALATE") {
    return (
      <div className="cycle-item fade-in">
        <div className="cycle-item-header">
          <div>
            <div className="cycle-item-skill">{skill}</div>
            <div className="cycle-item-name">{subtopic.replace(/_/g, " ")}</div>
          </div>
          <span className="badge badge-escalate">ESCALATE</span>
        </div>
        <div className="esc-panel">
          <span className="esc-icon">⚠️</span>
          <span className="esc-text">Critical decay detected. Immediate action required.</span>
        </div>
        <div className="cycle-reason">{reason}</div>
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
      <div className="cycle-item fade-in">
        <div className="cycle-item-header">
          <div>
            <div className="cycle-item-skill">{skill}</div>
            <div className="cycle-item-name">{subtopic.replace(/_/g, " ")}</div>
          </div>
          <span className="badge badge-test">TEST NOW</span>
        </div>
        <div className="cycle-reason">{reason}</div>

        <div className="quiz-panel" style={{ marginTop: "1rem" }}>
          <div className="quiz-question">{q.question}</div>
          <div className="quiz-options">
            {Object.entries(q.options || {}).map(([key, val]) => {
              let cls = "quiz-option";
              if (isAnswered) {
                const correctKey = answerResult?.grade_result?.correct_answer;
                if (key === correctKey) cls += " correct";
                else if (key === selected) cls += " wrong";
              } else if (selected === key) {
                cls += " selected";
              }
              return (
                <div key={key} className={cls} onClick={() => !submitted && setSelected(key)}>
                  <span className="option-key">{key}</span>
                  <span>{val}</span>
                </div>
              );
            })}
          </div>

          {isAnswered ? (
            <div className={`quiz-feedback ${isCorrect ? "correct" : "wrong"}`}>
              {isCorrect ? "✓ Correct!" : `✗ Incorrect — correct answer: ${answerResult?.grade_result?.correct_answer}`}
              {answerResult?.grade_result?.explanation && (
                <div className="quiz-explanation">{answerResult.grade_result.explanation}</div>
              )}
            </div>
          ) : (
            <button
              className="btn btn-primary btn-sm"
              onClick={handleSubmit}
              disabled={!selected || submitting}
            >
              {submitting ? <span className="spinner spinner-sm" /> : null}
              Submit Answer
            </button>
          )}
        </div>
      </div>
    );
  }

  // Fallback for TEST_NOW without quiz data
  return (
    <div className="cycle-item fade-in">
      <div className="cycle-item-header">
        <div>
          <div className="cycle-item-skill">{skill}</div>
          <div className="cycle-item-name">{subtopic.replace(/_/g, " ")}</div>
        </div>
        <span className="badge badge-test">TEST NOW</span>
      </div>
      <div className="cycle-reason">{reason}</div>
      {result.error && <div className="alert alert-error" style={{ marginTop: "0.5rem" }}>⚠ {result.error}</div>}
    </div>
  );
}
