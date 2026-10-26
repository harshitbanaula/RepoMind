"""Repo search MCP server — wraps Phase 2 hybrid_search."""
from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.repo import Repo
from app.rag.retriever import hybrid_search

mcp = FastMCP("repo_search", json_response=True)


@mcp.tool()
async def search_code(repo_id: int, query: str, user_id: int, top_k: int = 8) -> dict:
    """Hybrid (BM25 + vector) search inside an indexed repo, scoped to user_id."""
    if not query.strip():
        return {"ok": False, "error": "invalid_input", "detail": "empty query"}
    if top_k < 1 or top_k > 20:
        return {"ok": False, "error": "invalid_input", "detail": "top_k must be 1..20"}

    async with SessionLocal() as db:
        repo = (await db.execute(
            select(Repo).where(Repo.id == repo_id, Repo.user_id == user_id)
        )).scalar_one_or_none()
        if repo is None:
            return {"ok": False, "error": "not_found",
                    "detail": f"repo {repo_id} not indexed for user {user_id}"}
        if repo.index_status != "ready":
            return {"ok": False, "error": "not_ready",
                    "detail": f"index_status={repo.index_status}"}

    try:
        hits = await hybrid_search(user_id, repo_id, query, top_k=top_k)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "search_failed", "detail": repr(e)}

    # strip the full text to keep tool payloads small; keep a snippet
    out = []
    for h in hits:
        out.append({
            "path": h.get("path"),
            "start_line": h.get("start_line"),
            "end_line": h.get("end_line"),
            "kind": h.get("kind"),
            "symbol": h.get("symbol"),
            "snippet": (h.get("text") or "")[:400],
        })
    return {"ok": True, "count": len(out), "hits": out}


if __name__ == "__main__":
    mcp.run(transport="stdio")