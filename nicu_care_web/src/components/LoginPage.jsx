import React, { useState } from "react";
import { Heart, Mail, Phone, Lock, User, Baby, ArrowRight, CheckCircle, Bell, Shield, Sparkles } from "lucide-react";
import { authApi } from "../api";

export default function LoginPage({ onLoginSuccess }) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [babyName, setBabyName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (isRegister) {
        // Register parent account with email, mobile number, and registered baby name
        const cleanBabyName = babyName.trim() || "Baby";
        const regRes = await authApi.register(fullName.trim(), email.trim(), phoneNumber.trim(), password, cleanBabyName);
        // Automatically login
        const session = await authApi.login(email.trim(), password);
        localStorage.setItem("nicu_token", session.access_token);
        onLoginSuccess(session.user || regRes);
      } else {
        // Log in with existing credentials
        const session = await authApi.login(email.trim(), password);
        localStorage.setItem("nicu_token", session.access_token);
        onLoginSuccess(session.user);
      }
    } catch (err) {
      setError(err.message || "Authentication failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  }

  function handleQuickDemo(role = "parent") {
    if (role === "parent") {
      setEmail("mother_liam@example.com");
      setPassword("password123");
      setBabyName("Liam");
      setIsRegister(false);
    } else {
      setEmail("dr_sharma@rainbow.com");
      setPassword("doctor123");
      setBabyName("");
      setIsRegister(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(135deg, #f0fdfa 0%, #f8fafc 50%, #f1f5f9 100%)",
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      alignItems: "center",
      padding: "24px 16px"
    }}>
      {/* Branding Header */}
      <div style={{ textAlign: "center", marginBottom: "28px" }}>
        <div style={{
          background: "linear-gradient(135deg, #0f766e, #0d9488)",
          width: "56px",
          height: "56px",
          borderRadius: "16px",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
          boxShadow: "0 10px 15px -3px rgba(15, 118, 110, 0.25)",
          marginBottom: "12px"
        }}>
          <Heart size={30} fill="white" />
        </div>
        <h1 style={{ fontSize: "28px", fontWeight: "800", color: "#0f172a", margin: 0, letterSpacing: "-0.5px" }}>
          NICU HomeCare AI
        </h1>
        <p style={{ fontSize: "14px", color: "#64748b", margin: "6px 0 0 0" }}>
          Empathetic Preterm Care Companion & Proactive Regular-Interval Reminders
        </p>
      </div>

      {/* Main Authentication Card */}
      <div style={{
        background: "#ffffff",
        width: "100%",
        maxWidth: "460px",
        borderRadius: "20px",
        boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.04)",
        border: "1px solid #e2e8f0",
        overflow: "hidden"
      }}>
        {/* Tab Toggle: Sign In vs Create Account */}
        <div style={{ display: "flex", borderBottom: "1px solid #e2e8f0", background: "#f8fafc" }}>
          <button
            type="button"
            onClick={() => { setIsRegister(false); setError(null); }}
            style={{
              flex: 1,
              padding: "16px",
              background: !isRegister ? "#ffffff" : "transparent",
              border: "none",
              borderBottom: !isRegister ? "2px solid #0f766e" : "2px solid transparent",
              color: !isRegister ? "#0f766e" : "#64748b",
              fontWeight: "700",
              fontSize: "14px",
              cursor: "pointer"
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setIsRegister(true); setError(null); }}
            style={{
              flex: 1,
              padding: "16px",
              background: isRegister ? "#ffffff" : "transparent",
              border: "none",
              borderBottom: isRegister ? "2px solid #0f766e" : "2px solid transparent",
              color: isRegister ? "#0f766e" : "#64748b",
              fontWeight: "700",
              fontSize: "14px",
              cursor: "pointer"
            }}
          >
            Create Account
          </button>
        </div>

        <div style={{ padding: "28px" }}>
          {error && (
            <div style={{
              background: "#fff1f2",
              border: "1px solid #fecdd3",
              color: "#e11d48",
              padding: "10px 14px",
              borderRadius: "8px",
              fontSize: "13px",
              marginBottom: "18px"
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {isRegister && (
              <>
                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#334155", marginBottom: "4px" }}>
                    Mother / Parent Full Name:
                  </label>
                  <div style={{ position: "relative" }}>
                    <User size={16} style={{ position: "absolute", left: "12px", top: "12px", color: "#94a3b8" }} />
                    <input
                      type="text"
                      required
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="e.g. Ananya Sharma"
                      style={{
                        width: "100%",
                        padding: "10px 12px 10px 36px",
                        border: "1px solid #cbd5e1",
                        borderRadius: "8px",
                        fontSize: "14px",
                        outline: "none"
                      }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#334155", marginBottom: "4px" }}>
                    Registered Mobile Number (for Regular SMS Interval Reminders):
                  </label>
                  <div style={{ position: "relative" }}>
                    <Phone size={16} style={{ position: "absolute", left: "12px", top: "12px", color: "#94a3b8" }} />
                    <input
                      type="tel"
                      required
                      value={phoneNumber}
                      onChange={(e) => setPhoneNumber(e.target.value)}
                      placeholder="+91 98765 43210"
                      style={{
                        width: "100%",
                        padding: "10px 12px 10px 36px",
                        border: "1px solid #cbd5e1",
                        borderRadius: "8px",
                        fontSize: "14px",
                        outline: "none"
                      }}
                    />
                  </div>
                  <span style={{ fontSize: "11px", color: "#0f766e", marginTop: "4px", display: "block" }}>
                    🔔 Automated feeding reminders & medication drop alerts will be sent here.
                  </span>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#334155", marginBottom: "4px" }}>
                    Baby's Name:
                  </label>
                  <div style={{ position: "relative" }}>
                    <Baby size={16} style={{ position: "absolute", left: "12px", top: "12px", color: "#94a3b8" }} />
                    <input
                      type="text"
                      required
                      value={babyName}
                      onChange={(e) => setBabyName(e.target.value)}
                      placeholder="e.g. Liam"
                      style={{
                        width: "100%",
                        padding: "10px 12px 10px 36px",
                        border: "1px solid #cbd5e1",
                        borderRadius: "8px",
                        fontSize: "14px",
                        outline: "none"
                      }}
                    />
                  </div>
                </div>
              </>
            )}

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#334155", marginBottom: "4px" }}>
                Registered Email Address {isRegister ? "(for HTML Care Cards)" : ""}:
              </label>
              <div style={{ position: "relative" }}>
                <Mail size={16} style={{ position: "absolute", left: "12px", top: "12px", color: "#94a3b8" }} />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="mother_liam@example.com"
                  style={{
                    width: "100%",
                    padding: "10px 12px 10px 36px",
                    border: "1px solid #cbd5e1",
                    borderRadius: "8px",
                    fontSize: "14px",
                    outline: "none"
                  }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#334155", marginBottom: "4px" }}>
                Password:
              </label>
              <div style={{ position: "relative" }}>
                <Lock size={16} style={{ position: "absolute", left: "12px", top: "12px", color: "#94a3b8" }} />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  style={{
                    width: "100%",
                    padding: "10px 12px 10px 36px",
                    border: "1px solid #cbd5e1",
                    borderRadius: "8px",
                    fontSize: "14px",
                    outline: "none"
                  }}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                background: "#0f766e",
                color: "white",
                border: "none",
                padding: "12px",
                borderRadius: "10px",
                fontSize: "14px",
                fontWeight: "700",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                marginTop: "6px",
                boxShadow: "0 4px 6px -1px rgba(15, 118, 110, 0.25)"
              }}
            >
              {loading ? "Authenticating..." : (isRegister ? "Create Account & Start Reminders" : "Sign In to Care Companion")}
              <ArrowRight size={16} />
            </button>
          </form>

          {/* Quick Demo Login Fillers */}
          <div style={{ marginTop: "24px", borderTop: "1px solid #f1f5f9", paddingTop: "18px" }}>
            <span style={{ fontSize: "11px", color: "#94a3b8", display: "block", textAlign: "center", marginBottom: "10px", fontWeight: "700" }}>
              ⚡ 1-CLICK INSTANT DEMO LOGIN
            </span>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                type="button"
                onClick={() => handleQuickDemo("parent")}
                style={{
                  flex: 1,
                  background: "#f0fdfa",
                  border: "1px solid #ccfbf1",
                  color: "#0f766e",
                  padding: "9px 12px",
                  borderRadius: "8px",
                  fontSize: "12px",
                  fontWeight: "700",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "4px"
                }}
              >
                👶 Mother (Ananya)
              </button>
              <button
                type="button"
                onClick={() => handleQuickDemo("doctor")}
                style={{
                  flex: 1,
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  color: "#475569",
                  padding: "9px 12px",
                  borderRadius: "8px",
                  fontSize: "12px",
                  fontWeight: "600",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "4px"
                }}
              >
                🩺 Dr. Rao (Neonatologist)
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Feature Badges below card */}
      <div style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        gap: "18px",
        marginTop: "24px",
        maxWidth: "600px",
        fontSize: "12px",
        color: "#64748b"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <CheckCircle size={15} color="#059669" />
          <span>3-Hour Feeding Target (45–54 mL)</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <Bell size={15} color="#0284c7" />
          <span>Regular Interval SMS & Email Alerts</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <Sparkles size={15} color="#d97706" />
          <span>24/7 Voice & Text Clinical Assistant</span>
        </div>
      </div>
    </div>
  );
}
