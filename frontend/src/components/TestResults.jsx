import React from "react";

export default function TestResults({ results, onContinue }) {
  if (!results) return null;

  const total = results.detailed_answers?.length || 5;
  const correctCount = results.detailed_answers?.filter((a) => a.correct).length || 0;
  const incorrectCount = total - correctCount;
  const accuracyPct = Math.round((correctCount / total) * 100);

  // Generate breakdown based on user's actual responses
  const subtopicClean = results.sub_topic.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  
  // Distribute detailed answers across sub-components of the topic
  const details = results.detailed_answers || [];
  const part1 = details.slice(0, 2);
  const part2 = details.slice(2, 4);
  const part3 = details.slice(4);

  const c1 = part1.filter(d => d.correct).length;
  const t1 = part1.length || 2;
  const p1 = Math.round((c1 / t1) * 100);

  const c2 = part2.filter(d => d.correct).length;
  const t2 = part2.length || 2;
  const p2 = Math.round((c2 / t2) * 100);

  const c3 = part3.filter(d => d.correct).length;
  const t3 = part3.length || 1;
  const p3 = Math.round((c3 / t3) * 100);

  const topicBreakdown = [
    {
      topic: `${subtopicClean} Concepts`,
      correct: c1,
      total: t1,
      pct: p1,
      color: p1 >= 70 ? "#10b981" : p1 >= 40 ? "#f59e0b" : "#ef4444"
    },
    {
      topic: "Core Logic & Syntax",
      correct: c2,
      total: t2,
      pct: p2,
      color: p2 >= 70 ? "#10b981" : p2 >= 40 ? "#f59e0b" : "#ef4444"
    },
    {
      topic: "Complex Applications",
      correct: c3,
      total: t3,
      pct: p3,
      color: p3 >= 70 ? "#10b981" : p3 >= 40 ? "#f59e0b" : "#ef4444"
    },
  ];

  return (
    <div className="results-wrapper">
      <div className="results-white-card">
        <div className="results-trophy-circle">
          🏆
        </div>

        <h1 className="results-card-title">Test Submitted Successfully!</h1>
        <p className="results-card-sub">
          Here are your results for {results.subject} — {subtopicClean}
        </p>

        <div className="results-metrics-grid">
          {/* Circular gauge card */}
          <div className="res-gauge-card">
            <div className="res-gauge-circle">
              <span className="res-gauge-big">{correctCount}/{total}</span>
            </div>
            <div className="res-gauge-label">Correct Answers</div>
          </div>

          <div className="res-gauge-card">
            <div className="res-gauge-circle">
              <span className="res-gauge-big">{accuracyPct}%</span>
            </div>
            <div className="res-gauge-label">Accuracy</div>
          </div>

          <div className="res-gauge-card">
            <div className="res-gauge-circle">
              <span className="res-gauge-big text-green">{correctCount}</span>
            </div>
            <div className="res-gauge-label">Correct</div>
          </div>

          <div className="res-gauge-card">
            <div className="res-gauge-circle">
              <span className="res-gauge-big text-red">{incorrectCount}</span>
            </div>
            <div className="res-gauge-label">Incorrect</div>
          </div>
        </div>

        <div className="res-topic-section">
          <h3 className="res-topic-title">Performance by Topic</h3>

          <div className="res-topic-list">
            {topicBreakdown.map((item) => (
              <div className="res-topic-item" key={item.topic}>
                <div className="res-topic-lead">
                  <span className="res-topic-bullet">📋</span>
                  <span className="res-topic-name">{item.topic}</span>
                </div>

                <div className="res-topic-bar-wrap">
                  <div className="res-topic-track">
                    <div
                      className="res-topic-fill"
                      style={{ width: `${item.pct}%`, backgroundColor: item.color }}
                    />
                  </div>
                </div>

                <div className="res-topic-score">{item.correct}/{item.total}</div>
                <div className="res-topic-pct">{item.pct}%</div>
              </div>
            ))}
          </div>

          <div className="res-breakdown-btn-wrap">
            <button className="btn-view-breakdown">View Detailed Breakdown</button>
          </div>
        </div>

        <div className="res-bottom-action">
          <button className="btn-res-continue" onClick={onContinue}>
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}
