import React from "react";
import { Phone, Heart, User, LogOut, Bell, Calendar, Home, CheckCircle } from "lucide-react";

export default function Navbar({ user, baby, onOpenAuth, onLogout, activeTab, setActiveTab }) {
  return (
    <header style={{
      background: "#ffffff",
      borderBottom: "1px solid #e2e8f0",
      position: "sticky",
      top: 0,
      zIndex: 40,
      padding: "12px 24px",
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      boxShadow: "0 1px 3px rgba(0,0,0,0.03)"
    }}>
      {/* Brand & Hospital Affiliation */}
      <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
        <div style={{
          background: "linear-gradient(135deg, #0f766e, #0d9488)",
          color: "white",
          width: "40px",
          height: "40px",
          borderRadius: "10px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "0 2px 6px rgba(15,118,110,0.25)"
        }}>
          <Heart size={22} fill="white" />
        </div>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a", letterSpacing: "-0.2px" }}>
              NICU HomeCare AI
            </span>
            <span style={{
              background: "#f0fdfa",
              color: "#0f766e",
              fontSize: "11px",
              fontWeight: "700",
              padding: "2px 8px",
              borderRadius: "12px",
              border: "1px solid #ccfbf1"
            }}>
              POST-DISCHARGE
            </span>
          </div>
          <p style={{ fontSize: "11px", color: "#64748b", margin: 0 }}>
            Preterm Infant Post-Discharge Care Companion
          </p>
        </div>
      </div>

      {/* Center Navigation Tabs (Clean & Focused on Mother's Routine) */}
      <nav style={{ display: "flex", gap: "8px" }}>
        <button
          onClick={() => setActiveTab("dashboard")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "8px 16px",
            borderRadius: "8px",
            border: "none",
            fontSize: "13px",
            fontWeight: "600",
            cursor: "pointer",
            background: activeTab === "dashboard" ? "#f0fdfa" : "transparent",
            color: activeTab === "dashboard" ? "#0f766e" : "#64748b",
            transition: "all 0.15s ease"
          }}
        >
          <Home size={16} />
          Today's Routine
        </button>

        <button
          onClick={() => setActiveTab("reminders")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "8px 16px",
            borderRadius: "8px",
            border: "none",
            fontSize: "13px",
            fontWeight: "600",
            cursor: "pointer",
            background: activeTab === "reminders" ? "#f0fdfa" : "transparent",
            color: activeTab === "reminders" ? "#0f766e" : "#64748b",
            transition: "all 0.15s ease"
          }}
        >
          <Bell size={16} />
          Interval Reminders
        </button>
      </nav>

      {/* Right Side: Emergency Dialer & User Account */}
      <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
        {/* 24/7 NICU Helpline Dialer */}
        <a
          href="tel:04049694969"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            background: "#fff1f2",
            color: "#e11d48",
            border: "1px solid #fecdd3",
            padding: "7px 14px",
            borderRadius: "20px",
            fontSize: "12px",
            fontWeight: "700",
            textDecoration: "none",
            boxShadow: "0 1px 2px rgba(225,29,72,0.08)"
          }}
          title="Direct line to 24/7 NICU Neonatologist Helpline"
        >
          <Phone size={14} />
          24/7 NICU Line: 040-49694969
        </a>

        {/* User Account State */}
        {user ? (
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "13px", fontWeight: "600", color: "#0f172a" }}>
                {(() => {
                  const name = user?.full_name || user?.user?.full_name || user?.name || user?.email || "Ananya";
                  return typeof name === "string" ? name.split(" ")[0] : "Ananya";
                })()}
              </div>
              <div style={{ fontSize: "11px", color: "#64748b" }}>
                Baby {baby?.name || user?.baby_name || "Liam"} (36w CGA)
              </div>
            </div>
            <button
              onClick={onLogout}
              style={{
                background: "#f1f5f9",
                border: "1px solid #e2e8f0",
                color: "#64748b",
                padding: "8px",
                borderRadius: "8px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}
              title="Sign Out"
            >
              <LogOut size={16} />
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenAuth}
            style={{
              background: "#0f766e",
              color: "white",
              border: "none",
              padding: "8px 18px",
              borderRadius: "8px",
              fontSize: "13px",
              fontWeight: "600",
              cursor: "pointer",
              boxShadow: "0 2px 4px rgba(15,118,110,0.2)"
            }}
          >
            Sign In / Register
          </button>
        )}
      </div>
    </header>
  );
}
