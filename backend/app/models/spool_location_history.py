from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class SpoolLocationHistory(Base):
    """Audit trail when a spool's physical storage location changes (#1004 Phase 2)."""

    __tablename__ = "spool_location_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    spool_id: Mapped[int | None] = mapped_column(ForeignKey("spool.id", ondelete="CASCADE"), index=True)
    spoolman_spool_id: Mapped[int | None] = mapped_column(Integer, index=True)
    from_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    to_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    from_name: Mapped[str | None] = mapped_column(String(255))
    to_name: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
