"""Clasificador determinista de errores y sidecar de triaje con IA (Gemini Flash).

Provee mapeo de excepciones y estados de Amazon (2FA, CAPTCHA, DOM drift, red)
a códigos de acción estándar con 0 tokens de costo, y triaje opcional con LLM
para anomalías no catalogadas.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

from libraries.PriceTracker import (
    STATUS_ERROR_SELECTOR,
    STATUS_NEEDS_2FA,
    STATUS_RATE_LIMITED,
)

# Categorías estándar de error (alineadas a buenas prácticas ISTQB y RCA)
CATEGORY_AUTH_CHALLENGE = "AUTH_CHALLENGE"
CATEGORY_CAPTCHA = "CAPTCHA"
CATEGORY_DOM_DRIFT = "DOM_DRIFT"
CATEGORY_NETWORK_ERROR = "NETWORK_ERROR"
CATEGORY_UNKNOWN = "UNKNOWN"

CATEGORIES = {
    CATEGORY_AUTH_CHALLENGE,
    CATEGORY_CAPTCHA,
    CATEGORY_DOM_DRIFT,
    CATEGORY_NETWORK_ERROR,
    CATEGORY_UNKNOWN,
}

# Expresiones regulares deterministas para clasificación rápida (0 tokens)
RE_CAPTCHA = re.compile(
    r"(?:robot\s*check|verificaci[oó]n de robot|enter the characters you see below|"
    r"enter the characters|type the characters|ingresa los caracteres|"
    r"validatecaptcha|captchacharacters|images-na\.ssl-images-amazon\.com/captcha|"
    r"rate[-_ ]?limited|too many requests|http\s*429|bot detected)",
    re.IGNORECASE,
)

RE_AUTH = re.compile(
    r"(?:sign[- ]?in approval|amazon sign-in|aprobaci[oó]n de inicio de sesi[oó]n|"
    r"verificaci[oó]n (?:requerida|en dos pasos|de dos pasos)|verification required|"
    r"two[- ]step|two[- ]factor|doble factor|segundo paso|"
    r"\botp\b|one[- ]time password|c[oó]digo de verificaci[oó]n|"
    r"status_needs_2fa|auth[- ]?mfa|cvf-page-content|auth-portal)",
    re.IGNORECASE,
)

RE_DOM_DRIFT = re.compile(
    r"(?:element with locator|not found after|unable to locate element|"
    r"element not found|no such element|nosuchelementexception|"
    r"stale element|staleelementreferenceexception|timeoutexception|"
    r"invalid selector|syntax error in xpath|error_selector|wl-item-list|"
    r"could not find|no se encontr[oó] el elemento)",
    re.IGNORECASE,
)

RE_NETWORK = re.compile(
    r"(?:net::err_|err_connection|connectionrefused|connection timed out|"
    r"timed?out waiting for response|name_not_resolved|dns_probe|networkerror|"
    r"econnrefused|failed to establish a new connection|max retries exceeded with url)",
    re.IGNORECASE,
)


class ErrorClassifier:
    """Clasifica errores de ejecución en códigos de acción y categorías estructuradas."""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    CATEGORY_AUTH_CHALLENGE = CATEGORY_AUTH_CHALLENGE
    CATEGORY_CAPTCHA = CATEGORY_CAPTCHA
    CATEGORY_DOM_DRIFT = CATEGORY_DOM_DRIFT
    CATEGORY_NETWORK_ERROR = CATEGORY_NETWORK_ERROR
    CATEGORY_UNKNOWN = CATEGORY_UNKNOWN
    CATEGORIES = CATEGORIES

    STATUS_NEEDS_2FA = STATUS_NEEDS_2FA
    STATUS_RATE_LIMITED = STATUS_RATE_LIMITED
    STATUS_ERROR_SELECTOR = STATUS_ERROR_SELECTOR

    def classify_error(
        self,
        error_message: str = "",
        page_title: str = "",
        page_source: str = "",
        use_llm_fallback: bool = False,
        api_key: Optional[str] = None,
        log_text: str = "",
    ) -> Dict[str, Any]:
        """Clasifica un error ocurrido en la automatización de forma determinista.

        Prioriza la inspección de la página real (page_title y page_source) sobre
        el mensaje genérico de error de WebDriver, identificando la causa raíz
        (ej. un 'ElementNotFound' ocurrido porque Amazon redirigió a Robot Check
        se clasifica como CAPTCHA y no DOM_DRIFT).

        Args:
            error_message: Mensaje o traza de la excepción reportada.
            page_title: Título de la pestaña en el navegador al fallar.
            page_source: Fragmento o HTML completo de la página activa.
            use_llm_fallback: Si es True y la regla determinista no clasifica,
                invoca el triaje asistido por LLM.
            api_key: Clave opcional de API de Gemini para el sidecar.
            log_text: Contexto de logs adicional para el fallback de LLM.

        Returns:
            Dict con {"category": str, "action_code": str, "description": str}
        """
        err_str = str(error_message or "")
        title_str = str(page_title or "")
        source_str = str(page_source or "")

        # 1. Detección de CAPTCHA / Robot Check (Prioridad en page_title / page_source)
        if RE_CAPTCHA.search(title_str) or RE_CAPTCHA.search(source_str) or RE_CAPTCHA.search(err_str):
            return {
                "category": CATEGORY_CAPTCHA,
                "action_code": STATUS_RATE_LIMITED,
                "description": (
                    "Amazon bot detection or CAPTCHA challenge encountered "
                    "(Robot Check / Rate limiting)."
                ),
            }

        # 2. Detección de Desafío de Autenticación / 2FA / OTP
        if RE_AUTH.search(title_str) or RE_AUTH.search(source_str) or RE_AUTH.search(err_str):
            return {
                "category": CATEGORY_AUTH_CHALLENGE,
                "action_code": STATUS_NEEDS_2FA,
                "description": (
                    "Amazon requested sign-in approval, 2FA OTP verification, "
                    "or session renewal."
                ),
            }

        # 3. Detección de Fallas de Red / Conectividad
        if RE_NETWORK.search(err_str) or RE_NETWORK.search(title_str):
            return {
                "category": CATEGORY_NETWORK_ERROR,
                "action_code": STATUS_ERROR_SELECTOR,
                "description": (
                    "Network connectivity or timeout failure attempting to reach Amazon endpoint."
                ),
            }

        # 4. Detección de Deriva en DOM / Selector ausente
        if RE_DOM_DRIFT.search(err_str) or RE_DOM_DRIFT.search(title_str):
            return {
                "category": CATEGORY_DOM_DRIFT,
                "action_code": STATUS_ERROR_SELECTOR,
                "description": (
                    "Element selector not found or timed out, indicating potential DOM "
                    "drift or delayed rendering."
                ),
            }

        # 5. Fallback opcional a LLM si está habilitado
        if use_llm_fallback:
            combined_log = log_text or f"Title: {title_str}\nError: {err_str}\nSource: {source_str[:1000]}"
            return self.triage_with_llm(combined_log, api_key=api_key)

        # 6. Error no catalogado
        return {
            "category": CATEGORY_UNKNOWN,
            "action_code": STATUS_ERROR_SELECTOR,
            "description": "Unrecognized error condition; manual triage or offline AI analysis recommended.",
        }

    def triage_with_llm(
        self,
        log_text: str,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
    ) -> Dict[str, Any]:
        """Triaje de diagnóstico usando Gemini Flash con respuesta en esquema JSON.

        Diseñado como sidecar offline que sólo se ejecuta cuando ocurre un error
        desconocido o el usuario solicita diagnóstico explícito.
        """
        resolved_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not resolved_key:
            return {
                "category": CATEGORY_UNKNOWN,
                "action_code": STATUS_ERROR_SELECTOR,
                "description": "LLM triage skipped: no GEMINI_API_KEY configured in environment.",
                "triage_source": "offline_fallback",
            }

        prompt = (
            "You are an expert QA and DevOps Automation Triage Engineer analyzing an Amazon Robot Framework failure.\n"
            "Analyze the following execution log or error snippet and return a structured JSON evaluation.\n"
            f"Log Snippet:\n{log_text}\n\n"
            "Strict JSON schema:\n"
            "{\n"
            '  "category": "AUTH_CHALLENGE" | "CAPTCHA" | "DOM_DRIFT" | "NETWORK_ERROR" | "UNKNOWN",\n'
            '  "action_code": "STATUS_NEEDS_2FA" | "RATE_LIMITED" | "ERROR_SELECTOR",\n'
            '  "description": string (summary of what failed),\n'
            '  "root_cause": string (detailed technical diagnosis),\n'
            '  "suggested_action": string (recommended remediation for user or runner)\n'
            "}"
        )

        try:
            parsed = self._call_gemini_api(prompt, api_key=resolved_key, model=model)
            return {
                "category": parsed.get("category", CATEGORY_UNKNOWN),
                "action_code": parsed.get("action_code", STATUS_ERROR_SELECTOR),
                "description": parsed.get("description", "Analyzed by LLM triage sidecar"),
                "root_cause": parsed.get("root_cause", ""),
                "suggested_action": parsed.get("suggested_action", ""),
                "triage_source": "gemini_llm",
            }
        except Exception as exc:
            return {
                "category": CATEGORY_UNKNOWN,
                "action_code": STATUS_ERROR_SELECTOR,
                "description": f"LLM triage failed: {str(exc)}",
                "triage_source": "llm_error_fallback",
            }

    def _call_gemini_api(
        self,
        prompt: str,
        api_key: str,
        model: str = "gemini-2.5-flash",
    ) -> Dict[str, Any]:
        """Realiza la llamada al API de Gemini intentando SDK oficial o REST fallback."""
        # Intento con google.genai oficial si está instalado
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": {
                        "type": "OBJECT",
                        "properties": {
                            "category": {"type": "STRING"},
                            "action_code": {"type": "STRING"},
                            "description": {"type": "STRING"},
                            "root_cause": {"type": "STRING"},
                            "suggested_action": {"type": "STRING"},
                        },
                        "required": ["category", "action_code", "description"],
                    },
                },
            )
            raw_text = response.text or "{}"
            return json.loads(raw_text)
        except ImportError:
            pass

        # Fallback a REST vía standard library urllib.request (cero dependencias externas)
        import urllib.request

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "OBJECT",
                    "properties": {
                        "category": {"type": "STRING"},
                        "action_code": {"type": "STRING"},
                        "description": {"type": "STRING"},
                        "root_cause": {"type": "STRING"},
                        "suggested_action": {"type": "STRING"},
                    },
                    "required": ["category", "action_code", "description"],
                },
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            candidate = res_data.get("candidates", [{}])[0]
            text = candidate.get("content", {}).get("parts", [{}])[0].get("text", "{}")
            return json.loads(text)


# Instancia por defecto para uso directo a nivel módulo
_default_classifier = ErrorClassifier()


def classify_error(
    error_message: str = "",
    page_title: str = "",
    page_source: str = "",
    use_llm_fallback: bool = False,
    api_key: Optional[str] = None,
    log_text: str = "",
) -> Dict[str, Any]:
    """Atajo funcional a nivel módulo para ErrorClassifier().classify_error."""
    return _default_classifier.classify_error(
        error_message=error_message,
        page_title=page_title,
        page_source=page_source,
        use_llm_fallback=use_llm_fallback,
        api_key=api_key,
        log_text=log_text,
    )


def triage_with_llm(
    log_text: str,
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash",
) -> Dict[str, Any]:
    """Atajo funcional a nivel módulo para ErrorClassifier().triage_with_llm."""
    return _default_classifier.triage_with_llm(
        log_text=log_text,
        api_key=api_key,
        model=model,
    )

