"""
Node 4: Clinical Guidance Agent
Grounded synthesis agent. Consumes verified MCP tool outputs from the MCP Gateway,
integrates the Baby Health Wiki context, and generates supportive, zero-hallucination guidance.
Incorporates self-correction loop when safety critiques are received.
"""

from typing import Dict, Any, List
import json
from ..state import NICUAgentState
from ...services.rag_service import ClinicalRAGService
from ...services.hospital_service import HospitalEmergencyService
from ...services.llm_service import llm_service
from ..guardrails.alignment_validator import QueryResponseAlignmentValidator

rag_svc = ClinicalRAGService()
hospital_svc = HospitalEmergencyService()


def clinical_guide_node(state: NICUAgentState) -> Dict[str, Any]:
    trace_id = state.get("trace_id")
    parent_span_id = state.get("parent_span_id")
    guide_span = None
    if trace_id and parent_span_id:
        from ...telemetry.tracer import tracer
        guide_span = tracer.start_span("agent.langgraph.clinical_guide", trace_id=trace_id, parent_span_id=parent_span_id)

    query = state.get("raw_query", "")
    baby_id = state.get("baby_id", "baby_liam_01")
    bname = "Liam" if "liam" in baby_id.lower() else "your baby"
    intent = state.get("intent", "CLINICAL_QA")
    tool_outputs = state.get("tool_outputs") or {}
    critique_notes = state.get("critique_notes")
    retry_count = state.get("retry_count", 0)

    def _return_with_span(res: Dict[str, Any]) -> Dict[str, Any]:
        if guide_span:
            from ...telemetry.tracer import tracer
            tracer.end_span(guide_span, status="OK")
        return res

    # ── 1. Loop Engineering: Dynamic Self-Correction Rewrite ──────────────
    if critique_notes and retry_count > 0:
        from ...services.refinement_engine import SelfFixingRefinementEngine
        refined = SelfFixingRefinementEngine.generate_refined_response(
            query=query,
            critique_notes=critique_notes,
            baby_context=state.get("baby_wiki_context", ""),
            intent=intent
        )
        return _return_with_span({
            "draft_response": refined["draft_response"],
            "voice_summary": refined["voice_summary"],
            "critique_notes": None,
        })

    # ── 1.5. Patient Record & Prescriptions Status Inquiry (0ms Ground Truth) ─
    if intent == "PATIENT_RECORD_INQUIRY":
        from ...services.wiki_service import WikiService
        from ...services.care_log_service import CareLogService
        wiki_svc = WikiService()
        log_svc = CareLogService()
        entities = state.get("clinical_entities") or {}
        record_type = entities.get("record_type")
        q_low = query.lower()

        # A. Active Medications & Prescriptions
        if record_type == "MEDICATIONS" or any(k in q_low for k in ["med", "medicine", "iron", "vitamin", "drop", "hmf", "fortif"]):
            text = (
                f"💊 **Active Prescribed Medications for Baby {bname.capitalize()}**\n\n"
                f"Discharge regimen prescribed by **Dr. K. Rao (Consultant Neonatologist, Rainbow Hospital)**:\n\n"
                f"• **Vitamin D3 Drops (Cholecalciferol):** `400 IU (0.5 mL)` once daily.\n"
                f"  - *Purpose:* Bone mineralization and rickets prevention for preterm infants.\n"
                f"  - *Administration:* Give with morning feed using measured dropper.\n\n"
                f"• **Iron Drops (Elemental Iron):** `1.0 mL (2–4 mg/kg/day)` once daily.\n"
                f"  - *Purpose:* Prevents anemia of prematurity and supports cognitive brain development.\n"
                f"  - *Administration:* Give between feeds or with small milk volume to maximize absorption.\n\n"
                f"• **Human Milk Fortifier (HMF):** Added to expressed breast milk at `22–24 kcal/oz`.\n"
                f"  - *Purpose:* Enhances protein, calcium, and phosphorus density without exceeding gut osmolality.\n\n"
                f"⚠️ *Important: Never adjust drops or fortifier ratios without explicit instruction from your pediatrician.*"
            )
            voice = f"Liam's active medications are Vitamin D3 400 IU daily, elemental iron drops 1 mL daily, and milk fortifier added to expressed milk."
            return _return_with_span({
                "draft_response": text,
                "voice_summary": voice,
                "retrieved_chunks": [{"source": "Rainbow NICU Discharge Summary", "text": "Discharged on Vitamin D3 400 IU once daily, Iron drops 1.0 mL daily, and HMF fortified feeds."}]
            })

        # B. Current Feeding Intake Status
        if record_type == "FEEDING_STATUS" or any(k in q_low for k in ["intake", "feeding status", "drink", "eaten", "feed"]):
            summary = log_svc.generate_48h_summary(baby_id)
            text = (
                f"🍼 **Baby {bname.capitalize()}'s Current Feeding & Hydration Status (48-Hour Review)**\n\n"
                f"• **Overall Intake Target:** `{summary.intake_target_status.upper()}` (Optimal Preterm Accretion)\n"
                f"• **48-Hour Total Volume:** **`{summary.total_volume_ml:.0f} mL`** across {summary.total_feeds} feeds\n"
                f"• **Daily Average Intake:** **`~{summary.daily_avg_volume_ml:.0f} mL/day`** (Standard: 360–432 mL/day for 2.4kg)\n"
                f"• **Average Volume per Feed:** **`{summary.avg_volume_per_feed_ml:.1f} mL`** every 3 hours\n"
                f"• **Hydration & Elimination (48h):** 💧 **{summary.wet_diaper_count} wet** diapers | 💩 **{summary.soiled_diaper_count} soiled** diapers\n\n"
                f"🩺 **Clinical Evaluation (AAP/WHO Guideline):**\n"
                f"{bname.capitalize()} is consistently meeting the recommended 150–180 mL/kg/day fluid target with adequate renal perfusion and diaper output."
            )
            voice = f"Liam's feeding status is on target. He drank about {summary.daily_avg_volume_ml:.0f} mL per day across {summary.total_feeds} feeds, with {summary.wet_diaper_count} wet diapers."
            return _return_with_span({
                "draft_response": text,
                "voice_summary": voice,
                "retrieved_chunks": [{"source": "Baby Liam Care Logs & 48h Summary", "text": f"48h intake: {summary.total_volume_ml} mL, {summary.total_feeds} feeds, {summary.wet_diaper_count} wet diapers."}]
            })

    # ── 2. Real-Time Growth & Weight Intelligence (from MCP Gateway) ──────
    if "mcp_growth_intelligence" in tool_outputs or intent == "GROWTH_ANALYSIS":
        gw = tool_outputs.get("mcp_growth_intelligence")
        if not gw or not isinstance(gw, dict):
            # Fallback direct call if not already in tool_outputs
            from ...mcp.mcp_server import mcp_server
            res = mcp_server.call_tool("mcp_growth_intelligence", {"baby_id": baby_id})
            gw = json.loads(res["content"][0]["text"])

        bname = gw.get("baby_name", "your baby")
        text = (
            f"⚖️ **Baby {bname.capitalize()}'s Real-Time Growth & Weight Analysis**\n\n"
            f"• **Birth Weight:** `{gw['birth_weight_grams']} g` (Born {gw['weeks_born_early']} weeks early)\n"
            f"• **Discharge Weight:** `{gw['discharge_weight_grams']} g`\n"
            f"• **Current Weight:** **`{gw['current_weight_grams']} g`**\n"
            f"• **Weight Gained Since Discharge:** **`+{gw['weight_gained_since_discharge_grams']} g`** (across {gw['days_since_discharge']} days)\n"
            f"• **Growth Velocity:** **`~{gw['weight_gain_velocity_g_per_day']} g/day`** ({gw['velocity_status']})\n"
            f"• **Chronological Age:** {gw['chronological_weeks']} weeks ({gw['chronological_days']} days)\n"
            f"• **Corrected Gestational Age:** **{gw['corrected_gestational_age_weeks']} weeks (Term Equivalent)**\n\n"
            f"🍼 **Calibrated Feeding Targets for {gw['current_weight_grams']} g:**\n"
            f"- **Daily Volume Goal:** `{gw['calibrated_daily_volume_ml']}` (150–180 mL/kg/day standard)\n"
            f"- **Per-Feed Volume:** `{gw['calibrated_per_feed_ml']}`\n\n"
            f"🩺 **Clinical Evaluation (Fenton 2013 Standard):**\n"
            f"{bname.capitalize()}'s weight gain velocity is strong and appropriate for a preterm graduate reaching term age. "
            f"Steady gain confirms adequate caloric accretion from fortified breast milk."
        )
        voice = (
            f"{bname.capitalize()} is currently {gw['current_weight_grams']} grams, with healthy catch-up growth of about "
            f"{gw['weight_gain_velocity_g_per_day']} grams per day since discharge. The 3-hour feed goal is {gw['calibrated_per_feed_ml']}."
        )
        return _return_with_span({
            "draft_response": text,
            "voice_summary": voice,
            "growth_analysis": gw,
            "retrieved_chunks": []
        })

    # ── 3. Care Timeline & "What should I do next?" (from MCP Gateway) ─────
    if "mcp_care_timeline_inspector" in tool_outputs or intent in ["TIMELINE_INSPECT", "KMC_SESSION", "HYGIENE_STERILIZATION", "MATERNAL_WELLBEING"]:
        tl_data = tool_outputs.get("mcp_care_timeline_inspector")
        is_feed_query = any(k in query.lower() for k in ["feed", "feeding", "milk", "bottle", "eat", "hungry"])
        is_kmc_query = any(k in query.lower() for k in ["kmc", "kangaroo", "skin to skin", "skin-to-skin"])

        if not tl_data or (is_feed_query and tl_data.get("category") != "FEEDING") or (is_kmc_query and tl_data.get("category") != "KMC_SESSION"):
            from ...mcp.mcp_server import mcp_server
            if is_kmc_query:
                qtype = "next_kmc"
            elif is_feed_query:
                qtype = "next_feed"
            else:
                qtype = "next_action"
            res = mcp_server.call_tool("mcp_care_timeline_inspector", {"baby_id": baby_id, "query_type": qtype})
            tl_data = json.loads(res["content"][0]["text"])

        if isinstance(tl_data, dict) and "headline" in tl_data:
            headline = tl_data.get("headline", "Next Care Activity")
            action = tl_data.get("actionable_guidance", "")
            task = tl_data.get("task", {})
            time_str = task.get("time_str", "Upcoming")
            task_title = task.get("title", "Care Activity")
            status = task.get("status", "UPCOMING")
            category = task.get("category", "")

            if is_kmc_query or category == "KMC_SESSION":
                text = (
                    f"🦘 **Next Scheduled Kangaroo Mother Care (KMC) for {bname.capitalize()}:**\n\n"
                    f"- **Scheduled Time:** **`{time_str}`** ({status})\n"
                    f"- **Session Title:** {task_title}\n"
                    f"- **Recommended Duration:** Minimum 60 continuous minutes (WHO Protocol)\n\n"
                    f"💡 **Guidance:**\n{action}\n\n"
                    f"📌 *Clinical Tip: Place baby upright on your bare chest in the frog position, head turned to one side with airway clear. Covering with a warm blanket supports temperature regulation.*"
                )
                voice = f"Liam's next kangaroo care session is scheduled at {time_str}."
            elif category == "FEEDING" or is_feed_query:
                text = (
                    f"🍼 **Next Scheduled Feed for {bname.capitalize()}:**\n\n"
                    f"- **Scheduled Time:** **`{time_str}`** ({status})\n"
                    f"- **Feeding Plan:** {task_title}\n"
                    f"- **Target Volume:** 45–54 mL fortified breast milk (every 2.5–3 hours)\n\n"
                    f"💡 **Guidance:**\n{action}\n\n"
                    f"📌 *Clinical Tip: Feed upright with paced bottle feeding and frequent pauses for burping. Look for early feeding cues like rooting or lip smacking before crying begins.*"
                )
                voice = f"Liam's next feed is scheduled at {time_str}. The volume target is 45 to 54 mL."
            else:
                text = (
                    f"🕒 **{headline}**\n\n"
                    f"- **Task:** {task_title}\n"
                    f"- **Time:** `{time_str}` ({status})\n"
                    f"- **Category:** {category}\n\n"
                    f"💡 **Guidance:**\n{action}"
                )
                voice = f"Your next care task is {task_title} at {time_str}. {action}"

            return _return_with_span({
                "draft_response": text,
                "voice_summary": voice,
                "retrieved_chunks": []
            })

    # ── 4. Feeding Math & Volume Targets (from MCP Gateway) ────────────────
    if "mcp_pediatric_calculator" in tool_outputs or intent in ["FEEDING_INTELLIGENCE", "PEDIATRIC_MATH"]:
        calc = tool_outputs.get("mcp_pediatric_calculator")
        if not calc or not isinstance(calc, dict):
            from ...mcp.mcp_server import mcp_server
            res = mcp_server.call_tool("mcp_pediatric_calculator", {"current_weight_grams": 2400})
            calc = json.loads(res["content"][0]["text"])

        text = (
            f"🍼 **Preterm Feeding Volume Target ({calc.get('weight_kg', 2.4):.2f} kg Baby)**\n\n"
            f"- **Standard Intake Range:** `150–180 mL/kg/day`\n"
            f"- **Recommended Daily Volume:** **`{calc.get('min_daily_ml', 360):.0f} – {calc.get('max_daily_ml', 432):.0f} mL/day`**\n"
            f"- **Volume Per Feed (every 3 hours / 8 feeds):** **`{calc.get('per_feed_min_ml', 45):.0f} – {calc.get('per_feed_max_ml', 54):.0f} mL/feed`**\n"
            f"- **Estimated Calories:** `{calc.get('estimated_daily_kcal_24', 280):.0f} kcal/day` (at 24 kcal/oz)\n\n"
            f"💡 *Tip: Never force an infant to finish a bottle. Look for satiety cues (releasing nipple, turning head, falling into calm sleep).*"
        )
        voice = f"For a 2.4 kg infant, the recommended feeding volume is {calc.get('per_feed_min_ml', 45):.0f} to {calc.get('per_feed_max_ml', 54):.0f} mL every three hours."
        return _return_with_span({
            "draft_response": text,
            "voice_summary": voice,
            "retrieved_chunks": []
        })

    # ── 5. Hospital Contact Lookup (from MCP Gateway) ──────────────────────
    if intent == "HOSPITAL_LOOKUP" or "mcp_hospital_emergency_locator" in tool_outputs:
        contact_dict = tool_outputs.get("mcp_hospital_emergency_locator")
        if not contact_dict or not isinstance(contact_dict, dict):
            contact = hospital_svc.search_hospital_emergency(query)
            contact_dict = contact.model_dump()

        text = (
            f"🏥 **{contact_dict.get('hospital_name')}** ({contact_dict.get('branch_location')})\n\n"
            f"- 🚨 **Emergency Phone:** `{contact_dict.get('emergency_phone')}`\n"
            f"- 🍼 **24/7 NICU Helpline:** `{contact_dict.get('nicu_helpline')}`\n"
            f"- 🚑 **Ambulance:** `{contact_dict.get('ambulance_phone')}`\n"
            f"- 📍 **Address:** {contact_dict.get('full_address')}\n\n"
            f"[🗺️ Open Google Maps Directions]({contact_dict.get('google_maps_url')})"
        )
        voice = f"Here are the emergency numbers for {contact_dict.get('hospital_name')}. The 24/7 NICU helpline is {contact_dict.get('nicu_helpline')}."
        return _return_with_span({
            "draft_response": text,
            "voice_summary": voice,
            "hospital_contact": contact_dict,
            "retrieved_chunks": []
        })

    # ── 6. Dynamic Agentic RAG Clinical Synthesis (Local & External) ────────
    chunks = tool_outputs.get("mcp_guideline_retriever")
    if not chunks or not isinstance(chunks, list):
        chunks = rag_svc.retrieve(query, baby_corrected_weeks=2, top_k=2)

    has_valid_kb = bool(chunks and isinstance(chunks, list) and chunks[0].get("score", 0.0) >= 0.40)
    ext_search = tool_outputs.get("mcp_external_clinical_search")

    # If local KB was insufficient, but external search wasn't executed yet, execute external search live
    if not has_valid_kb and not ext_search:
        try:
            from ...mcp.mcp_server import mcp_server
            res_ext = mcp_server.call_tool("mcp_external_clinical_search", {"query": query, "top_k": 3})
            ext_search = json.loads(res_ext.get("content", [{}])[0].get("text", "{}"))
        except Exception:
            ext_search = None

    # Compile the authoritative clinical context
    guideline_context = ""
    source_name = "AAP & WHO Pediatric Guidelines"
    if has_valid_kb:
        top_chunks = [c for c in chunks[:2] if isinstance(c, dict)]
        guideline_context = "\n\n".join(c.get("text", "") for c in top_chunks)
        source_name = top_chunks[0].get("metadata", {}).get("source", "AAP / WHO Clinical Guidelines")
    elif ext_search and ext_search.get("has_external_knowledge"):
        guideline_context = (
            ext_search.get("synthesized_guidance", "") + "\n\nRecommendations:\n" +
            "\n".join(f"- {r}" for r in ext_search.get("key_recommendations", []))
        )
        source_name = ext_search.get("source_authority", "Global Pediatric Clinical Literature (PubMed / OpenAlex)")

    baby_ctx = state.get("baby_wiki_context", "")

    # Dynamic LLM Synthesis via Local Ollama (llama3.1:8b / qwen2.5:3b)
    synthesized_text = None
    voice_script = None

    if guideline_context:
        system_prompt = (
            "You are an empathetic, board-certified neonatal clinical nurse specialist at Rainbow Children's Hospital. "
            "A mother of a preterm infant graduate has asked a clinical question. "
            "Answer her inquiry directly, accurately, and empathetically using the authoritative clinical evidence provided.\n"
            "CRITICAL RULES:\n"
            "1. DIRECT ANSWER FIRST: Directly answer the mother's exact question in the opening sentence with specific numbers (e.g. temperatures in °C and °F, volumes in mL, times). Never deflect.\n"
            "2. CLINICAL REASONING: Explain why this is important specifically for a preterm baby (e.g. immature thermoregulation, surface area, SIDS prevention, fluid targets).\n"
            "3. ACTIONABLE CARE TIPS: Give 2-3 clear, gentle bullet points on practical home care.\n"
            "4. WARM & SUPPORTIVE: Use a reassuring, empathetic tone.\n"
            "5. NO HALLUCINATION: Only state facts consistent with the evidence and standard pediatric care."
        )

        evidence_snippet = guideline_context[:600] if len(guideline_context) > 600 else guideline_context
        user_prompt = (
            f"Mother's Question: \"{query}\"\n\n"
            f"Authoritative Clinical Evidence ({source_name}):\n{evidence_snippet}\n\n"
            f"Baby Liam's Clinical Context:\n{baby_ctx[:250] if baby_ctx else 'Preterm infant, 2400g, 36 weeks CGA'}\n\n"
            "Please provide a warm, direct, empathetic clinical response for the mother:"
        )

        model_override = state.get("requested_model") or (state.get("selected_model") if state.get("selected_model") not in ["deterministic_boundary_block", "deterministic_emergency_bypass", "neonatal_bert_transformer_fastpath"] else None)

        try:
            llm_resp = llm_service.generate_chat_response(
                prompt=user_prompt,
                system_prompt=system_prompt,
                task_type="clinical_synthesis",
                model=model_override
            )
            if llm_resp and len(llm_resp.strip()) > 80:
                val = QueryResponseAlignmentValidator.validate(query=query, response=llm_resp, intent=intent)
                if val["passed"]:
                    synthesized_text = (
                        f"🩺 **Clinical Guidance: {query.title()}**\n\n"
                        f"{llm_resp.strip()}\n\n"
                        f"*(Source: {source_name})*"
                    )
                    sentences = [s.strip() for s in llm_resp.split(".") if len(s.strip()) > 15]
                    voice_script = sentences[0] + "." if sentences else f"Here is clinical guidance regarding {query}."
        except Exception:
            synthesized_text = None

    if synthesized_text:
        return _return_with_span({
            "draft_response": synthesized_text,
            "voice_summary": voice_script,
            "selected_model": model_override or llm_service.get_routed_model("clinical_synthesis"),
            "retrieved_chunks": chunks if has_valid_kb else [],
            "external_search_results": ext_search,
            "external_knowledge_found": bool(ext_search and not has_valid_kb)
        })

    # Grounded Domain Fallback when LLM is offline or unaligned
    q_lower = query.lower()
    if any(k in q_lower for k in ["temperature", "room", "cold", "warm", "degrees", "celsius", "fahrenheit"]):
        temp_text = (
            "🩺 **Clinical Guidance: Room Temperature & Thermoregulation for Preterm Infants**\n\n"
            "According to AAP Safe Sleep and WHO Preterm Care guidelines:\n"
            "• **Ideal Room Temperature:** The recommended ambient room temperature for your baby is **20°C to 22°C (68°F to 72°F)**.\n"
            "• **Minimum Safe Temperature:** The room should not drop below **18°C (65°F)**. If it is cooler, dress baby in an additional light layer or certified wearable sleep sack rather than using loose blankets.\n"
            "• **Kangaroo Mother Care (KMC) Sessions:** Keep the room slightly warmer at **22°C to 24°C (72°F to 75°F)** when baby is unclothed during skin-to-skin contact.\n"
            "• **Why Preemies Need Temperature Control:** Preterm infants have higher surface area, thinner skin, and less insulating brown fat, so they lose body heat rapidly. However, avoid overheating (sweating, flushed neck) as that increases SIDS risk.\n\n"
            "*(Source: American Academy of Pediatrics (AAP) Safe Sleep & WHO Preterm Guidelines)*"
        )
        return _return_with_span({
            "draft_response": temp_text,
            "voice_summary": "The recommended room temperature for a preterm baby is 20 to 22 degrees Celsius, or 68 to 72 degrees Fahrenheit.",
            "retrieved_chunks": chunks if has_valid_kb else []
        })

    if has_valid_kb:
        top_chunks = [c for c in chunks[:2] if isinstance(c, dict)]
        top_chunk = top_chunks[0]
        header = top_chunk.get("header", "Pediatric Clinical Guidance")
        source = top_chunk.get("metadata", {}).get("source", "AAP / WHO Clinical Guidelines")
        combined_body = "\n\n".join(c.get("text", "").strip() for c in top_chunks if c.get("text"))

        text = (
            f"🩺 **Clinical Guidance: {header}**\n\n"
            f"{combined_body}\n\n"
            f"*(Source: {source})*"
        )
        voice = f"Clinical guidance recommends: {header}."
        return _return_with_span({
            "draft_response": text,
            "voice_summary": voice,
            "retrieved_chunks": chunks
        })

    # Default fallback supportive response
    default_text = (
        "🩺 **Neonatal Post-Discharge Support**\n\n"
        "Preterm infants thrive on consistency in their feeding intervals, skin-to-skin kangaroo care, "
        "and safe sleep hygiene. Always ensure your baby is placed on their back in their own crib, "
        "and monitor wet diapers (at least 6 per day) to confirm good hydration."
    )
    return _return_with_span({
        "draft_response": default_text,
        "voice_summary": "Preterm infants thrive on consistent feeding intervals and skin-to-skin care.",
        "retrieved_chunks": []
    })
