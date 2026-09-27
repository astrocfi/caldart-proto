import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import {
  API,
  emptyVerificationCalls,
  makeLeaderStatus,
  verificationHandlers,
} from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { PROFILE_KEY } from '@/portal/features/profile/api';
import { MemberVerificationPanel } from './MemberVerificationPanel';
import type { MemberVerificationDraft } from './memberDraft';

const INITIAL: MemberVerificationDraft = {
  pilot_certificate_type: 'private',
  certificate_number: '3181234',
  medical_type: 'third',
  medical_expiration: '2027-03-01',
  photo_id_type: 'not_provided',
  verified: ['certificate'],
};

function renderPanel(overrides: { handleSaved?: () => void } = {}) {
  const handleClose = vi.fn();
  const { handleSaved } = overrides;
  const { client } = renderWithProviders(
    <MemberVerificationPanel
      userId={7}
      initial={INITIAL}
      onSaved={handleSaved}
      onClose={handleClose}
    />,
  );
  return { handleClose, client };
}

describe('MemberVerificationPanel', () => {
  it('ticks the boxes of the items verified now', () => {
    renderPanel();
    expect(screen.getByLabelText('Pilot certificate verified')).toBeChecked();
    expect(screen.getByLabelText('Medical verified')).not.toBeChecked();
    expect(screen.getByLabelText('Photo ID verified')).not.toBeChecked();
  });

  it('opens with the fields the record holds', () => {
    renderPanel();
    expect(screen.getByLabelText('Certificate number')).toHaveValue('3181234');
  });

  it('sends the ticked items in one save and says so', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    const handleSaved = vi.fn();
    server.use(...verificationHandlers(calls));
    const { handleClose } = renderPanel({ handleSaved });

    await user.click(screen.getByLabelText('Medical verified'));
    await user.click(screen.getByLabelText('Photo ID verified'));
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Verification saved')).toBeInTheDocument();
    expect(calls.members).toEqual([
      { userId: 7, body: { verified: ['certificate', 'medical', 'photo_id'] } },
    ]);
    expect(handleSaved).toHaveBeenCalledWith(makeLeaderStatus());
    expect(handleClose).toHaveBeenCalled();
  });

  it('marks the /me/profile query stale, since a verifier may verify themselves', async () => {
    const user = userEvent.setup();
    server.use(...verificationHandlers(emptyVerificationCalls()));
    const { client } = renderPanel();
    const invalidated = vi.spyOn(client, 'invalidateQueries');

    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Verification saved')).toBeInTheDocument();
    const keys = invalidated.mock.calls.map(([filters]) => filters?.queryKey);
    expect(keys).toContainEqual(PROFILE_KEY);
  });

  it('unticks an item when one of its fields is edited', async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText('Certificate number'), '9');

    expect(screen.getByLabelText('Pilot certificate verified')).not.toBeChecked();
  });

  it('sends an edited field beside the items ticked again', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    server.use(...verificationHandlers(calls));
    renderPanel();

    await user.selectOptions(screen.getByLabelText('Photo ID'), 'passport');
    await user.click(screen.getByLabelText('Photo ID verified'));
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(calls.members).toHaveLength(1));
    expect(calls.members[0]?.body).toEqual({
      photo_id_type: 'passport',
      verified: ['certificate', 'photo_id'],
    });
  });

  it('shows a refused field under that field', async () => {
    const user = userEvent.setup();
    server.use(
      http.put(`${API}/leader/members/7/verification`, () =>
        HttpResponse.json(
          { medical_expiration: ['Give the expiration date of your medical certificate.'] },
          { status: 400 },
        ),
      ),
    );
    renderPanel();

    await user.clear(screen.getByLabelText('Medical expires'));
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Give the expiration date of your medical certificate.',
    );
    expect(screen.getByLabelText('Medical expires')).toHaveAttribute('aria-invalid', 'true');
  });

  it('shows a refused item above the fields', async () => {
    const user = userEvent.setup();
    server.use(
      http.put(`${API}/leader/members/7/verification`, () =>
        HttpResponse.json({ verified: ["Unknown item 'badge'."] }, { status: 400 }),
      ),
    );
    renderPanel();

    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByRole('alert')).toHaveTextContent("Unknown item 'badge'.");
  });

  it('closes without saving on Cancel', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    server.use(...verificationHandlers(calls));
    const { handleClose } = renderPanel();

    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(handleClose).toHaveBeenCalled();
    expect(calls.members).toEqual([]);
  });
});
