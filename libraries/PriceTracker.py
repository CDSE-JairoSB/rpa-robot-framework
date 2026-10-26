"""Utilidades de persistencia y comparación de precios para la wishlist Amazon."""

from __future__ import annotations

import csv
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional


class PriceTracker:
    """Expone keywords Robot Framework para históricos CSV de precios."""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

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
