from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import SessionLocal, get_db
from app.core.logging import get_logger
from app.core.security import decrypt_token
from app.models.repo import Repo
from app.models.user import User
from app.rag.github_client import GitHubClient
from app.rag.indexer import index_repo
from app.schemas.repos import RepoConnectRequest, RepoOut, RepoStatusOut

log = get_logger(__name__)
router = APIRouter(prefix="/repos", tags=["repos"])


@router.get("", response_model=list[RepoOut])
async def list_repos(db: AsyncSession = Depends(get_db),user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(Repo).where(Repo.user_id == user.id).order_by(Repo.id.desc())
    )).scalars().all()
    return rows


@router.post("", response_model=RepoOut, status_code=201)
async def connect_repo(
    body: RepoConnectRequest,
    bg: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    token = decrypt_token(user.encrypted_token)
    gh = GitHubClient(token)
    try:
        meta = await gh.get_repo(body.full_name)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"github: {e}")
    finally:
        await gh.aclose()

    row = (await db.execute(
        select(Repo).where(Repo.user_id == user.id, Repo.full_name == meta["full_name"])
    )).scalar_one_or_none()
    if row is None:
        row = Repo(user_id=user.id, full_name=meta["full_name"], index_status="queued")
        db.add(row)
        await db.commit()
        await db.refresh(row)
    else:
        row.index_status = "queued"
        await db.commit()
        await db.refresh(row)

    async def _job(uid: int, rid: int, full: str, tok: str) -> None:
        async with SessionLocal() as session:
            try:
                await index_repo(session, uid, rid, full, tok)
            except Exception:  # already logged inside index_repo
                pass

    bg.add_task(_job, user.id, row.id, row.full_name, token)
    log.info("repo_connect_queued", user_id=user.id, repo_id=row.id, full_name=row.full_name)
    return row


@router.get("/{repo_id}/status", response_model=RepoStatusOut)
async def repo_status(repo_id: int, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    row = (await db.execute(
        select(Repo).where(Repo.id == repo_id, Repo.user_id == user.id)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "repo not found")
    return RepoStatusOut(id=row.id, index_status=row.index_status, indexed_at=row.indexed_at)