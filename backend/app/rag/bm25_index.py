import pickle
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]+|\d+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def _path(user_id: int, repo_id: int) -> Path:
    return Path(get_settings().indexes_root) / str(user_id) / f"{repo_id}.bm25"


def save(user_id: int, repo_id: int, docs: list[dict]) -> None:
    p = _path(user_id, repo_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    corpus = [tokenize(d["text"]) for d in docs]
    with p.open("wb") as f:
        pickle.dump({"docs": docs, "corpus": corpus}, f, protocol=pickle.HIGHEST_PROTOCOL)
    log.info("bm25_saved", user_id=user_id, repo_id=repo_id, n=len(docs))


def load(user_id: int, repo_id: int) -> tuple[BM25Okapi, list[dict]] | None:
    p = _path(user_id, repo_id)
    if not p.exists():
        return None
    with p.open("rb") as f:
        payload = pickle.load(f)  # noqa: S301 — local trusted file
    docs = payload["docs"]
    corpus = payload["corpus"]
    if not corpus:
        return None
    return BM25Okapi(corpus), docs


def search(user_id: int, repo_id: int, query: str, top_k: int = 8) -> list[dict]:
    loaded = load(user_id, repo_id)
    if loaded is None:
        return []
    bm25, docs = loaded
    q = tokenize(query)
    if not q:
        return []
    scores = bm25.get_scores(q)
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [{"score": float(scores[i]), **docs[i]} for i in order if scores[i] > 0]