import React, { useState, useEffect } from "react";
import { X, Save, Calendar, User, Scale, Building2, Stethoscope, Heart, Clock, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { authApi, babyApi } from "../api";

export default function BabyProfileModal({ isOpen, onClose, baby, onProfileUpdated }) {
  if (!isOpen) return null;

  const [formData, setFormData] = useState({
    name: baby?.name || "Baby",
    date_of_birth: baby?.date_of_birth || new Date().toISOString().split("T")[0],
    gestational_age_weeks: baby?.gestational_age_weeks || 29,
    gestational_age_days: baby?.gestational_age_days || 0,
    sex: baby?.sex || "male",
    birth_weight_grams: baby?.birth_weight_grams || 1800,
    discharge_weight_grams: baby?.discharge_weight_grams || 2400,
    discharge_date: baby?.discharge_date || new Date().toISOString().split("T")[0],
    discharge_hospital: baby?.discharge_hospital || "BirthRight by Rainbow Hospital Vijayawada",
    pediatrician_name: baby?.pediatrician_name || "Dr. NICU Specialist",
    mother_preferred_language: baby?.mother_preferred_language || "en-US",
    blood_type: baby?.blood_type || "O+"
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    if (baby) {
      setFormData({
        name: baby.name || "Baby",
        date_of_birth: baby.date_of_birth || new Date().toISOString().split("T")[0],
        gestational_age_weeks: baby.gestational_age_weeks || 29,
        gestational_age_days: baby.gestational_age_days || 0,
        sex: baby.sex || "male",
        birth_weight_grams: baby.birth_weight_grams || 1800,
        discharge_weight_grams: baby.discharge_weight_grams || 2400,
        discharge_date: baby.discharge_date || new Date().toISOString().split("T")[0],
        discharge_hospital: baby.discharge_hospital || "BirthRight by Rainbow Hospital Vijayawada",
        pediatrician_name: baby.pediatrician_name || "Dr. NICU Specialist",
        mother_preferred_language: baby.mother_preferred_language || "en-US",
        blood_type: baby.blood_type || "O+"
      });
    }
  }, [baby]);

  // Live calculation of Chronological and Corrected Gestational Age
  const calculateAges = () => {
    try {
      const dob = new Date(formData.date_of_birth);
      const today = new Date();
      const diffTime = Math.max(0, today - dob);
      const chronoDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
      const chronoWeeks = Math.floor(chronoDays / 7);

      const weeksEarly = Math.max(0, 40 - Number(formData.gestational_age_weeks));
      const correctedWeeks = Math.max(0, chronoWeeks - weeksEarly);

      return {
        chronoWeeks,
        chronoDays: chronoDays % 7,
        weeksEarly,
        correctedWeeks
      };
    } catch {
      return { chronoWeeks: 0, chronoDays: 0, weeksEarly: 0, correctedWeeks: 0 };
    }
  };

  const ages = calculateAges();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const payload = {
        name: formData.name.trim() || "Baby",
        date_of_birth: formData.date_of_birth,
        gestational_age_weeks: Number(formData.gestational_age_weeks),
        gestational_age_days: Number(formData.gestational_age_days),
        sex: formData.sex,
        birth_weight_grams: Number(formData.birth_weight_grams),
        discharge_weight_grams: Number(formData.discharge_weight_grams),
        discharge_date: formData.discharge_date,
        discharge_hospital: formData.discharge_hospital.trim(),
        pediatrician_name: formData.pediatrician_name.trim(),
        mother_preferred_language: formData.mother_preferred_language,
        blood_type: formData.blood_type
      };

      const res = await authApi.updateBabyProfile(payload);
      setSuccess(`Baby ${res.baby.name}'s clinical profile updated successfully!`);

      if (onProfileUpdated) {
        onProfileUpdated(res.baby, res.user);
      }

      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err) {
      setError(err.message || "Failed to update baby profile. Please check the fields.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: "rgba(15, 23, 42, 0.65)",
      backdropFilter: "blur(4px)",
      zIndex: 100,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "20px"
    }}>
      <div style={{
        background: "white",
        borderRadius: "16px",
        width: "100%",
        maxWidth: "640px",
        maxHeight: "90vh",
        display: "flex",
        flexDirection: "column",
        boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
        overflow: "hidden"
      }}>
        {/* Header */}
        <div style={{
          background: "linear-gradient(135deg, #0f766e, #0d9488)",
          color: "white",
          padding: "18px 24px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center"
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Heart size={22} fill="white" />
            <div>
              <h3 style={{ margin: 0, fontSize: "17px", fontWeight: "700" }}>
                Baby Clinical Profile & Medical Identity
              </h3>
              <p style={{ margin: "2px 0 0 0", fontSize: "11px", opacity: 0.9 }}>
                AAP & Fenton Growth Norms • Preterm Corrected Age Tracker
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "rgba(255,255,255,0.2)",
              border: "none",
              color: "white",
              borderRadius: "8px",
              padding: "6px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center"
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Live Clinical Summary Banner */}
        <div style={{
          background: "#f0fdfa",
          borderBottom: "1px solid #ccfbf1",
          padding: "12px 24px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "8px",
          fontSize: "12px",
          color: "#0f766e"
        }}>
          <div>
            👶 <strong>{formData.name}</strong> • Born early at <b>{formData.gestational_age_weeks}w + {formData.gestational_age_days}d</b>
          </div>
          <div style={{ background: "#ccfbf1", padding: "3px 10px", borderRadius: "12px", fontWeight: "700" }}>
            ⏱️ Corrected Age: ~{ages.correctedWeeks} Weeks
          </div>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ overflowY: "auto", padding: "20px 24px", display: "flex", flexDirection: "column", gap: "16px" }}>
          {error && (
            <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", color: "#b91c1c", padding: "10px 14px", borderRadius: "8px", fontSize: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div style={{ background: "#ecfdf5", border: "1px solid #a7f3d0", color: "#065f46", padding: "10px 14px", borderRadius: "8px", fontSize: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
              <CheckCircle2 size={16} />
              <span>{success}</span>
            </div>
          )}

          {/* Section 1: Basic Identity */}
          <div>
            <label style={{ fontSize: "12px", fontWeight: "700", color: "#475569", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px", display: "block" }}>
              1. Basic Identity
            </label>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ fontSize: "11px", color: "#64748b", display: "block", marginBottom: "4px" }}>Baby's Name *</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  style={{ width: "100%", padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "13px" }}
                  placeholder="e.g. Vochetu"
                />
              </div>

              <div>
                <label style={{ fontSize: "11px", color: "#64748b", display: "block", marginBottom: "4px" }}>Date of Birth *</label>
                <input
                  type="date"
                  required
                  value={formData.date_of_birth}
                  onChange={(e) => setFormData({ ...formData, date_of_birth: e.target.value })}
                  style={{ width: "100%", padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "13px" }}
                />
              </div>

              <div>
                <label style={{ fontSize: "11px", color: "#64748b", display: "block", marginBottom: "4px" }}>Biological Sex *</label>
                <select
                  value={formData.sex}
                  onChange={(e) => setFormData({ ...formData, sex: e.target.value })}
                  style={{ width: "100%", padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "13px", background: "white" }}
                >
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                </select>
              </div>
            </div>
          </div>

          {/* Section 2: Gestational Age & Prematurity */}
          <div>
            <label style={{ fontSize: "12px", fontWeight: "700", color: "#475569", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px", display: "block" }}>
              2. Gestational Age at Birth (Weeks + Days)
            </label>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ fontSize: "11px", color: "#64748b", display: "block", marginBottom: "4px" }}>Completed Weeks (22–42) *</label>
                <input
                  type="number"
                  min="22"
                  max="42"
                  required
                  value={formData.gestational_age_weeks}
                  onChange={(e) => setFormData({ ...formData, gestational_age_weeks: e.target.value })}
                  style={{ width: "100%", padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "13px" }}
                />
              </div>

              <div>
                <label style={{ fontSize: "11px", color: "#64748b", display: "block", marginBottom: "4px" }}>Additional Days (0–6)</label>
                <input
                  type="number"
                  min="0"
                  max="6"
                  value={formData.gestational_age_days}
                  onChange={(e) => setFormData({ ...formData, gestational_age_days: e.target.value })}
                  style={{ width: "100%", padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "13px" }}
                />
              </div>

              <div>
                <label style={{ fontSize: "11px", color: "#64748b", display: "block", marginBottom: "4px" }}>Blood Type</label>
                <select
                  value={formData.blood_type}
                  onChange={(e) => setFormData({ ...formData, blood_type: e.target.value })}
                  style={{ width: "100%", padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "13px", background: "white" }}
                >
                  <option value="O+">O Positive (O+)</option>
                  <option value="O-">O Negative (O-)</option>
                  <option value="A+">A Positive (A+)</option>
                  <option value="A-">A Negative (A-)</option>
                  <option value="B+">B Positive (B+)</option>
                  <option value="B-">B Negative (B-)</option>
                  <option value="AB+">AB Positive (AB+)</option>
                  <option value="AB-">AB Negative (AB-)</option>
                </select>
              </div>
            </div>
          </div>

          {/* Section 3: Weights & NICU Discharge */}
          <div>
            <label style={{ fontSize: "12px", fontWeight: "700", color: "#475569", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px", display: "block" }}>
              3. Clinical Weights & NICU Discharge
            </label>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ fontSize: "11px", color: "#64748b", display: "block", marginBottom: "4px" }}>Birth Weight (grams) *</label>
                <input
                  type="number"
                  min="400"
                  max="6000"
                  required
                  value={formData.birth_weight_grams}
                  onChange={(e) => setFormData({ ...formData, birth_weight_grams: e.target.value })}
                  style={{ width: "100%", padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "13px" }}
                  placeholder="e.g. 1800"
                />
              </div>

              <div>
                <label style={{ fontSize: "11px", color: "#64748b", display: "block", marginBottom: "4px" }}>Discharge Weight (grams) *</label>
                <input
                  type="number"
                  min="400"
                  max="8000"
                  required
                  value={formData.discharge_weight_grams}
                  onChange={(e) => setFormData({ ...formData, discharge_weight_grams: e.target.value })}
                  style={{ width: "100%", padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "13px" }}
                  placeholder="e.g. 2400"
                />
              </div>

              <div>
                <label style={{ fontSize: "11px", color: "#64748b", display: "block", marginBottom: "4px" }}>Discharge Date *</label>
                <input
                  type="date"
                  required
                  value={formData.discharge_date}
                  onChange={(e) => setFormData({ ...formData, discharge_date: e.target.value })}
                  style={{ width: "100%", padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "13px" }}
                />
              </div>
            </div>
          </div>

          {/* Section 4: Care Team & Language */}
          <div>
            <label style={{ fontSize: "12px", fontWeight: "700", color: "#475569", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px", display: "block" }}>
              4. Hospital Affiliation & Language
            </label>
            <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ fontSize: "11px", color: "#64748b", display: "block", marginBottom: "4px" }}>Discharging Hospital</label>
                <input
                  type="text"
                  value={formData.discharge_hospital}
                  onChange={(e) => setFormData({ ...formData, discharge_hospital: e.target.value })}
                  style={{ width: "100%", padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "13px" }}
                  placeholder="e.g. BirthRight by Rainbow Hospital"
                />
              </div>

              <div>
                <label style={{ fontSize: "11px", color: "#64748b", display: "block", marginBottom: "4px" }}>Pediatrician / Neonatologist</label>
                <input
                  type="text"
                  value={formData.pediatrician_name}
                  onChange={(e) => setFormData({ ...formData, pediatrician_name: e.target.value })}
                  style={{ width: "100%", padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "13px" }}
                  placeholder="e.g. Dr. Preterm Specialist"
                />
              </div>
            </div>
          </div>

          {/* Footer Actions */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px", paddingTop: "14px", borderTop: "1px solid #e2e8f0" }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                background: "#f1f5f9",
                color: "#475569",
                border: "1px solid #cbd5e1",
                padding: "9px 16px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              style={{
                background: "#0f766e",
                color: "white",
                border: "none",
                padding: "9px 20px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: "700",
                cursor: saving ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                boxShadow: "0 2px 4px rgba(15,118,110,0.2)"
              }}
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              {saving ? "Saving Profile..." : "Save Profile"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
