import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeReminderSchedule } from '@test/fixtures/reminders';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { ReminderSchedule } from '@/portal/api/types';
import { ReminderScheduleCard } from './ReminderScheduleCard';

const SAVED: ReminderSchedule = makeReminderSchedule({
  first_days_before: 45,
  updated_by: 'Dana Fiske',
  updated_at: '2026-09-30T19:00:00Z',
});

/** Answer `GET /admin/reminders/schedule` with `schedule`. */
function serveSchedule(schedule: ReminderSchedule): void {
  server.use(http.get(`${API}/admin/reminders/schedule`, () => HttpResponse.json(schedule)));
}

describe('<ReminderScheduleCard/>', () => {
  it('puts the stored days in the four fields', async () => {
    serveSchedule(SAVED);
    renderWithProviders(<ReminderScheduleCard />);

    expect(await screen.findByLabelText('First reminder')).toHaveValue(45);
    expect(screen.getByLabelText('Second reminder')).toHaveValue(30);
    expect(screen.getByLabelText('Final reminder')).toHaveValue(7);
    expect(screen.getByLabelText('Lapsed reminder')).toHaveValue(30);
  });

  it('says who saved the schedule last and when', async () => {
    serveSchedule(SAVED);
    renderWithProviders(<ReminderScheduleCard />);

    expect(await screen.findByText('Last saved 09/30/2026 by Dana Fiske')).toBeInTheDocument();
  });

  it('says the defaults apply before anyone saves a schedule', async () => {
    renderWithProviders(<ReminderScheduleCard />);

    expect(
      await screen.findByText('The default schedule: nobody has changed it.'),
    ).toBeInTheDocument();
  });

  it('saves the edited days', async () => {
    const bodies: unknown[] = [];
    server.use(
      http.put(`${API}/admin/reminders/schedule`, async ({ request }) => {
        const body = (await request.json()) as Partial<ReminderSchedule>;
        bodies.push(body);
        return HttpResponse.json({ ...SAVED, ...body });
      }),
    );
    renderWithProviders(<ReminderScheduleCard />);

    const final = await screen.findByLabelText('Final reminder');
    await userEvent.clear(final);
    await userEvent.type(final, '3');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Reminder schedule saved.')).toBeInTheDocument();
    expect(bodies).toEqual([
      {
        first_days_before: 60,
        second_days_before: 30,
        final_days_before: 3,
        lapsed_days_after: 30,
      },
    ]);
  });

  it('shows the stored line of the saved schedule after a save', async () => {
    server.use(http.put(`${API}/admin/reminders/schedule`, () => HttpResponse.json(SAVED)));
    renderWithProviders(<ReminderScheduleCard />);

    await screen.findByLabelText('First reminder');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Last saved 09/30/2026 by Dana Fiske')).toBeInTheDocument();
  });

  it('shows the rule a refused day breaks under its field', async () => {
    server.use(
      http.put(`${API}/admin/reminders/schedule`, () =>
        HttpResponse.json(
          { lapsed_days_after: ['The lapsed reminder must be 7 to 365 days after expiry.'] },
          { status: 400 },
        ),
      ),
    );
    renderWithProviders(<ReminderScheduleCard />);

    const lapsed = await screen.findByLabelText('Lapsed reminder');
    await userEvent.clear(lapsed);
    await userEvent.type(lapsed, '3');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(
      await screen.findByText('The lapsed reminder must be 7 to 365 days after expiry.'),
    ).toBeInTheDocument();
    expect(lapsed).toHaveAttribute('aria-invalid', 'true');
  });

  it('asks for a number in a field left empty, and sends nothing', async () => {
    const bodies: unknown[] = [];
    server.use(
      http.put(`${API}/admin/reminders/schedule`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(SAVED);
      }),
    );
    renderWithProviders(<ReminderScheduleCard />);

    const second = await screen.findByLabelText('Second reminder');
    await userEvent.clear(second);
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Enter a number of days.')).toBeInTheDocument();
    expect(bodies).toEqual([]);
  });

  it.each([
    ['First reminder', '1', '180'],
    ['Lapsed reminder', '7', '365'],
  ])('bounds the %s field from %s to %s', async (label, min, max) => {
    renderWithProviders(<ReminderScheduleCard />);

    const field = await screen.findByLabelText(label);
    expect([field.getAttribute('min'), field.getAttribute('max')]).toEqual([min, max]);
  });

  it('reads the schedule out without a form when read-only', async () => {
    serveSchedule(SAVED);
    renderWithProviders(<ReminderScheduleCard readOnly />);

    const first = await screen.findByText('First reminder');
    expect(first.nextElementSibling).toHaveTextContent('45 days before expiry');
    expect(screen.getByText('Lapsed reminder').nextElementSibling).toHaveTextContent(
      '30 days after expiry',
    );
  });

  it('offers no field or Save button when read-only', async () => {
    serveSchedule(SAVED);
    renderWithProviders(<ReminderScheduleCard readOnly />);

    await screen.findByText('Last saved 09/30/2026 by Dana Fiske');
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument();
  });
});
