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
| **Manage Locations modal** | Catalog of named storage spots with spool counts |

## Managing locations

The catalog is managed from a compact modal, not a dedicated page.

1. Open the **Spool Inventory** page and click **Locations** in the header to open the **Manage Locations** modal
2. Type a name (e.g. `Regal Etage 2`) and click **Add**
3. Rename or delete an entry inline; deletion is blocked while spools are still assigned
4. Assign spools via the spool edit form **Storage Location** dropdown (or type a new name and click **Add** to create one on the fly)
5. Click a location name in the modal to filter the inventory by that shelf (`?location_id=<id>`) and close the modal

## Spoolman mode

Bambuddy keeps a local location catalog. When Spoolman integration is enabled:

- Assigning a location writes the location **name** to Spoolman's `location` field
- Listing locations syncs distinct names from Spoolman into the catalog
- Renaming a location bulk-renames spools in Spoolman via `PATCH /location/{old}`

## Upgrade migration

Existing free-text `storage_location` values are automatically imported into the location catalog and linked on upgrade (case-insensitive dedup via `name_key`).

## Testing before release

1. `./test_frontend.sh` — i18n parity, lint, Vitest (includes `ManageLocationsModal.test.tsx`)
2. `./test_backend.sh` — Ruff, pytest (includes `test_locations_api.py`, `test_location_service.py`)
3. Manual: assign a spool to a location → open **Manage Locations** → spool count updates without reload
4. Companion PR in [bambuddy-wiki](https://github.com/maziggy/bambuddy-wiki) (user-facing guide)
