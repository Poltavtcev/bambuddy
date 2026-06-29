"""Unit tests for spool location history recording (#1004 Phase 2)."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.location import Location
from backend.app.models.spool import Spool
from backend.app.models.spool_location_history import SpoolLocationHistory
from backend.app.services.location_service import (
    assign_location_name,
    location_state_changed,
    record_location_change_if_needed,
    snapshot_location_state,
)


def test_location_state_changed_detects_id_change():
    assert location_state_changed(1, "Shelf A", 2, "Shelf B") is True


def test_location_state_changed_ignores_case_only_name():
    old_id, old_name = snapshot_location_state(1, "Shelf A")
    new_id, new_name = snapshot_location_state(1, "shelf a")
    assert location_state_changed(old_id, old_name, new_id, new_name) is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_record_location_change_skips_no_op(db_session: AsyncSession):
    changed = await record_location_change_if_needed(
        db_session,
        spool_id=1,
        old_location_id=2,
        old_name="Shelf A",
        new_location_id=2,
        new_name="Shelf A",
        source="move",
        user_id=None,
    )
    assert changed is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_record_location_change_writes_row(db_session: AsyncSession):
    loc = Location()
    assign_location_name(loc, "Shelf A")
    db_session.add(loc)
    spool = Spool(material="PLA")
    db_session.add(spool)
    await db_session.flush()

    changed = await record_location_change_if_needed(
        db_session,
        spool_id=spool.id,
        old_location_id=None,
        old_name=None,
        new_location_id=loc.id,
        new_name=loc.name,
        source="move",
        user_id=None,
    )
    assert changed is True
    await db_session.commit()

    result = await db_session.execute(
        select(SpoolLocationHistory).where(SpoolLocationHistory.spool_id == spool.id)
    )
    rows = list(result.scalars().all())
    assert len(rows) == 1
    assert rows[0].to_location_id == loc.id
    assert rows[0].source == "move"
