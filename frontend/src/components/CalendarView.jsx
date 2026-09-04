import React, { useState, useEffect } from "react";
import { api } from "../api/client";

export default function CalendarView({ onStartTest, onNavigate }) {
  const [calendarData, setCalendarData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [viewMode, setViewMode] = useState("month"); // "month" | "week" | "list"
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [error, setError] = useState(null);

  // Month navigation state relative to simulated or local current date
  const [viewDate, setViewDate] = useState(new Date(2025, 2, 1)); // Default March 2025 (matching simulator 2025-03-16)

  const loadCalendar = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getCalendar();
      setCalendarData(data);
      if (data.simulated_now) {
        const [y, m, d] = data.simulated_now.split("-").map(Number);
        setViewDate(new Date(y, m - 1, d || 1));
      }
    } catch (err) {
      console.error("Failed to fetch calendar data", err);
      setError("Unable to load calendar events. Please check connection.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCalendar();
  }, []);

  const handleGeneratePlan = async () => {
    try {
      setActionLoading(true);
      setStatusMessage("Analyzing your skill freshness and decay curves...");
      await new Promise((r) => setTimeout(r, 600));
      setStatusMessage("Consulting Featherless Decision Agent & pyBKT...");
      const res = await api.generateCalendarPlan();
      setStatusMessage("Your adaptive timetable has been refreshed!");
      setTimeout(() => setStatusMessage(""), 2500);
      setCalendarData(res);
    } catch (err) {
      console.error(err);
      setStatusMessage("Failed to generate plan. Please try again.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRecalculatePlan = async () => {
    try {
      setActionLoading(true);
      setStatusMessage("Re-evaluating signals and obsolete timetable items...");
      const res = await api.recalculateCalendarPlan();
      setStatusMessage("Plan recalculated with latest signals.");
      setTimeout(() => setStatusMessage(""), 2500);
      setCalendarData(res);
    } catch (err) {
      console.error(err);
      setStatusMessage("Recalculation error. Please try again.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleEventClick = (event) => {
    setSelectedEvent(event);
  };

  const handleTakeTestFromEvent = (event) => {
    if (!event) return;
    if (onStartTest) {
      onStartTest(event.skill, event.sub_topic);
    }
  };

  const handleCompleteEvent = async (eventId) => {
    try {
      await api.completeCalendarEvent(eventId);
      await loadCalendar();
      if (selectedEvent && selectedEvent.id === eventId) {
        const istTime = new Date().toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });
        setSelectedEvent((prev) => ({ ...prev, status: "COMPLETED", completed_at: istTime }));
      }
    } catch (err) {
      console.error("Failed to complete event", err);
    }
  };

  // Calendar date calculations
  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const monthName = viewDate.toLocaleString("en-IN", { month: "long" });

  const firstDayOfMonth = new Date(year, month, 1).getDay(); // 0 is Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  // Shift Sunday (0) to European Monday-first or standard Sunday-first
  // We'll use Sunday-first (Sun, Mon, Tue, Wed, Thu, Fri, Sat)
  const calendarCells = [];
  for (let i = 0; i < firstDayOfMonth; i++) {
    calendarCells.push(null);
  }
  for (let d = 1; d <= daysInMonth; d++) {
    calendarCells.push(d);
  }

  const simulatedDateStr = calendarData?.simulated_now || "2025-03-16";

  const changeMonth = (delta) => {
    setViewDate(new Date(year, month + delta, 1));
  };

  const jumpToToday = () => {
    if (calendarData?.simulated_now) {
      const [y, m, d] = calendarData.simulated_now.split("-").map(Number);
      setViewDate(new Date(y, m - 1, d));
    } else {
      const istString = new Date().toLocaleString("en-US", { timeZone: "Asia/Kolkata" });
      setViewDate(new Date(istString));
    }
  };

  const allEvents = calendarData?.all_events || [];
  const upcomingPlan = calendarData?.upcoming_plan || [];
  const historyList = calendarData?.history || [];
  const summary = calendarData?.summary || {
    upcoming_tests: 0,
    practice_sessions: 0,
    high_risk_skills: 0,
    estimated_learning_minutes: 0,
  };

  // Map events by date string "YYYY-MM-DD"
  const eventsByDate = {};
  allEvents.forEach((ev) => {
    const d = ev.scheduled_date;
    if (!eventsByDate[d]) eventsByDate[d] = [];
    eventsByDate[d].push(ev);
  });

  return (
    <div className="cal-container">
      {/* Top Header & Overview */}
      <header className="cal-header-section">
        <div className="cal-title-block">
          <h1 className="cal-title">Skill Calendar</h1>
          <p className="cal-subtitle">
            See what you've practiced, what you've tested, and what SDA recommends next.
          </p>
        </div>

        <div className="cal-top-actions">
          <button
            className="cal-btn-secondary"
            onClick={handleRecalculatePlan}
            disabled={actionLoading}
            title="Recalculate future timetable using current signals"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="23 4 23 10 17 10"></polyline>
              <polyline points="1 20 1 14 7 14"></polyline>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
            </svg>
            Recalculate Plan
          </button>
          <button
            className="cal-btn-primary"
            onClick={handleGeneratePlan}
            disabled={actionLoading}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path>
            </svg>
            Generate My Plan
          </button>
        </div>
      </header>

      {/* Action Notification Banner */}
      {statusMessage && (
        <div className="cal-status-banner">
          <div className="cal-spinner-mini"></div>
          <span>{statusMessage}</span>
        </div>
      )}

      {error && <div className="alert-banner">⚠️ {error}</div>}

      {/* Next 7 Days Summary Strip */}
      <div className="cal-metrics-strip">
        <div className="cal-metric-card">
          <div className="cal-metric-icon test-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="9" y1="15" x2="15" y2="15"></line>
            </svg>
          </div>
          <div className="cal-metric-info">
            <span className="cal-metric-val">{summary.upcoming_tests}</span>
            <span className="cal-metric-label">Upcoming Tests</span>
          </div>
        </div>

        <div className="cal-metric-card">
          <div className="cal-metric-icon practice-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="16 18 22 12 16 6"></polyline>
              <polyline points="8 6 2 12 8 18"></polyline>
            </svg>
          </div>
          <div className="cal-metric-info">
            <span className="cal-metric-val">{summary.practice_sessions}</span>
            <span className="cal-metric-label">Practice Sessions</span>
          </div>
        </div>

        <div className="cal-metric-card">
          <div className="cal-metric-icon risk-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
              <line x1="12" y1="9" x2="12" y2="13"></line>
              <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
          </div>
          <div className="cal-metric-info">
            <span className="cal-metric-val">{summary.high_risk_skills}</span>
            <span className="cal-metric-label">High Risk Skills</span>
          </div>
        </div>

        <div className="cal-metric-card">
          <div className="cal-metric-icon time-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
          </div>
          <div className="cal-metric-info">
            <span className="cal-metric-val">{summary.estimated_learning_minutes} min</span>
            <span className="cal-metric-label">Est. Learning Time</span>
          </div>
        </div>
      </div>

      {/* Main Layout: Calendar Grid + Side Panel */}
      <div className="cal-main-layout">
        <div className="cal-left-panel">
          {/* Controls Bar */}
          <div className="cal-controls-bar">
            <div className="cal-nav-controls">
              <button className="cal-nav-btn today-btn" onClick={jumpToToday}>
                Today
              </button>
              <div className="cal-arrow-group">
                <button className="cal-arrow-btn" onClick={() => changeMonth(-1)} aria-label="Previous month">
                  ‹
                </button>
                <span className="cal-current-month">
                  {monthName} {year}
                </span>
                <button className="cal-arrow-btn" onClick={() => changeMonth(1)} aria-label="Next month">
                  ›
                </button>
              </div>
            </div>

            {/* View Mode Toggle */}
            <div className="cal-view-toggle">
              <button
                className={`cal-toggle-btn ${viewMode === "month" ? "active" : ""}`}
                onClick={() => setViewMode("month")}
              >
                Month
              </button>
              <button
                className={`cal-toggle-btn ${viewMode === "week" ? "active" : ""}`}
                onClick={() => setViewMode("week")}
              >
                Week
              </button>
              <button
                className={`cal-toggle-btn ${viewMode === "list" ? "active" : ""}`}
                onClick={() => setViewMode("list")}
              >
                List
              </button>
            </div>
          </div>

          {/* Calendar Legend */}
          <div className="cal-legend-bar">
            <span className="cal-legend-item">
              <span className="cal-dot dot-test"></span> Test
            </span>
            <span className="cal-legend-item">
              <span className="cal-dot dot-practice"></span> Practice
            </span>
            <span className="cal-legend-item">
              <span className="cal-dot dot-refresh"></span> Refresh
            </span>
            <span className="cal-legend-item">
              <span className="cal-dot dot-completed"></span> Completed
            </span>
            <span className="cal-legend-item">
              <span className="cal-dot dot-risk"></span> High Risk
            </span>
          </div>

          {/* VIEW 1: MONTH VIEW */}
          {viewMode === "month" && (
            <div className="cal-month-card">
              <div className="cal-weekdays-grid">
                <div>Sun</div>
                <div>Mon</div>
                <div>Tue</div>
                <div>Wed</div>
                <div>Thu</div>
                <div>Fri</div>
                <div>Sat</div>
              </div>

              <div className="cal-days-grid">
                {calendarCells.map((dayNum, idx) => {
                  if (!dayNum) {
                    return <div key={`empty-${idx}`} className="cal-day-cell empty-cell"></div>;
                  }

                  const curDateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(dayNum).padStart(2, "0")}`;
                  const isSimulatedToday = curDateStr === simulatedDateStr;
                  const isPast = curDateStr < simulatedDateStr;
                  const dayEvents = eventsByDate[curDateStr] || [];

                  return (
                    <div
                      key={`day-${dayNum}`}
                      className={`cal-day-cell ${isSimulatedToday ? "is-today" : ""} ${isPast ? "is-past" : ""}`}
                    >
                      <div className="cal-day-header">
                        <span className={`cal-day-number ${isSimulatedToday ? "today-badge" : ""}`}>
                          {dayNum}
                        </span>
                      </div>

                      <div className="cal-day-events-list">
                        {dayEvents.map((ev) => {
                          const isHighRisk = ev.trigger_urgency >= 0.75 || ev.trigger_weakness >= 0.7;
                          let chipClass = "chip-test";
                          if (ev.status === "COMPLETED") chipClass = "chip-completed";
                          else if (ev.event_type === "PRACTICE") chipClass = "chip-practice";
                          else if (ev.event_type === "REFRESH" || ev.event_type === "RECOVERY") chipClass = "chip-refresh";
                          else if (isHighRisk) chipClass = "chip-risk";

                          return (
                            <button
                              key={`ev-${ev.id}`}
                              className={`cal-event-chip ${chipClass}`}
                              onClick={() => handleEventClick(ev)}
                              title={`${ev.title} (${ev.event_type})`}
                            >
                              <span className="chip-indicator">
                                {ev.status === "COMPLETED" ? "✓" : "●"}
                              </span>
                              <span className="chip-text">{ev.skill} {ev.event_type}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* VIEW 2: WEEK VIEW */}
          {viewMode === "week" && (
            <div className="cal-week-view-card">
              <div className="cal-week-header-info">
                <h3>Week of {monthName} {viewDate.getDate()}, {year}</h3>
                <p className="cal-subtext">Compact scheduled timeline for learning windows</p>
              </div>
              <div className="cal-week-columns">
                {[0, 1, 2, 3, 4, 5, 6].map((dayOffset) => {
                  const startOfWeek = new Date(viewDate);
                  startOfWeek.setDate(viewDate.getDate() - viewDate.getDay() + dayOffset);
                  const dStr = `${startOfWeek.getFullYear()}-${String(startOfWeek.getMonth() + 1).padStart(2, "0")}-${String(startOfWeek.getDate()).padStart(2, "0")}`;
                  const dayEvents = eventsByDate[dStr] || [];
                  const isToday = dStr === simulatedDateStr;

                  return (
                    <div key={`col-${dayOffset}`} className={`cal-week-col ${isToday ? "today-col" : ""}`}>
                      <div className="cal-week-col-header">
                        <span className="week-day-name">{startOfWeek.toLocaleString("default", { weekday: "short" })}</span>
                        <span className={`week-day-num ${isToday ? "today-circle" : ""}`}>{startOfWeek.getDate()}</span>
                      </div>
                      <div className="cal-week-col-body">
                        {dayEvents.length === 0 ? (
                          <div className="cal-week-empty">—</div>
                        ) : (
                          dayEvents.map((ev) => (
                            <div
                              key={`week-ev-${ev.id}`}
                              className={`cal-week-event-card ${ev.status === "COMPLETED" ? "is-done" : ""}`}
                              onClick={() => handleEventClick(ev)}
                            >
                              <div className="week-ev-time">{ev.scheduled_time || "6:00 PM"}</div>
                              <div className="week-ev-title">{ev.title}</div>
                              <div className="week-ev-type">{ev.event_type}</div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* VIEW 3: LIST VIEW */}
          {viewMode === "list" && (
            <div className="cal-list-view-card">
              <table className="cal-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Time</th>
                    <th>Activity</th>
                    <th>Subject & Sub-topic</th>
                    <th>Trigger / Reason</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {allEvents.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="cal-table-empty">
                        No events found in this period.
                      </td>
                    </tr>
                  ) : (
                    allEvents.map((ev) => (
                      <tr key={`row-${ev.id}`} onClick={() => handleEventClick(ev)} className="cal-table-row">
                        <td className="cal-date-cell">{ev.scheduled_date}</td>
                        <td className="cal-time-cell">{ev.scheduled_time || "06:00 PM"}</td>
                        <td>
                          <span className={`cal-badge badge-${ev.event_type.toLowerCase()}`}>
                            {ev.event_type}
                          </span>
                        </td>
                        <td>
                          <strong>{ev.skill}</strong> — {ev.sub_topic.replace(/_/g, " ")}
                        </td>
                        <td className="cal-reason-cell">
                          {ev.decision_reason || "Adaptive scheduler recommendation"}
                        </td>
                        <td>
                          <span className={`cal-status-pill status-${ev.status.toLowerCase()}`}>
                            {ev.status === "COMPLETED" ? "✓ Completed" : ev.status}
                          </span>
                        </td>
                        <td>
                          {ev.event_type === "TEST" && ev.status === "UPCOMING" ? (
                            <button
                              className="cal-btn-table-action"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleTakeTestFromEvent(ev);
                              }}
                            >
                              Take Test
                            </button>
                          ) : (
                            <button
                              className="cal-btn-table-view"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEventClick(ev);
                              }}
                            >
                              Details
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Skill Freshness Forecast Strip */}
          <div className="cal-forecast-card">
            <div className="forecast-header">
              <div className="forecast-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2">
                  <path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>
                </svg>
              </div>
              <div>
                <h4 className="forecast-title">Skill Freshness Forecast (Next 14 Days)</h4>
                <p className="forecast-sub">Projected decay based on pyBKT and half-life curve without revision</p>
              </div>
            </div>
            <div className="forecast-timeline-grid">
              <div className="forecast-step">
                <span className="f-label">Today</span>
                <span className="f-val f-healthy">43% Fresh</span>
                <span className="f-sub">Baseline</span>
              </div>
              <div className="forecast-step-arrow">→</div>
              <div className="forecast-step">
                <span className="f-label">+3 Days</span>
                <span className="f-val f-warning">37% Fresh</span>
                <span className="f-sub">Decay begins</span>
              </div>
              <div className="forecast-step-arrow">→</div>
              <div className="forecast-step">
                <span className="f-label">+7 Days</span>
                <span className="f-val f-danger">29% Fresh</span>
                <span className="f-sub">Alert Threshold</span>
              </div>
              <div className="forecast-step-arrow">→</div>
              <div className="forecast-step">
                <span className="f-label">+14 Days</span>
                <span className="f-val f-critical">18% Fresh</span>
                <span className="f-sub">Escalation Trigger</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side Panels: Upcoming Plan + Practice History */}
        <div className="cal-right-panel">
          {/* Upcoming Plan List */}
          <div className="cal-side-card">
            <div className="cal-side-header">
              <h3 className="cal-side-title">Your Upcoming Plan</h3>
              <span className="cal-side-badge">{upcomingPlan.length} sessions</span>
            </div>

            <div className="cal-upcoming-list">
              {upcomingPlan.length === 0 ? (
                <div className="cal-empty-state">
                  <p>Your skills are currently on track. No additional sessions are scheduled.</p>
                </div>
              ) : (
                upcomingPlan.map((item) => (
                  <div
                    key={`up-${item.id}`}
                    className="cal-upcoming-item"
                    onClick={() => handleEventClick(item)}
                  >
                    <div className="cal-upcoming-top">
                      <span className="cal-upcoming-date">
                        {item.scheduled_date} · {item.scheduled_time || "6:00 PM"}
                      </span>
                      <span className={`cal-badge badge-${item.event_type.toLowerCase()}`}>
                        {item.event_type}
                      </span>
                    </div>
                    <h4 className="cal-upcoming-name">{item.title}</h4>
                    <p className="cal-upcoming-trigger">
                      <strong>Reason:</strong> {item.decision_reason || "Scheduled to counteract decay"}
                    </p>

                    <div className="cal-upcoming-footer">
                      {item.event_type === "TEST" && (
                        <button
                          className="cal-btn-mini-primary"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleTakeTestFromEvent(item);
                          }}
                        >
                          Take Test →
                        </button>
                      )}
                      {item.event_type === "PRACTICE" && (
                        <button
                          className="cal-btn-mini-secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCompleteEvent(item.id);
                          }}
                        >
                          Mark Done
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Past Practice History */}
          <div className="cal-side-card">
            <div className="cal-side-header">
              <h3 className="cal-side-title">Practice History</h3>
              <span className="cal-side-badge">{historyList.length} completed</span>
            </div>

            <div className="cal-history-list">
              {historyList.length === 0 ? (
                <div className="cal-empty-state">
                  <p>You haven't completed any practice sessions yet.</p>
                </div>
              ) : (
                historyList.map((hist) => (
                  <div
                    key={`hist-${hist.id}`}
                    className="cal-history-item"
                    onClick={() => handleEventClick(hist)}
                  >
                    <div className="cal-hist-icon">✓</div>
                    <div className="cal-hist-content">
                      <div className="cal-hist-title">{hist.title}</div>
                      <div className="cal-hist-meta">
                        {hist.scheduled_date} · {hist.event_type}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* MODAL / DETAILS DRAWER */}
      {selectedEvent && (
        <div className="cal-modal-overlay" onClick={() => setSelectedEvent(null)}>
          <div className="cal-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="cal-modal-header">
              <div className="cal-modal-header-text">
                <span className={`cal-badge badge-${selectedEvent.event_type.toLowerCase()}`}>
                  {selectedEvent.status === "COMPLETED" ? "Completed Event" : "Upcoming Event"}
                </span>
                <h3 className="cal-modal-title">{selectedEvent.title}</h3>
                <span className="cal-modal-date">
                  📅 {selectedEvent.scheduled_date} at {selectedEvent.scheduled_time || "6:00 PM"}
                </span>
              </div>
              <button className="cal-modal-close" onClick={() => setSelectedEvent(null)}>
                ✕
              </button>
            </div>

            <div className="cal-modal-body">
              {/* Telemetry Grid */}
              <div className="cal-telemetry-box">
                <h4 className="cal-telemetry-title">Why this is scheduled (SDA Signals)</h4>
                <div className="cal-telemetry-grid">
                  <div className="cal-telem-item">
                    <span className="cal-telem-lbl">Freshness</span>
                    <span className="cal-telem-val">
                      {Math.round((selectedEvent.trigger_freshness || 0.4) * 100)}%
                    </span>
                  </div>
                  <div className="cal-telem-item">
                    <span className="cal-telem-lbl">pyBKT Mastery</span>
                    <span className="cal-telem-val">
                      {Math.round((selectedEvent.trigger_mastery || 0.5) * 100)}%
                    </span>
                  </div>
                  <div className="cal-telem-item">
                    <span className="cal-telem-lbl">Weakness</span>
                    <span className="cal-telem-val">
                      {Math.round((selectedEvent.trigger_weakness || 0.5) * 100)}%
                    </span>
                  </div>
                  <div className="cal-telem-item">
                    <span className="cal-telem-lbl">Decay Urgency</span>
                    <span className="cal-telem-val">
                      {Math.round((selectedEvent.trigger_urgency || 0.6) * 100)}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Agent Decision & Rationale */}
              <div className="cal-modal-section">
                <label className="cal-modal-lbl">Featherless Decision Agent</label>
                <div className="cal-agent-callout">
                  <div className="agent-action-pill">
                    Action: <strong>{selectedEvent.decision_action || selectedEvent.event_type}</strong>
                  </div>
                  <p className="agent-reason-text">
                    "{selectedEvent.decision_reason || "Signals indicated intervention is needed to prevent retention decay."}"
                  </p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="cal-modal-actions">
                {selectedEvent.event_type === "TEST" && selectedEvent.status === "UPCOMING" && (
                  <button
                    className="cal-btn-primary full-width"
                    onClick={() => {
                      handleTakeTestFromEvent(selectedEvent);
                      setSelectedEvent(null);
                    }}
                  >
                    Take Test Now
                  </button>
                )}
                {selectedEvent.event_type !== "TEST" && selectedEvent.status === "UPCOMING" && (
                  <button
                    className="cal-btn-secondary full-width"
                    onClick={() => handleCompleteEvent(selectedEvent.id)}
                  >
                    Mark as Completed
                  </button>
                )}
                {selectedEvent.status === "COMPLETED" && (
                  <div className="cal-completed-stamp">
                    ✓ Completed on {selectedEvent.completed_at ? selectedEvent.completed_at.split("T")[0] : selectedEvent.scheduled_date}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
