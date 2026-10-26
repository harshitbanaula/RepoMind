import pytest
from unittest.mock import patch

from app.mcp_client import client as client_mod


@pytest.mark.asyncio
async def test_load_tools_survives_all_servers_down(monkeypatch):
    client_mod.invalidate_cache()

    def bad_configs():
        return {
            "github": {"transport": "stdio", "command": "definitely-not-a-real-binary",
                       "args": [], "onConnectionError": "ignore"},
            "repo_search": {"transport": "stdio", "command": "definitely-not-a-real-binary",
                            "args": [], "onConnectionError": "ignore"},
        }
    monkeypatch.setattr(client_mod, "_server_configs", bad_configs)

    tools, connected = await client_mod.load_tools()
    assert tools == []
    assert connected == {"github": False, "repo_search": False}
    client_mod.invalidate_cache()