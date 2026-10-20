from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import User


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    x_dev_user: str | None = Header(default=None, alias="X-Dev-User"),
) -> User:
    """Phase 2 shim: X-Dev-User header holds the github_id. Replaced in Phase 6."""
    if not x_dev_user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing X-Dev-User")
    try:
        gh_id = int(x_dev_user)
    except ValueError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "X-Dev-User must be numeric github_id"
        )
    row = (
        await db.execute(select(User).where(User.github_id == gh_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not seeded")
    return row