import { useState, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { MapPin, Plus, Loader2, Pencil, Trash2, Check, X } from 'lucide-react';
import { api, type StorageLocation } from '../api/client';
import { Button } from './Button';
import { ConfirmModal } from './ConfirmModal';
import { useToast } from '../contexts/ToastContext';
import { inventoryLocationsQueryKey, invalidateInventoryLocations } from '../utils/inventoryQueries';

interface ManageLocationsModalProps {
  isOpen: boolean;
  onClose: () => void;
  // Clicking a location row applies the inventory filter and closes the modal,
  // preserving the ?location_id=<id> deep-link behaviour of the old page.
  onSelectLocation?: (id: number) => void;
}

export function ManageLocationsModal({ isOpen, onClose, onSelectLocation }: ManageLocationsModalProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [newName, setNewName] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<StorageLocation | null>(null);

  const { data: locations = [], isLoading } = useQuery({
    queryKey: inventoryLocationsQueryKey,
    queryFn: api.getLocations,
    enabled: isOpen,
  });

  // Spool counts live on the spool list too, so refresh both stores after writes.
  const invalidate = () => {
    invalidateInventoryLocations(queryClient);
    queryClient.invalidateQueries({ queryKey: ['inventory-spools'] });
    queryClient.invalidateQueries({ queryKey: ['spoolman-inventory-spools'] });
  };

  const createMutation = useMutation({
    mutationFn: (name: string) => api.createLocation({ name }),
    onSuccess: () => {
      showToast(t('locations.created'), 'success');
      setNewName('');
      invalidate();
    },
    onError: (err: Error) => {
      showToast(err.message || t('locations.saveFailed'), 'error');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) => api.updateLocation(id, { name }),
    onSuccess: () => {
      showToast(t('locations.updated'), 'success');
      setEditingId(null);
      setEditName('');
      invalidate();
    },
    onError: (err: Error) => {
      showToast(err.message || t('locations.saveFailed'), 'error');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteLocation(id),
    onSuccess: () => {
      showToast(t('locations.deleted'), 'success');
      setDeleteTarget(null);
      invalidate();
    },
    onError: (err: Error) => {
      showToast(err.message || t('locations.deleteFailed'), 'error');
    },
  });

  const close = useCallback(() => {
    if (createMutation.isPending || updateMutation.isPending) return;
    setNewName('');
    setEditingId(null);
    setEditName('');
    onClose();
  }, [createMutation.isPending, updateMutation.isPending, onClose]);

  // Close on Escape — mirrors the SpoolFormModal dialog pattern.
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, close]);

  if (!isOpen) return null;

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newName.trim();
    if (!trimmed) return;
    createMutation.mutate(trimmed);
  };

  const startEdit = (loc: StorageLocation) => {
    setEditingId(loc.id);
    setEditName(loc.name);
  };

  const handleEditSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingId == null) return;
    const trimmed = editName.trim();
    if (!trimmed) return;
    updateMutation.mutate({ id: editingId, name: trimmed });
  };

  const titleId = 'manage-locations-title';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={close} />

      <div
        className="relative w-full max-w-md mx-4 bg-bambu-dark-secondary border border-bambu-dark-tertiary rounded-xl shadow-2xl max-h-[90vh] flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-bambu-dark-tertiary flex-shrink-0">
          <h2 id={titleId} className="text-lg font-semibold text-white flex items-center gap-2">
            <MapPin className="w-5 h-5 text-bambu-green" />
            {t('locations.title')}
          </h2>
          <button
            type="button"
            onClick={close}
            className="p-1.5 text-bambu-gray hover:text-white rounded-lg hover:bg-bambu-dark-tertiary"
            aria-label={t('common.close')}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 overflow-y-auto space-y-4">
          <p className="text-sm text-bambu-gray">{t('locations.subtitle')}</p>

          {/* Add form */}
          <form onSubmit={handleCreate} className="flex gap-2">
            <div className="flex-1">
              <label className="sr-only" htmlFor="new-location-name">
                {t('locations.name')}
              </label>
              <input
                id="new-location-name"
                type="text"
                maxLength={255}
                className="w-full px-3 py-2 bg-bambu-dark border border-bambu-dark-tertiary rounded-lg text-white text-sm placeholder:text-bambu-gray/50 focus:outline-none focus:border-bambu-green"
                placeholder={t('locations.createPlaceholder')}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                autoFocus
              />
            </div>
            <Button type="submit" disabled={!newName.trim() || createMutation.isPending}>
              {createMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              {t('locations.addShort')}
            </Button>
          </form>

          {/* List */}
          {isLoading ? (
            <div className="flex items-center justify-center py-10 text-bambu-gray">
              <Loader2 className="w-5 h-5 animate-spin mr-2" />
              {t('common.loading')}
            </div>
          ) : locations.length === 0 ? (
            <div className="py-10 text-center text-bambu-gray text-sm">{t('locations.empty')}</div>
          ) : (
            <ul className="divide-y divide-bambu-dark-tertiary/60 border border-bambu-dark-tertiary rounded-lg overflow-hidden">
              {locations.map((loc) => (
                <li key={loc.id} className="flex items-center gap-2 px-3 py-2">
                  {editingId === loc.id ? (
                    <form onSubmit={handleEditSave} className="flex items-center gap-2 flex-1">
                      <label className="sr-only" htmlFor={`edit-location-${loc.id}`}>
                        {t('locations.name')}
                      </label>
                      <input
                        id={`edit-location-${loc.id}`}
                        type="text"
                        maxLength={255}
                        className="flex-1 px-2 py-1.5 bg-bambu-dark border border-bambu-dark-tertiary rounded-lg text-white text-sm focus:outline-none focus:border-bambu-green"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        autoFocus
                      />
                      <button
                        type="submit"
                        className="p-1.5 text-bambu-gray hover:text-bambu-green rounded disabled:opacity-40"
                        disabled={!editName.trim() || updateMutation.isPending}
                        title={t('common.save')}
                      >
                        {updateMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                      </button>
                      <button
                        type="button"
                        className="p-1.5 text-bambu-gray hover:text-white rounded"
                        onClick={() => { setEditingId(null); setEditName(''); }}
                        title={t('common.cancel')}
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </form>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="flex-1 text-left text-white font-medium text-sm hover:text-bambu-green truncate"
                        onClick={() => onSelectLocation?.(loc.id)}
                        title={t('common.filter')}
                      >
                        {loc.name}
                      </button>
                      <span className="text-xs text-bambu-gray tabular-nums px-2">
                        {loc.spool_count} {t('locations.spools')}
                      </span>
                      <button
                        type="button"
                        className="p-1.5 text-bambu-gray hover:text-bambu-green rounded"
                        onClick={() => startEdit(loc)}
                        title={t('common.edit')}
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        className="p-1.5 text-bambu-gray hover:text-red-400 rounded disabled:opacity-40"
                        disabled={loc.spool_count > 0}
                        onClick={() => setDeleteTarget(loc)}
                        title={loc.spool_count > 0 ? t('locations.deleteBlocked') : t('common.delete')}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {deleteTarget && (
        <ConfirmModal
          title={t('locations.confirmDelete', { name: deleteTarget.name })}
          message={t('locations.confirmDeleteMessage')}
          confirmText={t('common.delete')}
          variant="danger"
          overlayZIndex="z-[60]"
          isLoading={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(deleteTarget.id)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
