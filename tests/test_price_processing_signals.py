"""Unit tests for price processing signals, status codes, and price extraction."""

import json
import pytest
from libraries.PriceTracker import PriceTracker, STATUS_CODES


def test_status_code_definitions():
    STATUS_CODES_SET = {"OK_UPDATED", "PRICE_UNCHANGED", "STATUS_NEEDS_2FA", "RATE_LIMITED", "ERROR_SELECTOR"}
    assert "STATUS_NEEDS_2FA" in STATUS_CODES_SET
    assert STATUS_CODES == STATUS_CODES_SET
    assert PriceTracker.STATUS_CODES == STATUS_CODES_SET


def test_extract_asin_and_normalize():
    tracker = PriceTracker()
    asin = tracker.extract_asin_from_url("https://www.amazon.com.mx/dp/B08N5WRWNW?psc=1")
    assert asin == "B08N5WRWNW"
    price_data = tracker.normalize_amazon_price("$ 1,299.50 MXN")
    assert price_data["price"] == "1299.50"


def test_extract_asin_variants():
    tracker = PriceTracker()
    assert tracker.extract_asin_from_url("https://www.amazon.com/gp/product/B09ABCDEF0/") == "B09ABCDEF0"
    assert tracker.extract_asin_from_url("https://www.amazon.com.mx/dp/b08n5wrwnw") == "B08N5WRWNW"
    assert tracker.extract_asin_from_url("https://example.com/not-amazon") == ""
    assert tracker.extract_asin_from_url("") == ""


def test_normalize_amazon_price_formats():
    tracker = PriceTracker()
    res_usd = tracker.normalize_amazon_price("US$ 45.99")
    assert res_usd["price"] == "45.99"
    assert res_usd["currency"] == "USD"

    res_comma = tracker.normalize_amazon_price("$500,00 MXN")
    assert res_comma["price"] == "500.00"

    res_invalid = tracker.normalize_amazon_price("No disponible")
    assert res_invalid["price"] == ""


def test_resolve_status_codes():
    tracker = PriceTracker()
    # Drops found -> OK_UPDATED
    assert tracker.resolve_execution_status(total_items=10, drops_count=2) == "OK_UPDATED"

    # No drops, valid items -> PRICE_UNCHANGED
    assert tracker.resolve_execution_status(total_items=10, drops_count=0) == "PRICE_UNCHANGED"

    # Zero items -> ERROR_SELECTOR
    assert tracker.resolve_execution_status(total_items=0, drops_count=0) == "ERROR_SELECTOR"

    # Auth challenge / 2FA -> STATUS_NEEDS_2FA
    assert (
        tracker.resolve_execution_status(total_items=0, error="[STATUS_NEEDS_2FA] Reautenticación 2FA requerida")
        == "STATUS_NEEDS_2FA"
    )
    assert (
        tracker.resolve_execution_status(total_items=0, error="Amazon sign-in required")
        == "STATUS_NEEDS_2FA"
    )

    # Captcha / Rate limit -> RATE_LIMITED
    assert (
        tracker.resolve_execution_status(total_items=0, error="[RATE_LIMITED] Robot check captcha")
        == "RATE_LIMITED"
    )

    # Selector drift error -> ERROR_SELECTOR
    assert (
        tracker.resolve_execution_status(total_items=0, error="[ERROR_SELECTOR] No se encontraron elementos de lista")
        == "ERROR_SELECTOR"
    )


def test_build_execution_summary():
    tracker = PriceTracker()
    drops = [
        {
            "asin": "B08N5WRWNW",
            "title": "Item A",
            "previous_price": 500.0,
            "current_price": 400.0,
            "is_drop": True,
        }
    ]
    summary = tracker.build_execution_summary(total_items=5, drops_found=drops)
    assert summary == {
        "total_items": 5,
        "drops_found": drops,
        "status": "OK_UPDATED",
    }


def test_save_status_to_json(tmp_path):
    tracker = PriceTracker()
    out_file = tmp_path / "results" / "status.json"
    drops = [{"asin": "B08N5WRWNW", "price": 400.0}]

    payload = tracker.save_status_to_json(
        status="OK_UPDATED",
        total_items=5,
        drops_found=drops,
        output_path=str(out_file),
    )

    assert out_file.exists()
    assert payload["status"] == "OK_UPDATED"
    assert payload["total_items"] == 5
    assert payload["drops_found"] == drops
    assert "timestamp" in payload

    with open(out_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["status"] == "OK_UPDATED"
    assert loaded["total_items"] == 5
    assert len(loaded["drops_found"]) == 1


def test_tracker_instance_state_and_teardown_save(tmp_path):
    tracker = PriceTracker()
    out_file = tmp_path / "results" / "status.json"

    # Initial state defaults to ERROR_SELECTOR
    assert tracker.get_execution_summary()["status"] == "ERROR_SELECTOR"

    # Record execution summary
    drops = [{"asin": "B123456789", "current_price": 250.0, "is_drop": True}]
    summary = tracker.build_execution_summary(total_items=3, drops_found=drops)
    assert summary["status"] == "OK_UPDATED"

    # Saving without explicit parameters persists the recorded summary
    saved = tracker.save_status_to_json(output_path=str(out_file))
    assert saved["status"] == "OK_UPDATED"
    assert saved["total_items"] == 3
    assert len(saved["drops_found"]) == 1

    # Error recording
    tracker.set_execution_summary(error="[STATUS_NEEDS_2FA] Reautenticación requerida")
    saved_err = tracker.save_status_to_json(output_path=str(out_file))
    assert saved_err["status"] == "STATUS_NEEDS_2FA"
    assert saved_err["total_items"] == 0

