from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class Repo(Base, TimestampMixin):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(512), index=True)  # owner/name
    index_status: Mapped[str] = mapped_column(String(32), default="queued")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="repos")

    __table_args__ = (Index("ix_repos_user_full_name", "user_id", "full_name", unique=True),)