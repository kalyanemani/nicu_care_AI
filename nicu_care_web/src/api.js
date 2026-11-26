/**
 * API Service for NICU HomeCare React Web Application.
 * Communicates directly with the FastAPI backend on http://127.0.0.1:8000.
 */

const API_HOST = typeof window !== "undefined" && window.location.hostname ? window.location.hostname : "127.0.0.1";
const API_BASE = (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_BASE)
  ? import.meta.env.VITE_API_BASE
  : `http://${API_HOST}:8000/api/v1`;

function getLocalTimestamp(custom) {
  if (custom) return String(custom).replace(/Z$/, "");
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}

export async function request(endpoint, options = {}) {
  const token = localStorage.getItem("nicu_token");
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Request failed with status ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.error(`API Error on ${endpoint}:`, err);
    throw err;
  }
}

// ── Auth Services ────────────────────────────────────────────────────
export const authApi = {
  login: (email, password) =>
    request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  register: (fullName, email, phone, password, babyName = "Liam") =>
    request("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        full_name: fullName,
        email,
        phone_number: phone,
        password,
        role: "parent",
        baby_name: babyName,
      }),
    }),

  getProfile: () => request("/auth/me"),
};

// ── Baby & Timeline Services ─────────────────────────────────────────
export const babyApi = {
  getProfile: (babyId = "baby_liam_01") => request(`/baby/${babyId}/profile`),
  getFeedingTargets: (babyId = "baby_liam_01") => request(`/baby/${babyId}/feeding-targets`),
  getTimeline: (babyId = "baby_liam_01") => request(`/timeline/${babyId}`),
  getKmcSummary: (babyId = "baby_liam_01") => request(`/timeline/kmc/summary/${babyId}`),
  getNextSchedule: (babyId = "baby_liam_01") => request(`/timeline/${babyId}/next-schedule`),
};

// ── Care Logging Services ────────────────────────────────────────────
export const careLogApi = {
  logFeed: (babyId, volumeMl, feedType = "fortified_breast_milk", customTimestamp = null) =>
    request(`/baby/${babyId}/feeds`, {
      method: "POST",
      body: JSON.stringify({
        baby_id: babyId,
        volume_ml: volumeMl,
        feed_type: feedType,
        feed_method: "Paced Bottle",
        timestamp: getLocalTimestamp(customTimestamp),
      }),
    }),

  logKmc: (babyId, durationMinutes, caregiver = "mother", customTimestamp = null) =>
    request("/timeline/kmc", {
      method: "POST",
      body: JSON.stringify({
        baby_id: babyId,
        duration_minutes: durationMinutes,
        caregiver: caregiver,
        timestamp: getLocalTimestamp(customTimestamp),
      }),
    }),
};

// ── Regular-Interval Reminders Services ──────────────────────────────
export const reminderApi = {
  getPreferences: (userId = "usr_mother_01") =>
    request(`/reminders/preferences/${userId}`),

  updatePreferences: (userId, preferences) =>
    request(`/reminders/preferences/${userId}`, {
      method: "PUT",
      body: JSON.stringify(preferences),
    }),

  sendTestReminder: (payload) =>
    request("/reminders/send-test", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getHistory: (babyId = "baby_liam_01") =>
    request(`/reminders/history/${babyId}?limit=20`),

  getStatus: () => request("/reminders/status"),
};

// ── Agent Conversational QA (Voice & Text) ───────────────────────────
export const agentApi = {
  sendQuery: (text, babyId = "baby_liam_01", model = null, language = "en-US") =>
    request("/agent/text-query", {
      method: "POST",
      body: JSON.stringify({
        baby_id: babyId,
        text,
        model: model || undefined,
        language: language || "en-US",
      }),
    }),
};
