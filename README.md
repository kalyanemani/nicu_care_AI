# NICU Baby Care Companion — Post-Discharge Clinical Platform

An end-to-end clinical AI platform designed for mothers of preterm infants discharged from the Neonatal Intensive Care Unit (NICU). Fully compliant with the permanent **Google Cloud Free Tier**, incorporating **LangGraph cyclic multi-agent reasoning, Jev System One probabilistic decisions, a Living LLM Wiki for conversational memory, 4-layer clinical safety guardrails, OpenTelemetry tracing, RAGAS telemetry, and dual Streamlit dashboards**.

---

## 📁 Repository Structure

```
C:\Users\krishkal\Desktop\nicu\
├── docs/                                 # Architectural specifications & blueprints
│   ├── nicu_baby_care_gcp_architecture.md
│   ├── guardrails_mcp_and_multiagent_architecture.md
│   ├── complete_frontend_backend_architecture.md
│   ├── backend_architecture_blueprint.md
│   ├── agentic_observability_and_memory_architecture.md
│   ├── verification_and_deployment_report.md
│   └── local_development_streamlit_plan.md
│
├── nicu_care_backend/                    # Python FastAPI & LangGraph Multi-Agent Backend
│   ├── app/
│   │   ├── agent/                        # Multi-Agent StateGraph, Jev engine, 4-layer guardrails
│   │   ├── knowledge/guidelines/         # Indexed AAP, WHO, and Fenton guidelines
│   │   ├── memory/                       # Short-Term (Redis/IRIS) & Long-Term (LLM Wiki) memory
│   │   ├── models/                       # Pydantic schemas (baby, care logs, hospital, agent)
│   │   ├── routers/                      # REST endpoints (agent, baby, care logs, hospitals, telemetry)
│   │   ├── services/                     # Pediatric math, RAG, wiki, care logs, hospital search
│   │   ├── telemetry/                    # OpenTelemetry tracer, RAGAS evaluator, metrics store
│   │   ├── harness/                      # 10-case clinical benchmark test harness
│   │   ├── config.py                     # Environment settings & feature flags
│   │   └── main.py                       # FastAPI application entry point
│   ├── tests/                            # 62 unit & integration tests (100% passing)
│   ├── data/                             # Living wiki markdown files, JSON logs, traces
│   ├── streamlit_app.py                  # Dashboard 1: Mother Application Interface (Port 8501)
│   ├── streamlit_monitoring.py           # Dashboard 2: Observability & RAGAS Telemetry (Port 8502)
│   ├── simulate_e2e_mother_scenarios.py  # End-to-end simulated mother care journey
│   ├── deploy_cloud_run.ps1              # Scale-to-zero Google Cloud Run deployment script
│   ├── requirements.txt                  # Python dependencies
│   └── Dockerfile                        # Production container definition
│
├── nicu_care_app/                        # Flutter Mobile & Web Client
│   ├── lib/
│   │   ├── models/                       # Agent response & hospital contact models
│   │   ├── services/                     # Voice assistant HTTP & audio service
│   │   └── main.dart                     # Material 3 UI with age banner & emergency dialer
│   ├── firebase.json                     # Firebase Hosting configuration for Flutter Web
│   └── pubspec.yaml                      # Flutter dependencies
│
└── README.md                             # Master repository guide (this file)
```

---

## 🚀 Quickstart Guide

### 1. Run the FastAPI Backend (Port 8000)
```powershell
cd nicu_care_backend
python -m uvicorn app.main:app --reload --port 8000
```
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/](http://localhost:8000/)

### 2. Run Dashboard 1: Mother Care Companion (Port 8501)
```powershell
cd nicu_care_backend
streamlit run streamlit_app.py --server.port 8501
```
- **App URL:** [http://localhost:8501](http://localhost:8501)
- Displays Baby Liam's profile, corrected age, natural language care logging, and 1-tap emergency dialer.

### 3. Run Dashboard 2: Observability & RAGAS Telemetry (Port 8502)
```powershell
cd nicu_care_backend
streamlit run streamlit_monitoring.py --server.port 8502
```
- **Monitoring URL:** [http://localhost:8502](http://localhost:8502)
- Features: 1-click 10-case benchmark harness, node-by-node latency waterfall, token savings tracker, RAGAS quality radar, Redis short-term inspector, and OpenTelemetry trace explorer.

### 4. Run the Full Test Suite
```powershell
cd nicu_care_backend
python -m pytest -v
```
*(All **62 unit & integration tests pass** across 9 test modules).*

### 5. Run the End-to-End Clinical Simulation
```powershell
cd nicu_care_backend
python simulate_e2e_mother_scenarios.py
```

### 6. Run the Flutter Frontend (Web / Mobile)
```powershell
cd nicu_care_app
flutter pub get
flutter run -d chrome
```

---

## 🏥 Clinical & Safety Guarantees

1. **100% Recall on Neonatal Red Flags:** Any mention of central cyanosis, respiratory retractions, rectal fever $\ge 38^\circ\text{C}$ in $<3$ months, or bilious green vomit immediately triggers Layer 1 emergency triage, bypassing generative LLM loops.
2. **Deterministic Pediatric Math:** Feeding volumes ($150\text{--}180\text{ mL/kg/day}$), caloric fortification, and corrected gestational age are computed in pure Python using published Fenton 2013 curves.
3. **Conversational Memory via Living LLM Wiki:** Rather than compounding raw chat history, the system compresses persistent medical state into 4 dense Markdown files (`profile.md`, `active_regimen.md`, `clinical_alerts.md`, `rolling_log_summary.md`), achieving **~350 tokens context size** (a **72% token reduction**).
4. **Permanent GCP Free-Tier Compliance:** Cloud Run minimum instances set to `0` (scales to zero), container memory strictly `512Mi`, and context bounded to prevent quota exhaustion.
