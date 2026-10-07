import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { answerBulkEmail, makeBatch, makeBulkEmail } from '@test/fixtures/bulkEmail';
import { API, SENDABLE_TYPES } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { EmailTypeChoice, NO_MISSION_TYPE, NO_TYPE_HINT } from './EmailTypeChoice';

/** Render the choice for email 7, with `emailType` chosen. */
function renderChoice(emailType: number | null, isEditable = true, isCallout = false) {
  renderWithProviders(
    <EmailTypeChoice
      emailId={7}
      emailType={emailType}
      emailTypeName={emailType === null ? '' : 'Operational'}
      isCallout={isCallout}
      isEditable={isEditable}
    />,
  );
}

describe('EmailTypeChoice', () => {
  it('offers each type the sender may send, with what it is for', async () => {
    renderChoice(null);

    const mission = await screen.findByRole('radio', { name: 'Mission' });
    expect(mission).toHaveAccessibleDescription('Requests for pilots and aircraft.');
    expect(screen.getByRole('radio', { name: 'Operational' })).not.toBeChecked();
  });

  it('offers a mission callout the Mission type alone', async () => {
    renderChoice(3, true, true);

    await screen.findByRole('radio', { name: 'Mission' });
    expect(screen.getAllByRole('radio').map((radio) => radio.getAttribute('value'))).toEqual(['3']);
  });

  it('says so when a callout has no Mission type the sender may send', async () => {
    server.use(
      http.get(`${API}/email-types/sendable`, () =>
        HttpResponse.json([{ ...SENDABLE_TYPES[0], is_mission: false }]),
      ),
    );
    renderChoice(null, true, true);

    expect(await screen.findByRole('alert')).toHaveTextContent(NO_MISSION_TYPE);
  });

  it('asks for a type while none is chosen', async () => {
    renderChoice(null);

    expect(await screen.findByText(NO_TYPE_HINT, { exact: false })).toBeInTheDocument();
  });

  it('marks the chosen type and drops the request', async () => {
    renderChoice(1);

    expect(await screen.findByRole('radio', { name: 'Operational' })).toBeChecked();
    expect(screen.queryByText(NO_TYPE_HINT, { exact: false })).not.toBeInTheDocument();
  });

  it('saves the type the moment it is chosen', async () => {
    const calls = answerBulkEmail({
      email: makeBulkEmail({ email_type: null }),
      batch: makeBatch(),
    });
    renderChoice(null);

    await userEvent.click(await screen.findByRole('radio', { name: 'Mission' }));

    await waitFor(() => expect(calls.patches).toEqual([{ email_type: 3 }]));
  });

  it('puts the choice back and says why when the save is refused', async () => {
    server.use(
      http.patch(`${API}/bulk-email/7`, () =>
        HttpResponse.json(
          { email_type: ['You cannot send Mission email. Choose another type.'] },
          { status: 400 },
        ),
      ),
    );
    renderChoice(null);

    await userEvent.click(await screen.findByRole('radio', { name: 'Mission' }));

    expect(
      await screen.findByText('You cannot send Mission email. Choose another type.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Mission' })).not.toBeChecked();
  });

  it('keeps the focus on the buttons and ignores a second choice while one saves', async () => {
    const patches: unknown[] = [];
    let release: () => void = () => undefined;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.patch(`${API}/bulk-email/7`, async ({ request }) => {
        patches.push(await request.json());
        await held;
        return HttpResponse.json(makeBulkEmail({ email_type: 3, email_type_name: 'Mission' }));
      }),
    );
    renderChoice(null);
    const user = userEvent.setup();

    const mission = await screen.findByRole('radio', { name: 'Mission' });
    await user.click(mission);
    await user.click(screen.getByRole('radio', { name: 'Operational' }));

    expect(screen.getByRole('radio', { name: 'Operational' })).toHaveFocus();
    expect(mission).toBeEnabled();
    release();
    await waitFor(() => expect(patches).toEqual([{ email_type: 3 }]));
  });

  it('shows the type as text once the email can no longer change', () => {
    renderChoice(1, false);

    expect(screen.getByText('Operational')).toBeInTheDocument();
    expect(screen.queryByRole('radio')).not.toBeInTheDocument();
  });

  it('says so when the sender may send no type', async () => {
    server.use(http.get(`${API}/email-types/sendable`, () => HttpResponse.json([])));
    renderChoice(null);

    expect(
      await screen.findByText(
        'There is no type of email you may send. Ask a system administrator.',
      ),
    ).toBeInTheDocument();
  });
});
