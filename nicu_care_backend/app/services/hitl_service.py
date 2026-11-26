"""
Human-in-the-Loop (HITL) Clinical Triage Service:
Manages safety escalations requiring human pediatric oversight:
- Borderline clinical vitals (temp 37.5-37.9 C, mild tachypnea)
- Caregiver inquiries regarding altering prescription medications
- Multi-feed refusal or weight loss flags
- Low retrieval confidence queries
- Severe maternal postpartum distress
Persists tickets to data/telemetry/hitl_queue.json for clinician review.
"""

import json
import time
import uuid
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

HITL_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "telemetry" / "hitl_queue.json"


class HITLTriageService:
    """Manages the lifecycle of Human-in-the-Loop triage tickets."""

    def __init__(self, queue_file: Path = HITL_FILE):
        self.queue_file = queue_file
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.queue_file.exists():
            self._save_tickets([])

    def _load_tickets(self) -> List[Dict[str, Any]]:
        try:
            if self.queue_file.exists():
                return json.loads(self.queue_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def _save_tickets(self, tickets: List[Dict[str, Any]]):
        self.queue_file.write_text(json.dumps(tickets, indent=2), encoding="utf-8")

    def evaluate_query_for_hitl(
        self,
        query: str,
        baby_id: str,
        retrieval_score: float = 0.8,
        intent: str = "CLINICAL_QA",
        ai_draft: str = ""
    ) -> Dict[str, Any]:
        """
        Evaluates whether a query requires Human-in-the-Loop clinician review.
        Returns evaluation result and optionally creates a ticket.
        """
        q_lower = query.lower()
        reasons: List[str] = []
        urgency = "LOW"

        # 1. Borderline Temperature (37.5 - 37.9 C or 35.5 - 36.4 C)
        temp_matches = re.findall(r'(\d{2}(?:\.\d)?)\s*(?:c|degrees|deg)?', q_lower)
        for t_str in temp_matches:
            try:
                t_val = float(t_str)
                if 37.4 <= t_val < 38.0:
                    reasons.append(f"Borderline elevated temperature ({t_val}°C) - requires pediatric temperature monitoring")
                    urgency = "MEDIUM"
                elif 35.0 <= t_val <= 36.4:
                    reasons.append(f"Subnormal temperature ({t_val}°C) - mild hypothermia risk")
                    urgency = "MEDIUM"
            except ValueError:
                pass

        # 2. Medication modification inquiries
        med_terms = ["stop", "increase", "double", "change", "discontinue", "higher dose"]
        if any(w in q_lower for w in ["caffeine", "iron", "vitamin", "drops", "citrate", "medication", "medicine"]):
            if any(m in q_lower for m in med_terms):
                reasons.append("Parent inquiring about modifying or stopping prescription medication")
                urgency = "HIGH"

        # 3. Feeding refusal (> 2 feeds)
        if any(w in q_lower for w in ["refused", "won't drink", "refusing", "not drinking", "skipping"]) and any(w in q_lower for w in ["feed", "bottle", "milk"]):
            reasons.append("Reported multiple feeding refusal or poor intake")
            urgency = "MEDIUM"

        # 4. Severe maternal distress or mental health concern
        if any(w in q_lower for w in ["can't cope", "giving up", "crying all day", "severely depressed", "panic attack", "cannot do this"]):
            reasons.append("Caregiver postpartum distress flagged for social work or nurse wellbeing review")
            urgency = "MEDIUM"

        # 5. Low retrieval confidence threshold (applies only to unstructured clinical RAG queries)
        exempt_intents = ["LOG_FEED", "LOG_DIAPER", "LOG_MEDICATION", "LOG_KMC", "EMERGENCY", "PATIENT_RECORD_INQUIRY", "GROWTH_ANALYSIS", "TIMELINE_INSPECT", "FEEDING_INTELLIGENCE"]
        if retrieval_score < 0.40 and intent not in exempt_intents:
            reasons.append(f"Low AI retrieval confidence ({retrieval_score:.2f}) on clinical inquiry")
            urgency = "LOW" if urgency == "LOW" else urgency

        requires_hitl = len(reasons) > 0
        ticket_id = None

        if requires_hitl:
            ticket = self.create_ticket(
                baby_id=baby_id,
                raw_query=query,
                reasons=reasons,
                urgency=urgency,
                ai_draft=ai_draft,
                intent=intent
            )
            ticket_id = ticket["ticket_id"]

        return {
            "requires_hitl": requires_hitl,
            "reasons": reasons,
            "urgency": urgency,
            "ticket_id": ticket_id
        }

    def create_ticket(
        self,
        baby_id: str,
        raw_query: str,
        reasons: List[str],
        urgency: str,
        ai_draft: str,
        intent: str
    ) -> Dict[str, Any]:
        """Creates a new HITL triage ticket in the queue."""
        tickets = self._load_tickets()
        ticket_id = f"hitl_{uuid.uuid4().hex[:8]}"

        ticket = {
            "ticket_id": ticket_id,
            "baby_id": baby_id,
            "timestamp": time.time(),
            "date_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            "raw_query": raw_query,
            "intent": intent,
            "urgency": urgency,
            "reasons": reasons,
            "ai_draft": ai_draft,
            "status": "PENDING",  # PENDING, APPROVED, MODIFIED, ESCALATED
            "clinician_notes": None,
            "resolved_at": None,
        }

        # Avoid exact duplicate pending tickets for same baby and query
        existing = [t for t in tickets if t["baby_id"] == baby_id and t["raw_query"] == raw_query and t["status"] == "PENDING"]
        if not existing:
            tickets.insert(0, ticket)
            self._save_tickets(tickets)
            return ticket
        return existing[0]

    def get_pending_tickets(self) -> List[Dict[str, Any]]:
        """Returns all unreviewed tickets."""
        tickets = self._load_tickets()
        return [t for t in tickets if t.get("status") == "PENDING"]

    def get_all_tickets(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns all tickets up to limit."""
        return self._load_tickets()[:limit]

    def resolve_ticket(
        self,
        ticket_id: str,
        status: str,
        clinician_notes: Optional[str] = None
    ) -> bool:
        """Clinician approves, modifies, or escalates a ticket."""
        tickets = self._load_tickets()
        updated = False

        for t in tickets:
            if t["ticket_id"] == ticket_id:
                t["status"] = status
                t["clinician_notes"] = clinician_notes
                t["resolved_at"] = time.time()
                updated = True
                break

        if updated:
            self._save_tickets(tickets)
        return updated


# Global Singleton HITL Service
hitl_service = HITLTriageService()
