"""MCP client — load each server's tools independently; never crash on server-down."""
import asyncio
import os
import sys
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.core.logging import get_logger

log = get_logger(__name__)

_cache: dict[str, Any] = {"tools": None, "connected": None}
_lock = asyncio.Lock()


def _server_configs() -> dict:
    """
    Each server gets its own stdio connection. Environment is passed explicitly
    (sys.executable + os.environ) so the subprocess can read DATABASE_URL,
    QDRANT_URL, etc. — otherwise `Settings()` inside the subprocess fails.
    """
    env = dict(os.environ)
    return {
        "github": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "app.mcp_servers.github_server"],
            "env": env,
        },
        "repo_search": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "app.mcp_servers.repo_search_server"],
            "env": env,
        },
    }


async def load_tools() -> tuple[list[BaseTool], dict[str, bool]]:
    """Return (tools, connected_by_server). Cached after first call."""
    if _cache["tools"] is not None:
        return _cache["tools"], _cache["connected"]

    async with _lock:
        if _cache["tools"] is not None:
            return _cache["tools"], _cache["connected"]

        all_tools: list[BaseTool] = []
        connected: dict[str, bool] = {"github": False, "repo_search": False}

        for name, cfg in _server_configs().items():
            try:
                client = MultiServerMCPClient({name: cfg})
                tools = await client.get_tools()
                all_tools.extend(tools)
                connected[name] = True
                log.info(
                    "mcp_server_connected",
                    server=name,
                    tools=sorted(t.name for t in tools),
                )
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "mcp_server_down",
                    server=name,
                    exc_type=type(e).__name__,
                    exc_repr=repr(e)[:300],
                )

        names = sorted(t.name for t in all_tools)
        log.info(
            "mcp_tools_loaded",
            count=len(all_tools),
            names=names,
            connected=connected,
        )
        _cache["tools"] = all_tools
        _cache["connected"] = connected
        return all_tools, connected


def invalidate_cache() -> None:
    """Test hook."""
    _cache["tools"] = None
    _cache["connected"] = None