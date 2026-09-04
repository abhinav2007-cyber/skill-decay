import React, { useState, useEffect } from "react";

const DOMAINS = [
  {
    subject: "Python",
    icon: "🐍",
    color: "#0284c7",
    bg: "#f0f9ff",
    border: "#bae6fd",
    subtopics: [
      { key: "syntax_and_core_libraries", label: "Syntax & Core Libraries", cat: "Procedural", desc: "Built-ins, data structures, list comprehensions, generators, slices" },
      { key: "oop_and_design_patterns", label: "OOP & Design Patterns", cat: "Conceptual", desc: "Classes, MRO (C3 Linearization), GIL, __slots__, decorators" },
    ]
  },
  {
    subject: "Java",
    icon: "☕",
    color: "#d97706",
    bg: "#fffbeb",
    border: "#fde68a",
    subtopics: [
      { key: "syntax_and_collections", label: "Syntax & Collections", cat: "Procedural", desc: "HashMap treeification, Generics (? super T), Streams, Collections" },
      { key: "oop_and_jvm_concepts", label: "OOP & JVM Concepts", cat: "Conceptual", desc: "JVM Memory (Metaspace), Method hiding, volatile, Double-checked locking" },
    ]
  },
  {
    subject: "DBMS",
    icon: "🗄️",
    color: "#2563eb",
    bg: "#eff6ff",
    border: "#bfdbfe",
    subtopics: [
      { key: "sql_queries_and_joins", label: "SQL Queries & Joins", cat: "Procedural", desc: "ANSI SQL processing order, Theta join, TRUNCATE vs DELETE, B+ Trees" },
      { key: "normalization_and_transactions", label: "Normalization & Transactions", cat: "Conceptual", desc: "1NF-BCNF normal forms, Dirty reads, Strict 2PL, ARIES Redo phase" },
    ]
  },
  {
    subject: "Machine Learning",
    icon: "🧠",
    color: "#7c3aed",
    bg: "#f5f3ff",
    border: "#ddd6fe",
    subtopics: [
      { key: "model_apis_and_libraries", label: "Model APIs & Libraries", cat: "Procedural", desc: "Confusion matrix metrics (Precision), PCA eigenvectors, CNN spatial sizing, SMOTE" },
      { key: "algorithms_and_theory", label: "Algorithms & Theory", cat: "Conceptual", desc: "L1 vs L2 regularization, Bias-Variance tradeoff, Sigmoid vanishing gradient, SVM support vectors" },
    ]
  },
  {
    subject: "DSA",
    icon: "⚡",
    color: "#059669",
    bg: "#ecfdf5",
    border: "#a7f3d0",
    subtopics: [
      { key: "implementation_and_syntax", label: "Implementation & Syntax", cat: "Procedural", desc: "Single queue stacks, AVL rotations (RL), DSU Inverse Ackermann, Prefix evaluation" },
      { key: "complexity_and_problem_solving", label: "Complexity & Problem Solving", cat: "Conceptual", desc: "BST worst case, In-place stable sorts, Bottom-up heap construction, 0/1 Knapsack DP" },
    ]
  }
];

export default function TakeTestLanding({ onStartTest, loading }) {
  const [selectedSubject, setSelectedSubject] = useState("DBMS");
  const [selectedSubtopic, setSelectedSubtopic] = useState("normalization_and_transactions");

  const currentDomain = DOMAINS.find(d => d.subject === selectedSubject) || DOMAINS[0];

  const handleSubjectChange = (subj) => {
    setSelectedSubject(subj);
    const domain = DOMAINS.find(d => d.subject === subj);
    if (domain && domain.subtopics.length > 0) {
      setSelectedSubtopic(domain.subtopics[0].key);
    }
  };

  const selectedSubtopicObj = currentDomain.subtopics.find(st => st.key === selectedSubtopic) || currentDomain.subtopics[0];

  return (
    <div className="take-test-page">
      {/* Header */}
      <div className="tt-page-header">
        <div className="tt-header-left">
          <div className="tt-badge-official">
            <span className="tt-badge-dot"></span>
            Official Question Bank • 50 Diagnostic MCQs
          </div>
          <h1 className="tt-page-title">Take Diagnostic Test</h1>
          <p className="tt-page-subtitle">
            Choose a domain and sub-topic to start your timed technical assessment. All questions are dynamically queried from the project database and evaluated by the SDA Signal Engine.
          </p>
        </div>
      </div>

      {/* Domain Selection Tabs */}
      <div className="tt-domain-selector">
        {DOMAINS.map(domain => {
          const isSelected = domain.subject === selectedSubject;
          return (
            <button
              key={domain.subject}
              className={`tt-domain-tab ${isSelected ? "active" : ""}`}
              style={{
                "--active-color": domain.color,
                "--active-bg": domain.bg,
                "--active-border": domain.border
              }}
              onClick={() => handleSubjectChange(domain.subject)}
            >
              <span className="tt-domain-icon">{domain.icon}</span>
              <span className="tt-domain-name">{domain.subject}</span>
              <span className="tt-domain-count">10 MCQs</span>
            </button>
          );
        })}
      </div>

      {/* Main Configuration Card */}
      <div className="tt-config-card">
        <div className="tt-config-header">
          <div className="tt-config-icon" style={{ backgroundColor: currentDomain.bg, borderColor: currentDomain.border, color: currentDomain.color }}>
            {currentDomain.icon}
          </div>
          <div>
            <h2 className="tt-config-title">{currentDomain.subject} Knowledge Assessment</h2>
            <p className="tt-config-sub">Select a targeted sub-topic module to validate your knowledge retention.</p>
          </div>
        </div>

        {/* Sub-Topic Radio Selector Cards */}
        <div className="tt-subtopics-grid">
          {currentDomain.subtopics.map(st => {
            const isSelected = st.key === selectedSubtopic;
            return (
              <div
                key={st.key}
                className={`tt-subtopic-card ${isSelected ? "selected" : ""}`}
                onClick={() => setSelectedSubtopic(st.key)}
              >
                <div className="tt-subtopic-top">
                  <div className="tt-radio-circle">
                    {isSelected && <div className="tt-radio-dot" />}
                  </div>
                  <div className="tt-subtopic-headings">
                    <span className="tt-subtopic-title">{st.label}</span>
                    <span className={`tt-cat-badge ${st.cat.toLowerCase()}`}>{st.cat}</span>
                  </div>
                </div>
                <p className="tt-subtopic-desc">{st.desc}</p>
                <div className="tt-subtopic-meta">
                  <span>⏱️ ~5 mins</span>
                  <span>📝 5 Rigorous MCQs</span>
                  <span>🎯 pyBKT Knowledge Tracked</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Instructions & Parameters */}
        <div className="tt-instructions-panel">
          <h3 className="tt-inst-title">Assessment Guidelines & Rules</h3>
          <ul className="tt-inst-list">
            <li>
              <strong>Authentic MCQ Assessment:</strong> Questions, options, and explanations originate directly from the verified Core Technical Assessment Question Bank stored in the database.
            </li>
            <li>
              <strong>Server-Side Security:</strong> Correct answers are graded strictly backend-side and never exposed to the client prior to final submission.
            </li>
            <li>
              <strong>Decay & pyBKT Integration:</strong> Your graded answers immediately feed into the <strong>SDA Signal Engine</strong> to update knowledge probability, recent accuracy, and knowledge decay state.
            </li>
            <li>
              <strong>Featherless Decision Loop:</strong> Once updated, the signal bundle is sent to the Featherless Decision Agent to recommend next actions (<code>TEST_NOW</code>, <code>WAIT</code>, <code>RECOMMEND</code>, <code>ESCALATE</code>) with reasonings.
            </li>
          </ul>
        </div>

        {/* Action Button */}
        <div className="tt-cta-bar">
          <div className="tt-selected-summary">
            Selected: <strong>{currentDomain.subject}</strong> → <em>{selectedSubtopicObj.label}</em>
          </div>
          <button
            className="tt-btn-start"
            disabled={loading}
            onClick={() => onStartTest(selectedSubject, selectedSubtopic)}
          >
            {loading ? "Initializing Test..." : "Start Test Now →"}
          </button>
        </div>
      </div>
    </div>
  );
}
