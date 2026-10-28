"""Unit tests for TelegramNotifier and telegram_bot_service."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from libraries.TelegramNotifier import TelegramNotifier
from scripts.telegram_bot_service import TelegramBotService


def test_format_price_drop_message():
    notifier = TelegramNotifier(bot_token="dummy", chat_id="12345")
    item = {
        "title": "PlayStation 5 Console",
        "current_price": 9999.00,
        "previous_price": 11999.00,
        "lowest_price": 9999.00,
        "drop_percentage": 16.67,
        "currency": "MXN",
        "url": "https://amazon.com.mx/dp/B08N5WRWNW",
    }
    msg = notifier.format_price_drop_message(item)
    assert "🔥 *¡Bajada de precio detectada!*" in msg
    assert "PlayStation 5 Console" in msg
    assert "$9,999.00 MXN" in msg
    assert "16.7%" in msg
    assert "https://amazon.com.mx/dp/B08N5WRWNW" in msg


def test_format_needs_2fa_alert():
    notifier = TelegramNotifier(bot_token="dummy", chat_id="12345")
    msg = notifier.format_needs_2fa_alert()
    assert "/login" in msg
    assert "2FA" in msg


def test_format_price_drop_with_minimal_fields():
    notifier = TelegramNotifier(bot_token="dummy", chat_id="12345")
    item = {
        "title": "Minimal Item",
        "current_price": 150.0,
    }
    msg = notifier.format_price_drop_message(item)
    assert "🔥 *¡Bajada de precio detectada!*" in msg
    assert "Minimal Item" in msg
    assert "$150.00 MXN" in msg


def test_format_price_drop_escapes_markdown_title():
    notifier = TelegramNotifier(bot_token="dummy", chat_id="12345")
    item = {
        "title": "[Special Edition_v2] *Bonus*",
        "current_price": 499.00,
        "currency": "MXN",
    }
    msg = notifier.format_price_drop_message(item)
    # Ensure markdown delimiters are escaped to prevent Telegram 400 Bad Request
    assert r"\[Special Edition\_v2] \*Bonus\*" in msg


def test_format_status_message():
    notifier = TelegramNotifier(bot_token="dummy", chat_id="12345")
    summary = {
        "status": "OK_UPDATED",
        "total_items": 12,
        "drops_found": [{"asin": "B123"}],
        "timestamp": "2026-10-27T21:00:00Z",
    }
    msg = notifier.format_status_message(summary)
    assert "OK_UPDATED" in msg
    assert "12" in msg
    assert "1" in msg


def test_escape_markdown_and_html():
    notifier = TelegramNotifier(bot_token="dummy", chat_id="12345")
    raw_text = "Special <tags> & _bold* [links]"
    escaped_html = notifier.escape_html(raw_text)
    assert "&lt;tags&gt;" in escaped_html
    assert "&amp;" in escaped_html

    escaped_md = notifier.escape_markdown_v2("Price: $10.00! [Check]")
    assert r"\." in escaped_md
    assert r"\!" in escaped_md
    assert r"\[" in escaped_md

    escaped_v2_backslash = notifier.escape_markdown_v2(r"C:\User\test")
    assert r"\\" in escaped_v2_backslash
    escaped_v1_backslash = notifier.escape_markdown(r"C:\User\test")
    assert r"\\" in escaped_v1_backslash


@patch("urllib.request.urlopen")
def test_send_message_success(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"ok": True, "result": {"message_id": 999}}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    notifier = TelegramNotifier(bot_token="test_token", chat_id="12345")
    result = notifier.send_message("Hola Telegram")
    assert result is True

    # Verify request payload
    assert mock_urlopen.called
    req = mock_urlopen.call_args[0][0]
    assert "api.telegram.org/bottest_token/sendMessage" in req.full_url
    body = json.loads(req.data.decode("utf-8"))
    assert body["chat_id"] == "12345"
    assert body["text"] == "Hola Telegram"


@patch("urllib.request.urlopen")
def test_send_message_failure_handles_exception(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")

    notifier = TelegramNotifier(bot_token="test_token", chat_id="12345")
    result = notifier.send_message("Mensaje de prueba")
    assert result is False


def test_send_message_missing_credentials():
    notifier = TelegramNotifier(bot_token="", chat_id="")
    result = notifier.send_message("Test")
    assert result is False


@patch.object(TelegramNotifier, "send_message")
def test_send_alert(mock_send):
    mock_send.return_value = True
    notifier = TelegramNotifier(bot_token="test_token", chat_id="12345")
    item = {
        "title": "SSD 1TB",
        "current_price": 1200.0,
        "previous_price": 1500.0,
        "drop_percentage": 20.0,
        "currency": "MXN",
        "url": "https://amazon.com.mx/dp/B001",
    }
    success = notifier.send_alert(item)
    assert success is True
    assert mock_send.called
    sent_text = mock_send.call_args[0][0]
    assert "SSD 1TB" in sent_text
    assert "$1,200.00 MXN" in sent_text


@patch.object(TelegramNotifier, "send_message")
def test_send_2fa_alert(mock_send):
    mock_send.return_value = True
    notifier = TelegramNotifier(bot_token="test_token", chat_id="12345")
    success = notifier.send_2fa_alert()
    assert success is True
    assert mock_send.called
    sent_text = mock_send.call_args[0][0]
    assert "/login" in sent_text
    assert "2FA" in sent_text


# Tests for scripts/telegram_bot_service.py

def test_bot_service_handle_help():
    bot = TelegramBotService(bot_token="dummy", allowed_chat_ids=["12345"])
    response = bot.handle_help(chat_id="12345", args=[])
    assert "/status" in response
    assert "/run" in response
    assert "/login" in response
    assert "/help" in response


def test_bot_service_handle_status_with_file(tmp_path):
    status_file = tmp_path / "status.json"
    status_file.write_text(
        json.dumps({
            "status": "OK_UPDATED",
            "total_items": 5,
            "drops_found": [{"asin": "B1"}],
            "timestamp": "2026-10-27T20:00:00Z",
        }),
        encoding="utf-8",
    )

    bot = TelegramBotService(bot_token="dummy", allowed_chat_ids=["12345"], status_file=str(status_file))
    response = bot.handle_status(chat_id="12345", args=[])
    assert "OK_UPDATED" in response
    assert "5" in response


def test_bot_service_handle_run_triggers_runner():
    runner_called = []

    def mock_runner():
        runner_called.append(True)
        return {"status": "OK_UPDATED"}

    bot = TelegramBotService(
        bot_token="dummy",
        allowed_chat_ids=["12345"],
        runner_callback=mock_runner,
    )
    response = bot.handle_run(chat_id="12345", args=[])
    assert "Iniciando" in response or "ejecución" in response.lower()
    assert len(runner_called) == 1


def test_bot_service_handle_run_no_runner_configured():
    bot = TelegramBotService(bot_token="dummy", allowed_chat_ids=["12345"], runner_callback=None)
    response = bot.handle_run(chat_id="12345", args=[])
    assert "no disponible" in response.lower() or "no hay un runner" in response.lower()


def test_bot_service_handle_run_runner_exception_sanitized():
    def failing_runner():
        raise RuntimeError("Crash with [unclosed tag and _delimiters_")

    bot = TelegramBotService(bot_token="dummy", allowed_chat_ids=["12345"], runner_callback=failing_runner)
    response = bot.handle_run(chat_id="12345", args=[])
    assert "Error al ejecutar" in response
    assert r"\[unclosed" in response
    assert r"\_delimiters\_" in response


@patch("subprocess.Popen")
def test_default_task_runner(mock_popen):
    from scripts.telegram_bot_service import default_task_runner
    mock_popen.return_value = MagicMock()
    proc = default_task_runner()
    assert mock_popen.called
    cmd = mock_popen.call_args[0][0]
    assert "robot" in cmd
    assert "tasks/amazon/wishlist_amazon_price_updater.robot" in cmd[-1]


def test_bot_service_handle_login():
    bot = TelegramBotService(bot_token="dummy", allowed_chat_ids=["12345"])
    response = bot.handle_login(chat_id="12345", args=[])
    assert "2FA" in response or "autenticación" in response.lower()
    assert "cookies" in response.lower() or "sesión" in response.lower()


def test_bot_service_unauthorized_user():
    bot = TelegramBotService(bot_token="dummy", allowed_chat_ids=["12345"])
    response = bot.process_message(chat_id="99999", text="/status")
    assert "no autorizado" in response.lower() or "acceso denegado" in response.lower()


@patch("urllib.request.urlopen")
def test_bot_service_poll_updates(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "ok": True,
        "result": [
            {
                "update_id": 100,
                "message": {
                    "message_id": 1,
                    "chat": {"id": 12345},
                    "text": "/help",
                },
            }
        ],
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    mock_notifier = MagicMock()
    bot = TelegramBotService(
        bot_token="dummy",
        allowed_chat_ids=["12345"],
        notifier=mock_notifier,
    )
    processed_count = bot.poll_once(timeout=1)
    assert processed_count == 1
    assert bot.last_update_id == 101
    assert mock_notifier.send_message.called
