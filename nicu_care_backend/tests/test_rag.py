"""
Unit tests for ClinicalRAGService.
Verifies section chunking, guideline coverage, and retrieval.
"""

import pytest
from app.services.rag_service import ClinicalRAGService


@pytest.fixture
def rag():
    return ClinicalRAGService()


def test_rag_indexes_guidelines(rag):
    assert len(rag.chunks) > 20
    doc_ids = {c["doc_id"] for c in rag.chunks}
    assert "aap_preterm_feeding" in doc_ids
    assert "aap_safe_sleep" in doc_ids
    assert "who_kangaroo_care" in doc_ids
    assert "neonatal_red_flags" in doc_ids


def test_rag_retrieve_fortification_query(rag):
    query = "How to prepare 24 kcal fortifier with breast milk"
    results = rag.retrieve(query, baby_corrected_weeks=2, top_k=3)

    assert len(results) > 0
    top_chunk = results[0]
    assert "aap_preterm_feeding" in top_chunk["doc_id"]
    assert "fortifi" in top_chunk["text"].lower()


def test_rag_retrieve_safe_sleep_query(rag):
    query = "Is it safe for baby to sleep on stomach or bed share"
    results = rag.retrieve(query, baby_corrected_weeks=4, top_k=3)

    assert len(results) > 0
    doc_ids = [r["doc_id"] for r in results]
    assert "aap_safe_sleep" in doc_ids


def test_rag_retrieve_kangaroo_care_query(rag):
    query = "skin to skin kangaroo care benefits and positioning"
    results = rag.retrieve(query, baby_corrected_weeks=0, top_k=3)

    assert len(results) > 0
    assert any("kangaroo" in r["doc_id"] for r in results)
