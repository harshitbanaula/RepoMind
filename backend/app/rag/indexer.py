from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.repo import Repo
from app.rag import bm25_index, vector_store
from app.rag.chunker import Chunk, chunk_file
from app.rag.clone import clone_or_fetch, iter_source_files, repo_path
from app.rag.embeddings import embed_texts

log = get_logger(__name__)
BATCH = 128


async def _set_status(db: AsyncSession, repo_id: int, status: str) -> None:
    await db.execute(update(Repo).where(Repo.id == repo_id).values(index_status=status))
    await db.commit()


async def index_repo(db: AsyncSession, user_id: int, repo_id: int,full_name: str, token: str) -> None:
    await _set_status(db, repo_id, "indexing")
    try:
        root = await clone_or_fetch(full_name, token, user_id, repo_id)

        # wipe previous vectors for this repo before re-indexing
        await vector_store.delete_collection(user_id, repo_id)

        all_chunks: list[Chunk] = []
        for path, lang in iter_source_files(root):
            all_chunks.extend(chunk_file(root, path, lang))

        if not all_chunks:
            raise RuntimeError("no indexable files found")

        # embed + upsert in batches; track id counter
        next_id = 1
        docs: list[dict] = []
        for i in range(0, len(all_chunks), BATCH):
            batch = all_chunks[i:i + BATCH]
            vecs = await embed_texts([c.text for c in batch])
            next_id = await vector_store.upsert_chunks(
                user_id, repo_id, batch, vecs, next_id
            )
            for c in batch:
                docs.append({
                    "path": c.path, "language": c.language,
                    "start_line": c.start_line, "end_line": c.end_line,
                    "kind": c.kind, "symbol": c.symbol, "text": c.text,
                })

        bm25_index.save(user_id, repo_id, docs)

        await db.execute(
            update(Repo).where(Repo.id == repo_id)
            .values(index_status="ready", indexed_at=datetime.now(timezone.utc))
        )
        await db.commit()
        log.info("index_ready", user_id=user_id, repo_id=repo_id,chunks=len(all_chunks), path=str(repo_path(user_id, repo_id)))
    except Exception:
        await _set_status(db, repo_id, "failed")
        log.exception("index_failed", user_id=user_id, repo_id=repo_id)
        raise