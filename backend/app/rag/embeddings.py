import asyncio
from functools import lru_cache

from fastembed import TextEmbedding

from app.core.config import get_settings


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    return TextEmbedding(model_name=get_settings().embed_model)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    loop = asyncio.get_running_loop()
    # fastembed returns a generator of numpy arrays
    vecs = await loop.run_in_executor(None, lambda: list(_model().embed(texts)))
    return [v.tolist() for v in vecs]


async def embed_query(text: str) -> list[float]:
    out = await embed_texts([text])
    return out[0]