import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MoveSpoolModal } from '../../components/MoveSpoolModal';
import { ToastProvider } from '../../contexts/ToastContext';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

const { getLocations } = vi.hoisted(() => ({
  getLocations: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  api: {
    getLocations,
    moveInventorySpool: vi.fn(),
    moveSpoolmanInventorySpool: vi.fn(),
  },
}));

describe('MoveSpoolModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getLocations.mockResolvedValue([
      { id: 1, name: 'Shelf A', identifier: null, spool_count: 0, created_at: '', updated_at: '' },
    ]);
  });

  it('renders move form when open', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MoveSpoolModal
            open
            spool={{ id: 7, material: 'PLA', color_name: 'Red', label_weight: 1000, weight_used: 0 } as never}
            onClose={vi.fn()}
          />
        </ToastProvider>
      </QueryClientProvider>,
    );

    expect(screen.getByText('locations.moveTitle')).toBeInTheDocument();
    await waitFor(() => expect(getLocations).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: 'locations.move' })).toBeInTheDocument();
  });
});
