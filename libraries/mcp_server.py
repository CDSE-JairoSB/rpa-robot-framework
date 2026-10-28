"""Model Context Protocol (MCP) Server Interface for Autonomous RPA Platform.

Provides a lightweight, zero-dependency MCP server conforming to the 
Model Context Protocol specification (2024-11-05). Exposes standardized tool 
schemas and JSON-RPC dispatching over stdio or programmatic calls for:
- `run_wishlist`: Triggers the Amazon Wishlist scraping automation.
- `get_tracked_items`: Queries tracked products and price histories from SQLite.
- `check_health`: Assesses operational health of database, status files, and runtime.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, Union

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from libraries.PriceRepository import PriceRepository

DEFAULT_DB_PATH = os.path.join(ROOT_DIR, "data", "prices.db")
DEFAULT_STATUS_FILE = os.path.join(ROOT_DIR, "results", "status.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mcp_server")


def default_task_runner(headless: bool = True) -> subprocess.Popen:
    """Launches the Amazon wishlist Robot Framework task as a background subprocess."""
    robot_task = os.path.join(ROOT_DIR, "tasks", "amazon", "wishlist_amazon_price_updater.robot")
    cmd = [
        sys.executable,
        "-m",
        "robot",
        "-d",
        "results",
        "--variable",
        f"BROWSER_HEADLESS:{str(headless).lower()}",
        robot_task,
    ]
    logger.info("Launching default task runner: %s", " ".join(cmd))
    return subprocess.Popen(cmd, cwd=ROOT_DIR)


class WishlistMCPServer:
    """Lightweight Model Context Protocol (MCP) Server for Amazon Wishlist RPA."""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    SERVER_NAME = "amazon-wishlist-mcp-server"
    SERVER_VERSION = "1.0.0"
    MCP_PROTOCOL_VERSION = "2024-11-05"

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        status_file: str = DEFAULT_STATUS_FILE,
        repository: Optional[PriceRepository] = None,
        runner_callback: Optional[Callable[..., Any]] = None,
        server_name: Optional[str] = None,
        server_version: Optional[str] = None,
    ) -> None:
        """Initializes the MCP Server.

        Args:
            db_path: Path to the SQLite database file.
            status_file: Path to results/status.json execution file.
            repository: Optional PriceRepository instance.
            runner_callback: Optional callable to trigger automation runs.
            server_name: Custom server identifier for initialize handshake.
            server_version: Custom server version.
        """
        self.db_path = db_path
        self.status_file = status_file
        self._repository = repository
        self.runner_callback = runner_callback
        self.server_name = server_name or self.SERVER_NAME
        self.server_version = server_version or self.SERVER_VERSION

    @property
    def repository(self) -> PriceRepository:
        """Returns or lazily instantiates the PriceRepository."""
        if self._repository is None:
            self._repository = PriceRepository(db_path=self.db_path)
        return self._repository

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns standardized MCP tool definitions matching the MCP specification."""
        return [
            {
                "name": "run_wishlist",
                "description": (
                    "Trigger the Amazon Wishlist price scraper automation in headless or visual mode. "
                    "Extracts current prices, detects discounts, and updates the SQLite repository."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "headless": {
                            "type": "boolean",
                            "description": "Run browser in headless mode (default: true).",
                            "default": True,
                        }
                    },
                },
            },
            {
                "name": "get_tracked_items",
                "description": (
                    "Retrieve all tracked products, their latest prices, lowest recorded prices, "
                    "and historical observations from the SQLite repository."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "asin": {
                            "type": "string",
                            "description": "Optional specific Amazon ASIN to filter or inspect.",
                        }
                    },
                },
            },
            {
                "name": "check_health",
                "description": (
                    "Check the operational health and readiness of the RPA platform, "
                    "including SQLite database connectivity, tracked product metrics, "
                    "and status file availability."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes a registered tool handler and returns structured result data.

        Args:
            name: Tool name identifier.
            arguments: Optional dictionary of arguments provided by the client.

        Returns:
            Dictionary containing the tool output payload.

        Raises:
            ValueError: If the requested tool name is not recognized.
        """
        args = arguments or {}

        if name == "check_health":
            return self._handle_check_health(args)
        elif name == "get_tracked_items":
            return self._handle_get_tracked_items(args)
        elif name == "run_wishlist":
            return self._handle_run_wishlist(args)
        else:
            raise ValueError(f"Unknown tool: {name}")

    def _handle_check_health(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Internal handler for check_health tool."""
        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        db_connected = False
        tracked_count = 0
        db_error = None

        try:
            items = self.repository.get_tracked_items()
            tracked_count = len(items)
            db_connected = True
        except Exception as err:
            db_error = str(err)
            logger.warning("Database health check error: %s", err)

        status_info: Dict[str, Any] = {
            "exists": False,
            "path": self.status_file,
        }

        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, "r", encoding="utf-8") as f:
                    status_data = json.load(f)
                status_info.update({
                    "exists": True,
                    "last_status": status_data.get("status"),
                    "total_items": status_data.get("total_items", 0),
                    "timestamp": status_data.get("timestamp"),
                })
            except Exception as err:
                status_info["read_error"] = str(err)

        overall_status = "HEALTHY" if db_connected else "UNHEALTHY"

        result: Dict[str, Any] = {
            "status": overall_status,
            "timestamp": now_iso,
            "server": {
                "name": self.server_name,
                "version": self.server_version,
            },
            "database": {
                "connected": db_connected,
                "path": self.db_path,
                "tracked_count": tracked_count,
            },
            "status_file": status_info,
        }
        if db_error:
            result["database"]["error"] = db_error

        return result

    def _handle_get_tracked_items(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Internal handler for get_tracked_items tool."""
        target_asin = args.get("asin")
        all_items = self.repository.get_tracked_items()

        if target_asin:
            clean_asin = str(target_asin).strip().upper()
            filtered = [it for it in all_items if str(it.get("asin", "")).strip().upper() == clean_asin]
            # Attach price history when a specific ASIN is queried
            for it in filtered:
                asin = it.get("asin")
                if asin:
                    it["price_history"] = self.repository.get_price_history(asin)
            items_to_return = filtered
        else:
            items_to_return = all_items

        return {
            "status": "SUCCESS",
            "count": len(items_to_return),
            "items": items_to_return,
        }

    def _handle_run_wishlist(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Internal handler for run_wishlist tool."""
        headless = bool(args.get("headless", True))

        if self.runner_callback is not None:
            try:
                runner_res = self.runner_callback(headless=headless)
            except TypeError:
                runner_res = self.runner_callback()

            res_payload: Dict[str, Any] = {
                "status": "TRIGGERED",
                "message": "Wishlist scraper triggered via custom runner callback",
                "headless": headless,
                "runner_result": runner_res,
            }
            if hasattr(runner_res, "pid"):
                res_payload["pid"] = runner_res.pid
            elif isinstance(runner_res, dict) and "pid" in runner_res:
                res_payload["pid"] = runner_res["pid"]
            return res_payload

        # Default subprocess runner
        proc = default_task_runner(headless=headless)
        return {
            "status": "TRIGGERED",
            "message": "Wishlist scraper triggered via default background process",
            "headless": headless,
            "pid": proc.pid if hasattr(proc, "pid") else None,
        }

    def handle_json_rpc(self, request: Union[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Processes a single JSON-RPC 2.0 request per the MCP specification.

        Args:
            request: JSON string or parsed dictionary representing a JSON-RPC message.

        Returns:
            JSON-RPC response dictionary, or None if the request was a notification.
        """
        if isinstance(request, str):
            try:
                req_obj = json.loads(request)
            except Exception as err:
                return {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {err}",
                    },
                }
        else:
            req_obj = request

        if not isinstance(req_obj, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: expected JSON object",
                },
            }

        req_id = req_obj.get("id")
        method = req_obj.get("method")
        params = req_obj.get("params") or {}

        # Handle notifications without ID
        is_notification = "id" not in req_obj

        if not method or not isinstance(method, str):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: missing or invalid method string",
                },
            }

        # Handshake / initialize
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": self.MCP_PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {
                        "name": self.server_name,
                        "version": self.server_version,
                    },
                },
            }

        # Initialized notification
        if method in ("notifications/initialized", "initialized"):
            return None

        # Ping
        if method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {},
            }

        # Tool discovery
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.list_tools(),
                },
            }

        # Tool execution
        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments") or {}

            if not tool_name:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32602,
                        "message": "Invalid params: missing tool name",
                    },
                }

            try:
                output = self.call_tool(tool_name, tool_args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(output, indent=2, ensure_ascii=False),
                            }
                        ],
                        "isError": False,
                    },
                }
            except Exception as err:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error executing tool '{tool_name}': {err}",
                            }
                        ],
                        "isError": True,
                    },
                }

        # Method not found
        if is_notification:
            return None

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }

    def process_stdio_stream(
        self,
        input_stream: Any = sys.stdin,
        output_stream: Any = sys.stdout,
        run_once: bool = False,
    ) -> None:
        """Reads JSON-RPC messages from input_stream and writes responses to output_stream.

        Supports both newline-delimited JSON (NDJSON) and Content-Length framed JSON-RPC.
        """
        while True:
            line = input_stream.readline()
            if not line:
                break
            line_str = line.strip()
            if not line_str:
                continue

            if line_str.lower().startswith("content-length:"):
                try:
                    length = int(line_str.split(":", 1)[1].strip())
                    while True:
                        sep = input_stream.readline()
                        if sep.strip() == "":
                            break
                    body = input_stream.read(length)
                    response = self.handle_json_rpc(body)
                    if response is not None:
                        resp_str = json.dumps(response, ensure_ascii=False)
                        resp_bytes = resp_str.encode("utf-8")
                        output_stream.write(f"Content-Length: {len(resp_bytes)}\r\n\r\n{resp_str}")
                        output_stream.flush()
                except Exception as err:
                    logger.error("Error processing framed stream: %s", err)
            else:
                response = self.handle_json_rpc(line_str)
                if response is not None:
                    output_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
                    output_stream.flush()

            if run_once:
                break


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments for the MCP server."""
    parser = argparse.ArgumentParser(
        description="Amazon Wishlist Model Context Protocol (MCP) Server",
    )
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite prices database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--status-file",
        default=DEFAULT_STATUS_FILE,
        help=f"Path to status.json execution file (default: {DEFAULT_STATUS_FILE})",
    )
    parser.add_argument(
        "--stdio",
        action="store_true",
        default=True,
        help="Run server in stdio mode (default)",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for running the MCP server standalone."""
    args = parse_args()
    server = WishlistMCPServer(
        db_path=args.db_path,
        status_file=args.status_file,
    )
    logger.info("Starting WishlistMCPServer over stdio...")
    server.process_stdio_stream()


if __name__ == "__main__":
    main()
