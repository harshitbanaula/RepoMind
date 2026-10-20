import pytest
from app.rag import retriever


@pytest.mark.asyncio
async def test_rrf_prefers_shared_hit(monkeypatch):
    async def fake_vec(uid, rid, v, top_k=16):
        return [
            {"path": "a.py", "start_line": 1, "end_line": 5, "text": "a"},
            {"path": "b.py", "start_line": 1, "end_line": 5, "text": "b"},
        ]
    def fake_bm(uid, rid, q, top_k=16):
        return [
            {"path": "b.py", "start_line": 1, "end_line": 5, "text": "b"},
            {"path": "c.py", "start_line": 1, "end_line": 5, "text": "c"},
        ]
    async def fake_embed(q):
        return [0.0] * 8

    monkeypatch.setattr(retriever.vector_store, "search", fake_vec)
    monkeypatch.setattr(retriever.bm25_index, "search", fake_bm)
    monkeypatch.setattr(retriever, "embed_query", fake_embed)

    hits = await retriever.hybrid_search(1, 1, "q", top_k=3)
    assert hits[0]["path"] == "b.py"  # appears in both rankings