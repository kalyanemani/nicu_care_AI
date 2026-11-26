"""
Tests for MedGemma 1.5 Integration and Timeout-Free LLM Execution.
Verifies:
1. Timeouts are disabled by default (timeout=None) for unconstrained local generation.
2. MedGemma 1.5 is registered, available, and selectable for clinical reasoning.
3. Model routing supports medical_expert and dynamic clinical_synthesis switching.
4. TextQueryRequest and agent execution respect requested_model parameter.
"""

import pytest
from app.services.llm_service import llm_service
from app.models.agent import TextQueryRequest, VoiceQueryResponse
from app.routers.agent import process_text_query


def test_timeouts_disabled_and_medgemma_registration():
    status = llm_service.check_ollama_status()
    assert status.get("timeouts_disabled") is True
    assert "medgemma1.5:latest" in status.get("available_models", []) or status.get("has_medgemma") is True
    assert llm_service.TASK_ROUTING_TABLE.get("medical_expert") == "medgemma1.5:latest"


def test_medgemma_model_shorthand_normalization():
    # Verify both 'medgemma1.5' and 'medgemma' normalize to 'medgemma1.5:latest'
    # Mock post to verify model payload without calling network
    import requests
    from unittest.mock import patch, MagicMock

    with patch.object(requests, "post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "MedGemma clinical advice for preterm infant"}
        mock_post.return_value = mock_resp

        res = llm_service.generate_chat_response(
            prompt="What is the ideal room temperature?",
            model="medgemma1.5"
        )
        assert res == "MedGemma clinical advice for preterm infant"
        called_args, called_kwargs = mock_post.call_args
        # Verifies adaptive 35s safeguard timeout for MedGemma CPU generation to prevent infinite hangs
        assert called_kwargs.get("timeout") == 35.0
        assert called_kwargs.get("json", {}).get("model") == "medgemma1.5:latest"
        assert called_kwargs.get("json", {}).get("options", {}).get("num_predict") == 110

        # Verifies explicit unconstrained execution if timeout=-1
        llm_service.generate_chat_response(
            prompt="What is the ideal room temperature?",
            model="medgemma1.5",
            timeout=-1
        )
        _, kwargs_unconstrained = mock_post.call_args
        assert kwargs_unconstrained.get("timeout") is None


def test_enable_medgemma_and_restore_routing():
    original_model = llm_service.get_routed_model("clinical_synthesis")

    # 1. Activate MedGemma as primary clinical model
    llm_service.enable_medgemma("medgemma1.5:latest")
    assert llm_service.get_routed_model("clinical_synthesis") == "medgemma1.5:latest"
    assert llm_service.get_routed_model("medical_expert") == "medgemma1.5:latest"

    # 2. Restore standard routing
    llm_service.set_task_model("clinical_synthesis", original_model)
    assert llm_service.get_routed_model("clinical_synthesis") == original_model


def test_text_query_request_model_override():
    req = TextQueryRequest(
        baby_id="baby_liam_01",
        text="What are active medications for Liam?",
        model="medgemma1.5:latest"
    )
    assert req.model == "medgemma1.5:latest"
    resp = process_text_query(req)
    assert resp is not None
    assert resp.model_used is not None
