import json
from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.models.repo import Repo
from app.models.user import User
from app.rag.retriever import hybrid_search
from app.schemas.ask import AskRequest

log = get_logger(__name__)
router = APIRouter(tags=["ask"])

SYSTEM = (
    "You are Repo Copilot. Answer ONLY from the provided context. "
    "Cite sources as path:start-end on their own line whenever you make a claim. "
    "If the context is insufficient, say so plainly."
)


def _fmt_context(chunks: list[dict]) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        lines.append(
            f"[{i}] {c['path']}:{c['start_line']}-{c['end_line']} ({c.get('kind','')})\n"
            f"{c['text']}"
        )
    return "\n\n".join(lines)


def _sse(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data)}


@router.post("/ask")
async def ask(body: AskRequest, db: AsyncSession = Depends(get_db),
              user: User = Depends(get_current_user)):
    repo = (await db.execute(
        select(Repo).where(Repo.id == body.repo_id, Repo.user_id == user.id)
    )).scalar_one_or_none()
    if repo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "repo not found")
    if repo.index_status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"repo not ready (status={repo.index_status})")

    s = get_settings()

    async def event_gen():
        try:
            yield _sse("step", {"name": "retrieving", "query": body.question})
            chunks = await hybrid_search(user.id, repo.id, body.question, top_k=body.top_k)
            yield _sse("step", {"name": "retrieved", "count": len(chunks)})

            if not chunks:
                yield _sse("final", {"answer": "No relevant context found.", "citations": []})
                return

            llm = ChatGroq(model=s.groq_model, api_key=s.groq_api_key, streaming=True)
            msgs = [
                SystemMessage(SYSTEM),
                HumanMessage(f"Context:\n{_fmt_context(chunks)}\n\nQuestion: {body.question}"),
            ]

            buf: list[str] = []
            async for chunk in llm.astream(msgs):
                delta = chunk.content or ""
                if delta:
                    buf.append(delta)
                    yield _sse("token", {"text": delta})

            citations = [
                {"path": c["path"], "start_line": c["start_line"], "end_line": c["end_line"]}
                for c in chunks
            ]
            yield _sse("final", {"answer": "".join(buf), "citations": citations})
        except Exception as e:  # noqa: BLE001
            log.error("ask_failed", user_id=user.id, repo_id=repo.id, error=str(e))
            yield _sse("error", {"message": str(e)})

    return EventSourceResponse(event_gen())