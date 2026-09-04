import React, { useState, useEffect, useCallback } from "react";
import "./index.css";
import Sidebar from "./components/Sidebar";
import TopHeader from "./components/TopHeader";
import HomeDashboard from "./components/HomeDashboard";
import ActiveTest from "./components/ActiveTest";
import TestResults from "./components/TestResults";
import UpdatedLearningSignals from "./components/UpdatedLearningSignals";
import FeatherlessDecision from "./components/FeatherlessDecision";
import MyProgressView from "./components/MyProgressView";
import TakeTestLanding from "./components/TakeTestLanding";
import CalendarView from "./components/CalendarView";
import RecommendationsPage from "./components/RecommendationsPage";
import SkillsPage from "./components/SkillsPage";

import { api } from "./api/client";
import Dashboard from "./components/Dashboard";

export default function App() {
  const [currentRoute, setCurrentRoute] = useState("/");
  const [skillsData, setSkillsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Active test session state
  const [activeTestSubject, setActiveTestSubject] = useState("Python");
  const [activeTestSubtopic, setActiveTestSubtopic] = useState("oop_and_design_patterns");
  const [testQuestions, setTestQuestions] = useState([]);
  const [cycleId, setCycleId] = useState(null);
  const [testResultsData, setTestResultsData] = useState(null);
  const [agentDecisionData, setAgentDecisionData] = useState(null);

  const fetchSkills = useCallback(async () => {
    try {
      const data = await api.getSkills();
      setSkillsData(data);
    } catch (e) {
      console.error("Failed to load skills telemetry", e);
    }
  }, []);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  const navigate = (route) => {
    setCurrentRoute(route);
    window.scrollTo(0, 0);
  };

  const handleStartTest = async (subject, subtopicKey) => {
    setLoading(true);
    setError(null);
    setActiveTestSubject(subject);
    setActiveTestSubtopic(subtopicKey);
    try {
      const res = await api.getTestQuestions(subject, subtopicKey);
      setTestQuestions(res.questions);
      setCycleId(res.cycle_id);
      setCurrentRoute(`/test/${encodeURIComponent(subject)}/${encodeURIComponent(subtopicKey)}`);
    } catch (e) {
      setError(e.message || "Failed to load test questions");
    } finally {
      setLoading(false);
    }
  };

  const handleStartBaselineTest = (subject, cycleId, questions) => {
    setActiveTestSubject(subject);
    setActiveTestSubtopic("mixed_baseline");
    setTestQuestions(questions);
    setCycleId(cycleId);
    setCurrentRoute(`/test/${encodeURIComponent(subject)}/baseline`);
  };

  const handleSubmitTest = async (answersPayload) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.submitTest({
        subject: activeTestSubject,
        sub_topic: activeTestSubtopic,
        cycle_id: cycleId,
        answers: answersPayload,
      });

      setTestResultsData(res);
      // Parse agent decisions returned from the feedback loop
      const primaryDec = res.primary_decision || (res.final_state?.agent_decisions && res.final_state.agent_decisions[0]);
      if (primaryDec) {
        setAgentDecisionData({
          action: primaryDec.action || "TEST_NOW",
          targetSubtopic: primaryDec.subtopic ? primaryDec.subtopic.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()) : `${activeTestSubject} — ${activeTestSubtopic.replace(/_/g, " ")}`,
          reason: primaryDec.reason || "Updated signals after test submission indicate this action."
        });
      } else {
        setAgentDecisionData({
          action: "WAIT",
          targetSubtopic: `${activeTestSubject} — ${activeTestSubtopic.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}`,
          reason: "Recent assessment performance demonstrates stable competency with no immediate intervention required."
        });
      }

      await fetchSkills();
      setCurrentRoute(`/test/results/${cycleId}`);
    } catch (e) {
      setError(e.message || "Failed to submit test");
    } finally {
      setLoading(false);
    }
  };

  const handleSimulateClock = async () => {
    setLoading(true);
    try {
      await api.advanceTime(14);
      await fetchSkills();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-layout">
      <Sidebar currentRoute={currentRoute} navigate={navigate} />

      <div className="main-wrapper">
        <TopHeader onSimulateClock={handleSimulateClock} />

        <main className="content-container">
          {error && <div className="alert-banner">⚠️ {error}</div>}

          {/* Screen 1: Dashboard */}
          {(currentRoute === "/" || currentRoute === "/dashboard") && (
            <HomeDashboard
              skillsData={skillsData}
              onTestNowClick={handleStartTest}
              onStartBaselineTest={handleStartBaselineTest}
              loading={loading}
              onRefresh={fetchSkills}
              navigate={navigate}
            />
          )}

          {/* Screen 2A: Dedicated Take Test Landing Page */}
          {currentRoute === "/take-test" && (
            <TakeTestLanding
              onStartTest={handleStartTest}
              loading={loading}
            />
          )}

          {/* Screen 2B: Active Test Page */}
          {currentRoute.startsWith("/test/") && !currentRoute.includes("/results/") && (
            <ActiveTest
              subject={activeTestSubject}
              subtopic={activeTestSubtopic}
              questions={testQuestions}
              onSubmitTest={handleSubmitTest}
              loading={loading}
            />
          )}

          {/* Screen 3: Test Results */}
          {currentRoute.startsWith("/test/results/") && (
            <TestResults
              results={testResultsData}
              onContinue={() => navigate("/progress/updated")}
            />
          )}

          {/* Screen 4: Updated Learning Signals */}
          {currentRoute === "/progress/updated" && (
            <UpdatedLearningSignals
              results={testResultsData}
              onProceedToDecision={() => navigate("/decision")}
            />
          )}

          {/* Screen 5: New Decision from Featherless Agent */}
          {currentRoute === "/decision" && (
            <FeatherlessDecision
              agentDecision={agentDecisionData}
              onGoToNextTest={() => handleStartTest("DSA", "complexity_and_problem_solving")}
            />
          )}

          {/* Screen 6: My Progress */}
          {currentRoute === "/progress" && (
            <MyProgressView
              skillsData={skillsData}
              onTestNow={handleStartTest}
              onRefresh={fetchSkills}
              loading={loading}
            />
          )}

          {/* Screen 7: Dedicated Calendar and Adaptive Future Timetable */}
          {currentRoute === "/calendar" && (
            <CalendarView
              onStartTest={handleStartTest}
              onNavigate={navigate}
            />
          )}

          {/* Secondary views */}
          {currentRoute === "/recommendations" && (
            <RecommendationsPage
              onTestNowClick={handleStartTest}
              loading={loading}
            />
          )}
          {currentRoute === "/skills" && (
            <SkillsPage
              skillsData={skillsData}
              onTestNowClick={handleStartTest}
              onStartBaselineTest={handleStartBaselineTest}
              onRefresh={fetchSkills}
              loading={loading}
            />
          )}
          {currentRoute === "/reports" && <Dashboard activeTab="insights" />}
          {currentRoute === "/settings" && <Dashboard activeTab="time" />}
        </main>
      </div>
    </div>
  );
}
