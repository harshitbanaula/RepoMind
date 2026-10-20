from datetime import datetime
from pydantic import BaseModel, Field


class RepoConnectRequest(BaseModel):
    full_name: str = Field(..., pattern=r"^[\w.-]+/[\w.-]+$")


class RepoOut(BaseModel):
    id: int
    full_name: str
    index_status: str
    indexed_at: datetime | None

    model_config = {"from_attributes": True}


class RepoStatusOut(BaseModel):
    id: int
    index_status: str
    indexed_at: datetime | None