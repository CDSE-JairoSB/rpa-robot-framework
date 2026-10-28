"""Unit tests for SQLite PriceRepository."""

import concurrent.futures
import os
import pytest
from libraries.PriceRepository import PriceRepository


@pytest.fixture
def repo(tmp_path):
    db_file = tmp_path / "test_prices.db"
    return PriceRepository(db_path=str(db_file))


def test_initial_price_insert_and_lowest_tracking(repo):
    item = {
        "asin": "B08N5WRWNW",
        "title": "Sample Item",
        "url": "https://amazon.com.mx/dp/B08N5WRWNW",
        "current_price": 500.00,
        "currency": "MXN",
    }
    result = repo.record_price(item)
    assert result["is_drop"] is False
    assert result["lowest_price"] == 500.00
    assert result["current_price"] == 500.00
    assert result["asin"] == "B08N5WRWNW"
    assert result["title"] == "Sample Item"


def test_price_drop_detection(repo):
    item_initial = {
        "asin": "B08N5WRWNW",
        "title": "Sample Item",
        "url": "https://amazon.com.mx/dp/B08N5WRWNW",
        "current_price": 500.00,
        "currency": "MXN",
    }
    repo.record_price(item_initial)

    item_discounted = {
        "asin": "B08N5WRWNW",
        "title": "Sample Item",
        "url": "https://amazon.com.mx/dp/B08N5WRWNW",
        "current_price": 400.00,
        "currency": "MXN",
    }
    result = repo.record_price(item_discounted)
    assert result["is_drop"] is True
    assert result["previous_price"] == 500.00
    assert result["current_price"] == 400.00
    assert result["lowest_price"] == 400.00
    assert result["drop_percentage"] == 20.0


def test_price_increase_does_not_trigger_drop(repo):
    item_initial = {
        "asin": "B08N5WRWNW",
        "title": "Sample Item",
        "url": "https://amazon.com.mx/dp/B08N5WRWNW",
        "current_price": 500.00,
        "currency": "MXN",
    }
    repo.record_price(item_initial)

    item_increased = {
        "asin": "B08N5WRWNW",
        "title": "Sample Item",
        "url": "https://amazon.com.mx/dp/B08N5WRWNW",
        "current_price": 600.00,
        "currency": "MXN",
    }
    result = repo.record_price(item_increased)
    assert result["is_drop"] is False
    assert result["previous_price"] == 500.00
    assert result["current_price"] == 600.00
    assert result["lowest_price"] == 500.00
    assert result["drop_percentage"] == 0.0


def test_price_unchanged_does_not_trigger_drop(repo):
    item_initial = {
        "asin": "B08N5WRWNW",
        "title": "Sample Item",
        "url": "https://amazon.com.mx/dp/B08N5WRWNW",
        "current_price": 500.00,
        "currency": "MXN",
    }
    repo.record_price(item_initial)

    item_same = {
        "asin": "B08N5WRWNW",
        "title": "Sample Item",
        "url": "https://amazon.com.mx/dp/B08N5WRWNW",
        "current_price": 500.00,
        "currency": "MXN",
    }
    result = repo.record_price(item_same)
    assert result["is_drop"] is False
    assert result["previous_price"] == 500.00
    assert result["current_price"] == 500.00
    assert result["lowest_price"] == 500.00
    assert result["drop_percentage"] == 0.0


def test_get_tracked_items(repo):
    item1 = {
        "asin": "ITEM111111",
        "title": "Item One",
        "url": "https://amazon.com.mx/dp/ITEM111111",
        "current_price": 100.00,
        "currency": "MXN",
    }
    item2 = {
        "asin": "ITEM222222",
        "title": "Item Two",
        "url": "https://amazon.com.mx/dp/ITEM222222",
        "current_price": 250.50,
        "currency": "MXN",
    }
    repo.record_price(item1)
    repo.record_price(item2)

    tracked = repo.get_tracked_items()
    assert len(tracked) == 2
    asins = {it["asin"] for it in tracked}
    assert asins == {"ITEM111111", "ITEM222222"}

    item_one = next(it for it in tracked if it["asin"] == "ITEM111111")
    assert item_one["title"] == "Item One"
    assert item_one["current_price"] == 100.00
    assert item_one["lowest_price"] == 100.00
    assert item_one["currency"] == "MXN"


def test_price_history_recorded(repo):
    item = {
        "asin": "B08N5WRWNW",
        "title": "Sample Item",
        "url": "https://amazon.com.mx/dp/B08N5WRWNW",
        "current_price": 500.00,
        "currency": "MXN",
    }
    repo.record_price(item)
    item["current_price"] = 450.00
    repo.record_price(item)

    history = repo.get_price_history("B08N5WRWNW")
    assert len(history) == 2
    assert history[0]["price"] == 500.00
    assert history[1]["price"] == 450.00


def test_string_price_coercion(repo):
    item = {
        "asin": "STRINGPRICE1",
        "title": "String Price Item",
        "url": "https://amazon.com.mx/dp/STRINGPRICE1",
        "current_price": "1,299.50",
        "currency": "MXN",
    }
    result = repo.record_price(item)
    assert result["current_price"] == 1299.50
    assert result["lowest_price"] == 1299.50


def test_concurrent_writes(repo):
    def record_concurrent(idx):
        item = {
            "asin": f"CONCURRENT_{idx}",
            "title": f"Concurrent Item {idx}",
            "url": f"https://amazon.com.mx/dp/CONCURRENT_{idx}",
            "current_price": float(100 + idx),
            "currency": "MXN",
        }
        return repo.record_price(item)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(record_concurrent, i) for i in range(20)]
        results = [f.result() for f in futures]

    assert len(results) == 20
    tracked = repo.get_tracked_items()
    assert len(tracked) == 20
