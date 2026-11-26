"""
NICU Baby Care Companion — Mother-Centered Conversational Application
Featuring:
  - Dynamic ChatGPT-style conversational feed
  - Voice-enabled Speech-to-Text (Microphone input) & Text-to-Speech (Audio Voice synthesis)
  - Multilingual support: English (en-US), Telugu (తెలుగు), Hindi (हिन्दी)
  - Empathetic, mother-friendly explanations with a built-in NICU Jargon Buster
  - 1-Tap Emergency Hospital Dialer (Rainbow Hospital Vijayawada & 108)
"""
import streamlit as st
import streamlit.components.v1 as components
import datetime
import json
import urllib.parse

from app.models.baby import BabyProfile
from app.models.agent import TextQueryRequest
from app.models.timeline import KMCSession, GrowthRecord, MaternalWellbeing
from app.services.pediatric_math_service import PediatricMathService
from app.services.wiki_service import WikiService
from app.services.care_log_service import CareLogService
from app.services.hospital_service import HospitalEmergencyService
from app.services.translation_service import translation_service
from app.services.timeline_service import timeline_service
from app.services.hitl_service import hitl_service
from app.routers.agent import process_text_query, cache_service
from app.services.auth_service import auth_service
from app.services.db_architecture_service import db_architecture_service
from app.memory.episodic_memory import episodic_memory, EpisodeType, EpisodeSeverity
from app.models.auth import UserLogin
from app.services.neonatal_bert_service import neonatal_bert_service
from app.services.notification_service import notification_service
from app.services.reminder_scheduler import reminder_scheduler
from app.models.reminder import ReminderCategory, NotificationChannel, NotificationPreferences

# ── Page Configuration ────────────────────────────────────────────────
st.set_page_config(
    page_title="NICU HomeCare AI — Post-Discharge Companion",
    page_icon="👶",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Initialize Core Services ──────────────────────────────────────────
@st.cache_resource
def load_services():
    return (
        PediatricMathService(),
        WikiService(),
        CareLogService(),
        HospitalEmergencyService(),
        timeline_service,
    )

math_service, wiki_service, log_service, hospital_service, timeline_svc = load_services()

# ── Sidebar: Authentication & Baby Profile Selector ───────────────────
with st.sidebar:
    st.header("🔐 User Authentication")
    if "auth_user" not in st.session_state:
        try:
            default_session = auth_service.login_user(UserLogin(email="mother_liam@example.com", password="password123"))
            st.session_state.auth_user = default_session.user
            st.session_state.auth_token = default_session.access_token
            st.session_state.storage_arch = default_session.storage_architecture
            st.session_state.memory_arch = default_session.agentic_memory_architecture
        except Exception:
            pass

    if "auth_user" in st.session_state and st.session_state.auth_user:
        current_user = st.session_state.auth_user
        role_label = "👩 MOTHER (Parent)" if current_user.role == "parent" else ("🩺 NEONATOLOGIST (Clinician)" if current_user.role == "clinician" else "⚡ ADMIN")
        st.markdown(f"""
        <div style="background-color: #E8F5E9; border-radius: 8px; padding: 10px 12px; border: 1px solid #C8E6C9; margin-bottom: 12px;">
            <div style="font-size: 11px; font-weight: 700; color: #2E7D32;">{role_label}</div>
            <div style="font-size: 13px; color: #1B5E20; font-weight: 700;">{current_user.full_name}</div>
            <div style="font-size: 11px; color: #558B2F;">{current_user.email}</div>
        </div>
        """, unsafe_allow_html=True)

        col_sw1, col_sw2 = st.columns(2)
        with col_sw1:
            if st.button("🩺 As Doctor", key="btn_sw_doc", use_container_width=True):
                s = auth_service.login_user(UserLogin(email="dr_sharma@rainbow.com", password="doctor123"))
                st.session_state.auth_user = s.user
                st.session_state.auth_token = s.access_token
                st.session_state.storage_arch = s.storage_architecture
                st.session_state.memory_arch = s.agentic_memory_architecture
                st.rerun()
        with col_sw2:
            if st.button("👩 As Mother", key="btn_sw_mom", use_container_width=True):
                s = auth_service.login_user(UserLogin(email="mother_liam@example.com", password="password123"))
                st.session_state.auth_user = s.user
                st.session_state.auth_token = s.access_token
                st.session_state.storage_arch = s.storage_architecture
                st.session_state.memory_arch = s.agentic_memory_architecture
                st.rerun()

    st.markdown("---")
    st.header("👶 Select Baby Profile")
    baby_options = ["Liam (baby_liam_01)", "vochetu (vochetu1)"]
    selected_baby_idx = 0
    if "selected_baby_id" in st.session_state and st.session_state.selected_baby_id == "vochetu1":
        selected_baby_idx = 1
        
    selected_baby_str = st.selectbox(
        "Active Infant Record",
        baby_options,
        index=selected_baby_idx,
    )
    current_baby_id = "vochetu1" if "vochetu1" in selected_baby_str else "baby_liam_01"
    st.session_state.selected_baby_id = current_baby_id

    st.markdown("---")
    st.header("🧠 Clinical AI Model")
    ai_model_options = {
        "MedGemma 1.5 (Pediatric Expert)": "medgemma1.5:latest",
        "Llama 3.1 8B (Authoritative)": "llama3.1:8b",
        "Qwen 2.5 3B (Ultra-Fast)": "qwen2.5:3b",
    }
    selected_ai_label = st.selectbox(
        "Active Reasoning Engine",
        list(ai_model_options.keys()),
        index=0,
        help="Select the local clinical LLM. Timeouts are disabled so answers generate completely."
    )
    active_selected_model = ai_model_options[selected_ai_label]
    st.caption("🟢 **Timeouts: DISABLED** (Unconstrained Generation)")

# Load selected Baby Profile
baby = wiki_service.load_baby_profile_json(current_baby_id)
if not baby:
    dob = datetime.date.today() - datetime.timedelta(days=56)
    baby = BabyProfile(
        baby_id="baby_liam_01",
        name="Liam",
        date_of_birth=dob,
        gestational_age_weeks=29,
        gestational_age_days=2,
        sex="male",
        birth_weight_grams=1180,
        discharge_weight_grams=1820,
        discharge_date=datetime.date.today() - datetime.timedelta(days=21),
        discharge_hospital="BirthRight Rainbow Vijayawada",
        pediatrician_name="Dr. K. Rao (Neonatologist)",
        mother_preferred_language="en-US",
    )
    wiki_service.save_baby_profile_json(baby)
    wiki_service.create_profile_from_baby(baby)

corrected_age = math_service.calculate_corrected_age(baby)
# Use discharge weight as base if current not yet logged
est_weight = baby.discharge_weight_grams if baby.discharge_weight_grams else 2400
if baby.baby_id == "baby_liam_01":
    est_weight = 2400
volume_target = math_service.calculate_daily_volume_target(est_weight)

# ── Session State for Chat ────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "text": (
                "👋 **Hello! I'm your NICU Home Care Companion.**\n\n"
                "I am here 24/7 to support you with Baby Liam after leaving the NICU. "
                "You can ask me questions, log feeds or diapers, or check warning signs in **English, Telugu (తెలుగు), or Hindi (हिन्दी)**.\n\n"
                "💡 *Tip: Try asking 'How much milk should Liam drink today?' or click the mic below to speak!*"
            ),
            "voice_note": "Hello! I am your NICU care companion. How can I help you and baby Liam today?",
            "is_emergency": False,
            "timestamp": "Just now",
        }
    ]

# ── Top Bar: Header & Language Switcher ────────────────────────────────
col_top_title, col_top_lang = st.columns([3, 1])
with col_top_title:
    st.title("👶 NICU Baby Care Companion")
    st.caption("A supportive, medically grounded companion for mothers of NICU babies post-discharge.")

with col_top_lang:
    selected_language = st.selectbox(
        "🌐 Language / భాష / भाषा",
        ["English (en-US)", "Telugu (తెలుగు)", "Hindi (हिन्दी)"],
        index=0,
    )
    lang_code = "te-IN" if "Telugu" in selected_language else ("hi-IN" if "Hindi" in selected_language else "en-US")

# ── Liam's Care Banner (Hero Section) ──────────────────────────────────
st.markdown("""
<style>
.hero-card {
    background: linear-gradient(135deg, #E0F2F1 0%, #B2DFDB 100%);
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 20px;
    border: 1px solid #80CBC4;
}
.hero-title { font-size: 19px; font-weight: 700; color: #004D40; margin-bottom: 4px; }
.hero-sub { font-size: 14px; color: #00695C; line-height: 1.5; }
.hero-highlight { font-weight: 600; color: #004D40; }
.pill-alert {
    background-color: #FFEBEE;
    border: 1px solid #FFCDD2;
    color: #C62828;
    padding: 6px 12px;
    border-radius: 8px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

col_hero1, col_hero2 = st.columns([3, 1])
with col_hero1:
    st.markdown(f"""
    <div class="hero-card">
        <div class="hero-title">👶 Baby {baby.name.capitalize()}'s Health Overview</div>
        <div class="hero-sub">
            • <b>Actual Age:</b> {corrected_age.chronological_weeks} weeks ({corrected_age.chronological_days} days since birth)<br>
            • <b>Corrected (Developmental) Age:</b> <span class="hero-highlight">{corrected_age.corrected_weeks} weeks</span> (Born {corrected_age.weeks_born_early} weeks early at {baby.gestational_age_weeks}w+{baby.gestational_age_days}d)<br>
            • <b>Feeding Goal:</b> <span class="hero-highlight">{volume_target['min_daily_ml']:.0f}–{volume_target['max_daily_ml']:.0f} mL/day</span> ({volume_target['per_feed_min_ml']:.0f}–{volume_target['per_feed_max_ml']:.0f} mL every 3 hours)<br>
            • <b>Discharge Hospital:</b> {baby.discharge_hospital or 'BirthRight by Rainbow Hospital, Vijayawada'} | <b>Pediatrician:</b> {baby.pediatrician_name or 'Dr. K. Rao'}
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_hero2:
    st.markdown("""
    <div style="background-color: #FFF3E0; border-radius: 12px; padding: 14px; border: 1px solid #FFE0B2; text-align: center;">
        <span style="font-size: 13px; font-weight: 700; color: #E65100;">🚨 24/7 NICU HELPLINE</span><br>
        <a href="tel:+918666690000" style="text-decoration: none; font-size: 16px; font-weight: 800; color: #D84315;">+91 866 669 0000</a><br>
        <span style="font-size: 11px; color: #BF360C;">Rainbow Hospital Vijayawada</span><br>
        <a href="tel:108" style="display: inline-block; margin-top: 8px; background-color: #D32F2F; color: white; padding: 5px 12px; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: 700;">DIAL 108 (AMBULANCE)</a>
    </div>
    """, unsafe_allow_html=True)


# ── Sidebar: NICU Jargon Buster & Medical Explainer ────────────────────
with st.sidebar:
    st.header("📖 NICU Jargon Buster")
    st.caption("Common medical terms explained in plain, comforting language:")

    with st.expander("❓ What is 'Corrected Age'?", expanded=True):
        st.write("""
        **Corrected Age** adjusts for the weeks your baby was born before their 40-week due date.
        
        *Example:* If Liam was born **11 weeks early**, and his birthday was **8 weeks ago**, his physical development matches a baby born right around today (Term 0 weeks).
        
        👉 **Always use corrected age** when checking for smiles, rolling over, and solid foods!
        """)

    with st.expander("🍼 What is 'Milk Fortification' (HMF)?"):
        st.write("""
        Preterm babies grew very fast in the NICU and missed out on third-trimester mineral transfers in the womb.
        
        **Human Milk Fortifier (HMF)** adds extra protein, calcium, and phosphorus to mother's breast milk to protect bone density and brain development.
        """)

    with st.expander("⚠️ What are 'Subcostal Retractions'?"):
        st.write("""
        **Retractions** happen when a baby works extra hard to breathe, and the skin sucks in under the ribcage or neck with each breath.
        
        If you see skin pulling in deeply, or hear grunting sounds, **this is an acute red flag** — call your NICU hotline immediately!
        """)

    with st.expander("🦘 Why is 'Kangaroo Mother Care' so powerful?"):
        st.write("""
        Skin-to-skin contact against your bare chest helps preterm infants stabilize their body temperature, heart rate, and oxygen levels.
        It also boosts maternal milk supply and reduces infant stress hormones!
        """)

    st.markdown("---")
    st.subheader(f"🍼 {baby.name.capitalize()}'s Active Care Summary")
    
    # 48h Summary & Live Feeds
    try:
        care_sum = log_service.generate_48h_summary(baby.baby_id)
        st.markdown(f"""
        - **Intake Status:** `{care_sum.intake_target_status.upper()}`
        - **48h Intake:** **{care_sum.total_volume_ml:.0f} mL** across {care_sum.total_feeds} feeds
        - **Daily Average:** ~{care_sum.daily_avg_volume_ml:.0f} mL/day (Avg {care_sum.avg_volume_per_feed_ml:.1f} mL/feed)
        - **Diapers (48h):** 💧 {care_sum.wet_diaper_count} wet | 💩 {care_sum.soiled_diaper_count} dirty
        - **Current Weight:** ~2,400 g
        - **Active Meds:** Vitamin D3 (400 IU once daily), Iron drops
        """)
        
        with st.expander("📋 View Recent Feed Logs", expanded=False):
            recent_feeds = log_service.get_feeds(baby.baby_id)[:8]
            if recent_feeds:
                for f in recent_feeds:
                    feed_time = f.timestamp.strftime("%b %d, %I:%M %p") if hasattr(f.timestamp, 'strftime') else str(f.timestamp)[:16]
                    tol = "✅" if f.tolerated else "⚠️"
                    st.markdown(f"**{tol} {f.volume_ml} mL** ({f.feed_type.replace('_', ' ')})<br><span style='font-size:11px; color:#666;'>{feed_time} — {f.notes or 'No notes'}</span>", unsafe_allow_html=True)
            else:
                st.caption("No feeds logged yet.")
    except Exception as e:
        st.markdown(f"""
        - **Current Weight:** ~2,400 g
        - **Active Meds:** Vitamin D3 (400 IU once daily), Iron drops
        - **Follow-up:** Pediatric Clinic (in 2 weeks)
        """)

    st.markdown("---")
    st.markdown("🔗 **[Open Observability & Tracing Dashboard](http://localhost:8502)**")


# ── Main Tabbed Subsystems (Organized around Mother's Routine) ─────────
tabs = st.tabs([
    "🕒 Daily Care Timeline",
    "💬 Voice & Text Companion",
    "🦘 Kangaroo Care (KMC)",
    "🍼 Feeding & Meds",
    "🧼 Hygiene & Sterilization",
    "📈 Growth Intelligence",
    "🌸 Mother's Wellbeing",
    "🗄️ Storage & Agentic Memory Architecture",
    "🔔 Regular Interval Reminders (Email & SMS)",
])

# ==============================================================================
# TAB 1: 🕒 Today's Personalized Care Timeline ("What should I do next?")
# ==============================================================================
with tabs[0]:
    st.subheader(f"📅 Today's Care Routine & Schedule — {baby.name.capitalize()}")
    
    # 1. "What should I do next?" Smart Assistant Card
    next_action = timeline_svc.get_what_should_i_do_next(baby.baby_id)
    badge_color = "#E65100" if next_action["status"] == "DUE" else "#00695C"
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #FFF8E1 0%, #FFECB3 100%); border-radius: 12px; padding: 18px 22px; border: 1px solid #FFE082; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span style="font-size: 13px; font-weight: 800; color: {badge_color}; text-transform: uppercase; letter-spacing: 0.5px;">
                ⚡ WHAT SHOULD I DO NEXT? ({next_action['status']})
            </span>
            <span style="font-size: 12px; font-weight: 600; color: #795548;">{next_action['task']['time_str']}</span>
        </div>
        <div style="font-size: 18px; font-weight: 700; color: #3E2723; margin-bottom: 6px;">
            {next_action['task']['title']}
        </div>
        <div style="font-size: 14px; color: #4E342E; line-height: 1.5;">
            {next_action['actionable_guidance']}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. Timeline Schedule Table
    timeline_tasks = timeline_svc.get_daily_timeline(baby.baby_id)
    
    # Metrics Bar
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    completed_tasks = sum(1 for t in timeline_tasks if t.status == "COMPLETED")
    due_tasks = sum(1 for t in timeline_tasks if t.status == "DUE")
    kmc_stats = timeline_svc.get_daily_kmc_summary(baby.baby_id)
    care_sum = log_service.generate_48h_summary(baby.baby_id)
    
    col_m1.metric("Tasks Completed", f"{completed_tasks} / {len(timeline_tasks)}")
    col_m2.metric("Tasks Due Now", f"{due_tasks}")
    col_m3.metric("KMC Skin-to-Skin", f"{kmc_stats['completed_hours']} / {kmc_stats['target_hours']} hrs")
    col_m4.metric("24h Intake Volume", f"{care_sum.daily_avg_volume_ml:.0f} mL")
    
    st.markdown("---")
    st.markdown("##### 📋 Unified Daily Care Timeline")
    
    for t in timeline_tasks:
        col_time, col_info, col_status = st.columns([1, 4, 1.2])
        
        status_icons = {
            "COMPLETED": "✅ <span style='color:#2E7D32; font-weight:700;'>Done</span>",
            "DUE": "🔔 <span style='color:#D84315; font-weight:700;'>Due Now</span>",
            "UPCOMING": "⏳ <span style='color:#757575;'>Upcoming</span>",
            "MISSED": "⚠️ <span style='color:#C62828; font-weight:700;'>Missed</span>"
        }
        
        with col_time:
            st.markdown(f"**{t.time_str}**")
            
        with col_info:
            category_badges = {
                "FEEDING": "🍼 Feeding",
                "KMC_SESSION": "🦘 KMC Skin-to-Skin",
                "MEDICATION": "💊 Medication",
                "HYGIENE": "🧼 Hygiene & Sterilization",
                "MATERNAL_CARE": "🌸 Mother's Care",
                "GROWTH": "📏 Growth"
            }
            cat_label = category_badges.get(t.category, t.category)
            highlight_border = "border-left: 4px solid #00897B; padding-left: 8px;" if t.is_next else ""
            st.markdown(f"<div style='{highlight_border}'><b>{t.title}</b> <span style='font-size:11px; background:#ECEFF1; padding:2px 6px; border-radius:4px; margin-left:6px;'>{cat_label}</span><br><span style='font-size:12px; color:#555;'>{t.description}</span></div>", unsafe_allow_html=True)
            
        with col_status:
            st.markdown(status_icons.get(t.status, t.status), unsafe_allow_html=True)
        st.markdown("<hr style='margin:4px 0; border:0; border-top:1px solid #f0f0f0;'>", unsafe_allow_html=True)


# ==============================================================================
# TAB 2: 💬 Voice & Text Companion
# ==============================================================================
with tabs[1]:
    st.subheader(f"💬 Multimodal Assistant for {baby.name.capitalize()}")
    st.caption("Speak or type in Telugu, English, or Hindi. Get grounded answers and nurse voice notes.")

    # ── In-Chatbot Human-in-the-Loop (HITL) Care Team Review Station ───────
    pending_hitl_tickets = [t for t in hitl_service.get_pending_tickets() if t.get("baby_id") == baby.baby_id]
    if pending_hitl_tickets:
        with st.expander(f"👨‍⚕️ Clinical Care Team & HITL Review Station ({len(pending_hitl_tickets)} Pending)", expanded=True):
            st.warning(f"⚠️ **{len(pending_hitl_tickets)} inquiry requires pediatric clinician review.**")
            for idx, ticket in enumerate(pending_hitl_tickets):
                urgency_color = "#D32F2F" if ticket.get("urgency") in ["HIGH", "CRITICAL"] else "#E65100"
                st.markdown(f"""
                <div style="background:#FFF8E1; border:1px solid #FFE082; border-left:5px solid {urgency_color}; border-radius:8px; padding:12px; margin-bottom:12px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <b>Ticket ID:</b> <code>{ticket['ticket_id']}</code>
                        <span style="background:{urgency_color}; color:white; font-size:11px; padding:2px 8px; border-radius:10px; font-weight:bold;">{ticket.get('urgency', 'MEDIUM')} URGENCY</span>
                    </div>
                    <div style="margin-top:6px; font-size:13px;"><b>Mother's Query:</b> <em>"{ticket['raw_query']}"</em></div>
                    <div style="font-size:12px; color:#C62828; margin-top:4px;"><b>Escalation Reasons:</b> {', '.join(ticket.get('reasons', []))}</div>
                    <div style="font-size:12px; color:#37474F; margin-top:4px;"><b>AI Candidate Guidance:</b> {ticket.get('ai_draft', '')[:160]}...</div>
                </div>
                """, unsafe_allow_html=True)

                col_hitl_a, col_hitl_b = st.columns([1.2, 2.8])
                with col_hitl_a:
                    if st.button("✅ Approve AI Guidance", key=f"hitl_appr_{ticket['ticket_id']}_{idx}", use_container_width=True):
                        hitl_service.resolve_ticket(ticket["ticket_id"], "APPROVED", "Approved by pediatric care team")
                        st.session_state.messages.append({
                            "role": "assistant",
                            "text": f"👨‍⚕️ **Verified by Pediatric Care Team (Dr. K. Rao):**\n\nThe guidance for *\"{ticket['raw_query']}\"* has been reviewed and clinically approved for {baby.name.capitalize()}.",
                            "voice_note": "Your pediatric care team has reviewed and approved this guidance.",
                            "is_emergency": False,
                            "timestamp": datetime.datetime.now().strftime("%I:%M %p"),
                        })
                        st.success(f"Ticket {ticket['ticket_id']} approved.")
                        st.rerun()
                with col_hitl_b:
                    override_note = st.text_input("Physician/Nurse Clinical Directive", key=f"hitl_over_{ticket['ticket_id']}_{idx}", placeholder="e.g. Bring Liam to OPD tomorrow; hold feeds if spitting continues.")
                    if st.button("📝 Submit Doctor Directive to Chat", key=f"hitl_sub_{ticket['ticket_id']}_{idx}", use_container_width=True):
                        if override_note:
                            hitl_service.resolve_ticket(ticket["ticket_id"], "MODIFIED", override_note)
                            st.session_state.messages.append({
                                "role": "assistant",
                                "text": f"👨‍⚕️ **Clinical Care Team Directive (Dr. K. Rao, Neonatologist):**\n\n{override_note}\n\n*Direct clinician instruction logged for {baby.name.capitalize()}.*",
                                "voice_note": f"Pediatric care team update: {override_note}",
                                "is_emergency": False,
                                "timestamp": datetime.datetime.now().strftime("%I:%M %p"),
                            })
                            st.success("Doctor directive delivered to chat.")
                            st.rerun()
                        else:
                            st.error("Please enter a clinical note before submitting.")
    
    # Embedded JavaScript Speech-to-Text Microphone
    st.markdown("##### 🎙️ Hands-Free Voice Input (Telugu / English / Hindi)")
    speech_component = f"""
    <div style="background-color: #F5F5F5; border-radius: 10px; padding: 12px; margin-bottom: 12px; border: 1px dashed #BDBDBD; display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <button id="micBtn" onclick="toggleRecognition()" style="background-color: #00897B; color: white; border: none; border-radius: 50%; width: 44px; height: 44px; font-size: 20px; cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                🎙️
            </button>
            <span id="speechStatus" style="font-size: 13px; color: #424242; font-weight: 500;">Click mic and speak your question or care update...</span>
        </div>
        <div style="font-size: 11px; color: #757575;">Language: <b>{selected_language}</b></div>
    </div>

    <script>
    let recognition = null;
    let recognizing = false;

    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {{
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = '{lang_code}';

        recognition.onstart = function() {{
            recognizing = true;
            document.getElementById('micBtn').style.backgroundColor = '#D32F2F';
            document.getElementById('speechStatus').innerText = 'Listening... Speak now into your microphone!';
        }};

        recognition.onresult = function(event) {{
            const transcript = event.results[0][0].transcript;
            document.getElementById('speechStatus').innerText = 'Captured: "' + transcript + '" (Copied! Paste into the chat box below)';
            navigator.clipboard.writeText(transcript);
        }};

        recognition.onerror = function(event) {{
            recognizing = false;
            document.getElementById('micBtn').style.backgroundColor = '#00897B';
            document.getElementById('speechStatus').innerText = 'Mic notice: ' + event.error + '. Please type below.';
        }};

        recognition.onend = function() {{
            recognizing = false;
            document.getElementById('micBtn').style.backgroundColor = '#00897B';
        }};
    }} else {{
        document.getElementById('speechStatus').innerText = 'Speech recognition not supported in browser. Please type below.';
    }}

    function toggleRecognition() {{
        if (!recognition) return;
        if (recognizing) {{
            recognition.stop();
        }} else {{
            recognition.start();
        }}
    }}
    </script>
    """
    components.html(speech_component, height=75)

    # Quick Suggestions
    st.markdown("**Quick Topics (1-Click Suggestions):**")
    pill_cols = st.columns(4)
    selected_preset = None
    with pill_cols[0]:
        if st.button("🍼 Log 50 mL Feed", key="preset_feed", use_container_width=True):
            selected_preset = "Baby drank 50 mL fortified breast milk at 10 AM, tolerated well"
    with pill_cols[1]:
        if st.button("🧷 Log Wet Diaper", key="preset_diaper", use_container_width=True):
            selected_preset = "Changed diaper: wet with yellow seedy stool"
    with pill_cols[2]:
        if st.button("🦘 How to do KMC?", key="preset_kmc", use_container_width=True):
            selected_preset = "How to safely practice kangaroo mother care skin to skin at home?"
    with pill_cols[3]:
        if st.button("🚨 Test Red Flag", key="preset_flag", use_container_width=True):
            selected_preset = "Baby's chest is retracting under ribs and lips look dusky blue"

    if lang_code == "te-IN":
        tel_cols = st.columns(2)
        with tel_cols[0]:
            if st.button("🌐 Telugu: బాబుకి పాలు సరిపోతున్నాయా?", key="tel_milk", use_container_width=True):
                selected_preset = "బాబుకి పాలు సరిగ్గా సరిపోతున్నాయా? రోజుకి ఎన్ని సార్లు ఇవ్వాలి?"
        with tel_cols[1]:
            if st.button("🚨 Telugu: ఆకుపచ్చ వాంతులు (Emergency)", key="tel_vomit", use_container_width=True):
                selected_preset = "బాబుకి ఆకుపచ్చ వాంతులు అవుతున్నాయి మరియు ఆయాసంగా ఉంది"

    # Chat Messages Stream
    for m_idx, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            with st.chat_message("user", avatar="👩"):
                st.markdown(f"**Mother:** {msg['text']}")
        else:
            avatar_icon = "🚨" if msg.get("is_emergency") else "🩺"
            with st.chat_message("assistant", avatar=avatar_icon):
                if msg.get("is_emergency"):
                    st.error("⚠️ **CRITICAL NEONATAL EMERGENCY DETECTED**")

                # Inline HITL Notice Banner
                if msg.get("requires_hitl") or msg.get("hitl_ticket_id"):
                    t_id = msg.get("hitl_ticket_id", "Pending")
                    t_urg = msg.get("hitl_urgency", "MEDIUM")
                    t_reasons = msg.get("hitl_reasons", [])
                    st.markdown(f"""
                    <div style="background:#FFFDE7; border-left:4px solid #FBC02D; padding:8px 12px; margin:6px 0; border-radius:4px; font-size:12px; color:#5D4037;">
                        👨‍⚕️ <b>Pediatric Care Team Review Active</b> (Ticket <code>{t_id}</code> | {t_urg} Urgency)<br>
                        <em>{', '.join(t_reasons) if t_reasons else 'Under clinician review'}</em>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown(msg["text"])
                if msg.get("model_used"):
                    st.caption(f"🤖 Powered by `{msg['model_used']}` (Timeouts Disabled)")

                # Voice Note Player via components.html
                voice_text = msg.get("voice_note", "")
                if voice_text:
                    voice_html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                    <style>
                      body {{ margin: 0; padding: 0; font-family: sans-serif; background: transparent; }}
                      .voice-container {{ display: flex; align-items: center; gap: 10px; padding: 2px 0; }}
                      .voice-btn {{
                        background: linear-gradient(135deg, #00897B 0%, #004D40 100%);
                        color: #ffffff; border: none; border-radius: 20px; padding: 6px 16px;
                        font-size: 13px; font-weight: 600; cursor: pointer; display: inline-flex;
                        align-items: center; gap: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.18);
                      }}
                      .voice-btn:hover {{ background: linear-gradient(135deg, #00796B 0%, #00332C 100%); }}
                      .voice-text {{ font-size: 12px; font-style: italic; color: #424242; }}
                      .playing {{ background: #D32F2F !important; }}
                    </style>
                    </head>
                    <body>
                    <div class="voice-container">
                      <button id="playBtn" class="voice-btn" onclick="togglePlay()">
                        🔊 <span id="btnText">Listen to Nurse Voice Note</span>
                      </button>
                      <span class="voice-text">"{voice_text}"</span>
                    </div>
                    <script>
                    function togglePlay() {{
                        const synth = window.speechSynthesis || (window.top && window.top.speechSynthesis);
                        if (!synth) return;
                        const btn = document.getElementById('playBtn');
                        const btnText = document.getElementById('btnText');
                        if (synth.speaking) {{
                            synth.cancel();
                            btn.classList.remove('playing');
                            btnText.innerText = 'Listen to Nurse Voice Note';
                            return;
                        }}
                        const text = {json.dumps(voice_text)};
                        const utterance = new SpeechSynthesisUtterance(text);
                        utterance.lang = '{lang_code}';
                        utterance.rate = 0.95;
                        utterance.onstart = function() {{ btn.classList.add('playing'); btnText.innerText = 'Speaking... (Click to Stop)'; }};
                        utterance.onend = function() {{ btn.classList.remove('playing'); btnText.innerText = 'Listen to Nurse Voice Note'; }};
                        utterance.onerror = function() {{ btn.classList.remove('playing'); btnText.innerText = 'Listen to Nurse Voice Note'; }};
                        synth.speak(utterance);
                    }}
                    </script>
                    </body>
                    </html>
                    """
                    components.html(voice_html, height=42)

                # Optional Mother-initiated HITL escalation button
                if not msg.get("requires_hitl") and not msg.get("is_emergency") and m_idx > 0:
                    col_esc1, col_esc2 = st.columns([1, 4])
                    with col_esc1:
                        if st.button("🙋 Request Care Team Review", key=f"btn_hitl_req_{m_idx}"):
                            t = hitl_service.create_ticket(
                                baby_id=baby.baby_id,
                                raw_query=msg["text"][:120],
                                reasons=["Mother requested care team validation in chatbot"],
                                urgency="MEDIUM",
                                ai_draft=msg["text"],
                                intent=msg.get("intent", "CLINICAL_QA")
                            )
                            msg["requires_hitl"] = True
                            msg["hitl_ticket_id"] = t["ticket_id"]
                            msg["hitl_reasons"] = ["Mother requested pediatrician review"]
                            st.success("Review ticket created for pediatric care team.")
                            st.rerun()

    user_prompt = st.chat_input("Type your question or care update (e.g., 'Liam drank 50 ml' or in Telugu)...")
    active_query = selected_preset or user_prompt

    if active_query:
        st.session_state.messages.append({
            "role": "user",
            "text": active_query,
            "timestamp": datetime.datetime.now().strftime("%I:%M %p"),
        })
        with st.spinner("NICU Nurse Specialist reasoning (MedGemma / Llama without timeouts)..."):
            req = TextQueryRequest(
                baby_id=baby.baby_id,
                text=active_query,
                language=lang_code,
                model=active_selected_model,
            )
            agent_res = process_text_query(req)
            st.session_state.messages.append({
                "role": "assistant",
                "text": agent_res.text_card,
                "voice_note": agent_res.voice_summary,
                "is_emergency": agent_res.is_emergency,
                "intent": agent_res.intent,
                "model_used": getattr(agent_res, "model_used", None) or active_selected_model,
                "requires_hitl": agent_res.requires_hitl,
                "hitl_ticket_id": agent_res.hitl_ticket_id,
                "hitl_reasons": agent_res.hitl_reasons,
                "hitl_urgency": agent_res.hitl_urgency,
                "timestamp": datetime.datetime.now().strftime("%I:%M %p"),
            })
        st.rerun()


# ==============================================================================
# TAB 3: 🦘 Kangaroo Mother Care (KMC) Tracker
# ==============================================================================
with tabs[2]:
    st.subheader(f"🦘 Kangaroo Mother Care (KMC) — Skin-to-Skin Tracker")
    st.caption("WHO recommends 2–4 hours of skin-to-skin contact daily for preterm infants to regulate body temperature, breathing, and brain growth.")
    
    col_kmc_prog, col_kmc_guide = st.columns([3, 2])
    
    with col_kmc_prog:
        kmc_data = timeline_svc.get_daily_kmc_summary(baby.baby_id)
        st.markdown(f"#### Today's Progress: **{kmc_data['completed_hours']} / {kmc_data['target_hours']} Hours**")
        st.progress(kmc_data['percent_completed'] / 100.0)
        
        if kmc_data['remaining_hours'] > 0:
            st.info(f"⏳ **{kmc_data['remaining_hours']} hours remaining** to reach today's clinical KMC target.")
        else:
            st.success("🎉 **Clinical KMC Goal Achieved for Today!** Great job keeping baby skin-to-skin.")
            
        st.markdown("---")
        st.markdown("##### ⏱️ Log a KMC Session")
        with st.form("kmc_form"):
            col_k1, col_k2 = st.columns(2)
            with col_k1:
                kmc_duration = st.number_input("Session Duration (Minutes)", min_value=15, max_value=360, value=60, step=15)
                caregiver = st.selectbox("Caregiver", ["mother", "father", "other"])
            with col_k2:
                tolerated = st.checkbox("Baby Tolerated Well (Calm & warm)", value=True)
                kmc_notes = st.text_input("Session Notes", placeholder="e.g. Baby slept comfortably on chest")
                
            submitted = st.form_submit_button("✅ Save KMC Session", use_container_width=True)
            if submitted:
                new_kmc = KMCSession(
                    baby_id=baby.baby_id,
                    duration_minutes=kmc_duration,
                    caregiver=caregiver,
                    tolerated=tolerated,
                    notes=kmc_notes,
                )
                timeline_svc.log_kmc_session(new_kmc)
                st.success(f"Logged {kmc_duration} minutes of KMC! Progress updated.")
                st.rerun()
                
    with col_kmc_guide:
        st.markdown("""
        <div style="background-color: #E8F5E9; border-radius: 12px; padding: 16px; border: 1px solid #C8E6C9;">
            <div style="font-size: 15px; font-weight: 700; color: #1B5E20; margin-bottom: 8px;">
                🏥 WHO Safe KMC Positioning Checklist
            </div>
            <ul style="font-size: 13px; color: #2E7D32; line-height: 1.6; margin: 0; padding-left: 18px;">
                <li><b>Chest-to-Chest:</b> Baby wears only diaper and cap, placed directly against your bare chest.</li>
                <li><b>Upright 'Frog' Position:</b> Legs flexed and hips abducted like a little frog; arms folded.</li>
                <li><b>Airway Open:</b> Turn head gently to one side with neck slightly extended (sniffing position). <b>Never allow chin to drop onto chest!</b></li>
                <li><b>Secure Wrap:</b> Secure baby firmly with a soft binder or shirt so mother can breathe and rest.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)


# ==============================================================================
# TAB 4: 🍼 Feeding & Medications
# ==============================================================================
with tabs[3]:
    st.subheader("🍼 Feeding & Medicine Management")
    col_feed_plan, col_med_sched = st.columns(2)
    
    with col_feed_plan:
        st.markdown(f"""
        <div style="background:#F3E5F5; border-radius:12px; padding:16px; border:1px solid #E1BEE7; margin-bottom:16px;">
            <span style="font-size:12px; font-weight:800; color:#6A1B9A;">PRESCRIBED FEEDING PLAN</span><br>
            <span style="font-size:16px; font-weight:700; color:#4A148C;">{volume_target['per_feed_min_ml']:.0f}–{volume_target['per_feed_max_ml']:.0f} mL every 3 hours</span><br>
            <span style="font-size:13px; color:#4A148C;">Target: {volume_target['min_daily_ml']:.0f}–{volume_target['max_daily_ml']:.0f} mL/day (Fortified EBM with Similac HMF)</span>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("quick_feed_form"):
            st.markdown("##### ➕ Log Feeding")
            f_vol = st.number_input("Volume (mL)", min_value=10.0, max_value=150.0, value=50.0, step=5.0)
            f_type = st.selectbox("Feed Type", ["fortified_breast_milk", "breast_milk", "formula"])
            f_notes = st.text_input("Notes", placeholder="e.g. Drank full bottle, burped well")
            if st.form_submit_button("Record Feed"):
                from app.models.care_log import FeedingEntry
                log_service.log_feed(FeedingEntry(
                    baby_id=baby.baby_id,
                    volume_ml=f_vol,
                    feed_type=f_type,
                    notes=f_notes
                ))
                st.success(f"Logged {f_vol} mL feed!")
                st.rerun()

    with col_med_sched:
        st.markdown("""
        <div style="background:#E1F5FE; border-radius:12px; padding:16px; border:1px solid #B3E5FC; margin-bottom:16px;">
            <span style="font-size:12px; font-weight:800; color:#0277BD;">PRESCRIBED MEDICINES & VITAMINS</span><br>
            • <b>Vitamin D3:</b> 400 IU (1 mL) once daily at 10:00 AM<br>
            • <b>Elemental Iron:</b> 0.5 mL once daily at 06:00 PM<br>
            <span style="font-size:11px; color:#01579B;">⚠️ Clinician rule: Never double up if missed; administer when remembered same day.</span>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("med_confirm_form"):
            st.markdown("##### ✅ Confirm Medication Dose")
            med_choice = st.selectbox("Medicine Given", ["Vitamin D3 Drops (400 IU)", "Iron Drops (0.5 mL)"])
            med_dose = 1.0 if "Vitamin" in med_choice else 0.5
            if st.form_submit_button("Confirm Administered"):
                from app.models.care_log import MedicationEntry
                log_service.log_medication(MedicationEntry(
                    baby_id=baby.baby_id,
                    medication_name=med_choice,
                    dose_ml=med_dose,
                    notes="Confirmed dose given by mother"
                ))
                st.success(f"Confirmed: {med_choice} recorded!")
                st.rerun()


# ==============================================================================
# TAB 5: 🧼 Hygiene & Sterilization Assistant
# ==============================================================================
with tabs[4]:
    st.subheader("🧼 Hygiene & Feeding Equipment Sterilization")
    st.caption("Preterm babies have immature immune systems. Follow the AAP/CDC 5-step safe sterilization protocol:")
    
    proto = timeline_svc.get_sterilization_protocol()
    for s in proto["steps"]:
        st.markdown(f"""
        <div style="background:#FAFAFA; border-left: 4px solid #00897B; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px;">
            <span style="font-weight:700; color:#004D40;">Step {s['step']}: {s['title']}</span><br>
            <span style="font-size:13px; color:#424242;">{s['instruction']}</span>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    st.markdown("##### 🥛 Safe Expressed Milk Storage Rules")
    col_s1, col_s2, col_s3 = st.columns(3)
    col_s1.info(f"**Room Temp (<25°C):**\n\n{proto['milk_storage_guidelines']['room_temperature']}")
    col_s2.info(f"**Refrigerator (4°C):**\n\n{proto['milk_storage_guidelines']['refrigerator']}")
    col_s3.info(f"**Deep Freezer (-18°C):**\n\n{proto['milk_storage_guidelines']['freezer']}")


# ==============================================================================
# TAB 6: 📈 Growth Intelligence & Developmental Tracking
# ==============================================================================
with tabs[5]:
    st.subheader("📈 Preterm Growth & Developmental Tracking")
    
    col_g_log, col_g_trend = st.columns([2, 3])
    with col_g_log:
        with st.form("growth_form"):
            st.markdown("##### ⚖️ Record Growth Measurement")
            g_weight = st.number_input("Weight (grams)", min_value=800, max_value=8000, value=int(est_weight), step=10)
            g_length = st.number_input("Length (cm, optional)", min_value=25.0, max_value=75.0, value=45.0, step=0.5)
            g_hc = st.number_input("Head Circumference (cm, optional)", min_value=20.0, max_value=50.0, value=32.0, step=0.5)
            
            if st.form_submit_button("Save Measurement"):
                new_growth = GrowthRecord(
                    baby_id=baby.baby_id,
                    weight_grams=g_weight,
                    length_cm=g_length,
                    head_circumference_cm=g_hc,
                    notes="Home scale measurement"
                )
                timeline_svc.log_growth(new_growth)
                st.success("Measurement saved and growth velocity calculated!")
                st.rerun()
                
    with col_g_trend:
        growth_history = timeline_svc.get_growth_records(baby.baby_id)
        st.markdown("##### 📊 Measurement History & Velocity")
        if growth_history:
            g_data = []
            for g in growth_history:
                g_data.append({
                    "Date": str(g.date_recorded),
                    "Weight (g)": g.weight_grams,
                    "Length (cm)": g.length_cm or "—",
                    "Head Circ (cm)": g.head_circumference_cm or "—",
                    "Gain (g/day)": f"{g.daily_gain_g_per_day:.1f}" if g.daily_gain_g_per_day else "Baseline",
                    "Status": g.velocity_status or "Baseline"
                })
            st.dataframe(g_data, use_container_width=True)
            st.caption("Standard target weight gain for preterm infants post-NICU: 15–20 g/kg/day.")


# ==============================================================================
# TAB 7: 🌸 Mother's Recovery & Emotional Wellbeing
# ==============================================================================
with tabs[6]:
    st.subheader("🌸 Mother's Recovery & Emotional Wellbeing")
    st.caption("Caring for a preterm infant is demanding. Your health and emotional recovery directly protect your baby.")
    
    col_m_log, col_m_card = st.columns([3, 2])
    with col_m_log:
        with st.form("mother_form"):
            m_glasses = st.slider("Water Consumed Today (Glasses)", min_value=0, max_value=16, value=6)
            m_rest = st.slider("Rest / Sleep Achieved in Past 24h (Hours)", min_value=0.0, max_value=12.0, value=5.5, step=0.5)
            m_mood = st.select_slider(
                "How are you feeling right now?",
                options=["exhausted", "overwhelmed", "tired_but_coping", "feeling_good"],
                value="tired_but_coping"
            )
            m_notes = st.text_input("Personal notes or thoughts", placeholder="e.g. Baby had peaceful afternoon, feeling calmer")
            
            if st.form_submit_button("Record Wellbeing Check-In"):
                timeline_svc.log_maternal_checkin(MaternalWellbeing(
                    baby_id=baby.baby_id,
                    hydration_glasses=m_glasses,
                    rest_hours=m_rest,
                    mood=m_mood,
                    notes=m_notes
                ))
                st.success("Recovery check-in saved! Be proud of the care you are giving.")
                st.rerun()
                
    with col_m_card:
        st.markdown("""
        <div style="background-color: #FCE4EC; border-radius: 12px; padding: 18px; border: 1px solid #F8BBD0;">
            <div style="font-size: 15px; font-weight: 700; color: #880E4F; margin-bottom: 8px;">
                💖 Gentle Reminders for You
            </div>
            <ul style="font-size: 13px; color: #AD1457; line-height: 1.6; margin: 0; padding-left: 18px;">
                <li><b>Hydration boosts milk supply:</b> Drink a glass of water every time you nurse or pump.</li>
                <li><b>Sleep when baby sleeps:</b> Sleep deprivation is real. Accept help from family for diapers and laundry.</li>
                <li><b>You are doing enough:</b> Preterm development takes time. Every ounce of milk and every hour of skin-to-skin matters.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)


# ==============================================================================
# TAB 8: 🗄️ Storage & Agentic Memory Architecture (Structured, Semi, Unstructured + Short, Long, Episodic)
# ==============================================================================
with tabs[7]:
    st.subheader(f"🗄️ Multi-Modal Storage & Agentic Memory Architecture — {baby.name.capitalize()}")
    st.caption("Live, transparent inspection of how Post-NICU clinical data is stored across Structured, Semi-Structured, and Unstructured databases, and how Short-Term, Long-Term, and Episodic agentic memories are managed.")

    storage_arch = db_architecture_service.get_storage_architecture(baby.baby_id)
    memory_arch = db_architecture_service.get_agentic_memory_summary(baby.baby_id)

    # ── Section 1: Multi-Modal Storage Architecture ──────────────────
    st.markdown("### 1️⃣ Multi-Modal Database Storage Architecture")
    col_str1, col_str2, col_str3 = st.columns(3)

    with col_str1:
        st.markdown("""
        <div style="background-color: #E3F2FD; border-radius: 10px; padding: 14px; border: 1px solid #BBDEFB; min-height: 300px;">
            <div style="font-size: 15px; font-weight: 700; color: #0D47A1; margin-bottom: 6px;">🔷 Structured Storage</div>
            <div style="font-size: 12px; color: #1565C0; margin-bottom: 10px;">Deterministic schemas, graphs & tabular tables</div>
        """, unsafe_allow_html=True)
        for s in storage_arch.structured:
            st.markdown(f"""
            <div style="background: white; border-radius: 6px; padding: 8px 10px; margin-bottom: 8px; border: 1px solid #E0E0E0;">
                <div style="font-size: 12px; font-weight: 700; color: #212121;">{s.name}</div>
                <div style="font-size: 11px; color: #616161;"><b>Engine:</b> {s.engine}</div>
                <div style="font-size: 11px; color: #616161;"><b>Items / Nodes:</b> {s.item_count} | <b>Status:</b> <span style="color:#2E7D32; font-weight:600;">{s.status}</span></div>
                <div style="font-size: 10px; color: #757575; margin-top: 4px;">{s.description}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_str2:
        st.markdown("""
        <div style="background-color: #FFF3E0; border-radius: 10px; padding: 14px; border: 1px solid #FFE0B2; min-height: 300px;">
            <div style="font-size: 15px; font-weight: 700; color: #E65100; margin-bottom: 6px;">🔶 Semi-Structured Storage</div>
            <div style="font-size: 12px; color: #EF6C00; margin-bottom: 10px;">JSON logs, Markdown Wikis & Obsidian Vaults</div>
        """, unsafe_allow_html=True)
        for s in storage_arch.semi_structured:
            st.markdown(f"""
            <div style="background: white; border-radius: 6px; padding: 8px 10px; margin-bottom: 8px; border: 1px solid #E0E0E0;">
                <div style="font-size: 12px; font-weight: 700; color: #212121;">{s.name}</div>
                <div style="font-size: 11px; color: #616161;"><b>Engine:</b> {s.engine}</div>
                <div style="font-size: 11px; color: #616161;"><b>Files / Records:</b> {s.item_count} | <b>Status:</b> <span style="color:#2E7D32; font-weight:600;">{s.status}</span></div>
                <div style="font-size: 10px; color: #757575; margin-top: 4px;">{s.description}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_str3:
        st.markdown("""
        <div style="background-color: #F3E5F5; border-radius: 10px; padding: 14px; border: 1px solid #E1BEE7; min-height: 300px;">
            <div style="font-size: 15px; font-weight: 700; color: #4A148C; margin-bottom: 6px;">🟣 Unstructured Storage</div>
            <div style="font-size: 12px; color: #6A1B9A; margin-bottom: 10px;">Clinical guidelines, audio speech & transcripts</div>
        """, unsafe_allow_html=True)
        for s in storage_arch.unstructured:
            st.markdown(f"""
            <div style="background: white; border-radius: 6px; padding: 8px 10px; margin-bottom: 8px; border: 1px solid #E0E0E0;">
                <div style="font-size: 12px; font-weight: 700; color: #212121;">{s.name}</div>
                <div style="font-size: 11px; color: #616161;"><b>Engine:</b> {s.engine}</div>
                <div style="font-size: 11px; color: #616161;"><b>Corpus Size:</b> {s.item_count} files/entries | <b>Status:</b> <span style="color:#2E7D32; font-weight:600;">{s.status}</span></div>
                <div style="font-size: 10px; color: #757575; margin-top: 4px;">{s.description}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    # ── Section 2: Three-Tier Agentic Memory Management ───────────────
    st.markdown("### 2️⃣ Three-Tier Agentic Memory Management")
    col_mem1, col_mem2, col_mem3 = st.columns(3)

    with col_mem1:
        stm = memory_arch.short_term
        st.markdown(f"""
        <div style="background-color: #E8F5E9; border-radius: 10px; padding: 14px; border: 1px solid #C8E6C9; min-height: 240px;">
            <div style="font-size: 14px; font-weight: 700; color: #1B5E20;">⚡ Short-Term Working Memory</div>
            <div style="font-size: 12px; color: #2E7D32; margin-bottom: 8px;"><b>{stm.name}</b></div>
            <div style="font-size: 11px; color: #33691E; line-height: 1.4;">{stm.description}</div>
            <hr style="margin: 8px 0; border: none; border-top: 1px solid #A5D6A7;">
            <div style="font-size: 11px; color: #1B5E20;">
                • <b>Storage:</b> {stm.storage_engine}<br>
                • <b>Active Turn Buffers:</b> {stm.key_metrics.get('active_turn_keys', 0)}<br>
                • <b>Verified Cached Q&As:</b> {stm.key_metrics.get('cached_clinical_answers', 0)}<br>
                • <b>Cache Hit Rate:</b> {stm.key_metrics.get('hit_rate_pct', 0.0)}%
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_mem2:
        ltm = memory_arch.long_term
        st.markdown(f"""
        <div style="background-color: #EDE7F6; border-radius: 10px; padding: 14px; border: 1px solid #D1C4E9; min-height: 240px;">
            <div style="font-size: 14px; font-weight: 700; color: #311B92;">🧠 Long-Term Semantic Memory</div>
            <div style="font-size: 12px; color: #4527A0; margin-bottom: 8px;"><b>{ltm.name}</b></div>
            <div style="font-size: 11px; color: #512DA8; line-height: 1.4;">{ltm.description}</div>
            <hr style="margin: 8px 0; border: none; border-top: 1px solid #B39DDB;">
            <div style="font-size: 11px; color: #311B92;">
                • <b>Storage:</b> {ltm.storage_engine}<br>
                • <b>Active Wiki Sections:</b> {ltm.key_metrics.get('wiki_sections_active', 0)}<br>
                • <b>Compressed Context:</b> ~{ltm.key_metrics.get('compressed_context_tokens', 350)} tokens<br>
                • <b>Token Savings:</b> {ltm.key_metrics.get('token_savings_vs_transcripts', '75-80%')} vs raw chat
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_mem3:
        epm = memory_arch.episodic
        st.markdown(f"""
        <div style="background-color: #FBE9E7; border-radius: 10px; padding: 14px; border: 1px solid #FFCCBC; min-height: 240px;">
            <div style="font-size: 14px; font-weight: 700; color: #BF360C;">📖 Episodic Longitudinal Memory</div>
            <div style="font-size: 12px; color: #D84315; margin-bottom: 8px;"><b>{epm.name}</b></div>
            <div style="font-size: 11px; color: #E64A19; line-height: 1.4;">{epm.description}</div>
            <hr style="margin: 8px 0; border: none; border-top: 1px solid #FFAB91;">
            <div style="font-size: 11px; color: #BF360C;">
                • <b>Storage:</b> {epm.storage_engine}<br>
                • <b>Total Recorded Episodes:</b> {epm.key_metrics.get('total_episodes_recorded', 0)}<br>
                • <b>Unresolved Alerts:</b> {epm.key_metrics.get('unresolved_critical_alerts', 0)}<br>
                • <b>Obsidian Sync:</b> Active (YAML frontmatter + #episodic_memory)
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Section 3: Interactive Episodic Memory Logger & Timeline ──────
    st.markdown("### 3️⃣ Longitudinal Clinical Episodic Memory Feed & Logger")
    
    col_ep_feed, col_ep_add = st.columns([3, 2])

    with col_ep_add:
        with st.expander("➕ Record New Clinical Episode / Milestone", expanded=True):
            with st.form("new_episode_form"):
                ep_type = st.selectbox(
                    "Episode Category",
                    [
                        EpisodeType.ACUTE_EVENT.value,
                        EpisodeType.MILESTONE.value,
                        EpisodeType.REGIMEN_CHANGE.value,
                        EpisodeType.FEEDING_TOLERANCE.value,
                        EpisodeType.KMC_SESSION.value,
                        EpisodeType.CLINICAL_CHECKUP.value,
                    ],
                    index=0,
                )
                ep_sev = st.selectbox(
                    "Clinical Severity",
                    [
                        EpisodeSeverity.INFO.value,
                        EpisodeSeverity.MILD.value,
                        EpisodeSeverity.MODERATE.value,
                        EpisodeSeverity.CRITICAL.value,
                    ],
                    index=0,
                )
                ep_title = st.text_input("Episode Title", placeholder="e.g. Mild Reflux after 45 mL Feed")
                ep_desc = st.text_area("Clinical Description & Context", placeholder="Infant burped upright for 20m; 5mL non-bilious regurgitation.")
                ep_tags = st.text_input("Tags (comma separated)", value="feeding, reflux, post_discharge")
                
                submitted = st.form_submit_button("Record Clinical Episode")
                if submitted and ep_title and ep_desc:
                    tags_list = [t.strip() for t in ep_tags.split(",") if t.strip()]
                    user_email = st.session_state.auth_user.email if "auth_user" in st.session_state and st.session_state.auth_user else "mother_liam@example.com"
                    episodic_memory.record_episode(
                        baby_id=baby.baby_id,
                        episode_type=EpisodeType(ep_type),
                        title=ep_title,
                        description=ep_desc,
                        severity=EpisodeSeverity(ep_sev),
                        clinical_data={"recorded_by": user_email},
                        resolved=True,
                        tags=tags_list,
                    )
                    st.success("Clinical episode logged to Episodic Memory and mirrored to Obsidian Vault!")
                    st.rerun()

    with col_ep_feed:
        st.markdown(f"**Chronological Episode History ({baby.name.capitalize()})**")
        episodes_list = episodic_memory.get_episodes(baby.baby_id, limit=10)
        
        if episodes_list:
            for ep in episodes_list:
                sev = ep.get("severity", "INFO")
                sev_color = "#D32F2F" if sev == "CRITICAL" else ("#F57C00" if sev == "MODERATE" else ("#FBC02D" if sev == "MILD" else "#1976D2"))
                bg_color = "#FFEBEE" if sev == "CRITICAL" else ("#FFF3E0" if sev == "MODERATE" else ("#FFFDE7" if sev == "MILD" else "#E3F2FD"))
                
                tags_html = " ".join([f"<span style='background:#E0E0E0; border-radius:4px; padding:2px 6px; font-size:10px;'>#{t}</span>" for t in ep.get("tags", [])])
                
                st.markdown(f"""
                <div style="background-color: {bg_color}; border-left: 5px solid {sev_color}; border-radius: 6px; padding: 10px 14px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 13px; font-weight: 700; color: #212121;">{ep.get('title')}</span>
                        <span style="background-color: {sev_color}; color: white; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: 700;">{sev}</span>
                    </div>
                    <div style="font-size: 11px; color: #616161; margin: 3px 0 6px 0;"><b>{ep.get('episode_type')}</b> | <i>{ep.get('date')}</i></div>
                    <div style="font-size: 12px; color: #37474F; line-height: 1.4;">{ep.get('description')}</div>
                    <div style="margin-top: 6px;">{tags_html}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No clinical episodes recorded yet.")

    st.markdown("---")

    # ── Section 4: NeonatalBERT Transformer Engine ───────────────────
    st.markdown("### 4️⃣ 🔬 NeonatalBERT Clinical Transformer Intelligence")
    st.caption("Sub-20ms domain-specific NLU transformer for neonatal phenotype extraction, emergency fast-path triage, and discharge summary deconstruction.")

    col_bert_info, col_bert_demo = st.columns([1, 1])

    with col_bert_info:
        st.markdown("""
        <div style="background-color: #E8EAF6; border-radius: 10px; padding: 14px; border: 1px solid #C5CAE9;">
            <div style="font-size: 14px; font-weight: 700; color: #1A237E; margin-bottom: 6px;">🧠 NeonatalBERT Architecture Highlights</div>
            <ul style="font-size: 12px; color: #283593; line-height: 1.6; margin: 0; padding-left: 18px;">
                <li><b>Model Specs:</b> 110M parameter clinical transformer calibrated on NICU electronic records & AAP/WHO guidelines.</li>
                <li><b>Latency:</b> &lt;15ms CPU inference time — acts as an ultra-fast edge guardrail before generative LLM reasoning.</li>
                <li><b>Phenotype Normalizer:</b> Maps maternal colloquial descriptions (e.g. <i>"chest sinking in"</i>) to standardized SNOMED/Neo4j ontology nodes (<code>symptom_retractions</code>).</li>
                <li><b>Discharge Deconstructor:</b> Automatically extracts gestational age, birth weight, fortifier regimen, and BPD/ROP staging from hospital summaries.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with col_bert_demo:
        st.markdown("**Interactive NeonatalBERT Query Analyzer**")
        sample_query = st.text_input(
            "Test Maternal Query or Clinical Note:",
            value="Liam threw up dark greenish liquid and his chest is pulling in under ribs",
            key="bert_test_query"
        )
        if sample_query:
            analysis = neonatal_bert_service.analyze_query(sample_query)
            
            badge_color = "#D32F2F" if analysis.urgency_tier == "CRITICAL" else ("#F57C00" if analysis.urgency_tier == "MODERATE" else "#2E7D32")
            
            st.markdown(f"""
            <div style="background: white; border-radius: 8px; padding: 10px 14px; border: 1px solid #E0E0E0; margin-top: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 12px; font-weight: 700; color: #333;">Intent: <code>{analysis.intent}</code></span>
                    <span style="background-color: {badge_color}; color: white; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700;">{analysis.urgency_tier} ({analysis.urgency_score:.2f})</span>
                </div>
                <div style="font-size: 11px; color: #666;"><b>Inference Latency:</b> {analysis.latency_ms} ms | <b>Tokens:</b> {len(analysis.tokens)}</div>
                <div style="font-size: 11px; color: #424242; margin-top: 6px;"><b>Subword Tokens:</b> <code>{' '.join(analysis.tokens[:12])}</code></div>
                <div style="font-size: 11px; color: #424242; margin-top: 4px;"><b>Detected Clinical Phenotypes:</b> {', '.join(analysis.phenotype_codes) if analysis.phenotype_codes else 'None detected'}</div>
            </div>
            """, unsafe_allow_html=True)


# ==============================================================================
# TAB 9: 🔔 Regular Interval Reminders (Email & Mobile SMS Dispatcher)
# ==============================================================================
with tabs[8]:
    st.subheader(f"🔔 Proactive Care Reminders & Alerts — {baby.name.capitalize()}")
    st.caption("Sends automated, clinically grounded reminders at regular intervals to the registered email address and mobile phone.")

    user_prefs = notification_service.get_preferences(user_id="usr_mother_01")
    sched_status = reminder_scheduler.get_status()

    # ── Top Status Cards ──────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Scheduler Engine", "ONLINE" if sched_status["is_running"] else "STANDBY", delta="Evaluates 60s")
    with c2:
        st.metric("Feed Interval Target", f"{user_prefs.feeding_interval_hours:.1f} Hours", delta="AAP Standard: 2.5-3.5h")
    with c3:
        st.metric("Registered Email", user_prefs.email, delta="Active" if user_prefs.email_enabled else "Paused")
    with c4:
        st.metric("Registered Mobile", user_prefs.phone_number, delta="Active" if user_prefs.sms_enabled else "Paused")

    st.markdown("---")

    col_config, col_action = st.columns([1, 1])

    # ── Left Column: Contact & Interval Preferences ────────────────────────
    with col_config:
        st.markdown("### ⚙️ Contact Details & Schedule Settings")
        with st.form("reminder_prefs_form"):
            new_email = st.text_input("Registered Email Address (HTML Care Cards):", value=user_prefs.email)
            new_phone = st.text_input("Registered Mobile Number (SMS Alerts):", value=user_prefs.phone_number)
            
            f_col, k_col = st.columns(2)
            with f_col:
                new_feed_int = st.slider("Feeding Interval (Hours):", min_value=1.5, max_value=5.0, value=float(user_prefs.feeding_interval_hours), step=0.5)
            with k_col:
                new_kmc_int = st.slider("KMC Interval (Hours):", min_value=2.0, max_value=8.0, value=float(user_prefs.kmc_interval_hours), step=1.0)

            st.markdown("**Notification Channels:**")
            t_col1, t_col2, t_col3 = st.columns(3)
            with t_col1:
                en_email = st.checkbox("📧 Email Alerts", value=user_prefs.email_enabled)
            with t_col2:
                en_sms = st.checkbox("📱 Mobile SMS", value=user_prefs.sms_enabled)
            with t_col3:
                en_med = st.checkbox("💊 Med Routine", value=user_prefs.medication_reminder_enabled)

            submitted = st.form_submit_button("💾 Save Preferences & Update Intervals", use_container_width=True)
            if submitted:
                updated = NotificationPreferences(
                    user_id=user_prefs.user_id,
                    baby_id=baby.baby_id,
                    email=new_email,
                    phone_number=new_phone,
                    feeding_interval_hours=new_feed_int,
                    kmc_interval_hours=new_kmc_int,
                    email_enabled=en_email,
                    sms_enabled=en_sms,
                    medication_reminder_enabled=en_med,
                )
                notification_service.update_preferences(updated)
                st.success("✅ Notification preferences and contact details successfully saved!")
                st.rerun()

    # ── Right Column: Instant Trigger & Live Delivery Test ────────────────
    with col_action:
        st.markdown("### 🚀 Send Immediate Reminder (Test Delivery)")
        st.caption("Trigger an instant care notification to inspect the formatted email card and SMS alert.")
        
        test_cat = st.selectbox(
            "Select Care Reminder Category:",
            [
                ("FEEDING", "🍼 Scheduled Feed (50 mL Preterm Target)"),
                ("KMC_SESSION", "🦘 Kangaroo Mother Care (Skin-to-Skin Session)"),
                ("MEDICATION", "💊 Prescribed Vitamin D3 Drops (400 IU)"),
                ("SYSTEM_TEST", "🔔 General System Connectivity Test"),
            ],
            format_func=lambda x: x[1]
        )[0]

        channel_choice = st.radio(
            "Target Dispatch Channel:",
            [("both", "📧 Email + 📱 Mobile SMS"), ("email", "📧 Email Only"), ("sms", "📱 Mobile SMS Only")],
            format_func=lambda x: x[1],
            horizontal=True
        )[0]

        if st.button("📨 Dispatch Immediate Reminder Now", type="primary", use_container_width=True):
            with st.spinner("Dispatching clinical reminder..."):
                cat_enum = ReminderCategory(test_cat)
                chan_enum = NotificationChannel(channel_choice)
                rec = notification_service.send_notification(
                    category=cat_enum,
                    baby_id=baby.baby_id,
                    user_id=user_prefs.user_id,
                    channel=chan_enum,
                    details={"target_volume_ml": 50.0}
                )
                st.session_state["last_test_rec"] = rec
                st.toast(f"Reminder dispatched! ID: {rec.id}", icon="🔔")

        # Preview Section
        if "last_test_rec" in st.session_state:
            last_rec = st.session_state["last_test_rec"]
            st.markdown(f"**Delivery Receipt:** `{last_rec.id}` | **Status:** `{last_rec.status.value}` | **Timestamp:** `{last_rec.timestamp}`")
            
            with st.expander("📱 Mobile SMS Preview (As delivered to phone)", expanded=True):
                st.markdown(f"""
                <div style="background-color: #263238; color: #ECEFF1; border-radius: 12px; padding: 14px 18px; font-family: monospace; font-size: 13px; line-height: 1.5; border-left: 5px solid #00E676;">
                    <b>To:</b> {last_rec.recipient_phone}<br>
                    <b>Sender:</b> RAINBOW-NICU<br><br>
                    {last_rec.message_sms}
                </div>
                """, unsafe_allow_html=True)

            with st.expander("📧 Rendered Email HTML Card (As delivered to inbox)", expanded=False):
                st.markdown(f"**Subject:** `{last_rec.title}` | **To:** `{last_rec.recipient_email}`")
                st.components.v1.html(last_rec.message_html, height=360, scrolling=True)

    st.markdown("---")

    # ── Notification Delivery Audit Log ────────────────────────────────────
    st.markdown("### 📋 Notification History & Delivery Audit Log")
    history_records = notification_service.get_history(baby_id=baby.baby_id, limit=15)
    
    if history_records:
        table_rows = []
        for r in history_records:
            table_rows.append({
                "Timestamp": r.timestamp,
                "Category": r.category.value,
                "Channel": r.channel.value.upper(),
                "Recipient Email": r.recipient_email or "-",
                "Recipient Mobile": r.recipient_phone or "-",
                "Title": r.title[:45] + "...",
                "Status": r.status.value,
            })
        st.dataframe(table_rows, use_container_width=True)
    else:
        st.info("No notifications dispatched yet. Click 'Dispatch Immediate Reminder Now' to send the first alert.")

