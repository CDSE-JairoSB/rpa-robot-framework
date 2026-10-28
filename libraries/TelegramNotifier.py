"""Telegram notification service for Amazon price tracking and 2FA alerts.

Provides zero-external-dependency Telegram Bot API HTTP integration,
Markdown/HTML escaping, and formatted price drop alerts.
"""

from __future__ import annotations

from datetime import datetime, timezone
import html
import json
import logging
import os
import re
from typing import Any, Dict, Optional
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Manages Telegram Bot notifications for price drops and human-in-the-loop alerts."""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        base_url: str = "https://api.telegram.org",
        timeout: int = 15,
    ) -> None:
        """Initializes the Telegram notifier.

        Args:
            bot_token: Telegram bot token. Falls back to TELEGRAM_BOT_TOKEN env var.
            chat_id: Telegram chat ID. Falls back to TELEGRAM_CHAT_ID env var.
            base_url: Base Telegram Bot API endpoint.
            timeout: HTTP request timeout in seconds.
        """
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = str(chat_id) if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def escape_html(text: str) -> str:
        """Escapes text for Telegram HTML mode."""
        return html.escape(str(text), quote=True)

    @staticmethod
    def escape_markdown_v2(text: str) -> str:
        """Escapes special characters for Telegram MarkdownV2 mode."""
        return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(text))

    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escapes special characters for Telegram legacy Markdown mode."""
        return re.sub(r"([_*`\[])", r"\\\1", str(text))

    def format_price_drop_message(self, item: Dict[str, Any]) -> str:
        """Formats a structured price drop notification message.

        Args:
            item: Dictionary containing product drop details:
                  'title', 'current_price', 'previous_price', 'lowest_price',
                  'drop_percentage', 'currency', 'url'.

        Returns:
            Formatted notification string with Markdown formatting.
        """
        title = str(item.get("title", "Artículo sin título")).strip()
        currency = str(item.get("currency", "MXN")).strip()
        current_price = float(item.get("current_price", 0.0))
        previous_price = item.get("previous_price")
        lowest_price = item.get("lowest_price")
        drop_pct = float(item.get("drop_percentage", 0.0))
        url = str(item.get("url", "")).strip()

        lines = [
            "🔥 *¡Bajada de precio detectada!*",
            "",
            f"📦 *Producto:* {title}",
            f"💰 *Precio actual:* ${current_price:,.2f} {currency}",
        ]

        if previous_price is not None:
            prev_val = float(previous_price)
            lines.append(f"🏷️ *Precio anterior:* ${prev_val:,.2f} {currency}")

        if lowest_price is not None and float(lowest_price) != current_price:
            lowest_val = float(lowest_price)
            lines.append(f"⭐ *Mínimo histórico previo:* ${lowest_val:,.2f} {currency}")

        lines.append(f"📉 *Descuento:* {drop_pct:.1f}%")

        if url:
            lines.append(f"🔗 *Enlace:* {url}")

        return "\n".join(lines)

    def format_needs_2fa_alert(self) -> str:
        """Formats a human-in-the-loop alert for 2FA / CAPTCHA session expiration.

        Returns:
            Formatted alert string containing instructions and /login command.
        """
        return (
            "⚠️ *¡Atención: Verificación de seguridad requerida (2FA)!*\n\n"
            "La sesión de Amazon requiere verificación en dos pasos (2FA) o aprobación de inicio de sesión.\n"
            "El proceso desatendido ha finalizado limpiamente para evitar bloqueos en el runner.\n\n"
            "Por favor ejecuta el comando /login en este chat cuando tengas tu dispositivo disponible "
            "para iniciar el flujo interactivo de reautenticación y actualizar las cookies persistentes."
        )

    def format_status_message(self, summary: Dict[str, Any]) -> str:
        """Formats an execution summary for operational status inquiries.

        Args:
            summary: Dictionary containing execution metrics:
                     'status', 'total_items', 'drops_found', and optional 'timestamp'.

        Returns:
            Formatted status report string.
        """
        status = str(summary.get("status", "UNKNOWN")).strip()
        total_items = int(summary.get("total_items", 0))
        drops = summary.get("drops_found", [])
        drops_count = len(drops) if isinstance(drops, list) else int(drops)
        timestamp = summary.get(
            "timestamp",
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

        status_icons = {
            "OK_UPDATED": "✅",
            "PRICE_UNCHANGED": "ℹ️",
            "STATUS_NEEDS_2FA": "⚠️",
            "RATE_LIMITED": "🛑",
            "ERROR_SELECTOR": "❌",
        }
        icon = status_icons.get(status, "📊")

        return (
            f"{icon} *Estado de Monitoreo Amazon*\n\n"
            f"📌 *Código de estado:* `{status}`\n"
            f"📦 *Total de artículos:* {total_items}\n"
            f"📉 *Bajadas detectadas:* {drops_count}\n"
            f"⏱️ *Última actualización:* {timestamp}"
        )

    def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: Optional[str] = "Markdown",
        disable_web_page_preview: bool = False,
    ) -> bool:
        """Sends a text message via Telegram Bot API using urllib standard library.

        Args:
            text: Message body to send.
            chat_id: Target Telegram chat ID (defaults to self.chat_id).
            parse_mode: 'Markdown', 'MarkdownV2', 'HTML', or None.
            disable_web_page_preview: Whether to disable URL rich preview.

        Returns:
            True if the message was accepted by Telegram (ok: True), False otherwise.
        """
        target_chat_id = str(chat_id) if chat_id is not None else self.chat_id
        if not self.bot_token or not target_chat_id:
            logger.warning(
                "Telegram message not sent: bot_token or chat_id is not configured."
            )
            return False

        url = f"{self.base_url}/bot{self.bot_token}/sendMessage"
        payload: Dict[str, Any] = {
            "chat_id": target_chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                res = json.loads(body)
                return bool(res.get("ok", False))
        except urllib.error.HTTPError as http_err:
            logger.error(
                "Telegram API HTTP error %d: %s",
                http_err.code,
                http_err.read().decode("utf-8", errors="ignore"),
            )
            return False
        except Exception as err:
            logger.error("Error sending Telegram message: %s", err)
            return False

    def send_alert(
        self,
        item: Dict[str, Any],
        chat_id: Optional[str] = None,
    ) -> bool:
        """Formats and sends a price drop alert.

        Args:
            item: Product price drop details dictionary.
            chat_id: Target chat ID (optional).

        Returns:
            True if sent successfully, False otherwise.
        """
        message = self.format_price_drop_message(item)
        return self.send_message(message, chat_id=chat_id)

    def send_2fa_alert(self, chat_id: Optional[str] = None) -> bool:
        """Formats and sends a 2FA authentication alert.

        Args:
            chat_id: Target chat ID (optional).

        Returns:
            True if sent successfully, False otherwise.
        """
        message = self.format_needs_2fa_alert()
        return self.send_message(message, chat_id=chat_id)

    def send_status_alert(
        self,
        summary: Dict[str, Any],
        chat_id: Optional[str] = None,
    ) -> bool:
        """Formats and sends an execution status summary alert.

        Args:
            summary: Summary dictionary.
            chat_id: Target chat ID (optional).

        Returns:
            True if sent successfully, False otherwise.
        """
        message = self.format_status_message(summary)
        return self.send_message(message, chat_id=chat_id)
