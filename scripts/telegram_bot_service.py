#!/usr/bin/env python3
"""Interactive Telegram Bot Daemon Service for Autonomous RPA Platform.

Provides long-polling command handling (/status, /run, /login, /help)
with zero external dependencies (pure Python urllib), decoupled 2FA triggers,
and integration with SQLite PriceRepository and execution status files.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
import signal
import sys
import time
from typing import Any, Callable, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

# Ensure workspace root is in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from libraries.PriceRepository import PriceRepository
from libraries.TelegramNotifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("telegram_bot_service")


class TelegramBotService:
    """Daemon service that processes Telegram commands for the RPA platform."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        allowed_chat_ids: Optional[List[str]] = None,
        notifier: Optional[TelegramNotifier] = None,
        repository: Optional[PriceRepository] = None,
        status_file: str = "results/status.json",
        db_path: str = "data/prices.db",
        base_url: str = "https://api.telegram.org",
        runner_callback: Optional[Callable[[], Any]] = None,
        timeout: int = 30,
    ) -> None:
        """Initializes the bot service.

        Args:
            bot_token: Telegram bot token. Falls back to env TELEGRAM_BOT_TOKEN.
            allowed_chat_ids: Allowed chat IDs list. Falls back to env TELEGRAM_CHAT_ID.
            notifier: Optional TelegramNotifier instance.
            repository: Optional PriceRepository instance.
            status_file: Path to results/status.json.
            db_path: Path to SQLite prices database.
            base_url: Telegram API base URL.
            runner_callback: Optional callback invoked when /run is received.
            timeout: Long-polling HTTP timeout in seconds.
        """
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.status_file = status_file
        self.db_path = db_path
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.runner_callback = runner_callback
        self.is_running = False
        self.last_update_id = 0

        # Build allowed chat IDs set
        self.allowed_chat_ids: set[str] = set()
        if allowed_chat_ids:
            self.allowed_chat_ids = {str(cid).strip() for cid in allowed_chat_ids if str(cid).strip()}
        else:
            env_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
            if env_chat:
                self.allowed_chat_ids.add(env_chat)
            env_allowed = os.environ.get("TELEGRAM_ALLOWED_CHATS", "").strip()
            if env_allowed:
                for cid in env_allowed.split(","):
                    if cid.strip():
                        self.allowed_chat_ids.add(cid.strip())

        # Initialize notifier
        self.notifier = notifier or TelegramNotifier(
            bot_token=self.bot_token,
            chat_id=next(iter(self.allowed_chat_ids)) if self.allowed_chat_ids else None,
            base_url=self.base_url,
        )

        # Lazy-loaded repository
        self._repository = repository

    @property
    def repository(self) -> PriceRepository:
        """Returns or creates the PriceRepository instance."""
        if self._repository is None:
            self._repository = PriceRepository(db_path=self.db_path)
        return self._repository

    def is_authorized(self, chat_id: str) -> bool:
        """Checks if a chat_id is allowed to execute bot commands."""
        if not self.allowed_chat_ids:
            # If no whitelist is set, allow all for development/testing
            return True
        return str(chat_id).strip() in self.allowed_chat_ids

    def handle_help(self, chat_id: str, args: List[str]) -> str:
        """Returns help documentation for all available commands."""
        return (
            "🤖 *Comandos disponibles en el Bot RPA Amazon*\n\n"
            "• `/status` - Consulta el estado del último rastreo y métricas de la base de datos\n"
            "• `/run` - Dispara manualmente el rastreo de la wishlist de Amazon\n"
            "• `/login` - Inicia el flujo interactivo de reautenticación 2FA / cookies\n"
            "• `/help` - Muestra esta ayuda con los comandos soportados"
        )

    def handle_status(self, chat_id: str, args: List[str]) -> str:
        """Returns the latest execution status and SQLite repository metrics."""
        summary: Dict[str, Any] = {}
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, "r", encoding="utf-8") as f:
                    summary = json.load(f)
            except Exception as err:
                logger.warning("Could not read status file %s: %s", self.status_file, err)

        if summary:
            msg = self.notifier.format_status_message(summary)
        else:
            # Fallback to database metrics if status.json is not present yet
            try:
                items = self.repository.get_tracked_items()
                total_items = len(items)
                msg = (
                    "📊 *Estado de Monitoreo Amazon*\n\n"
                    "ℹ️ No se encontró un archivo reciente de ejecución (`status.json`).\n"
                    f"📦 *Productos en base de datos:* {total_items}\n"
                    "💡 Utiliza `/run` para iniciar una ejecución desatendida."
                )
            except Exception as err:
                msg = (
                    "📊 *Estado de Monitoreo Amazon*\n\n"
                    f"⚠️ Sin ejecuciones recientes registradas.\n"
                    f"Detalle: {err}"
                )

        return msg

    def handle_run(self, chat_id: str, args: List[str]) -> str:
        """Dispatches an unattended scraping run."""
        logger.info("Executing /run command requested by chat %s", chat_id)
        if self.runner_callback:
            try:
                result = self.runner_callback()
                logger.info("Runner callback executed with result: %s", result)
            except Exception as err:
                logger.error("Runner callback failed: %s", err)
                return f"❌ *Error al ejecutar el rastreador:* {err}"

        return (
            "🚀 *Iniciando ejecución de monitoreo de wishlist...*\n\n"
            "El proceso desatendido ha sido disparado. Al finalizar, "
            "se registrarán los precios y recibirás alertas si se detectan bajadas."
        )

    def handle_login(self, chat_id: str, args: List[str]) -> str:
        """Acknowledges decoupled 2FA / interactive re-authentication request."""
        logger.info("Decoupled 2FA re-auth requested by chat %s", chat_id)
        return (
            "🔐 *Flujo de reautenticación 2FA iniciado*\n\n"
            "Por favor verifica si recibiste una notificación en tu app de Amazon o código OTP.\n"
            "El perfil persistente de Chrome se actualizará automáticamente con las nuevas cookies de sesión "
            "para reanudar los monitoreos desatendidos 24/7."
        )

    def process_message(self, chat_id: str, text: str) -> str:
        """Processes an incoming message text from a specific chat.

        Args:
            chat_id: Sender chat ID.
            text: Message body.

        Returns:
            Response text to be sent to the user.
        """
        if not self.is_authorized(chat_id):
            logger.warning("Unauthorized access attempt from chat_id %s", chat_id)
            return "⛔ *Acceso denegado.* Tu ID de usuario no está autorizado para operar este bot."

        clean_text = text.strip()
        if not clean_text:
            return self.handle_help(chat_id, [])

        parts = clean_text.split()
        command = parts[0].lower().split("@")[0]  # Strip bot handle if present (e.g. /status@my_bot)
        args = parts[1:]

        if command in ("/status", "status"):
            return self.handle_status(chat_id, args)
        elif command in ("/run", "run"):
            return self.handle_run(chat_id, args)
        elif command in ("/login", "login"):
            return self.handle_login(chat_id, args)
        elif command in ("/help", "/start", "help"):
            return self.handle_help(chat_id, args)
        else:
            return (
                f"❓ Comando `{command}` no reconocido.\n\n"
                "Usa `/help` para consultar los comandos disponibles."
            )

    def get_updates(self, offset: Optional[int] = None, timeout: int = 30) -> List[Dict[str, Any]]:
        """Retrieves new updates via Telegram Bot API getUpdates method.

        Args:
            offset: Identifier of the first update to be returned.
            timeout: Timeout in seconds for long polling.

        Returns:
            List of update dictionaries.
        """
        if not self.bot_token:
            logger.warning("get_updates called without bot_token configured.")
            return []

        params: Dict[str, Any] = {"timeout": timeout}
        if offset is not None and offset > 0:
            params["offset"] = offset

        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}/bot{self.bot_token}/getUpdates?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "AutonomousRPA-Bot/1.0"})

        try:
            with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    return data.get("result", [])
                return []
        except Exception as err:
            logger.warning("Error during getUpdates: %s", err)
            return []

    def poll_once(self, timeout: int = 1) -> int:
        """Polls for new updates once and processes incoming messages.

        Args:
            timeout: Polling timeout in seconds.

        Returns:
            Count of updates processed.
        """
        updates = self.get_updates(offset=self.last_update_id, timeout=timeout)
        processed_count = 0

        for update in updates:
            update_id = update.get("update_id", 0)
            self.last_update_id = max(self.last_update_id, update_id + 1)
            processed_count += 1

            message = update.get("message") or update.get("edited_message")
            if not message:
                continue

            chat = message.get("chat", {})
            chat_id = str(chat.get("id", ""))
            text = message.get("text", "")

            if not text or not chat_id:
                continue

            response = self.process_message(chat_id=chat_id, text=text)
            if response:
                self.notifier.send_message(response, chat_id=chat_id)

        return processed_count

    def run_forever(self, poll_interval: float = 1.0) -> None:
        """Runs the long-polling loop indefinitely until interrupted."""
        self.is_running = True
        logger.info("Telegram Bot Service started. Listening for commands...")

        def _handle_exit(signum: int, frame: Any) -> None:
            logger.info("Exit signal received (%s). Stopping bot service...", signum)
            self.is_running = False

        signal.signal(signal.SIGINT, _handle_exit)
        signal.signal(signal.SIGTERM, _handle_exit)

        while self.is_running:
            try:
                self.poll_once(timeout=self.timeout)
            except Exception as err:
                logger.error("Unhandled error in polling loop: %s", err)
                time.sleep(3.0)

            if poll_interval > 0 and self.is_running:
                time.sleep(poll_interval)

        logger.info("Telegram Bot Service stopped cleanly.")


def parse_args() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous RPA Telegram Interactive Bot Service"
    )
    parser.add_argument(
        "--token",
        dest="bot_token",
        default=os.getenv("TELEGRAM_BOT_TOKEN"),
        help="Telegram Bot Token",
    )
    parser.add_argument(
        "--chat-id",
        dest="chat_id",
        default=os.getenv("TELEGRAM_CHAT_ID"),
        help="Allowed Telegram Chat ID (comma separated for multiple)",
    )
    parser.add_argument(
        "--status-file",
        default="results/status.json",
        help="Path to execution status.json file",
    )
    parser.add_argument(
        "--db-path",
        default="data/prices.db",
        help="Path to SQLite prices.db",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run polling cycle once and exit",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Interval between poll calls (seconds)",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point for running the bot service."""
    args = parse_args()
    allowed_chats = [c.strip() for c in args.chat_id.split(",")] if args.chat_id else []

    service = TelegramBotService(
        bot_token=args.bot_token,
        allowed_chat_ids=allowed_chats,
        status_file=args.status_file,
        db_path=args.db_path,
    )

    if args.once:
        count = service.poll_once(timeout=2)
        logger.info("Processed %d updates in single-poll mode.", count)
    else:
        service.run_forever(poll_interval=args.interval)


if __name__ == "__main__":
    main()
