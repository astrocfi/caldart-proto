import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import {
  API,
  NOT_VERIFIED,
  emptyVerificationCalls,
  makeVerifiedAircraft,
  verificationHandlers,
} from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { InsuranceVerificationPanel } from './InsuranceVerificationPanel';

const UNVERIFIED = makeVerifiedAircraft({
  insurance_verification: NOT_VERIFIED,
});

function renderPanel(handleClose = vi.fn(), handleSaved = vi.fn()) {
  renderWithProviders(
    <InsuranceVerificationPanel
      aircraft={UNVERIFIED}
      onSaved={handleSaved}
      onClose={handleClose}
    />,
  );
  return { handleClose, handleSaved };
}

describe('InsuranceVerificationPanel', () => {
  it('opens on the policy the record holds, unticked when unverified', () => {
    renderPanel();
    expect(screen.getByLabelText('Carrier')).toHaveValue('Avemco');
    expect(screen.getByLabelText('Insurance verified')).not.toBeChecked();
  });

  it('verifies the insurance in one save and says so', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    server.use(...verificationHandlers(calls));
    const { handleClose, handleSaved } = renderPanel();

    await user.click(screen.getByLabelText('Insurance verified'));
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Verification saved')).toBeInTheDocument();
    expect(calls.aircraft).toEqual([{ aircraftId: 1, body: { verified: true } }]);
    expect(handleSaved).toHaveBeenCalledWith(makeVerifiedAircraft());
    expect(handleClose).toHaveBeenCalled();
  });

  it('unticks the box when a field is edited, and sends the edit', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    server.use(...verificationHandlers(calls));
    renderWithProviders(
      <InsuranceVerificationPanel aircraft={makeVerifiedAircraft()} onClose={() => {}} />,
    );

    await user.clear(screen.getByLabelText('Carrier'));
    await user.type(screen.getByLabelText('Carrier'), 'AIG');
    expect(screen.getByLabelText('Insurance verified')).not.toBeChecked();
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(calls.aircraft).toHaveLength(1));
    expect(calls.aircraft[0]?.body).toEqual({ insurance_carrier: 'AIG', verified: false });
  });

  it('shows a refused field under that field', async () => {
    const user = userEvent.setup();
    server.use(
      http.put(`${API}/leader/aircraft/1/verification`, () =>
        HttpResponse.json(
          { insurance_hull_cents: ['Ensure this value is greater than or equal to 0.'] },
          { status: 400 },
        ),
      ),
    );
    renderPanel();

    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Ensure this value is greater than or equal to 0.',
    );
    expect(screen.getByLabelText('Hull')).toHaveAttribute('aria-invalid', 'true');
  });
});
