import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Loader2, MapPin, X } from 'lucide-react';
import { api, type InventorySpool } from '../api/client';
import { Button } from './Button';
import { useToast } from '../contexts/ToastContext';
import { inventoryLocationsQueryKey, invalidateSpoolAndLocationQueries } from '../utils/inventoryQueries';

interface MoveSpoolModalProps {
  open: boolean;
  spool: InventorySpool | null;
  spoolmanMode?: boolean;
  onClose: () => void;
  onMoved?: () => void;
}

export function MoveSpoolModal({ open, spool, spoolmanMode = false, onClose, onMoved }: MoveSpoolModalProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [locationId, setLocationId] = useState<string>('');

  useEffect(() => {
    if (!open || !spool) return;
    setLocationId(spool.location_id != null ? String(spool.location_id) : '');
  }, [open, spool?.id, spool?.location_id]);

  const { data: locations = [] } = useQuery({
    queryKey: inventoryLocationsQueryKey,
    queryFn: api.getLocations,
    enabled: open,
  });

  const moveMutation = useMutation({
    mutationFn: async () => {
      if (!spool) throw new Error('No spool selected');
      const target = locationId === '' ? null : Number(locationId);
      if (locationId !== '' && !Number.isFinite(target)) {
        throw new Error(t('locations.moveInvalid'));
      }
      return spoolmanMode
        ? api.moveSpoolmanInventorySpool(spool.id, target)
        : api.moveInventorySpool(spool.id, target);
    },
    onSuccess: () => {
      showToast(t('locations.moveSuccess'), 'success');
      const spoolsQueryKey = spoolmanMode ? ['spoolman-inventory-spools'] : ['inventory-spools'];
      invalidateSpoolAndLocationQueries(queryClient, spoolsQueryKey);
      onMoved?.();
      onClose();
    },
    onError: (err: Error) => {
      showToast(err.message || t('locations.moveFailed'), 'error');
    },
  });

  if (!open || !spool) return null;

  const spoolLabel = spool.material
    ? `${spool.material}${spool.color_name ? ` — ${spool.color_name}` : ''}`
    : `#${spool.id}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={() => !moveMutation.isPending && onClose()} />
      <div
        className="relative w-full max-w-md mx-4 bg-bambu-dark-secondary border border-bambu-dark-tertiary rounded-xl p-6 shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="move-spool-title"
      >
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <h2 id="move-spool-title" className="text-lg font-semibold text-white flex items-center gap-2">
              <MapPin className="w-5 h-5 text-bambu-green" />
              {t('locations.moveTitle')}
            </h2>
            <p className="text-sm text-bambu-gray mt-1">{spoolLabel}</p>
          </div>
          <button
            type="button"
            className="p-1.5 text-bambu-gray hover:text-white rounded"
            onClick={onClose}
            disabled={moveMutation.isPending}
            aria-label={t('common.close')}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <label className="block text-sm font-medium text-bambu-gray mb-1" htmlFor="move-location-select">
          {t('inventory.storageLocation')}
        </label>
        <select
          id="move-location-select"
          className="w-full px-3 py-2 bg-bambu-dark border border-bambu-dark-tertiary rounded-lg text-white text-sm focus:outline-none focus:border-bambu-green mb-6"
          value={locationId}
          onChange={(e) => setLocationId(e.target.value)}
        >
          <option value="">{t('inventory.storageLocationNone')}</option>
          {locations.map((loc) => (
            <option key={loc.id} value={loc.id}>{loc.name}</option>
          ))}
        </select>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={moveMutation.isPending}>
            {t('common.cancel')}
          </Button>
          <Button type="button" onClick={() => moveMutation.mutate()} disabled={moveMutation.isPending}>
            {moveMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            {t('locations.move')}
          </Button>
        </div>
      </div>
    </div>
  );
}
