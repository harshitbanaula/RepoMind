import pytest
from unittest.mock import AsyncMock, patch

from app.mcp_servers import github_server, repo_search_server


@pytest.mark.asyncio
async def test_get_diff_not_found_returns_structured_error():
    fake = AsyncMock()
    fake.get.return_value.status_code = 404
    fake.get.return_value.text = "nope"

    class FakeClient:
        async def __aenter__(self): return fake
        async def __aexit__(self, *_): pass

    with patch.object(github_server, "_client", lambda token: FakeClient()):
        res = await github_server.get_diff("o", "r", 1, "tok")
    assert res["ok"] is False
    assert res["error"] == "not_found"


@pytest.mark.asyncio
async def test_post_review_comment_rejects_empty_body():
    res = await github_server.post_review_comment(
        "o", "r", 1, "a.py", 10, "   ", "tok"
    )
    assert res["ok"] is False
    assert res["error"] == "invalid_input"


@pytest.mark.asyncio
async def test_search_code_propagates_not_ready(monkeypatch):
    class FakeRepo:
        index_status = "indexing"
    class FakeRes:
        def scalar_one_or_none(self): return FakeRepo()
    class FakeDB:
        async def execute(self, *_): return FakeRes()
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass

    monkeypatch.setattr(repo_search_server, "SessionLocal", lambda: FakeDB())
    res = await repo_search_server.search_code(1, "x", 1, 5)
    assert res["ok"] is False
    assert res["error"] == "not_ready"