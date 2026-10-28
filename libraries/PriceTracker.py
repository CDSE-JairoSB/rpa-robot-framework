"""Utilidades de persistencia y comparación de precios para la wishlist Amazon."""

from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

STATUS_OK_UPDATED = "OK_UPDATED"
STATUS_PRICE_UNCHANGED = "PRICE_UNCHANGED"
STATUS_NEEDS_2FA = "STATUS_NEEDS_2FA"
STATUS_RATE_LIMITED = "RATE_LIMITED"
STATUS_ERROR_SELECTOR = "ERROR_SELECTOR"

STATUS_CODES = {
    STATUS_OK_UPDATED,
    STATUS_PRICE_UNCHANGED,
    STATUS_NEEDS_2FA,
    STATUS_RATE_LIMITED,
    STATUS_ERROR_SELECTOR,
}


class PriceTracker:
    """Expone keywords Robot Framework para históricos CSV de precios y señales de estado."""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    STATUS_OK_UPDATED = STATUS_OK_UPDATED
    STATUS_PRICE_UNCHANGED = STATUS_PRICE_UNCHANGED
    STATUS_NEEDS_2FA = STATUS_NEEDS_2FA
    STATUS_RATE_LIMITED = STATUS_RATE_LIMITED
    STATUS_ERROR_SELECTOR = STATUS_ERROR_SELECTOR
    STATUS_CODES = STATUS_CODES

    def __init__(self) -> None:
        self._last_summary: Dict[str, Any] = {
            "status": self.STATUS_ERROR_SELECTOR,
            "total_items": 0,
            "drops_found": [],
        }

    def set_execution_summary(
        self,
        summary: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Almacena el resumen o estado actual en la instancia de PriceTracker."""
        if summary is not None:
            self._last_summary = dict(summary)
        elif status is not None:
            self._last_summary["status"] = status
        elif error is not None:
            self._last_summary = {
                "status": self.resolve_execution_status(0, 0, error),
                "total_items": 0,
                "drops_found": [],
            }
        return self._last_summary

    def get_execution_summary(self) -> Dict[str, Any]:
        """Recupera el último resumen registrado en la ejecución."""
        return dict(self._last_summary)

    HISTORY_FIELDS = [
        "product_id",
        "product_name",
        "product_url",
        "current_price",
        "currency",
        "availability",
        "checked_at",
        "previous_price",
        "price_delta",
        "price_change_type",
        "status",
        "error_message",
    ]

    def current_timestamp(self) -> str:
        """Retorna una fecha UTC ISO-8601 para auditoría."""
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def normalize_amazon_price(self, raw_price: Any) -> Dict[str, str]:
        """Normaliza un importe mostrado por Amazon a precio decimal y moneda.

        Un precio no parseable se representa con valores vacíos para que el flujo
        Robot pueda clasificarlo como artículo sin precio en vez de abortar el lote.
        """
        text = "" if raw_price is None else str(raw_price).strip()
        currency = ""
        upper_text = text.upper()

        if "MXN" in upper_text or "MX$" in upper_text:
            currency = "MXN"
        elif "USD" in upper_text or "US$" in upper_text:
            currency = "USD"
        elif "$" in text:
            currency = "MXN"

        # Conserva únicamente el primer número decimal, considerando separadores
        # comunes de miles y decimal en formatos MXN/USD.
        match = re.search(r"(\d[\d,.\s]*)", text)
        if not match:
            return {"price": "", "currency": currency, "raw_price": text}

        numeric = match.group(1).replace(" ", "")
        if "," in numeric and "." in numeric:
            numeric = numeric.replace(",", "")
        elif "," in numeric:
            trailing = numeric.rsplit(",", 1)[-1]
            numeric = numeric.replace(",", ".") if len(trailing) in (1, 2) else numeric.replace(",", "")

        try:
            price = Decimal(numeric).quantize(Decimal("0.01"))
        except InvalidOperation:
            return {"price": "", "currency": currency, "raw_price": text}

        return {"price": format(price, ".2f"), "currency": currency, "raw_price": text}

    def extract_asin_from_url(self, product_url: str) -> str:
        """Extrae el ASIN de enlaces habituales de productos Amazon."""
        url = product_url or ""
        match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", url, re.IGNORECASE)
        return match.group(1).upper() if match else ""

    def build_price_record(
        self,
        product_id: str,
        product_name: str,
        product_url: str,
        raw_price: Any,
        availability: str = "",
        checked_at: Optional[str] = None,
    ) -> Dict[str, str]:
        """Crea un registro normalizado todavía sin comparación histórica."""
        normalized = self.normalize_amazon_price(raw_price)
        identifier = product_id or self.extract_asin_from_url(product_url) or (product_url or "").strip()
        status = "OK" if normalized["price"] else "PRICE_NOT_AVAILABLE"

        return {
            "product_id": identifier,
            "product_name": (product_name or "").strip(),
            "product_url": (product_url or "").strip(),
            "current_price": normalized["price"],
            "currency": normalized["currency"],
            "availability": (availability or "").strip(),
            "checked_at": checked_at or self.current_timestamp(),
            "previous_price": "",
            "price_delta": "",
            "price_change_type": "NEW",
            "status": status,
            "error_message": "",
        }

    def load_price_history(self, history_path: str) -> List[Dict[str, str]]:
        """Carga el histórico CSV; devuelve una lista vacía si aún no existe."""
        if not os.path.exists(history_path):
            return []

        with open(history_path, "r", newline="", encoding="utf-8-sig") as history_file:
            return list(csv.DictReader(history_file))

    def get_latest_price_record(
        self, history: Iterable[Dict[str, str]], product_id: str
    ) -> Dict[str, str]:
        """Obtiene el último registro temporal de un producto."""
        matches = [
            row for row in history if row.get("product_id", "").strip() == (product_id or "").strip()
        ]
        if not matches:
            return {}
        return max(matches, key=lambda row: row.get("checked_at", ""))

    def compare_price_record(
        self, current_record: Dict[str, str], previous_record: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Compara un registro actual con el último precio y devuelve el resultado."""
        record = {field: str(current_record.get(field, "")) for field in self.HISTORY_FIELDS}
        previous = previous_record or {}

        if record["status"] != "OK":
            record["price_change_type"] = "NOT_COMPARABLE"
            return record

        previous_price = previous.get("current_price", "").strip()
        if not previous_price:
            record["price_change_type"] = "NEW"
            return record

        try:
            current = Decimal(record["current_price"])
            old = Decimal(previous_price)
        except InvalidOperation:
            record["price_change_type"] = "NOT_COMPARABLE"
            return record

        delta = (current - old).quantize(Decimal("0.01"))
        record["previous_price"] = format(old, ".2f")
        record["price_delta"] = format(delta, ".2f")
        record["price_change_type"] = (
            "DECREASED" if delta < 0 else "INCREASED" if delta > 0 else "UNCHANGED"
        )
        return record

    def create_error_price_record(
        self,
        product_id: str,
        product_name: str,
        product_url: str,
        error_message: str,
        checked_at: Optional[str] = None,
    ) -> Dict[str, str]:
        """Genera un registro persistible para errores aislados por producto."""
        record = self.build_price_record(
            product_id, product_name, product_url, "", "", checked_at
        )
        record["status"] = "ERROR"
        record["price_change_type"] = "NOT_COMPARABLE"
        record["error_message"] = str(error_message)
        return record

    def append_price_records(self, history_path: str, records: Iterable[Dict[str, str]]) -> int:
        """Añade registros al histórico CSV, creando directorios y cabecera cuando haga falta."""
        rows = list(records)
        if not rows:
            return 0

        os.makedirs(os.path.dirname(os.path.abspath(history_path)), exist_ok=True)
        file_exists = os.path.exists(history_path) and os.path.getsize(history_path) > 0

        with open(history_path, "a", newline="", encoding="utf-8") as history_file:
            writer = csv.DictWriter(history_file, fieldnames=self.HISTORY_FIELDS, extrasaction="ignore")
            if not file_exists:
                writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in self.HISTORY_FIELDS})

        return len(rows)

    def write_execution_report(
        self, output_directory: str, records: Iterable[Dict[str, str]], timestamp: Optional[str] = None
    ) -> str:
        """Crea un CSV inmutable con los resultados de una ejecución."""
        rows = list(records)
        os.makedirs(output_directory, exist_ok=True)
        stamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_directory, f"amazon_wishlist_report_{stamp}.csv")

        with open(report_path, "w", newline="", encoding="utf-8") as report_file:
            writer = csv.DictWriter(report_file, fieldnames=self.HISTORY_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in self.HISTORY_FIELDS})

        return report_path

    def resolve_execution_status(
        self, total_items: int, drops_count: int = 0, error: Optional[str] = None
    ) -> str:
        """Determina el código de estado estándar según el resultado de extracción."""
        if error:
            err_lower = str(error).lower()
            if any(term in err_lower for term in ("status_needs_2fa", "2fa", "sign-in", "login", "auth")):
                return self.STATUS_NEEDS_2FA
            if any(term in err_lower for term in ("rate_limited", "captcha", "robot")):
                return self.STATUS_RATE_LIMITED
            if any(term in err_lower for term in ("error_selector", "selector", "artículo", "articulo", "heading")):
                return self.STATUS_ERROR_SELECTOR
            return self.STATUS_ERROR_SELECTOR

        if int(total_items) <= 0:
            return self.STATUS_ERROR_SELECTOR

        if int(drops_count) > 0:
            return self.STATUS_OK_UPDATED

        return self.STATUS_PRICE_UNCHANGED

    def build_execution_summary(
        self,
        total_items: int,
        drops_found: Optional[List[Dict[str, Any]]] = None,
        status: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Construye un diccionario resumen con la estructura esperada: total_items, drops_found, status."""
        drops = list(drops_found or [])
        resolved_status = status or self.resolve_execution_status(total_items, len(drops), error)
        summary = {
            "total_items": int(total_items),
            "drops_found": drops,
            "status": resolved_status,
        }
        self._last_summary = dict(summary)
        return summary

    def save_status_to_json(
        self,
        status: Optional[str] = None,
        total_items: Optional[int] = None,
        drops_found: Optional[List[Dict[str, Any]]] = None,
        output_path: str = "results/status.json",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Escribe el estado y resumen final a results/status.json."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        final_status = str(status) if status is not None else self._last_summary.get("status", self.STATUS_ERROR_SELECTOR)
        count = int(total_items if total_items is not None else self._last_summary.get("total_items", 0))
        drops = list(drops_found if drops_found is not None else self._last_summary.get("drops_found", []))

        payload: Dict[str, Any] = {
            "status": final_status,
            "total_items": count,
            "drops_found": drops,
            "timestamp": self.current_timestamp(),
        }
        if extra:
            payload.update(extra)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return payload
