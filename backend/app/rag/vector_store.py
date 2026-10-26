from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.chunker import Chunk

log = get_logger(__name__)
_client: AsyncQdrantClient | None = None


def client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = AsyncQdrantClient(
            url=s.qdrant_url,
            api_key=s.qdrant_api_key or None,
            timeout=30.0,
            check_compatibility=False,
        )
    return _client


def collection_name(user_id: int, repo_id: int) -> str:
    return f"repo_{user_id}_{repo_id}"


async def ensure_collection(user_id: int, repo_id: int) -> str:
    name = collection_name(user_id, repo_id)
    s = get_settings()

    need_create = True
    try:
        info = await client().get_collection(collection_name=name)
        existing_dim = info.config.params.vectors.size  # type: ignore[union-attr]
        if existing_dim == s.embed_dim:
            need_create = False
        else:
            log.warning(
                "qdrant_dim_mismatch_recreate",
                name=name,
                expected=s.embed_dim,
                actual=existing_dim,
            )
            await client().delete_collection(collection_name=name)
    except Exception:  # 404 → doesn't exist
        pass

    if need_create:
        await client().create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=s.embed_dim, distance=Distance.COSINE),
        )
        log.info(
            "qdrant_collection_created",
            name=name,
            user_id=user_id,
            repo_id=repo_id,
        )

    # Ensure payload indexes exist — idempotent, safe to run on every call.
    for field in ("user_id", "repo_id"):
        try:
            await client().create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=PayloadSchemaType.INTEGER,
            )
        except Exception as e:  # already exists or unsupported
            log.debug(
                "qdrant_index_skip",
                name=name,
                field=field,
                error=repr(e)[:120],
            )

    return name


async def upsert_chunks(
    user_id: int,
    repo_id: int,
    chunks: list[Chunk],
    vectors: list[list[float]],
    start_id: int,
) -> int:
    if not chunks:
        return start_id
    name = await ensure_collection(user_id, repo_id)

    points: list[PointStruct] = []
    kept = 0
    for c, v in zip(chunks, vectors):
        norm = sum(x * x for x in v) ** 0.5
        if norm < 1e-6:
            log.warning(
                "skip_zero_vector",
                user_id=user_id,
                repo_id=repo_id,
                path=c.path,
                start_line=c.start_line,
                end_line=c.end_line,
            )
            continue
        points.append(
            PointStruct(
                id=start_id + kept,
                vector=v,
                payload={
                    "user_id": user_id,
                    "repo_id": repo_id,
                    "path": c.path,
                    "language": c.language,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "kind": c.kind,
                    "symbol": c.symbol,
                    "text": c.text,
                },
            )
        )
        kept += 1

    if points:
        await client().upsert(collection_name=name, points=points, wait=True)
    return start_id + kept


async def delete_collection(user_id: int, repo_id: int) -> None:
    name = collection_name(user_id, repo_id)
    try:
        exists = await client().collection_exists(collection_name=name)
    except Exception as e:  # noqa: BLE001
        log.warning("qdrant_exists_check_failed", name=name, error=repr(e))
        return
    if not exists:
        return
    try:
        await client().delete_collection(collection_name=name)
    except Exception as e:  # noqa: BLE001
        log.warning("qdrant_delete_failed", name=name, error=repr(e))


async def search(
    user_id: int,
    repo_id: int,
    vector: list[float],
    top_k: int = 8,
) -> list[dict]:
    name = collection_name(user_id, repo_id)
    try:
        res = await client().query_points(
            collection_name=name,
            query=vector,
            limit=top_k,
            query_filter=Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    FieldCondition(key="repo_id", match=MatchValue(value=repo_id)),
                ]
            ),
            with_payload=True,
        )
    except Exception as e:  # noqa: BLE001
        log.warning(
            "qdrant_query_failed",
            name=name,
            exc_type=type(e).__name__,
            error=repr(e)[:300],
        )
        return []
    return [{"score": p.score, **(p.payload or {})} for p in res.points]