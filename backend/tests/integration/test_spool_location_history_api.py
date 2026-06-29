"""Integration tests for spool location move + history (#1004 Phase 2)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@pytest.mark.integration
async def test_move_spool_records_history(async_client: AsyncClient, db_session: AsyncSession):
    loc_a = await async_client.post("/api/v1/inventory/locations", json={"name": "Shelf A"})
    loc_b = await async_client.post("/api/v1/inventory/locations", json={"name": "Shelf B"})
    assert loc_a.status_code == 201
    assert loc_b.status_code == 201

    spool_resp = await async_client.post(
        "/api/v1/inventory/spools",
        json={"material": "PLA", "location_id": loc_a.json()["id"]},
    )
    assert spool_resp.status_code == 200
    spool_id = spool_resp.json()["id"]

    move_resp = await async_client.post(
        f"/api/v1/inventory/spools/{spool_id}/move",
        json={"location_id": loc_b.json()["id"]},
    )
    assert move_resp.status_code == 200
    assert move_resp.json()["location_id"] == loc_b.json()["id"]

    history_resp = await async_client.get(f"/api/v1/inventory/spools/{spool_id}/location-history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    move_rows = [row for row in history if row["source"] == "move"]
    assert len(move_rows) == 1
    assert move_rows[0]["from_name"] == "Shelf A"
    assert move_rows[0]["to_name"] == "Shelf B"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_move_spool_no_op_skips_extra_history(async_client: AsyncClient):
    loc = await async_client.post("/api/v1/inventory/locations", json={"name": "Drawer 1"})
    spool_resp = await async_client.post(
        "/api/v1/inventory/spools",
        json={"material": "PLA", "location_id": loc.json()["id"]},
    )
    spool_id = spool_resp.json()["id"]

    same_move = await async_client.post(
        f"/api/v1/inventory/spools/{spool_id}/move",
        json={"location_id": loc.json()["id"]},
    )
    assert same_move.status_code == 200

    history_resp = await async_client.get(f"/api/v1/inventory/spools/{spool_id}/location-history")
    move_rows = [row for row in history_resp.json() if row["source"] == "move"]
    assert len(move_rows) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_location_moves_endpoint(async_client: AsyncClient):
    loc = await async_client.post("/api/v1/inventory/locations", json={"name": "Rack 1"})
    other = await async_client.post("/api/v1/inventory/locations", json={"name": "Rack 2"})
    spool = await async_client.post(
        "/api/v1/inventory/spools",
        json={"material": "PETG", "location_id": loc.json()["id"]},
    )
    spool_id = spool.json()["id"]
    await async_client.post(
        f"/api/v1/inventory/spools/{spool_id}/move",
        json={"location_id": other.json()["id"]},
    )

    moves_resp = await async_client.get(f"/api/v1/inventory/locations/{other.json()['id']}/moves")
    assert moves_resp.status_code == 200
    assert any(row["to_name"] == "Rack 2" for row in moves_resp.json())
