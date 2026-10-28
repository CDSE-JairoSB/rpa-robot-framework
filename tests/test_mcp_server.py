"""Unit tests for WishlistMCPServer Model Context Protocol interface."""

from __future__ import annotations

import io
import json
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from libraries.PriceRepository import PriceRepository
from libraries.mcp_server import WishlistMCPServer


def test_mcp_list_tools():
    """Verifies that list_tools returns standardized MCP tool definitions."""
    server = WishlistMCPServer()
    tools = server.list_tools()
    tool_names = [t["name"] for t in tools]

    assert "run_wishlist" in tool_names
    assert "get_tracked_items" in tool_names
    assert "check_health" in tool_names

    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert tool["inputSchema"].get("type") == "object"
        assert "properties" in tool["inputSchema"]


def test_mcp_execute_check_health(tmp_path):
    """Verifies check_health tool returns status HEALTHY and diagnostic metadata."""
    db_file = tmp_path / "test_prices.db"
    status_file = tmp_path / "results" / "status.json"
    server = WishlistMCPServer(db_path=str(db_file), status_file=str(status_file))

    result = server.call_tool("check_health", {})
    assert result["status"] == "HEALTHY"
    assert "database" in result
    assert result["database"]["connected"] is True
    assert result["database"]["tracked_count"] == 0
    assert "status_file" in result
    assert result["status_file"]["exists"] is False


def test_mcp_execute_check_health_with_status_file(tmp_path):
    """Verifies check_health inspects execution status file when available."""
    db_file = tmp_path / "prices.db"
    status_file = tmp_path / "status.json"
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(
        json.dumps({"status": "OK_UPDATED", "total_items": 5, "drops_found": []}),
        encoding="utf-8",
    )

    server = WishlistMCPServer(db_path=str(db_file), status_file=str(status_file))
    result = server.call_tool("check_health", {})
    assert result["status"] == "HEALTHY"
    assert result["status_file"]["exists"] is True
    assert result["status_file"]["last_status"] == "OK_UPDATED"
    assert result["status_file"]["total_items"] == 5


def test_mcp_execute_get_tracked_items_empty(tmp_path):
    """Verifies get_tracked_items returns empty list when no items are tracked."""
    db_file = tmp_path / "prices.db"
    server = WishlistMCPServer(db_path=str(db_file))

    result = server.call_tool("get_tracked_items", {})
    assert result["status"] == "SUCCESS"
    assert result["count"] == 0
    assert result["items"] == []


def test_mcp_execute_get_tracked_items_populated(tmp_path):
    """Verifies get_tracked_items returns recorded products."""
    db_file = tmp_path / "prices.db"
    repo = PriceRepository(db_path=str(db_file))
    repo.record_price({
        "asin": "B01N5IB20Q",
        "title": "Echo Dot 5th Gen",
        "url": "https://amazon.com.mx/dp/B01N5IB20Q",
        "current_price": 999.00,
        "currency": "MXN",
    })
    repo.record_price({
        "asin": "B084DCJKSL",
        "title": "Kindle Paperwhite",
        "url": "https://amazon.com.mx/dp/B084DCJKSL",
        "current_price": 2499.00,
        "currency": "MXN",
    })

    server = WishlistMCPServer(db_path=str(db_file), repository=repo)
    result = server.call_tool("get_tracked_items", {})
    assert result["status"] == "SUCCESS"
    assert result["count"] == 2
    asins = [it["asin"] for it in result["items"]]
    assert "B01N5IB20Q" in asins
    assert "B084DCJKSL" in asins


def test_mcp_execute_get_tracked_items_filter_asin(tmp_path):
    """Verifies get_tracked_items filters by specific ASIN when requested."""
    db_file = tmp_path / "prices.db"
    repo = PriceRepository(db_path=str(db_file))
    repo.record_price({
        "asin": "B01N5IB20Q",
        "title": "Echo Dot 5th Gen",
        "url": "https://amazon.com.mx/dp/B01N5IB20Q",
        "current_price": 999.00,
    })
    repo.record_price({
        "asin": "B084DCJKSL",
        "title": "Kindle Paperwhite",
        "url": "https://amazon.com.mx/dp/B084DCJKSL",
        "current_price": 2499.00,
    })

    server = WishlistMCPServer(db_path=str(db_file), repository=repo)
    result = server.call_tool("get_tracked_items", {"asin": "B01N5IB20Q"})
    assert result["status"] == "SUCCESS"
    assert result["count"] == 1
    assert result["items"][0]["asin"] == "B01N5IB20Q"
    assert result["items"][0]["title"] == "Echo Dot 5th Gen"


def test_mcp_execute_run_wishlist_custom_runner():
    """Verifies run_wishlist invokes configured runner callback with arguments."""
    mock_runner = MagicMock(return_value={"pid": 1234, "status": "running"})
    server = WishlistMCPServer(runner_callback=mock_runner)

    result = server.call_tool("run_wishlist", {"headless": True})
    assert result["status"] == "TRIGGERED"
    assert result["headless"] is True
    assert result["runner_result"] == {"pid": 1234, "status": "running"}
    mock_runner.assert_called_once_with(headless=True)


def test_mcp_execute_run_wishlist_default_runner():
    """Verifies run_wishlist triggers subprocess when no custom callback is supplied."""
    server = WishlistMCPServer()

    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 9876
        mock_popen.return_value = mock_proc

        result = server.call_tool("run_wishlist", {"headless": False})
        assert result["status"] == "TRIGGERED"
        assert result["headless"] is False
        assert result["pid"] == 9876
        mock_popen.assert_called_once()


def test_mcp_execute_unknown_tool():
    """Verifies call_tool raises ValueError when tool name is unknown."""
    server = WishlistMCPServer()
    with pytest.raises(ValueError, match="Unknown tool: non_existent_tool"):
        server.call_tool("non_existent_tool", {})


def test_mcp_json_rpc_initialize():
    """Verifies JSON-RPC 2.0 initialize method handler."""
    server = WishlistMCPServer()
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }
    response = server.handle_json_rpc(request)
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert response["result"]["protocolVersion"] == "2024-11-05"
    assert "tools" in response["result"]["capabilities"]
    assert response["result"]["serverInfo"]["name"] == "amazon-wishlist-mcp-server"


def test_mcp_json_rpc_tools_list():
    """Verifies JSON-RPC 2.0 tools/list request returns MCP tool list."""
    server = WishlistMCPServer()
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    response = server.handle_json_rpc(request)
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 2
    assert "tools" in response["result"]
    tool_names = [t["name"] for t in response["result"]["tools"]]
    assert "run_wishlist" in tool_names
    assert "get_tracked_items" in tool_names
    assert "check_health" in tool_names


def test_mcp_json_rpc_tools_call():
    """Verifies JSON-RPC 2.0 tools/call execution returns MCP content payload."""
    server = WishlistMCPServer()
    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "check_health",
            "arguments": {},
        },
    }
    response = server.handle_json_rpc(request)
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 3
    result = response["result"]
    assert result["isError"] is False
    assert len(result["content"]) == 1
    assert result["content"][0]["type"] == "text"

    parsed_body = json.loads(result["content"][0]["text"])
    assert parsed_body["status"] == "HEALTHY"


def test_mcp_json_rpc_tools_call_unknown():
    """Verifies JSON-RPC 2.0 tools/call with unknown tool returns MCP error object."""
    server = WishlistMCPServer()
    request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "non_existent_tool",
            "arguments": {},
        },
    }
    response = server.handle_json_rpc(request)
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 4
    result = response["result"]
    assert result["isError"] is True
    assert "Unknown tool" in result["content"][0]["text"]


def test_mcp_json_rpc_parse_error():
    """Verifies handling of invalid JSON strings with parse error code -32700."""
    server = WishlistMCPServer()
    response = server.handle_json_rpc("{invalid-json")
    assert response["jsonrpc"] == "2.0"
    assert response["id"] is None
    assert response["error"]["code"] == -32700


def test_mcp_json_rpc_method_not_found():
    """Verifies handling of unsupported methods with error code -32601."""
    server = WishlistMCPServer()
    request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "unknown/method",
        "params": {},
    }
    response = server.handle_json_rpc(request)
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 5
    assert response["error"]["code"] == -32601


def test_mcp_stdio_stream_dispatch():
    """Verifies stdio stream processing over input/output text streams."""
    server = WishlistMCPServer()
    req_obj = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/list",
        "params": {},
    }
    input_stream = io.StringIO(json.dumps(req_obj) + "\n")
    output_stream = io.StringIO()

    server.process_stdio_stream(input_stream=input_stream, output_stream=output_stream, run_once=True)

    output_lines = [line.strip() for line in output_stream.getvalue().splitlines() if line.strip()]
    assert len(output_lines) == 1
    resp = json.loads(output_lines[0])
    assert resp["id"] == 10
    assert "tools" in resp["result"]
