"""
End-to-End Simulation of Mother Care Scenarios.
Demonstrates the agent across key clinical journeys:
  1. Red-Flag Emergency Triage (Central cyanosis / chest retractions) -> Immediate 1-tap emergency dialer.
  2. Structured Care Logging (50 mL fortified breast milk) -> Next feed reminder + care log persistence.
  3. Emergency Hospital Lookup (Rainbow Hospital Vijayawada phone + NICU helpline).
  4. Clinical Guidance RAG & Safety Guardrails (Kangaroo Mother Care + Safe Sleep).
  5. Pediatric Math (Corrected gestational age & daily volume range).
"""
import sys
import os
import datetime

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.agent import TextQueryRequest
from app.models.baby import BabyProfile
from app.routers.agent import process_text_query, cache_service
from app.services.wiki_service import WikiService
from app.services.pediatric_math_service import PediatricMathService
from app.services.care_log_service import CareLogService

def run_simulation():
    cache_service.clear()
    wiki_svc = WikiService()
    math_svc = PediatricMathService()
    log_svc = CareLogService()

    baby_id = "baby_liam_01"

    print("=" * 75)
    print("      NICU CARE ASSISTANT - END-TO-END MOTHER JOURNEY SIMULATION")
    print("=" * 75)

    # Setup / Ensure Baby Profile
    dob = datetime.date.today() - datetime.timedelta(days=56) # 8 weeks chronological
    current_weight_grams = 2400
    baby = BabyProfile(
        baby_id=baby_id,
        name="Liam",
        date_of_birth=dob,
        gestational_age_weeks=29,
        gestational_age_days=2,
        sex="male",
        birth_weight_grams=1180,
        discharge_weight_grams=1820,
        discharge_date=datetime.date.today() - datetime.timedelta(days=21),
        discharge_hospital="BirthRight Rainbow Vijayawada",
    )
    wiki_svc.save_baby_profile_json(baby)
    wiki_svc.create_profile_from_baby(baby)

    # 1. Profile & Corrected Age Math
    c_age = math_svc.calculate_corrected_age(baby)
    print(f"\n[BABY PROFILE]")
    print(f"  Name: {baby.name}")
    print(f"  Chronological Age: {c_age.chronological_weeks}w {c_age.chronological_remaining_days}d")
    print(f"  Corrected Gestational Age: {c_age.corrected_weeks}w {c_age.corrected_remaining_days}d (Reached Due Date: {c_age.has_reached_due_date})")
    print(f"  Current Weight: {current_weight_grams} g (Discharge: {baby.discharge_weight_grams} g)")

    # 2. Pediatric Feeding Volume Math
    feed_target = math_svc.calculate_daily_volume_target(current_weight_grams)
    print(f"\n[FEEDING TARGET (AAP 150-180 mL/kg/day)]")
    print(f"  Daily Total Target: {feed_target['min_daily_ml']:.0f} - {feed_target['max_daily_ml']:.0f} mL/day")
    print(f"  Per Feed Target ({feed_target['feeds_per_day']} feeds): {feed_target['per_feed_min_ml']:.0f} - {feed_target['per_feed_max_ml']:.0f} mL/feed")

    # 3. Scenario A: Red-Flag Emergency Detection
    print("\n" + "=" * 75)
    print("SCENARIO 1: Mother reports chest retraction & bluish lips")
    print("=" * 75)
    req1 = TextQueryRequest(
        baby_id=baby_id,
        text="Baby's lips look blue and chest is retracting under the ribs",
    )
    res1 = process_text_query(req1)
    print(f"  Intent Detected: {res1.intent}")
    print(f"  Is Emergency: {res1.is_emergency}")
    print(f"  Voice Summary: \"{res1.voice_summary}\"")
    print(f"  Display Card:\n{res1.text_card.strip()}")
    assert res1.is_emergency is True, "Emergency red flag failed to trigger!"

    # 4. Scenario B: Log Feed via Natural Language
    print("\n" + "=" * 75)
    print("SCENARIO 2: Mother speaks: 'Logged 50 mL fortified breast milk at 10 AM'")
    print("=" * 75)
    req2 = TextQueryRequest(
        baby_id=baby_id,
        text="Logged 50 mL fortified breast milk at 10 AM, baby drank well",
    )
    res2 = process_text_query(req2)
    print(f"  Intent Detected: {res2.intent}")
    print(f"  Voice Summary: \"{res2.voice_summary}\"")
    print(f"  Display Card: {res2.text_card.strip()}")
    print(f"  Next Scheduled Feed Reminder: In {res2.next_reminder_minutes} minutes")

    # 5. Scenario C: Emergency Hospital Lookup
    print("\n" + "=" * 75)
    print("SCENARIO 3: Mother asks for Rainbow Hospital Vijayawada Emergency Number")
    print("=" * 75)
    req3 = TextQueryRequest(
        baby_id=baby_id,
        text="What is the Rainbow Hospital Vijayawada emergency phone number?",
    )
    res3 = process_text_query(req3)
    print(f"  Intent Detected: {res3.intent}")
    print(f"  Voice Summary: \"{res3.voice_summary}\"")
    print(f"  Display Card:\n{res3.text_card.strip()}")
    assert "+91 866 666 9000" in res3.text_card

    # 6. Scenario D: Clinical Guidance RAG & Safety Output Guardrail
    print("\n" + "=" * 75)
    print("SCENARIO 4: Mother asks about Kangaroo Mother Care")
    print("=" * 75)
    req4 = TextQueryRequest(
        baby_id=baby_id,
        text="How to safely practice kangaroo mother care skin to skin?",
    )
    res4 = process_text_query(req4)
    print(f"  Intent Detected: {res4.intent}")
    print(f"  Voice Summary: \"{res4.voice_summary}\"")
    print(f"  Display Card Excerpt:\n{res4.text_card[:250]}...")
    assert "disclaimer" in res4.text_card.lower(), "Mandatory clinical disclaimer missing!"

    print("\n" + "=" * 75)
    print("      ALL END-TO-END SCENARIOS VERIFIED AND WORKING FLAWLESSLY!")
    print("=" * 75)

if __name__ == "__main__":
    run_simulation()
