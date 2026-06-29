# Storage Locations (#1004)

Structured storage locations let you manage physical shelves, drawers, and dryboxes as a catalog instead of free-text only.

## Architecture

- **`locations` table** — catalog of named storage spots (`name` + case-insensitive `name_key`).
- **`spool.location_id`** — source of truth for structured assignment.
- **`spool.storage_location`** — denormalized display string and Spoolman wire format; always derived on write via `location_service.resolve_spool_location_fields()`.
- **Frontend** — spool form sends only `location_id`; backend fills `storage_location`.

## Location vs Storage Location vs AMS Location

| UI label | Meaning |
|----------|---------|
| **Location** (inventory table column) | AMS slot or printer assignment (e.g. `H2D-1 B4`) |
| **Storage Location** | Physical shelf/drawer where the spool lives when not in AMS |
| **Locations page** | Catalog of named storage spots with spool counts |

## Managing locations

1. Open **Inventory → Locations**
2. Click **Add Location** and enter a name (e.g. `Regal Etage 2`)
3. Assign spools via the spool edit form **Storage Location** dropdown, the **Move** action on a spool row, or bulk edit
4. Click a location row to filter inventory by that shelf
5. Use the history icon on a location row to see recent moves to/from that shelf

## Move workflow and audit trail (Phase 2)

- **Move action** — use the map-pin button on a spool row or click the storage location chip when the spool is not in AMS
- **Dedicated API** — `POST /api/v1/inventory/spools/{id}/move` with `{ "location_id": <id|null> }` (Spoolman mode: `/spoolman/inventory/spools/{id}/move`)
- **History** — every location change is recorded in `spool_location_history` with from/to names, timestamp, source (`move`, `edit`, `bulk`, `spoolman`), and optional user id
- **View history** — spool edit form → **Location history** panel; location modal → history icon per shelf; `GET /inventory/spools/{id}/location-history` and `GET /inventory/locations/{id}/moves`

## Location column vs Storage Location

When a spool is loaded in AMS, the **Location** column shows the printer/AMS slot (purple). When it is **not** in AMS but has a storage assignment, the **Location** column shows the physical shelf name (blue) instead of `-`.

## Spoolman mode

Bambuddy keeps a local location catalog. When Spoolman integration is enabled:

- Assigning a location writes the location **name** to Spoolman's `location` field
- Listing locations syncs distinct names from Spoolman into the catalog
- Renaming a location bulk-renames spools in Spoolman via `PATCH /location/{old}`

## Upgrade migration

Existing free-text `storage_location` values are automatically imported into the location catalog and linked on upgrade (case-insensitive dedup via `name_key`).

## Testing before release

1. `./test_frontend.sh` — i18n parity, lint, Vitest
2. `./test_backend.sh` — Ruff, pytest (includes `test_locations_api.py`, `test_location_service.py`)
3. Manual: assign a spool to a location → open **Locations** → spool count updates without reload
4. Companion PR in [bambuddy-wiki](https://github.com/maziggy/bambuddy-wiki) (user-facing guide)
