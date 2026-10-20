from app.rag import bm25_index, vector_store
from app.rag.embeddings import embed_query


def _key(d: dict) -> tuple:
    return (d.get("path"), d.get("start_line"), d.get("end_line"))


def _rrf(ranked_lists: list[list[dict]], k: int = 60) -> list[dict]:
    scores: dict[tuple, float] = {}
    keep: dict[tuple, dict] = {}
    for lst in ranked_lists:
        for rank, d in enumerate(lst):
            key = _key(d)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            keep.setdefault(key, d)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    out = []
    for key, sc in ordered:
        d = dict(keep[key])
        d["score"] = sc
        out.append(d)
    return out


async def hybrid_search(user_id: int, repo_id: int, query: str, top_k: int = 8) -> list[dict]:
    vec = await embed_query(query)
    vec_hits = await vector_store.search(user_id, repo_id, vec, top_k=top_k * 2)
    bm_hits = bm25_index.search(user_id, repo_id, query, top_k=top_k * 2)
    fused = _rrf([vec_hits, bm_hits])
    return fused[:top_k]