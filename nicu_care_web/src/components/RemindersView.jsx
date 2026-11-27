import React, { useState, useEffect } from "react";
import { Bell, Mail, Phone, Clock, Send, CheckCircle, RefreshCw, Smartphone, Inbox, ShieldCheck, Zap, Calculator } from "lucide-react";
import { reminderApi, careLogApi, babyApi } from "../api";

export default function RemindersView({ user, baby }) {
  const babyName = baby?.name || user?.baby_name || "Baby";
  const babyId = baby?.baby_id || user?.assigned_baby_ids?.[0] || "";
  const [prefs, setPrefs] = useState({
    email: user?.email || "",
    phone_number: user?.phone_number || "",
    feeding_interval_hours: 1.0,
    feeding_volume_range: "45–54 mL",
    target_volume_ml: 50.0,
    kmc_interval_hours: 4.0,
    email_enabled: true,
    sms_enabled: true,
    medication_reminder_enabled: true,
    hourly_updates_enabled: true
  });
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [testCategory, setTestCategory] = useState("FEEDING");
  const [testChannel, setTestChannel] = useState("both");
  const [isManualRange, setIsManualRange] = useState(false);
  const [manualVolumeInput, setManualVolumeInput] = useState("50");
  const [calcType, setCalcType] = useState("FEEDING"); // "FEEDING" | "KMC_SESSION"
  const [calcTime, setCalcTime] = useState(() => {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  });
  const [calcSuccess, setCalcSuccess] = useState(null);

  function computeNextTime(timeStr, intervalHours) {
    if (!timeStr) return "--:--";
    const [hh, mm] = timeStr.split(":").map(Number);
    const d = new Date();
    d.setHours(hh, mm, 0, 0);
    const msToAdd = (intervalHours || 1.0) * 3600 * 1000;
    const nextD = new Date(d.getTime() + msToAdd);
    return nextD.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function computeMinutesDiff(timeStr, intervalHours) {
    if (!timeStr) return 0;
    const [hh, mm] = timeStr.split(":").map(Number);
    const d = new Date();
    d.setHours(hh, mm, 0, 0);
    const msToAdd = (intervalHours || 1.0) * 3600 * 1000;
    const nextD = new Date(d.getTime() + msToAdd);
    const now = new Date();
    return Math.round((nextD.getTime() - now.getTime()) / 60000);
  }

  async function handleApplyCalculatedTime() {
    try {
      const [hh, mm] = calcTime.split(":").map(Number);
      const d = new Date();
      d.setHours(hh, mm, 0, 0);
      const customIso = d.toISOString();
      if (calcType === "FEEDING") {
        await careLogApi.logFeed(babyId, prefs.target_volume_ml || 50, "fortified_breast_milk", customIso);
        setCalcSuccess(`✓ Logged feed for Baby ${babyName} at ${calcTime}! Next feed scheduled for ${computeNextTime(calcTime, prefs.feeding_interval_hours)}.`);
      } else {
        await careLogApi.logKmc(babyId, 60, "mother", customIso);
        setCalcSuccess(`✓ Logged KMC session for Baby ${babyName} at ${calcTime}! Next KMC scheduled for ${computeNextTime(calcTime, prefs.kmc_interval_hours)}.`);
      }
      setTimeout(() => setCalcSuccess(null), 5000);
      loadPreferencesAndHistory();
    } catch (err) {
      alert("Failed to apply time: " + err.message);
    }
  }

  useEffect(() => {
    loadPreferencesAndHistory();
  }, [user]);

  async function loadPreferencesAndHistory() {
    setLoading(true);
    try {
      const userId = user?.id || "usr_mother_01";
      const [pData, hData] = await Promise.all([
        reminderApi.getPreferences(userId).catch(() => null),
        reminderApi.getHistory(babyId).catch(() => [])
      ]);
      if (pData) {
        setPrefs(pData);
        if (pData.target_volume_ml) setManualVolumeInput(String(pData.target_volume_ml));
      }
      setHistory(hData);
    } catch (err) {
      console.error("Failed to load reminders data:", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSavePreferences(e) {
    e.preventDefault();
    try {
      const userId = user?.id || "usr_mother_01";
      const toSave = {
        ...prefs,
        feeding_volume_range: isManualRange ? `${manualVolumeInput} mL (Manual Entry)` : prefs.feeding_volume_range,
        target_volume_ml: parseFloat(manualVolumeInput) || 50.0
      };
      const updated = await reminderApi.updatePreferences(userId, toSave);
      setPrefs(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3500);
    } catch (err) {
      alert("Failed to save preferences: " + err.message);
    }
  }

  async function handleSendTestReminder() {
    try {
      const payload = {
        baby_id: babyId,
        user_id: user?.id || "usr_mother_01",
        category: testCategory,
        channel: testChannel,
        recipient_email: prefs.email,
        recipient_phone: prefs.phone_number,
        custom_note: `Configured Target: ${prefs.feeding_volume_range || manualVolumeInput + ' mL'}`
      };
      const res = await reminderApi.sendTestReminder(payload);
      setTestResult(res);
      loadPreferencesAndHistory();
    } catch (err) {
      alert("Failed to send test reminder: " + err.message);
    }
  }

  const isHourly = prefs.feeding_interval_hours <= 1.0;

  return (
    <div style={{ maxWidth: "1080px", margin: "0 auto", padding: "24px 16px 140px 16px" }}>
      {/* Header */}
      <div style={{ marginBottom: "22px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <h1 style={{ fontSize: "24px", fontWeight: "800", color: "#0f172a", margin: 0 }}>
            🔔 Proactive Reminders & Hourly Care Alerts for Baby {babyName}
          </h1>
          {isHourly && (
            <span style={{
              background: "#dcfce7",
              color: "#15803d",
              fontSize: "12px",
              fontWeight: "700",
              padding: "4px 10px",
              borderRadius: "14px",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              border: "1px solid #bbf7d0"
            }}>
              <Zap size={14} fill="#15803d" />
              Hourly Alerts Active
            </span>
          )}
        </div>
        <p style={{ fontSize: "14px", color: "#64748b", margin: "4px 0 0 0" }}>
          Configure custom feeding ranges, manual volume entries, and automated hourly care reminders to your registered email and phone.
        </p>
      </div>

      {saveSuccess && (
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
          <CheckCircle size={16} />
          Your feeding volume target, interval timings, and contact numbers have been updated!
        </div>
      )}

      {/* Grid: Settings on Left, Instant Dispatch Test on Right */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "20px", marginBottom: "28px" }}>
        {/* Card 1: Configuration Form */}
        <div style={{ background: "white", padding: "24px", borderRadius: "14px", border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
          <h2 style={{ fontSize: "17px", fontWeight: "700", color: "#0f172a", marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
            <Mail size={18} color="#0f766e" />
            Interval & Feeding Range Settings
          </h2>

          <form onSubmit={handleSavePreferences} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#475569", marginBottom: "4px" }}>
                Registered Email Address (HTML Care Cards):
              </label>
              <input
                type="email"
                required
                value={prefs.email}
                onChange={(e) => setPrefs({ ...prefs, email: e.target.value })}
                style={{ width: "100%", padding: "10px 12px", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "14px" }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#475569", marginBottom: "4px" }}>
                Registered Mobile Number (SMS Alerts):
              </label>
              <input
                type="tel"
                required
                value={prefs.phone_number}
                onChange={(e) => setPrefs({ ...prefs, phone_number: e.target.value })}
                style={{ width: "100%", padding: "10px 12px", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "14px" }}
              />
            </div>

            {/* FEEDING RANGE / MANUAL ENTRY SELECTOR */}
            <div style={{ background: "#f8fafc", padding: "14px", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#334155", marginBottom: "6px" }}>
                🍼 Select Feeding Range or Enter Manually:
              </label>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {[
                  { label: "45–54 mL (Recommended AAP Target for 2.4kg Preterm)", range: "45–54 mL", avg: 50 },
                  { label: "35–45 mL (Early Post-NICU Gradual Catch-up)", range: "35–45 mL", avg: 40 },
                  { label: "50–60 mL (Caloric Advancement)", range: "50–60 mL", avg: 55 }
                ].map((item, idx) => (
                  <label key={idx} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", cursor: "pointer" }}>
                    <input
                      type="radio"
                      name="feedingRangeChoice"
                      checked={!isManualRange && prefs.feeding_volume_range === item.range}
                      onChange={() => {
                        setIsManualRange(false);
                        setPrefs({ ...prefs, feeding_volume_range: item.range, target_volume_ml: item.avg });
                        setManualVolumeInput(String(item.avg));
                      }}
                      style={{ accentColor: "#0f766e" }}
                    />
                    <span>{item.label}</span>
                  </label>
                ))}

                {/* Manual Entry Option */}
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", cursor: "pointer", marginTop: "2px" }}>
                  <input
                    type="radio"
                    name="feedingRangeChoice"
                    checked={isManualRange}
                    onChange={() => setIsManualRange(true)}
                    style={{ accentColor: "#0f766e" }}
                  />
                  <span style={{ fontWeight: "700", color: isManualRange ? "#0f766e" : "#334155" }}>
                    ✍️ Enter Custom Manual Volume (mL):
                  </span>
                </label>

                {isManualRange && (
                  <div style={{ marginTop: "4px", paddingLeft: "24px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <input
                        type="number"
                        min="10"
                        max="120"
                        step="1"
                        value={manualVolumeInput}
                        onChange={(e) => {
                          setManualVolumeInput(e.target.value);
                          setPrefs({
                            ...prefs,
                            feeding_volume_range: `${e.target.value} mL (Custom Entry)`,
                            target_volume_ml: parseFloat(e.target.value) || 50
                          });
                        }}
                        style={{
                          width: "110px",
                          padding: "8px 10px",
                          borderRadius: "6px",
                          border: "2px solid #0f766e",
                          fontSize: "14px",
                          fontWeight: "700",
                          outline: "none"
                        }}
                        placeholder="e.g. 48"
                      />
                      <span style={{ fontSize: "13px", color: "#475569", fontWeight: "600" }}>mL per feed</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* INTERVAL SLIDER (FEATURING 1-HOUR HOURLY OPTION) */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: "700", color: "#334155" }}>
                  Alert Interval Frequency:
                </label>
                <span style={{
                  fontSize: "13px",
                  fontWeight: "800",
                  color: isHourly ? "#15803d" : "#0f766e",
                  background: isHourly ? "#dcfce7" : "#f0fdfa",
                  padding: "2px 8px",
                  borderRadius: "6px",
                  border: isHourly ? "1px solid #86efac" : "1px solid #ccfbf1"
                }}>
                  {isHourly ? "⚡ Every 1.0 Hour (Hourly)" : `Every ${prefs.feeding_interval_hours} Hours`}
                </span>
              </div>

              {/* Quick 1-Click Interval Buttons */}
              <div style={{ display: "flex", gap: "6px", marginBottom: "10px" }}>
                {[
                  { label: "⚡ Every 1 Hour", val: 1.0 },
                  { label: "2.0h", val: 2.0 },
                  { label: "2.5h", val: 2.5 },
                  { label: "3.0h (AAP Standard)", val: 3.0 }
                ].map((b, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setPrefs({ ...prefs, feeding_interval_hours: b.val })}
                    style={{
                      flex: 1,
                      padding: "6px 8px",
                      borderRadius: "6px",
                      border: prefs.feeding_interval_hours === b.val ? "2px solid #0f766e" : "1px solid #cbd5e1",
                      background: prefs.feeding_interval_hours === b.val ? "#f0fdfa" : "white",
                      color: prefs.feeding_interval_hours === b.val ? "#0f766e" : "#475569",
                      fontSize: "11px",
                      fontWeight: prefs.feeding_interval_hours === b.val ? "700" : "500",
                      cursor: "pointer"
                    }}
                  >
                    {b.label}
                  </button>
                ))}
              </div>

              <input
                type="range"
                min="1.0"
                max="4.0"
                step="0.5"
                value={prefs.feeding_interval_hours}
                onChange={(e) => setPrefs({ ...prefs, feeding_interval_hours: parseFloat(e.target.value) })}
                style={{ width: "100%", accentColor: isHourly ? "#15803d" : "#0f766e" }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#94a3b8" }}>
                <span style={{ fontWeight: isHourly ? "700" : "normal", color: isHourly ? "#15803d" : "#94a3b8" }}>1.0h (Hourly)</span>
                <span>2.0h</span>
                <span>3.0h (AAP Standard)</span>
                <span>4.0h</span>
              </div>
            </div>

            {/* CHANNEL TOGGLES */}
            <div style={{ background: "#f8fafc", padding: "12px 14px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
              <span style={{ fontSize: "12px", fontWeight: "700", color: "#334155", display: "block", marginBottom: "8px" }}>
                Active Notification Channels:
              </span>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={prefs.email_enabled}
                    onChange={(e) => setPrefs({ ...prefs, email_enabled: e.target.checked })}
                    style={{ accentColor: "#0f766e" }}
                  />
                  <span>📧 HTML Care Cards to Registered Email</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={prefs.sms_enabled}
                    onChange={(e) => setPrefs({ ...prefs, sms_enabled: e.target.checked })}
                    style={{ accentColor: "#0f766e" }}
                  />
                  <span>📱 Urgent SMS Alerts to Registered Mobile</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={prefs.medication_reminder_enabled}
                    onChange={(e) => setPrefs({ ...prefs, medication_reminder_enabled: e.target.checked })}
                    style={{ accentColor: "#0f766e" }}
                  />
                  <span>💊 Daily Medication Routines (Vitamin D3 / Iron drops)</span>
                </label>
              </div>
            </div>

            <button
              type="submit"
              style={{
                background: "#0f766e",
                color: "white",
                border: "none",
                padding: "12px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: "700",
                cursor: "pointer",
                boxShadow: "0 2px 4px rgba(15,118,110,0.2)"
              }}
            >
              Save Feeding Targets & Restart Scheduler
            </button>
          </form>
        </div>

        {/* Card 2: Interactive Test Trigger & Live Dual Previews */}
        <div style={{ background: "white", padding: "24px", borderRadius: "14px", border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
          <h2 style={{ fontSize: "17px", fontWeight: "700", color: "#0f172a", marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
            <Send size={18} color="#0284c7" />
            Test Delivery Now
          </h2>
          <p style={{ fontSize: "12px", color: "#64748b", marginBottom: "16px" }}>
            Send an instant test alert using your selected volume target (<b>{prefs.feeding_volume_range || manualVolumeInput + ' mL'}</b>) and frequency.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#475569", marginBottom: "4px" }}>
                Reminder Category:
              </label>
              <select
                value={testCategory}
                onChange={(e) => setTestCategory(e.target.value)}
                style={{ width: "100%", padding: "9px 12px", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "13px" }}
              >
                <option value="FEEDING">🍼 Feeding Reminder ({prefs.feeding_volume_range || manualVolumeInput + ' mL'})</option>
                <option value="KMC_SESSION">🦘 Kangaroo Mother Care (Skin-to-Skin)</option>
                <option value="MEDICATION">💊 Prescribed Vitamin D3 Drops</option>
                <option value="SYSTEM_TEST">🔔 General Connectivity Test</option>
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#475569", marginBottom: "4px" }}>
                Target Channels:
              </label>
              <div style={{ display: "flex", gap: "12px" }}>
                <label style={{ fontSize: "13px", display: "flex", alignItems: "center", gap: "6px" }}>
                  <input
                    type="radio"
                    name="channel"
                    value="both"
                    checked={testChannel === "both"}
                    onChange={(e) => setTestChannel(e.target.value)}
                  />
                  <span>Email + Mobile SMS</span>
                </label>
                <label style={{ fontSize: "13px", display: "flex", alignItems: "center", gap: "6px" }}>
                  <input
                    type="radio"
                    name="channel"
                    value="sms"
                    checked={testChannel === "sms"}
                    onChange={(e) => setTestChannel(e.target.value)}
                  />
                  <span>SMS Only</span>
                </label>
              </div>
            </div>

            <button
              onClick={handleSendTestReminder}
              style={{
                background: "#0284c7",
                color: "white",
                border: "none",
                padding: "11px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: "700",
                cursor: "pointer",
                boxShadow: "0 2px 4px rgba(2,132,199,0.2)"
              }}
            >
              🚀 Send Immediate Test Alert
            </button>
          </div>

          {/* Dual Previews */}
          {testResult ? (
            <div style={{ marginTop: "14px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ fontSize: "12px", fontWeight: "700", color: "#059669" }}>
                  ✓ Delivery Confirmed ({testResult.notification_id})
                </span>
                <span style={{ fontSize: "11px", color: "#64748b" }}>
                  {testResult.timestamp}
                </span>
              </div>

              {/* Mobile SMS Preview */}
              <div style={{
                background: "#1e293b",
                color: "#f1f5f9",
                padding: "12px 14px",
                borderRadius: "10px",
                fontSize: "12px",
                lineHeight: 1.4,
                marginBottom: "10px",
                borderLeft: "4px solid #10b981"
              }}>
                <div style={{ fontSize: "10px", color: "#94a3b8", marginBottom: "4px" }}>
                  📱 SMS Delivered to {testResult.recipient_phone}:
                </div>
                {testResult.preview_sms}
              </div>

              {/* HTML Email Snippet */}
              <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "12px" }}>
                <div style={{ fontSize: "11px", fontWeight: "600", color: "#475569", marginBottom: "4px" }}>
                  📧 HTML Care Card to {testResult.recipient_email}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b" }}>
                  Target Volume: <b>{prefs.feeding_volume_range || manualVolumeInput + ' mL'}</b> | Frequency: <b>{isHourly ? "Hourly" : `${prefs.feeding_interval_hours}h`}</b>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ padding: "20px", textAlign: "center", color: "#94a3b8", fontSize: "12px", background: "#f8fafc", borderRadius: "8px", border: "1px dashed #cbd5e1" }}>
              Click "Send Immediate Test Alert" above to generate live SMS & Email previews with your chosen range.
            </div>
          )}
        </div>
      </div>

      {/* INTERACTIVE MANUAL TIME & INTERVAL CALCULATOR */}
      <div style={{
        background: "white",
        padding: "24px",
        borderRadius: "14px",
        border: "1px solid #cbd5e1",
        boxShadow: "0 2px 4px rgba(0,0,0,0.04)",
        marginBottom: "28px"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "8px" }}>
          <div>
            <h3 style={{ fontSize: "17px", fontWeight: "800", color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <Calculator size={20} color="#0f766e" />
              Manual Time Interval Calculator & Schedule Projector
            </h3>
            <p style={{ fontSize: "13px", color: "#64748b", margin: "4px 0 0 0" }}>
              Enter any past or current event time manually — our clinical engine projects the exact next alert schedule from that moment.
            </p>
          </div>
          <span style={{ background: "#f0fdfa", color: "#0f766e", fontSize: "12px", fontWeight: "700", padding: "4px 10px", borderRadius: "12px", border: "1px solid #99f6e4" }}>
            Real-time Projection
          </span>
        </div>

        {calcSuccess && (
          <div style={{
            background: "#ecfdf5",
            border: "1px solid #a7f3d0",
            color: "#065f46",
            padding: "10px 14px",
            borderRadius: "8px",
            fontSize: "13px",
            fontWeight: "600",
            marginBottom: "16px"
          }}>
            {calcSuccess}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px", marginBottom: "18px" }}>
          {/* Input column */}
          <div style={{ background: "#f8fafc", padding: "16px", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#334155", marginBottom: "8px" }}>
              1. Choose Activity to Calculate:
            </label>
            <div style={{ display: "flex", gap: "8px", marginBottom: "14px" }}>
              <button
                type="button"
                onClick={() => setCalcType("FEEDING")}
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  borderRadius: "8px",
                  border: calcType === "FEEDING" ? "2px solid #0f766e" : "1px solid #cbd5e1",
                  background: calcType === "FEEDING" ? "#f0fdfa" : "white",
                  color: calcType === "FEEDING" ? "#0f766e" : "#475569",
                  fontWeight: "700",
                  fontSize: "12px",
                  cursor: "pointer"
                }}
              >
                🍼 Infant Feeding
              </button>
              <button
                type="button"
                onClick={() => setCalcType("KMC_SESSION")}
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  borderRadius: "8px",
                  border: calcType === "KMC_SESSION" ? "2px solid #be185d" : "1px solid #cbd5e1",
                  background: calcType === "KMC_SESSION" ? "#fdf2f8" : "white",
                  color: calcType === "KMC_SESSION" ? "#be185d" : "#475569",
                  fontWeight: "700",
                  fontSize: "12px",
                  cursor: "pointer"
                }}
              >
                🦘 KMC Skin-to-Skin
              </button>
            </div>

            <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#334155", marginBottom: "4px" }}>
              2. Enter Time of Event:
            </label>
            <input
              type="time"
              value={calcTime}
              onChange={(e) => setCalcTime(e.target.value)}
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: "8px",
                border: "1px solid #cbd5e1",
                fontSize: "16px",
                fontWeight: "600",
                outline: "none",
                marginBottom: "8px"
              }}
            />
            <div style={{ fontSize: "11px", color: "#64748b" }}>
              Applied interval: <b>{calcType === "FEEDING" ? `${prefs.feeding_interval_hours} hours` : `${prefs.kmc_interval_hours} hours`}</b>
            </div>
          </div>

          {/* Result column */}
          <div style={{
            background: calcType === "FEEDING" ? "linear-gradient(135deg, #f0fdfa, #ccfbf1)" : "linear-gradient(135deg, #fdf2f8, #fce7f3)",
            padding: "18px",
            borderRadius: "10px",
            border: calcType === "FEEDING" ? "1px solid #99f6e4" : "1px solid #fbcfe8",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between"
          }}>
            <div>
              <span style={{
                fontSize: "11px",
                fontWeight: "800",
                textTransform: "uppercase",
                letterSpacing: "0.5px",
                color: calcType === "FEEDING" ? "#0f766e" : "#be185d"
              }}>
                Calculated Projection from {calcTime}
              </span>
              <div style={{ fontSize: "28px", fontWeight: "900", color: "#0f172a", margin: "6px 0 2px 0" }}>
                {computeNextTime(calcTime, calcType === "FEEDING" ? prefs.feeding_interval_hours : prefs.kmc_interval_hours)}
              </div>
              <div style={{ fontSize: "13px", fontWeight: "600", color: calcType === "FEEDING" ? "#0f766e" : "#be185d" }}>
                {(() => {
                  const mins = computeMinutesDiff(calcTime, calcType === "FEEDING" ? prefs.feeding_interval_hours : prefs.kmc_interval_hours);
                  if (mins < -10) return `🚨 Overdue by ${Math.abs(mins)} minutes`;
                  if (mins <= 0) return `⚡ Due right now`;
                  return `⏳ Due in approximately ${mins} minutes`;
                })()}
              </div>
              <div style={{ fontSize: "12px", color: "#475569", marginTop: "8px" }}>
                Target: {calcType === "FEEDING" ? (prefs.feeding_volume_range || `${manualVolumeInput} mL`) : "60 min Skin-to-Skin"}
              </div>
            </div>

            <button
              onClick={handleApplyCalculatedTime}
              style={{
                marginTop: "16px",
                background: calcType === "FEEDING" ? "#0f766e" : "#be185d",
                color: "white",
                border: "none",
                padding: "10px 16px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: "700",
                cursor: "pointer",
                boxShadow: "0 2px 4px rgba(0,0,0,0.1)"
              }}
            >
              ✓ Save Log at {calcTime} & Recalculate Timeline
            </button>
          </div>
        </div>
      </div>

      {/* Delivery History Table */}
      <div style={{ background: "white", padding: "20px 24px", borderRadius: "14px", border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
        <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#0f172a", marginBottom: "14px" }}>
          📋 Notification Delivery History & Audit Log
        </h3>
        {history.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #e2e8f0", color: "#64748b", textAlign: "left" }}>
                  <th style={{ padding: "8px 10px" }}>Timestamp</th>
                  <th style={{ padding: "8px 10px" }}>Category</th>
                  <th style={{ padding: "8px 10px" }}>Channel</th>
                  <th style={{ padding: "8px 10px" }}>Recipient Mobile</th>
                  <th style={{ padding: "8px 10px" }}>Recipient Email</th>
                  <th style={{ padding: "8px 10px" }}>Delivery Status</th>
                </tr>
              </thead>
              <tbody>
                {history.map((item, idx) => (
                  <tr key={item.id || idx} style={{ borderBottom: "1px solid #f1f5f9" }}>
                    <td style={{ padding: "10px", color: "#64748b" }}>{item.timestamp}</td>
                    <td style={{ padding: "10px", fontWeight: "600" }}>{item.category}</td>
                    <td style={{ padding: "10px" }}>
                      <span style={{ background: "#f1f5f9", padding: "2px 8px", borderRadius: "10px", fontSize: "11px", fontWeight: "600" }}>
                        {item.channel?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: "10px", color: "#475569" }}>{item.recipient_phone || "-"}</td>
                    <td style={{ padding: "10px", color: "#475569" }}>{item.recipient_email || "-"}</td>
                    <td style={{ padding: "10px" }}>
                      <span style={{ color: "#059669", fontWeight: "700", fontSize: "12px" }}>
                        ✓ {item.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ padding: "20px", textAlign: "center", color: "#94a3b8", fontSize: "13px" }}>
            No notifications recorded yet.
          </div>
        )}
      </div>
    </div>
  );
}
