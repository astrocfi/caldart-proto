import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { BulkEmailPatch } from '@/portal/api/types';
import { makeBulkEmail } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { CALLOUT_HINT, CalloutFields } from './CalloutFields';

/** When the callout in these tests closes: 8:30 AM Pacific time on 04/09/2026. */
const CLOSES_AT = '2026-04-09T15:30:00Z';

/** Answer every PATCH of email 7 with the email, and record each one. */
function recordPatches(): BulkEmailPatch[] {
  const patches: BulkEmailPatch[] = [];
  server.use(
    http.patch(`${API}/bulk-email/7`, async ({ request }) => {
      const patch = (await request.json()) as BulkEmailPatch;
      patches.push(patch);
      return HttpResponse.json(
        makeBulkEmail({ is_callout: true, closes_at: CLOSES_AT, email_type_name: 'Mission' }),
      );
    }),
  );
  return patches;
}

/** Render the fields for email 7. */
function renderFields(isCallout: boolean, isEditable = true) {
  renderWithProviders(
    <CalloutFields
      emailId={7}
      isCallout={isCallout}
      closesAt={isCallout ? CLOSES_AT : null}
      isEditable={isEditable}
    />,
  );
}

describe('CalloutFields', () => {
  it('offers the switch, off, with what a callout does', () => {
    renderFields(false);

    const toggle = screen.getByRole('switch', { name: 'This is a mission callout' });
    expect(toggle).not.toBeChecked();
    expect(toggle).toHaveAccessibleDescription(CALLOUT_HINT);
  });

  it('asks for no close time while the email is not a callout', () => {
    renderFields(false);

    expect(screen.queryByRole('group', { name: 'Answers close' })).not.toBeInTheDocument();
  });

  it('saves the switch the moment it is turned on', async () => {
    const patches = recordPatches();
    renderFields(false);

    await userEvent.click(screen.getByRole('switch', { name: 'This is a mission callout' }));

    await waitFor(() => expect(patches).toEqual([{ is_callout: true }]));
  });

  it('shows when the answers close, in the site time zone', () => {
    renderFields(true);

    const closes = screen.getByRole('group', { name: 'Answers close' });
    expect(closes).toBeInTheDocument();
    expect(screen.getByLabelText('Date')).toHaveValue('2026-04-09');
    expect(screen.getByLabelText('Time')).toHaveValue('08:30');
  });

  it('saves a new close time the moment it is chosen', async () => {
    const patches = recordPatches();
    renderFields(true);

    await userEvent.selectOptions(screen.getByLabelText('Time'), '18:00');

    await waitFor(() => expect(patches).toEqual([{ closes_at: '2026-04-09T18:00' }]));
  });

  it('says why a close time is refused', async () => {
    server.use(
      http.patch(`${API}/bulk-email/7`, () =>
        HttpResponse.json({ closes_at: ['Choose a time in the future.'] }, { status: 400 }),
      ),
    );
    renderFields(true);

    await userEvent.selectOptions(screen.getByLabelText('Time'), '06:00');

    expect(await screen.findByRole('alert')).toHaveTextContent('Choose a time in the future.');
  });

  it('shows a sent callout and when its answers close, without the switch', () => {
    renderFields(true, false);

    expect(screen.queryByRole('switch')).not.toBeInTheDocument();
    expect(screen.getByText(/answers close 04\/09\/2026 at 8:30 AM Pacific time/)).toBeVisible();
  });

  it('shows nothing for a sent email that is not a callout', () => {
    renderFields(false, false);

    expect(screen.queryByText(/Mission callout/)).not.toBeInTheDocument();
  });
});
