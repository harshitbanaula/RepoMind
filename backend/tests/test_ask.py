import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import ask as ask_mod


@pytest.mark.asyncio
async def test_ask_stream(monkeypatch):
    # stub auth + repo lookup + retriever + llm
    class FakeUser:
        id = 1
        github_id = 42

    async def fake_user(*_, **__):
        return FakeUser()

    class FakeRepo:
        id = 1
        index_status = "ready"

    class FakeRes:
        def scalar_one_or_none(self): return FakeRepo()

    class FakeDB:
        async def execute(self, *_): return FakeRes()

    async def fake_search(*_, **__):
        return [{"path": "a.py", "start_line": 1, "end_line": 3,"kind": "function", "text": "def a(): return 1"}]

    class FakeChunk:
        def __init__(self, c): self.content = c

    class FakeLLM:
        def __init__(self, *_, **__): pass
        async def astream(self, _msgs):
            for tok in ["Hello ", "world"]:
                yield FakeChunk(tok)

    monkeypatch.setattr(ask_mod, "get_current_user", fake_user)
    monkeypatch.setattr(ask_mod, "get_db", lambda: FakeDB())
    monkeypatch.setattr(ask_mod, "hybrid_search", fake_search)
    monkeypatch.setattr(ask_mod, "ChatGroq", FakeLLM)

    client = TestClient(app)
    with client.stream("POST", "/ask",json={"repo_id": 1, "question": "what does a do?"}) as r:
        body = "".join(r.iter_text())

    assert "event: step" in body
    assert "event: token" in body
    assert "event: final" in body
    assert "a.py" in body