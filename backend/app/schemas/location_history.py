from datetime import datetime

from pydantic import BaseModel, Field


class SpoolMoveRequest(BaseModel):
    location_id: int | None = Field(default=None, description="Target location id; null clears assignment")


class SpoolLocationHistoryResponse(BaseModel):
    id: int
    spool_id: int | None = None
    spoolman_spool_id: int | None = None
    from_location_id: int | None = None
    to_location_id: int | None = None
    from_name: str | None = None
    to_name: str | None = None
    source: str
    user_id: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True
