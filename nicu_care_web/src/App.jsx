import React, { useState, useEffect, Component } from "react";
import Navbar from "./components/Navbar";
import Dashboard from "./components/Dashboard";
import RemindersView from "./components/RemindersView";
import ChatbotSlider from "./components/ChatbotSlider";
import LoginPage from "./components/LoginPage";
import { authApi } from "./api";

// Error Boundary to prevent blank white screens
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "#f8fafc",
          padding: "24px",
          textAlign: "center"
        }}>
          <div style={{
            background: "white",
            padding: "32px",
            borderRadius: "16px",
            border: "1px solid #e2e8f0",
            maxWidth: "480px",
            boxShadow: "0 10px 15px -3px rgba(0,0,0,0.05)"
          }}>
            <h2 style={{ fontSize: "20px", fontWeight: "800", color: "#0f766e", marginBottom: "8px" }}>
              NICU HomeCare AI
            </h2>
            <p style={{ fontSize: "14px", color: "#64748b", marginBottom: "20px" }}>
              Something interrupted the view. Click below to refresh your preterm care dashboard.
            </p>
            <button
              onClick={() => {
                localStorage.removeItem("nicu_token");
                window.location.reload();
              }}
              style={{
                background: "#0f766e",
                color: "white",
                border: "none",
                padding: "10px 20px",
                borderRadius: "8px",
                fontWeight: "700",
                cursor: "pointer"
              }}
            >
              🔄 Refresh Dashboard & Session
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const [user, setUser] = useState(null);
  const [baby, setBaby] = useState(null);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    // Check if user has a verified stored session
    const token = localStorage.getItem("nicu_token");
    if (token) {
      authApi.getProfile()
        .then((profile) => {
          const userData = profile?.user || profile;
          setUser(userData);
          if (profile?.baby && profile.baby.name) {
            setBaby(profile.baby);
          } else if (userData?.baby_name) {
            setBaby({
              name: userData.baby_name,
              baby_id: userData?.assigned_baby_ids?.[0] || ""
            });
          } else {
            const bId = userData?.assigned_baby_ids?.[0] || "";
            setBaby({ name: "Baby", baby_id: bId });
          }
        })
        .catch(() => {
          localStorage.removeItem("nicu_token");
          setUser(null);
        })
        .finally(() => setCheckingAuth(false));
    } else {
      setUser(null);
      setCheckingAuth(false);
    }
  }, []);

  function handleLogout() {
    localStorage.removeItem("nicu_token");
    setUser(null);
    setBaby(null);
  }

  function handleUpdateBaby(newBabyData) {
    if (!newBabyData) return;
    setBaby((prev) => ({ ...(prev || {}), ...newBabyData }));
    if (user && newBabyData.name) {
      setUser((prev) => ({ ...(prev || {}), baby_name: newBabyData.name }));
    }
  }

  // Loading state while checking session
  if (checkingAuth) {
    return (
      <div style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#f8fafc",
        color: "#0f766e",
        fontSize: "14px",
        fontWeight: "600"
      }}>
        Loading NICU HomeCare Companion...
      </div>
    );
  }

  // ── 1. GATED AUTHENTICATION: SHOW LOGIN PAGE FIRST ─────────────────────
  if (!user) {
    return (
      <ErrorBoundary>
        <LoginPage onLoginSuccess={(loggedInUser) => {
          const u = loggedInUser?.user || loggedInUser;
          setUser(u);
          const bName = u?.baby_name || "Baby";
          const bId = u?.assigned_baby_ids?.[0] || "";
          setBaby({ name: bName, baby_id: bId });
        }} />
      </ErrorBoundary>
    );
  }

  // ── 2. AUTHENTICATED PARENT APPLICATION ────────────────────────────────
  return (
    <ErrorBoundary>
      <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "#f8fafc" }}>
        {/* Top Header Navigation */}
        <Navbar
          user={user}
          baby={baby}
          onUpdateBaby={handleUpdateBaby}
          onOpenAuth={() => {}}
          onLogout={handleLogout}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
        />

        {/* Main View: Routine Checklist or Interval Reminders */}
        <main style={{ flex: 1 }}>
          {activeTab === "dashboard" ? (
            <Dashboard
              user={user}
              baby={baby}
              onUpdateBaby={handleUpdateBaby}
              onOpenReminders={() => setActiveTab("reminders")}
            />
          ) : (
            <RemindersView user={user} baby={baby} />
          )}
        </main>

        {/* Bottom-Right Floating Clinical Chatbot (Voice & Text) */}
        <ChatbotSlider baby={baby} />
      </div>
    </ErrorBoundary>
  );
}
