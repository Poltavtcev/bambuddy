import { describe, it, expect } from 'vitest';

function storageLabelForSpool(
  spool: { location_id?: number | null; storage_location?: string | null },
  byId: Record<number, string>,
): string | null {
  if (spool.location_id != null && byId[spool.location_id]) return byId[spool.location_id];
  const text = spool.storage_location?.trim();
  return text || null;
}

describe('storage location label fallback', () => {
  it('prefers catalog name from location_id', () => {
    expect(storageLabelForSpool({ location_id: 3, storage_location: 'legacy' }, { 3: 'Shelf C' })).toBe('Shelf C');
  });

  it('falls back to storage_location text', () => {
    expect(storageLabelForSpool({ location_id: null, storage_location: ' Drawer 1 ' }, {})).toBe('Drawer 1');
  });
});
