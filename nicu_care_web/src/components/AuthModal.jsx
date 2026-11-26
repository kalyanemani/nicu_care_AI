import React, { useState } from "react";
import { X, Mail, Phone, Lock, User, Heart, ShieldCheck, ArrowRight } from "lucide-react";
import { authApi } from "../api";

export default function AuthModal({ isOpen, onClose, onLoginSuccess }) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("mother_liam@example.com");
  const [password, setPassword] = useState("password123");
  const [fullName, setFullName] = useState("Ananya Sharma");
  const [phoneNumber, setPhoneNumber] = useState("+919876543210");
  const [babyName, setBabyName] = useState("Liam");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (isRegister) {
        // Register new account with email and mobile
        await authApi.register(fullName, email, phoneNumber, password, "baby_liam_01");
        // Automatically login
        const session = await authApi.login(email, password);
        localStorage.setItem("nicu_token", session.access_token);
        onLoginSuccess(session.user);
        onClose();
      } else {
        // Log in with existing account
        const session = await authApi.login(email, password);
        localStorage.setItem("nicu_token", session.access_token);
        onLoginSuccess(session.user);
        onClose();
      }
    } catch (err) {
      setError(err.message || "Authentication failed. Please verify your credentials.");
    } finally {
      setLoading(false);
    }
  }

  function handleQuickDemoLogin(role = "parent") {
    if (role === "parent") {
      setEmail("mother_liam@example.com");
      setPassword("password123");
      setIsRegister(false);
    } else {
      setEmail("dr_sharma@rainbow.com");
      setPassword("doctor123");
      setIsRegister(false);
    }
  }

  return (
    <div style={{
      position: "fixed",
      inset: 0,
      background: "rgba(15, 23, 42, 0.6)",
      backdropFilter: "blur(4px)",
      zIndex: 100,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "16px"
    }}>
      <div style={{
        background: "white",
        width: "100%",
        maxWidth: "480px",
        borderRadius: "16px",
        overflow: "hidden",
        boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
        border: "1px solid #e2e8f0"
      }}>
        {/* Modal Header */}
        <div style={{
          background: "linear-gradient(135deg, #0f766e, #0d9488)",
          color: "white",
          padding: "22px 24px",
          position: "relative"
        }}>
          <button
            onClick={onClose}
            style={{
              position: "absolute",
              right: "16px",
              top: "16px",
              background: "rgba(255,255,255,0.2)",
              border: "none",
              color: "white",
              width: "32px",
              height: "32px",
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer"
            }}
          >
            <X size={18} />
          </button>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
            <Heart size={24} fill="white" />
            <h2 style={{ fontSize: "20px", fontWeight: "700", margin: 0 }}>
              {isRegister ? "Create Parent Account" : "Sign In to NICU HomeCare"}
            </h2>
          </div>
          <p style={{ fontSize: "12px", opacity: 0.9, margin: 0 }}>
            {isRegister
              ? "Your registered email and mobile will receive interval care reminders"
              : "Access Liam's clinical schedule, feeding math, and smart reminders"}
          </p>
        </div>

        {/* Modal Body */}
        <div style={{ padding: "24px" }}>
          {error && (
            <div style={{
              background: "#fff1f2",
              border: "1px solid #fecdd3",
              color: "#e11d48",
              padding: "10px 14px",
              borderRadius: "8px",
              fontSize: "13px",
              marginBottom: "16px"
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
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
                    Registered Mobile Number (for SMS Interval Reminders):
                  </label>
                  <div style={{ position: "relative" }}>
                    <Phone size={16} style={{ position: "absolute", left: "12px", top: "12px", color: "#94a3b8" }} />
                    <input
                      type="tel"
                      required
                      value={phoneNumber}
                      onChange={(e) => setPhoneNumber(e.target.value)}
                      placeholder="+919876543210"
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
                  <span style={{ fontSize: "11px", color: "#0f766e", marginTop: "2px", display: "block" }}>
                    💡 Overdue feeds and medication alerts will be sent here.
                  </span>
                </div>
              </>
            )}

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "#334155", marginBottom: "4px" }}>
                Registered Email Address (for HTML Care Cards):
              </label>
              <div style={{ position: "relative" }}>
                <Mail size={16} style={{ position: "absolute", left: "12px", top: "12px", color: "#94a3b8" }} />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="e.g. mother_liam@example.com"
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
                borderRadius: "8px",
                fontSize: "14px",
                fontWeight: "700",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                marginTop: "6px",
                boxShadow: "0 2px 4px rgba(15,118,110,0.2)"
              }}
            >
              {loading ? "Processing..." : (isRegister ? "Create Account & Connect Reminders" : "Sign In to Companion")}
              <ArrowRight size={16} />
            </button>
          </form>

          {/* Toggle between Login and Register */}
          <div style={{ textAlign: "center", marginTop: "16px", fontSize: "13px", color: "#64748b" }}>
            {isRegister ? "Already have an account? " : "New parent at Rainbow NICU? "}
            <button
              onClick={() => { setIsRegister(!isRegister); setError(null); }}
              style={{
                background: "none",
                border: "none",
                color: "#0f766e",
                fontWeight: "700",
                cursor: "pointer",
                textDecoration: "underline"
              }}
            >
              {isRegister ? "Sign In" : "Create Account"}
            </button>
          </div>

          {/* Quick Demo Login Fillers */}
          <div style={{ marginTop: "20px", borderTop: "1px solid #f1f5f9", paddingTop: "16px" }}>
            <span style={{ fontSize: "11px", color: "#94a3b8", display: "block", textAlign: "center", marginBottom: "8px" }}>
              ⚡ ONE-CLICK DEMO LOGIN (RAINBOW HOSPITAL TRIAL)
            </span>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                type="button"
                onClick={() => handleQuickDemoLogin("parent")}
                style={{
                  flex: 1,
                  background: "#f0fdfa",
                  border: "1px solid #ccfbf1",
                  color: "#0f766e",
                  padding: "8px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontWeight: "600",
                  cursor: "pointer"
                }}
              >
                👶 Mother (Ananya)
              </button>
              <button
                type="button"
                onClick={() => handleQuickDemoLogin("doctor")}
                style={{
                  flex: 1,
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  color: "#475569",
                  padding: "8px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontWeight: "600",
                  cursor: "pointer"
                }}
              >
                🩺 Dr. Rao (Neonatologist)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
