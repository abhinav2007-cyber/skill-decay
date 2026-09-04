import React, { useState, useEffect } from "react";

export default function ActiveTest({ subject, subtopic, questions, onSubmitTest, loading }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [timeLeft, setTimeLeft] = useState(272); // 04:32 countdown

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  if (!questions || questions.length === 0) {
    return (
      <div className="test-page-container">
        <div className="card-loading">Loading assessment questions...</div>
      </div>
    );
  }

  const currentQ = questions[currentIndex];
  const totalQ = questions.length;
  const isLast = currentIndex === totalQ - 1;

  const handleSelectOption = (optionText) => {
    setAnswers((prev) => ({
      ...prev,
      [currentQ.question_id]: optionText,
    }));
  };

  const handleNext = () => {
    if (currentIndex < totalQ - 1) {
      setCurrentIndex((prev) => prev + 1);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1);
    }
  };

  const handleSubmit = () => {
    const payload = questions.map((q) => ({
      question_id: q.question_id,
      selected_option: answers[q.question_id] || "",
    }));
    onSubmitTest(payload);
  };


  // Parse code block if formatted with markdown
  let questionText = currentQ.question;
  let codeSnippet = null;
  if (currentQ.question.includes("```")) {
    const parts = currentQ.question.split("```");
    questionText = parts[0].trim();
    codeSnippet = parts[1] ? parts[1].replace(/^(python|java|sql)/i, "").trim() : null;
  }

  return (
    <div className="test-page-container">
      {/* Subject Header & Countdown Badge */}
      <div className="test-top-header">
        <div className="test-subject-identity">
          <span className="test-subject-icon">
            {subject === "Python" ? "🐍" : subject === "Java" ? "☕" : subject === "DBMS" ? "🗄️" : subject === "Machine Learning" ? "🧠" : "⚡"}
          </span>
          <h2 className="test-subject-title">
            {subject} — {subtopic.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
          </h2>
        </div>

        <div className="test-timer-box">
          <span className="timer-title">Time Left</span>
          <span className="timer-digits">{formatTime(timeLeft)}</span>
        </div>
      </div>

      {/* Question progress */}
      <div className="test-progress-section">
        <span className="test-progress-counter">Question {currentIndex + 1} of {totalQ}</span>
        <div className="test-progress-rail">
          <div
            className="test-progress-indicator"
            style={{ width: `${((currentIndex + 1) / totalQ) * 100}%` }}
          />
        </div>
      </div>

      {/* Large white card matching mock */}
      <div className="mock-question-card">
        <div className="q-badge-num">Q{currentIndex + 1}</div>

        <div className="q-title-text">{questionText}</div>

        {codeSnippet && (
          <div className="mock-code-block">
            <div className="code-lines">
              {codeSnippet.split("\n").map((line, idx) => (
                <div key={idx} className="code-line-row">
                  <span className="line-num">{idx + 1}</span>
                  <span className="line-code">{line}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mock-options-group">
          {currentQ.options.map((opt, idx) => {
            const isSelected = answers[currentQ.question_id] === opt;
            return (
              <div
                key={idx}
                className={`mock-option-row ${isSelected ? "selected" : ""}`}
                onClick={() => handleSelectOption(opt)}
              >
                <div className="mock-radio-disc">
                  {isSelected && <div className="mock-radio-dot" />}
                </div>
                <div className="mock-option-content">{opt}</div>
              </div>
            );
          })}
        </div>

        <div className="mock-test-nav-bar">
          <button
            className="mock-btn-prev"
            onClick={handlePrev}
            disabled={currentIndex === 0 || loading}
          >
            ← Previous
          </button>

          {isLast ? (
            <button
              className="mock-btn-submit"
              onClick={handleSubmit}
              disabled={loading}
            >
              {loading ? "Submitting..." : "Submit Test"}
            </button>
          ) : (
            <button
              className="mock-btn-next"
              onClick={handleNext}
              disabled={loading}
            >
              Next →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
