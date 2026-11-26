# NICU Care Python Backend

FastAPI server providing:
1. **Location-Based Hospital Emergency Contact Retrieval** (e.g., *BirthRight by Rainbow Hospitals, Vijayawada*).
2. **Neonatal Agentic Voice & Guidance Engine** with deterministic red-flag emergency screening.

---

## Quickstart (Run Locally on Windows)

1. Navigate to this directory in your terminal:
   ```powershell
   cd C:\Users\krishkal\.gemini\antigravity\scratch\nicu_care_backend
   ```

2. Create and activate a Python virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Install requirements:
   ```powershell
   pip install -r requirements.txt
   ```

4. Run the API:
   ```powershell
   python -m uvicorn app.main:app --reload --port 8000
   ```

5. Open your browser:
   - Interactive Swagger Docs: `http://localhost:8000/docs`
   - Test Hospital Search: `http://localhost:8000/api/v1/hospitals/search?query=birthright%20rainbow%20hospital%20vijayawada`

---

## Deploy to Google Cloud Run (Free Tier)
```powershell
gcloud run deploy nicu-care-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

