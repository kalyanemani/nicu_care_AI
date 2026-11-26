"""
Unit tests for Layer 3 Tool Guardrails (Volume, Dose, Temperature).
"""

from app.agent.guardrails.tool_guardrails import ToolGuardrails


def test_feed_volume_normal():
    # 2000g baby -> ceiling is 2.0 * 45 = 90 mL
    res = ToolGuardrails.validate_feed_volume(volume_ml=50.0, weight_grams=2000)
    assert res["valid"] is True
    assert res["reason"] is None


def test_feed_volume_excessive_reject():
    # 2000g baby giving 150 mL (impossible single feed)
    res = ToolGuardrails.validate_feed_volume(volume_ml=150.0, weight_grams=2000)
    assert res["valid"] is False
    assert "exceeds the maximum safe single-feed capacity" in res["reason"]


def test_feed_volume_zero_reject():
    res = ToolGuardrails.validate_feed_volume(volume_ml=-5.0, weight_grams=2000)
    assert res["valid"] is False


def test_temperature_normal():
    res = ToolGuardrails.validate_temperature(37.0)
    assert res["valid"] is True
    assert res["status"] == "normal"
    assert res["is_emergency"] is False


def test_temperature_hypothermia_emergency():
    # < 36.5 is hypothermia
    res = ToolGuardrails.validate_temperature(36.1)
    assert res["valid"] is True
    assert res["status"] == "hypothermia"
    assert res["is_emergency"] is True
    assert "hypothermia" in res["alert"].lower()


def test_temperature_fever_emergency():
    # >= 38.0 is emergency in neonate
    res = ToolGuardrails.validate_temperature(38.4)
    assert res["valid"] is True
    assert res["status"] == "hyperthermia_fever"
    assert res["is_emergency"] is True
    assert "emergency" in res["alert"].lower()


def test_temperature_out_of_bounds_sensor_error():
    res = ToolGuardrails.validate_temperature(24.0)
    assert res["valid"] is False
    assert "outside biologically valid limits" in res["reason"]
