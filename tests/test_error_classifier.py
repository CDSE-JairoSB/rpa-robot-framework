"""Pruebas unitarias para ErrorClassifier y el sidecar de triaje con IA."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from libraries.ErrorClassifier import (
    CATEGORY_AUTH_CHALLENGE,
    CATEGORY_CAPTCHA,
    CATEGORY_DOM_DRIFT,
    CATEGORY_NETWORK_ERROR,
    CATEGORY_UNKNOWN,
    ErrorClassifier,
    classify_error,
    triage_with_llm,
)
from libraries.PriceTracker import (
    STATUS_ERROR_SELECTOR,
    STATUS_NEEDS_2FA,
    STATUS_RATE_LIMITED,
)


def test_classify_2fa_challenge():
    classifier = ErrorClassifier()
    result = classifier.classify_error(
        error_message="Verification required",
        page_title="Amazon Sign-In Approval",
    )
    assert result["action_code"] == STATUS_NEEDS_2FA
    assert result["category"] == CATEGORY_AUTH_CHALLENGE
    assert "description" in result
    assert len(result["description"]) > 0


def test_classify_captcha_challenge():
    classifier = ErrorClassifier()
    result = classifier.classify_error(
        error_message="Enter the characters you see below",
        page_title="Robot Check",
    )
    assert result["action_code"] == STATUS_RATE_LIMITED
    assert result["category"] == CATEGORY_CAPTCHA
    assert "description" in result


def test_classify_generic_selector_failure():
    classifier = ErrorClassifier()
    result = classifier.classify_error(
        error_message='Element with locator \'//div[@id="wl-item-list"]\' not found after 10s',
        page_title="Amazon.com.mx: Mi Lista de Deseos",
    )
    assert result["action_code"] == STATUS_ERROR_SELECTOR
    assert result["category"] == CATEGORY_DOM_DRIFT
    assert "description" in result


def test_classify_prioritizes_captcha_in_page_source_over_selector_error():
    """Si el scraper falla buscando un selector porque cayó en Robot Check/CAPTCHA,

    el clasificador debe reportar CAPTCHA y no DOM_DRIFT.
    """
    classifier = ErrorClassifier()
    result = classifier.classify_error(
        error_message='Element with locator \'//div[@id="wl-item-list"]\' not found',
        page_title="Amazon.com.mx",
        page_source='<html><body><form action="/errors/validateCaptcha"><input id="captchacharacters"/></form></body></html>',
    )
    assert result["action_code"] == STATUS_RATE_LIMITED
    assert result["category"] == CATEGORY_CAPTCHA


def test_classify_prioritizes_2fa_in_page_source_over_selector_error():
    """Si el scraper falla buscando un selector porque la sesión expiró y pide OTP/2FA,

    el clasificador debe reportar AUTH_CHALLENGE y no DOM_DRIFT.
    """
    classifier = ErrorClassifier()
    result = classifier.classify_error(
        error_message="Could not find item container",
        page_title="Amazon.com.mx",
        page_source='<div id="auth-portal-main-section"><input id="auth-mfa-otpcode"/></div>',
    )
    assert result["action_code"] == STATUS_NEEDS_2FA
    assert result["category"] == CATEGORY_AUTH_CHALLENGE


def test_classify_spanish_amazon_patterns():
    classifier = ErrorClassifier()
    # 2FA en español
    res_2fa = classifier.classify_error(
        error_message="Se requiere verificación de dos pasos",
        page_title="Aprobación de inicio de sesión de Amazon",
    )
    assert res_2fa["action_code"] == STATUS_NEEDS_2FA
    assert res_2fa["category"] == CATEGORY_AUTH_CHALLENGE

    # Robot check / Captcha en español
    res_captcha = classifier.classify_error(
        error_message="Ingresa los caracteres que ves a continuación",
        page_title="Verificación de Robot",
    )
    assert res_captcha["action_code"] == STATUS_RATE_LIMITED
    assert res_captcha["category"] == CATEGORY_CAPTCHA


def test_classify_network_errors():
    classifier = ErrorClassifier()
    result = classifier.classify_error(
        error_message="net::ERR_CONNECTION_TIMED_OUT at https://www.amazon.com.mx",
        page_title="",
    )
    assert result["action_code"] == STATUS_ERROR_SELECTOR
    assert result["category"] == CATEGORY_NETWORK_ERROR


def test_classify_unknown_error():
    classifier = ErrorClassifier()
    result = classifier.classify_error(
        error_message="Unexpected internal memory buffer allocation fault in driver",
        page_title="Unknown Page",
    )
    assert result["action_code"] == STATUS_ERROR_SELECTOR
    assert result["category"] == CATEGORY_UNKNOWN


def test_triage_with_llm_missing_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    classifier = ErrorClassifier()
    result = classifier.triage_with_llm("Log: unhandled exception in line 42")
    assert result["category"] == CATEGORY_UNKNOWN
    assert result["action_code"] == STATUS_ERROR_SELECTOR
    assert "GEMINI_API_KEY" in result["description"]
    assert result.get("triage_source") == "offline_fallback"


def test_triage_with_llm_mocked_success():
    classifier = ErrorClassifier()
    mock_payload = {
        "category": "AUTH_CHALLENGE",
        "action_code": "STATUS_NEEDS_2FA",
        "description": "Log indicates OTP challenge page intercepted session cookies.",
        "root_cause": "Session expired after 14 days",
        "suggested_action": "Request human login via Telegram /login",
    }

    with patch.object(classifier, "_call_gemini_api", return_value=mock_payload):
        result = classifier.triage_with_llm("2026-10-27 OTP prompt observed", api_key="test-key")
        assert result["category"] == CATEGORY_AUTH_CHALLENGE
        assert result["action_code"] == STATUS_NEEDS_2FA
        assert result["description"] == mock_payload["description"]
        assert result["root_cause"] == mock_payload["root_cause"]
        assert result["triage_source"] == "gemini_llm"


def test_triage_with_llm_api_failure_fallback():
    classifier = ErrorClassifier()
    with patch.object(classifier, "_call_gemini_api", side_effect=RuntimeError("Connection refused")):
        result = classifier.triage_with_llm("some failure log", api_key="dummy-key")
        assert result["category"] == CATEGORY_UNKNOWN
        assert result["action_code"] == STATUS_ERROR_SELECTOR
        assert "Connection refused" in result["description"]
        assert result["triage_source"] == "llm_error_fallback"


def test_classify_error_delegates_to_llm_when_unknown_and_enabled():
    classifier = ErrorClassifier()
    mock_llm_res = {
        "category": "AUTH_CHALLENGE",
        "action_code": "STATUS_NEEDS_2FA",
        "description": "Resolved via LLM sidecar",
        "triage_source": "gemini_llm",
    }
    with patch.object(classifier, "triage_with_llm", return_value=mock_llm_res) as mock_triage:
        result = classifier.classify_error(
            error_message="Strange unparsed token error",
            page_title="Weird Title",
            use_llm_fallback=True,
            api_key="mock-key",
        )
        assert mock_triage.called
        assert result["category"] == "AUTH_CHALLENGE"
        assert result["action_code"] == STATUS_NEEDS_2FA


def test_module_level_helpers():
    result = classify_error(
        error_message="Enter the characters you see below",
        page_title="Robot Check",
    )
    assert result["category"] == CATEGORY_CAPTCHA
    assert result["action_code"] == STATUS_RATE_LIMITED

    fallback = triage_with_llm("test log", api_key="")
    assert fallback["category"] == CATEGORY_UNKNOWN

