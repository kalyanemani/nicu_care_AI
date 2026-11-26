import React, { useState, useEffect } from "react";
import { Clock, CheckCircle2, AlertCircle, Droplet, Heart, Scale, ShieldAlert, Plus, RefreshCw, Zap } from "lucide-react";
import { babyApi, careLogApi } from "../api";

export default function Dashboard({ user, baby, onOpenReminders }) {
  const babyName = baby?.name || user?.baby_name || "Baby";
  const babyId = baby?.baby_id || user?.assigned_baby_ids?.[0] || "baby_liam_01";

  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [kmcSummary, setKmcSummary] = useState({ completed_hours: 1.0, target_hours: 3.0 });
  const [schedule, setSchedule] = useState(null);

  // Feed Modal State
  const [showLogFeed, setShowLogFeed] = useState(false);
  const [feedVol, setFeedVol] = useState(50);
  const [feedTimeMode, setFeedTimeMode] = useState("now"); // "now" | "manual"
  const [feedManualTime, setFeedManualTime] = useState(() => {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  });

  // KMC Modal State
  const [showLogKmc, setShowLogKmc] = useState(false);
  const [kmcDuration, setKmcDuration] = useState(60);
  const [kmcTimeMode, setKmcTimeMode] = useState("now"); // "now" | "manual"
  const [kmcManualTime, setKmcManualTime] = useState(() => {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  });

  const [logSuccess, setLogSuccess] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [tlData, kmcData, schedData] = await Promise.all([
        babyApi.getTimeline(babyId).catch(() => []),
        babyApi.getKmcSummary(babyId).catch(() => ({ completed_hours: 1.0, target_hours: 3.0 })),
        babyApi.getNextSchedule(babyId).catch(() => null)
      ]);
      setTimeline(tlData);
      setKmcSummary(kmcData);
      setSchedule(schedData);
    } catch (err) {
      console.error("Dashboard data load error:", err);
    } finally {
      setLoading(false);
    }
  }

  function buildIsoTimestamp(timeStr) {
    if (!timeStr) return new Date().toISOString();
    const [hh, mm] = timeStr.split(":").map(Number);
    const d = new Date();
    d.setHours(hh, mm, 0, 0);
    return d.toISOString();
  }

  async function handleQuickLogFeed(e) {
    e.preventDefault();
    try {
      const customIso = feedTimeMode === "manual" ? buildIsoTimestamp(feedManualTime) : null;
      await careLogApi.logFeed(babyId, feedVol, "fortified_breast_milk", customIso);
      setShowLogFeed(false);
      setLogSuccess(`Logged ${feedVol} mL feed for Baby ${babyName} ${feedTimeMode === "manual" ? `at ${feedManualTime}` : 'just now'}! Next feed recalculated.`);
      setTimeout(() => setLogSuccess(null), 5000);
      loadData();
    } catch (err) {
      alert("Failed to log feed: " + err.message);
    }
  }

  async function handleQuickLogKmc(e) {
    e.preventDefault();
    try {
      const customIso = kmcTimeMode === "manual" ? buildIsoTimestamp(kmcManualTime) : null;
      await careLogApi.logKmc(babyId, kmcDuration, "mother", customIso);
      setShowLogKmc(false);
      setLogSuccess(`Logged ${kmcDuration} min KMC session for Baby ${babyName} ${kmcTimeMode === "manual" ? `completed at ${kmcManualTime}` : 'just now'}! Next KMC recalculated.`);
      setTimeout(() => setLogSuccess(null), 5000);
      loadData();
    } catch (err) {
      alert("Failed to log KMC: " + err.message);
    }
  }

  const feedingInfo = schedule?.feeding || {
    last_feed_time: "01:00 AM",
    next_feed_time: "02:00 PM",
    target_volume_range: "45–54 mL",
    interval_hours: 1.0,
    status: "DUE_NOW",
    is_due: true,
    minutes_remaining: -5
  };

  const kmcInfo = schedule?.kmc || {
    last_kmc_time: "11:30 PM",
    next_kmc_time: "03:30 AM",
    completed_hours_today: kmcSummary?.completed_hours || 1.0,
    target_hours_today: 3.0,
    interval_hours: 3.0,
    status: "UPCOMING",
    is_due: false,
    minutes_remaining: 120
  };

  return (
    <div style={{ maxWidth: "1080px", margin: "0 auto", padding: "24px 16px 120px 16px" }}>
      {/* Welcome Banner */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: "20px",
        flexWrap: "wrap",
        gap: "12px"
      }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: "800", color: "#0f172a", margin: 0 }}>
            Hello, {(() => {
              const name = user?.full_name || user?.user?.full_name || user?.name || user?.email || "Ananya";
              return typeof name === "string" ? name.split(" ")[0] : "Ananya";
            })()} 👋
          </h1>
          <p style={{ fontSize: "14px", color: "#64748b", margin: "4px 0 0 0" }}>
            Here is Baby {babyName}'s routine and clinical targets for today.
          </p>
        </div>
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <button
            onClick={() => setShowLogFeed(true)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              background: "#0f766e",
              color: "white",
              border: "none",
              padding: "10px 16px",
              borderRadius: "8px",
              fontSize: "13px",
              fontWeight: "700",
              cursor: "pointer",
              boxShadow: "0 2px 4px rgba(15,118,110,0.2)"
            }}
          >
            <Plus size={16} />
            Quick Log Feed
          </button>
          <button
            onClick={() => setShowLogKmc(true)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              background: "#be185d",
              color: "white",
              border: "none",
              padding: "10px 16px",
              borderRadius: "8px",
              fontSize: "13px",
              fontWeight: "700",
              cursor: "pointer",
              boxShadow: "0 2px 4px rgba(190,24,93,0.2)"
            }}
          >
            <Heart size={16} />
            Quick Log KMC
          </button>
          <button
            onClick={loadData}
            style={{
              background: "white",
              border: "1px solid #cbd5e1",
              color: "#64748b",
              padding: "10px",
              borderRadius: "8px",
              cursor: "pointer"
            }}
            title="Refresh Timeline"
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {logSuccess && (
        <div style={{
          background: "#ecfdf5",
          border: "1px solid #a7f3d0",
          color: "#065f46",
          padding: "12px 16px",
          borderRadius: "8px",
          fontSize: "13px",
          fontWeight: "600",
          marginBottom: "18px",
          display: "flex",
          alignItems: "center",
          gap: "8px"
        }}>
          <CheckCircle2 size={16} />
          {logSuccess}
        </div>
      )}

      {/* 1. HERO CARD: DYNAMIC "WHAT SHOULD I DO NEXT?" CALCULATED FROM ENTERED TIMES */}
      <div style={{
        background: feedingInfo.status === "OVERDUE"
          ? "linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)"
          : "linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)",
        border: feedingInfo.status === "OVERDUE" ? "1px solid #fca5a5" : "1px solid #fcd34d",
        borderRadius: "14px",
        padding: "20px 24px",
        marginBottom: "24px",
        boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px", flexWrap: "wrap", gap: "8px" }}>
          <span style={{
            background: feedingInfo.status === "OVERDUE" ? "#dc2626" : "#d97706",
            color: "white",
            fontSize: "11px",
            fontWeight: "800",
            padding: "3px 10px",
            borderRadius: "12px",
            letterSpacing: "0.5px"
          }}>
            ⚡ WHAT SHOULD I DO NEXT?
          </span>
          <span style={{
            fontSize: "13px",
            fontWeight: "700",
            color: feedingInfo.status === "OVERDUE" ? "#991b1b" : "#92400e"
          }}>
            Next Feed Due: {feedingInfo.next_feed_time} ({feedingInfo.status === "OVERDUE" ? `OVERDUE by ${Math.abs(feedingInfo.minutes_remaining)}m` : (feedingInfo.minutes_remaining <= 0 ? 'DUE NOW' : `In ${feedingInfo.minutes_remaining}m`)})
          </span>
        </div>

        <h2 style={{ fontSize: "20px", fontWeight: "800", color: feedingInfo.status === "OVERDUE" ? "#7f1d1d" : "#78350f", margin: "6px 0" }}>
          🍼 Feeding Target: {feedingInfo.target_volume_range} (Interval: {feedingInfo.interval_hours}h)
        </h2>

        <p style={{ fontSize: "14px", color: feedingInfo.status === "OVERDUE" ? "#991b1b" : "#92400e", lineHeight: 1.5, margin: "0 0 14px 0" }}>
          <strong>Calculated from last feed:</strong> {feedingInfo.last_feed_time}. Hold baby semi-upright with paced bottle feeding, burp upright every 15–20 mL.
          {kmcInfo && (
            <span style={{ display: "block", marginTop: "4px" }}>
              🦘 <strong>Next Skin-to-Skin KMC:</strong> Due at {kmcInfo.next_kmc_time} (Last completed: {kmcInfo.last_kmc_time}).
            </span>
          )}
        </p>

        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <button
            onClick={() => setShowLogFeed(true)}
            style={{
              background: feedingInfo.status === "OVERDUE" ? "#b91c1c" : "#b45309",
              color: "white",
              border: "none",
              padding: "8px 16px",
              borderRadius: "6px",
              fontSize: "13px",
              fontWeight: "700",
              cursor: "pointer"
            }}
          >
            ✓ Log Feed Completed (Custom Time / Volume)
          </button>
          <button
            onClick={() => setShowLogKmc(true)}
            style={{
              background: "#be185d",
              color: "white",
              border: "none",
              padding: "8px 16px",
              borderRadius: "6px",
              fontSize: "13px",
              fontWeight: "700",
              cursor: "pointer"
            }}
          >
            🦘 Log KMC Session (Custom Time)
          </button>
          <button
            onClick={onOpenReminders}
            style={{
              background: "white",
              color: "#92400e",
              border: "1px solid #fcd34d",
              padding: "8px 14px",
              borderRadius: "6px",
              fontSize: "13px",
              fontWeight: "600",
              cursor: "pointer"
            }}
          >
            🔔 Configure Hourly Alerts
          </button>
        </div>
      </div>

      {/* 2. THREE CLINICAL METRIC CARDS */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "16px", marginBottom: "28px" }}>
        {/* Card 1: Weight & Growth */}
        <div style={{ background: "white", padding: "18px 20px", borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
            <span style={{ fontSize: "13px", fontWeight: "700", color: "#64748b" }}>CURRENT WEIGHT</span>
            <Scale size={18} color="#0f766e" />
          </div>
          <div style={{ fontSize: "24px", fontWeight: "800", color: "#0f172a" }}>
            2,400 <span style={{ fontSize: "16px", fontWeight: "600", color: "#64748b" }}>grams</span>
          </div>
          <div style={{ fontSize: "12px", color: "#059669", fontWeight: "600", marginTop: "4px" }}>
            ▲ +20 g/day velocity (Fenton 2013 Optimal)
          </div>
        </div>

        {/* Card 2: Calibrated Feeding Interval */}
        <div style={{ background: "white", padding: "18px 20px", borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
            <span style={{ fontSize: "13px", fontWeight: "700", color: "#64748b" }}>FEED INTERVAL & DUE TIME</span>
            <Droplet size={18} color="#0284c7" />
          </div>
          <div style={{ fontSize: "22px", fontWeight: "800", color: "#0f172a" }}>
            {feedingInfo.next_feed_time} <span style={{ fontSize: "14px", fontWeight: "600", color: "#0284c7" }}>({feedingInfo.interval_hours}h cycle)</span>
          </div>
          <div style={{ fontSize: "12px", color: "#64748b", marginTop: "4px" }}>
            Last: {feedingInfo.last_feed_time} • Target: {feedingInfo.target_volume_range}
          </div>
        </div>

        {/* Card 3: Kangaroo Mother Care */}
        <div style={{ background: "white", padding: "18px 20px", borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
            <span style={{ fontSize: "13px", fontWeight: "700", color: "#64748b" }}>KANGAROO CARE (TODAY)</span>
            <Heart size={18} color="#e11d48" />
          </div>
          <div style={{ fontSize: "24px", fontWeight: "800", color: "#0f172a" }}>
            {Math.round((kmcSummary?.completed_hours || 1.0) * 60)} <span style={{ fontSize: "16px", fontWeight: "600", color: "#64748b" }}>/ 180 min</span>
          </div>
          <div style={{ fontSize: "12px", color: "#d97706", fontWeight: "600", marginTop: "4px" }}>
            Next KMC session: {kmcInfo.next_kmc_time}
          </div>
        </div>
      </div>

      {/* 3. TODAY'S CARE TIMELINE CHECKLIST */}
      <div style={{ background: "white", borderRadius: "14px", border: "1px solid #e2e8f0", padding: "20px 24px", boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
        <h3 style={{ fontSize: "17px", fontWeight: "700", color: "#0f172a", marginBottom: "16px" }}>
          📋 Today's Scheduled Routine & Checklist
        </h3>

        {loading ? (
          <div style={{ padding: "30px", textAlign: "center", color: "#94a3b8" }}>Loading schedule...</div>
        ) : timeline.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {timeline.map((item, idx) => {
              const isDone = item.status === "COMPLETED";
              const isDue = item.status === "DUE";
              return (
                <div
                  key={item.task_id || idx}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px 16px",
                    borderRadius: "10px",
                    background: isDone ? "#f8fafc" : (isDue ? "#fffbeb" : "white"),
                    border: isDue ? "1px solid #fde68a" : "1px solid #e2e8f0",
                    transition: "all 0.15s ease"
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                    <div style={{
                      width: "32px",
                      height: "32px",
                      borderRadius: "8px",
                      background: isDone ? "#dcfce7" : (isDue ? "#fef3c7" : "#f1f5f9"),
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center"
                    }}>
                      {isDone ? (
                        <CheckCircle2 size={18} color="#16a34a" />
                      ) : isDue ? (
                        <AlertCircle size={18} color="#d97706" />
                      ) : (
                        <Clock size={18} color="#64748b" />
                      )}
                    </div>
                    <div>
                      <div style={{
                        fontSize: "14px",
                        fontWeight: "700",
                        color: isDone ? "#64748b" : "#0f172a",
                        textDecoration: isDone ? "line-through" : "none"
                      }}>
                        {item.title}
                      </div>
                      <div style={{ fontSize: "12px", color: "#64748b" }}>
                        {item.description}
                      </div>
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <span style={{
                      fontSize: "12px",
                      fontWeight: "700",
                      padding: "4px 10px",
                      borderRadius: "12px",
                      background: isDone ? "#f1f5f9" : (isDue ? "#fef3c7" : "#f8fafc"),
                      color: isDone ? "#64748b" : (isDue ? "#b45309" : "#475569")
                    }}>
                      {item.time_str}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ padding: "20px", textAlign: "center", color: "#64748b", fontSize: "14px" }}>
            Care checklist ready. Use "Quick Log Feed" or "Quick Log KMC" above to record activities.
          </div>
        )}
      </div>

      {/* MODAL 1: QUICK LOG FEED (WITH CUSTOM VOLUME & MANUAL TIME ENTRY) */}
      {showLogFeed && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(15, 23, 42, 0.6)",
          backdropFilter: "blur(4px)",
          zIndex: 80,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "16px"
        }}>
          <div style={{ background: "white", borderRadius: "16px", padding: "24px", width: "100%", maxWidth: "440px", boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)" }}>
            <h3 style={{ fontSize: "18px", fontWeight: "800", color: "#0f172a", marginBottom: "4px" }}>
              🍼 Log Baby {babyName}'s Feed
            </h3>
            <p style={{ fontSize: "12px", color: "#64748b", marginBottom: "16px" }}>
              Enter feed volume and exact completion time — next feed is calculated automatically from this time.
            </p>

            <form onSubmit={handleQuickLogFeed}>
              {/* Feeding Time Mode */}
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#334155", marginBottom: "6px" }}>
                  Feed Completion Time:
                </label>
                <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
                  <button
                    type="button"
                    onClick={() => setFeedTimeMode("now")}
                    style={{
                      flex: 1,
                      padding: "7px 10px",
                      borderRadius: "8px",
                      border: feedTimeMode === "now" ? "2px solid #0f766e" : "1px solid #cbd5e1",
                      background: feedTimeMode === "now" ? "#f0fdfa" : "white",
                      color: feedTimeMode === "now" ? "#0f766e" : "#475569",
                      fontWeight: feedTimeMode === "now" ? "700" : "500",
                      fontSize: "12px",
                      cursor: "pointer"
                    }}
                  >
                    ⏱️ Just Now (Live)
                  </button>
                  <button
                    type="button"
                    onClick={() => setFeedTimeMode("manual")}
                    style={{
                      flex: 1,
                      padding: "7px 10px",
                      borderRadius: "8px",
                      border: feedTimeMode === "manual" ? "2px solid #0f766e" : "1px solid #cbd5e1",
                      background: feedTimeMode === "manual" ? "#f0fdfa" : "white",
                      color: feedTimeMode === "manual" ? "#0f766e" : "#475569",
                      fontWeight: feedTimeMode === "manual" ? "700" : "500",
                      fontSize: "12px",
                      cursor: "pointer"
                    }}
                  >
                    ✍️ Enter Time Manually
                  </button>
                </div>

                {feedTimeMode === "manual" && (
                  <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                    <label style={{ display: "block", fontSize: "11px", color: "#64748b", marginBottom: "4px" }}>
                      Select exact feed time:
                    </label>
                    <input
                      type="time"
                      required
                      value={feedManualTime}
                      onChange={(e) => setFeedManualTime(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "8px 12px",
                        borderRadius: "6px",
                        border: "1px solid #cbd5e1",
                        fontSize: "14px",
                        fontWeight: "600",
                        outline: "none"
                      }}
                    />
                    <div style={{ fontSize: "11px", color: "#0f766e", marginTop: "4px", fontWeight: "600" }}>
                      ⚡ Next feed will be scheduled from {feedManualTime}
                    </div>
                  </div>
                )}
              </div>

              {/* Quick Range Selector Chips */}
              <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#334155", marginBottom: "6px" }}>
                Select Recommended Preterm Range:
              </label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "14px" }}>
                {[
                  { label: "35–40 mL", val: 38 },
                  { label: "40–45 mL", val: 43 },
                  { label: "45–54 mL (AAP Target)", val: 50 },
                  { label: "50–55 mL", val: 52 },
                  { label: "55–60 mL", val: 58 }
                ].map((preset, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setFeedVol(preset.val)}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "16px",
                      border: feedVol === preset.val ? "2px solid #0f766e" : "1px solid #cbd5e1",
                      background: feedVol === preset.val ? "#f0fdfa" : "white",
                      color: feedVol === preset.val ? "#0f766e" : "#334155",
                      fontSize: "12px",
                      fontWeight: feedVol === preset.val ? "700" : "500",
                      cursor: "pointer"
                    }}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>

              {/* Exact Manual Entry Input */}
              <div style={{ marginBottom: "16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <label style={{ fontSize: "12px", fontWeight: "700", color: "#334155" }}>
                    Or Enter Exact Volume Manually (mL):
                  </label>
                  <span style={{ fontSize: "12px", color: "#0f766e", fontWeight: "700" }}>
                    {feedVol} mL
                  </span>
                </div>
                <input
                  type="number"
                  min="5"
                  max="120"
                  step="1"
                  required
                  value={feedVol}
                  onChange={(e) => setFeedVol(Number(e.target.value))}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: "8px",
                    border: "1px solid #cbd5e1",
                    fontSize: "16px",
                    fontWeight: "600",
                    outline: "none"
                  }}
                  placeholder="e.g. 48"
                />
              </div>

              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  type="submit"
                  style={{
                    flex: 1,
                    background: "#0f766e",
                    color: "white",
                    padding: "11px",
                    borderRadius: "8px",
                    border: "none",
                    fontWeight: "700",
                    fontSize: "13px",
                    cursor: "pointer",
                    boxShadow: "0 2px 4px rgba(15,118,110,0.2)"
                  }}
                >
                  ✓ Save {feedVol} mL Feed
                </button>
                <button
                  type="button"
                  onClick={() => setShowLogFeed(false)}
                  style={{
                    flex: 1,
                    background: "#f1f5f9",
                    color: "#475569",
                    padding: "11px",
                    borderRadius: "8px",
                    border: "none",
                    fontWeight: "600",
                    fontSize: "13px",
                    cursor: "pointer"
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: QUICK LOG KMC (WITH DURATION & MANUAL TIME ENTRY) */}
      {showLogKmc && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(15, 23, 42, 0.6)",
          backdropFilter: "blur(4px)",
          zIndex: 80,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "16px"
        }}>
          <div style={{ background: "white", borderRadius: "16px", padding: "24px", width: "100%", maxWidth: "440px", boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)" }}>
            <h3 style={{ fontSize: "18px", fontWeight: "800", color: "#0f172a", marginBottom: "4px" }}>
              🦘 Log Skin-to-Skin (KMC) for Baby {babyName}
            </h3>
            <p style={{ fontSize: "12px", color: "#64748b", marginBottom: "16px" }}>
              Enter duration and session time — next KMC reminder is calculated from this completion time.
            </p>

            <form onSubmit={handleQuickLogKmc}>
              {/* KMC Time Mode */}
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#334155", marginBottom: "6px" }}>
                  Session Completed Time:
                </label>
                <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
                  <button
                    type="button"
                    onClick={() => setKmcTimeMode("now")}
                    style={{
                      flex: 1,
                      padding: "7px 10px",
                      borderRadius: "8px",
                      border: kmcTimeMode === "now" ? "2px solid #be185d" : "1px solid #cbd5e1",
                      background: kmcTimeMode === "now" ? "#fdf2f8" : "white",
                      color: kmcTimeMode === "now" ? "#be185d" : "#475569",
                      fontWeight: kmcTimeMode === "now" ? "700" : "500",
                      fontSize: "12px",
                      cursor: "pointer"
                    }}
                  >
                    ⏱️ Just Ended (Now)
                  </button>
                  <button
                    type="button"
                    onClick={() => setKmcTimeMode("manual")}
                    style={{
                      flex: 1,
                      padding: "7px 10px",
                      borderRadius: "8px",
                      border: kmcTimeMode === "manual" ? "2px solid #be185d" : "1px solid #cbd5e1",
                      background: kmcTimeMode === "manual" ? "#fdf2f8" : "white",
                      color: kmcTimeMode === "manual" ? "#be185d" : "#475569",
                      fontWeight: kmcTimeMode === "manual" ? "700" : "500",
                      fontSize: "12px",
                      cursor: "pointer"
                    }}
                  >
                    ✍️ Enter Time Manually
                  </button>
                </div>

                {kmcTimeMode === "manual" && (
                  <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                    <label style={{ display: "block", fontSize: "11px", color: "#64748b", marginBottom: "4px" }}>
                      Select exact completion time:
                    </label>
                    <input
                      type="time"
                      required
                      value={kmcManualTime}
                      onChange={(e) => setKmcManualTime(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "8px 12px",
                        borderRadius: "6px",
                        border: "1px solid #cbd5e1",
                        fontSize: "14px",
                        fontWeight: "600",
                        outline: "none"
                      }}
                    />
                    <div style={{ fontSize: "11px", color: "#be185d", marginTop: "4px", fontWeight: "600" }}>
                      ⚡ Next KMC session will be scheduled from {kmcManualTime}
                    </div>
                  </div>
                )}
              </div>

              {/* KMC Duration Presets */}
              <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#334155", marginBottom: "6px" }}>
                Session Duration:
              </label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "14px" }}>
                {[
                  { label: "30 min", val: 30 },
                  { label: "45 min", val: 45 },
                  { label: "60 min (WHO Goal)", val: 60 },
                  { label: "90 min", val: 90 },
                  { label: "120 min", val: 120 }
                ].map((preset, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setKmcDuration(preset.val)}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "16px",
                      border: kmcDuration === preset.val ? "2px solid #be185d" : "1px solid #cbd5e1",
                      background: kmcDuration === preset.val ? "#fdf2f8" : "white",
                      color: kmcDuration === preset.val ? "#be185d" : "#334155",
                      fontSize: "12px",
                      fontWeight: kmcDuration === preset.val ? "700" : "500",
                      cursor: "pointer"
                    }}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>

              <div style={{ marginBottom: "16px" }}>
                <label style={{ fontSize: "12px", fontWeight: "700", color: "#334155", display: "block", marginBottom: "4px" }}>
                  Or Enter Custom Minutes:
                </label>
                <input
                  type="number"
                  min="10"
                  max="360"
                  step="5"
                  required
                  value={kmcDuration}
                  onChange={(e) => setKmcDuration(Number(e.target.value))}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: "8px",
                    border: "1px solid #cbd5e1",
                    fontSize: "16px",
                    fontWeight: "600",
                    outline: "none"
                  }}
                />
              </div>

              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  type="submit"
                  style={{
                    flex: 1,
                    background: "#be185d",
                    color: "white",
                    padding: "11px",
                    borderRadius: "8px",
                    border: "none",
                    fontWeight: "700",
                    fontSize: "13px",
                    cursor: "pointer",
                    boxShadow: "0 2px 4px rgba(190,24,93,0.2)"
                  }}
                >
                  ✓ Save {kmcDuration} min KMC
                </button>
                <button
                  type="button"
                  onClick={() => setShowLogKmc(false)}
                  style={{
                    flex: 1,
                    background: "#f1f5f9",
                    color: "#475569",
                    padding: "11px",
                    borderRadius: "8px",
                    border: "none",
                    fontWeight: "600",
                    fontSize: "13px",
                    cursor: "pointer"
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
