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
  it('checks the boxes of the items verified now', () => {
    renderPanel();
    expect(screen.getByLabelText('Pilot certificate verified')).toBeChecked();
    expect(screen.getByLabelText('Medical verified')).not.toBeChecked();
  });

  it('offers no box for an item the person does not hold', () => {
    renderPanel();
    expect(screen.queryByLabelText('Photo ID verified')).not.toBeInTheDocument();
  });

  it('takes the box away when an item is changed to one not held', async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.selectOptions(screen.getByLabelText('Pilot certificate'), 'none');

    expect(screen.queryByLabelText('Pilot certificate verified')).not.toBeInTheDocument();
  });

  it('says there is nothing to verify when the person holds none of the items', async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.selectOptions(screen.getByLabelText('Pilot certificate'), 'none');
    await user.selectOptions(screen.getByLabelText('Medical'), 'none');

    expect(screen.getByText(/Nothing to verify yet/)).toBeInTheDocument();
  });

  it('opens with the fields the record holds', () => {
    renderPanel();
    expect(screen.getByLabelText('Certificate number')).toHaveValue('3181234');
  });

  it('sends the checked items in one save and says so', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    const handleSaved = vi.fn();
    server.use(...verificationHandlers(calls));
    const { handleClose } = renderPanel({ handleSaved });

    await user.click(screen.getByLabelText('Medical verified'));
    await user.click(screen.getByRole('button', { name: 'Save verification' }));

    expect(await screen.findByText('Verification saved')).toBeInTheDocument();
    expect(calls.members).toEqual([{ userId: 7, body: { verified: ['certificate', 'medical'] } }]);
    expect(handleSaved).toHaveBeenCalledWith(makeLeaderStatus());
    expect(handleClose).toHaveBeenCalled();
  });

  it('marks the /me/profile query stale, since a verifier may verify themselves', async () => {
    const user = userEvent.setup();
    server.use(...verificationHandlers(emptyVerificationCalls()));
    const { client } = renderPanel();
    const invalidated = vi.spyOn(client, 'invalidateQueries');

    await user.click(screen.getByRole('button', { name: 'Save verification' }));

    expect(await screen.findByText('Verification saved')).toBeInTheDocument();
    const keys = invalidated.mock.calls.map(([filters]) => filters?.queryKey);
    expect(keys).toContainEqual(PROFILE_KEY);
  });

  it('unchecks an item when one of its fields is edited', async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText('Certificate number'), '9');

    expect(screen.getByLabelText('Pilot certificate verified')).not.toBeChecked();
  });

  it('sends an edited field beside the items checked again', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    server.use(...verificationHandlers(calls));
    renderPanel();

    await user.selectOptions(screen.getByLabelText('Photo ID'), 'passport');
    await user.click(screen.getByLabelText('Photo ID verified'));
    await user.click(screen.getByRole('button', { name: 'Save verification' }));

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
          { medical_expiration: ["Enter the medical's expiration date."] },
          { status: 400 },
        ),
      ),
    );
    renderPanel();

    await user.clear(screen.getByLabelText('Medical expires'));
    await user.click(screen.getByRole('button', { name: 'Save verification' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Enter the medical's expiration date.",
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

    await user.click(screen.getByRole('button', { name: 'Save verification' }));

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
