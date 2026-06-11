import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useState } from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ManageLocationsModal } from '../../components/ManageLocationsModal';
import { api, ApiError } from '../../api/client';

const mockShowToast = vi.fn();

vi.mock('../../api/client', () => ({
  api: {
    getLocations: vi.fn(),
    createLocation: vi.fn(),
    updateLocation: vi.fn(),
    deleteLocation: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
}));

vi.mock('../../contexts/ToastContext', () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

const locations = [
  { id: 1, name: 'Shelf A', identifier: null, spool_count: 2, created_at: '2026-01-01', updated_at: '2026-01-01' },
  { id: 2, name: 'Drawer 1', identifier: null, spool_count: 0, created_at: '2026-01-01', updated_at: '2026-01-01' },
];

function renderModal(onSelectLocation = vi.fn()) {
  const onClose = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const result = render(
    <QueryClientProvider client={client}>
      <ManageLocationsModal isOpen onClose={onClose} onSelectLocation={onSelectLocation} />
    </QueryClientProvider>,
  );
  return { onClose, onSelectLocation, ...result };
}

// Stateful harness so Escape actually unmounts the dialog (mirrors real usage).
function Harness() {
  const [open, setOpen] = useState(true);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <ManageLocationsModal isOpen={open} onClose={() => setOpen(false)} />
    </QueryClientProvider>
  );
}

describe('ManageLocationsModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getLocations).mockResolvedValue(locations);
  });

  it('renders locations from the API', async () => {
    renderModal();
    expect(await screen.findByText('Shelf A')).toBeInTheDocument();
    expect(screen.getByText('Drawer 1')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('renders the empty state when the API returns no locations', async () => {
    vi.mocked(api.getLocations).mockResolvedValue([]);
    renderModal();
    expect(await screen.findByText(/no storage locations|locations\.empty/i)).toBeInTheDocument();
  });

  it('creates a location and shows a success toast', async () => {
    vi.mocked(api.createLocation).mockResolvedValue({
      id: 3, name: 'Garage', identifier: null, spool_count: 0, created_at: '', updated_at: '',
    });
    const user = userEvent.setup();
    renderModal();
    await screen.findByText('Shelf A');
    await user.type(screen.getByLabelText(/name|locations\.name/i), 'Garage');
    await user.click(screen.getByRole('button', { name: /^add$/i }));
    await waitFor(() => {
      expect(api.createLocation).toHaveBeenCalledWith({ name: 'Garage' });
    });
    expect(mockShowToast).toHaveBeenCalledWith(expect.stringMatching(/created|locations\.created/i), 'success');
  });

  it('submits the create form on Enter', async () => {
    vi.mocked(api.createLocation).mockResolvedValue({
      id: 3, name: 'Garage', identifier: null, spool_count: 0, created_at: '', updated_at: '',
    });
    const user = userEvent.setup();
    renderModal();
    await screen.findByText('Shelf A');
    await user.type(screen.getByLabelText(/name|locations\.name/i), 'Garage{Enter}');
    await waitFor(() => {
      expect(api.createLocation).toHaveBeenCalledWith({ name: 'Garage' });
    });
  });

  it('edits a location and shows a success toast', async () => {
    vi.mocked(api.updateLocation).mockResolvedValue({
      id: 2, name: 'Drawer 2', identifier: null, spool_count: 0, created_at: '', updated_at: '',
    });
    const user = userEvent.setup();
    renderModal();
    await screen.findByText('Drawer 1');
    const row = screen.getByText('Drawer 1').closest('li')!;
    await user.click(within(row).getByTitle(/^edit$|common\.edit/i));
    const input = screen.getByDisplayValue('Drawer 1');
    await user.clear(input);
    await user.type(input, 'Drawer 2');
    await user.click(screen.getByTitle(/^save$|common\.save/i));
    await waitFor(() => {
      expect(api.updateLocation).toHaveBeenCalledWith(2, { name: 'Drawer 2' });
    });
    expect(mockShowToast).toHaveBeenCalledWith(expect.stringMatching(/updated|locations\.updated/i), 'success');
  });

  it('deletes an empty location after confirmation', async () => {
    vi.mocked(api.deleteLocation).mockResolvedValue({ status: 'deleted' });
    const user = userEvent.setup();
    renderModal();
    await screen.findByText('Drawer 1');
    const row = screen.getByText('Drawer 1').closest('li')!;
    await user.click(within(row).getByTitle(/^delete$|common\.delete/i));
    // ConfirmModal confirm button carries the visible "Delete" label.
    await user.click(screen.getAllByRole('button', { name: /^delete$/i }).pop()!);
    await waitFor(() => {
      expect(api.deleteLocation).toHaveBeenCalledWith(2);
    });
    expect(mockShowToast).toHaveBeenCalledWith(expect.stringMatching(/deleted|locations\.deleted/i), 'success');
  });

  it('blocks delete when spool_count > 0', async () => {
    renderModal();
    await screen.findByText('Shelf A');
    const row = screen.getByText('Shelf A').closest('li')!;
    const blocked = within(row).getByTitle(/remove all spools|locations\.deleteBlocked/i);
    expect(blocked).toBeDisabled();
  });

  it('surfaces a 409 duplicate-name error to the toast', async () => {
    vi.mocked(api.createLocation).mockRejectedValue(
      new ApiError('A location with this name already exists', 409),
    );
    const user = userEvent.setup();
    renderModal();
    await screen.findByText('Shelf A');
    await user.type(screen.getByLabelText(/name|locations\.name/i), 'Shelf A');
    await user.click(screen.getByRole('button', { name: /^add$/i }));
    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith('A location with this name already exists', 'error');
    });
  });

  it('applies the inventory filter when a location row is clicked', async () => {
    const user = userEvent.setup();
    const { onSelectLocation } = renderModal();
    await screen.findByText('Shelf A');
    await user.click(screen.getByRole('button', { name: 'Shelf A' }));
    expect(onSelectLocation).toHaveBeenCalledWith(1);
  });

  it('closes on Escape', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    await user.keyboard('{Escape}');
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });
});
