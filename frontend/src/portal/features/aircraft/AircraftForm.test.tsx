/** The aircraft form's N-number typeahead over the FAA registry and its aircraft type picker. */
import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { makeAircraftType } from '@test/fixtures/profile';
import { makeRegistration } from '@test/fixtures/registry';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { AircraftPatch } from '@/portal/api/types';
import { SEARCH_DEBOUNCE_MS } from '@/portal/components/useDebounced';
import { AircraftForm } from './AircraftForm';
import type { AircraftFormValues } from './form';
import { emptyAircraftValues } from './form';

/** A userEvent instance whose internal waits advance the fake clock instead of sleeping. */
function setupUser() {
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
}

/** Render the form over `initial`, recording what it submits. */
function renderForm(initial: AircraftFormValues = emptyAircraftValues()) {
  const submitted: AircraftPatch[] = [];
  const user = setupUser();
  renderWithProviders(
    <AircraftForm
      initial={initial}
      submitLabel="Save"
      onSubmit={(payload) => submitted.push(payload)}
    />,
  );
  return { user, submitted };
}

/** Answer the N-number typeahead with `found`, recording each prefix asked about. */
function registryAnswers(asked: string[] = [], found = [makeRegistration()]) {
  return http.get(`${API}/aircraft/registrations`, ({ request }) => {
    asked.push(new URL(request.url).searchParams.get('q') ?? '');
    return HttpResponse.json(found);
  });
}

function nNumberBox(): HTMLElement {
  return screen.getByRole('combobox', { name: /^N-number/ });
}

/** Type `text` into the N-number box and settle the typeahead's debounce. */
async function typeNNumber(user: ReturnType<typeof setupUser>, text: string): Promise<void> {
  await user.type(nNumberBox(), text);
  await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS));
}

/** The values of the boxes a registration fills, in the order the form shows them. */
function filledBoxes(): string[] {
  return [
    screen.getByRole('combobox', { name: /^Aircraft type/ }),
    screen.getByLabelText('Year'),
    screen.getByLabelText('Seats'),
    screen.getByLabelText('Owner name'),
    screen.getByLabelText('Owner type'),
  ].map((box) => (box as HTMLInputElement | HTMLSelectElement).value);
}

describe('<AircraftForm/> N-number typeahead', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('asks the registry for the registrations starting with what was typed', async () => {
    const asked: string[] = [];
    server.use(registryAnswers(asked));
    const { user } = renderForm();
    await typeNNumber(user, '739');
    await screen.findByRole('listbox', { name: 'FAA registrations' });
    expect(asked.at(-1)).toBe('N739');
  });

  it('lists each registration with its type, year, and registrant', async () => {
    server.use(registryAnswers());
    const { user } = renderForm();
    await typeNNumber(user, '739');
    const option = await screen.findByRole('option', { name: /^N739TA/ });
    expect(option).toHaveTextContent('N739TA Cessna 172S 2004 PALO ALTO FLYING CLUB');
  });

  it('keeps the N-number mask on what is typed', async () => {
    server.use(registryAnswers());
    const { user } = renderForm();
    await user.type(nNumberBox(), 'n-739ta');
    expect(nNumberBox()).toHaveValue('N739TA');
  });

  it('fills the airframe and its owner from the registration picked', async () => {
    server.use(registryAnswers());
    const { user } = renderForm();
    await typeNNumber(user, '739');
    await user.click(await screen.findByRole('option', { name: /^N739TA/ }));
    expect(filledBoxes()).toEqual(['Cessna 172S', '2004', '4', 'PALO ALTO FLYING CLUB', 'fbo']);
  });

  it('fills the category and airworthiness from the registration picked', async () => {
    server.use(
      registryAnswers(
        [],
        [
          makeRegistration({
            type: makeAircraftType({
              id: 9,
              make: 'Robinson',
              model: 'R44',
              category: 'helicopter',
            }),
            airworthiness: 'standard',
          }),
        ],
      ),
    );
    const { user } = renderForm();
    await typeNNumber(user, '739');
    await user.click(await screen.findByRole('option', { name: /^N739TA/ }));
    expect([screen.getByLabelText('Category'), screen.getByLabelText('Airworthiness')]).toEqual([
      expect.objectContaining({ value: 'helicopter' }),
      expect.objectContaining({ value: 'standard' }),
    ]);
  });

  it('sets the box to the N-number picked', async () => {
    server.use(registryAnswers());
    const { user } = renderForm();
    await typeNNumber(user, '739');
    await user.click(await screen.findByRole('option', { name: /^N739TA/ }));
    expect(nNumberBox()).toHaveValue('N739TA');
  });

  it('picks with the arrow keys and Enter', async () => {
    server.use(
      registryAnswers(
        [],
        [makeRegistration(), makeRegistration({ n_number: 'N739TB', year: 1981 })],
      ),
    );
    const { user } = renderForm();
    await typeNNumber(user, '739');
    await screen.findByRole('listbox', { name: 'FAA registrations' });
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}');
    expect(screen.getByLabelText('Year')).toHaveValue('1981');
  });

  it('shuts the list on Escape without filling anything', async () => {
    server.use(registryAnswers());
    const { user } = renderForm();
    await typeNNumber(user, '739');
    await screen.findByRole('listbox', { name: 'FAA registrations' });
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('listbox', { name: 'FAA registrations' })).toBeNull();
  });

  it('says which day of the registry the details come from', async () => {
    server.use(registryAnswers());
    const { user } = renderForm();
    await typeNNumber(user, '739');
    await user.click(await screen.findByRole('option', { name: /^N739TA/ }));
    expect(screen.getByText('From FAA data as of 09/20/2026')).toBeVisible();
  });

  it('forgets what the registry said once the N-number changes', async () => {
    server.use(registryAnswers());
    const { user } = renderForm();
    await typeNNumber(user, '739');
    await user.click(await screen.findByRole('option', { name: /^N739TA/ }));
    await user.type(nNumberBox(), '{Backspace}');
    expect(screen.queryByText(/From FAA data/)).toBeNull();
  });

  it('leaves the form alone while nothing is picked', async () => {
    server.use(registryAnswers());
    const { user } = renderForm({ ...emptyAircraftValues(), year: '1999' });
    await typeNNumber(user, '739ta');
    await screen.findByRole('option', { name: /^N739TA/ });
    await user.tab();
    expect(screen.getByLabelText('Year')).toHaveValue('1999');
  });

  it('offers no Look up button', () => {
    renderForm();
    expect(screen.queryByRole('button', { name: 'Look up' })).toBeNull();
  });
});

describe('<AircraftForm/> aircraft type', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('will not submit without a type picked from the list', async () => {
    const { user, submitted } = renderForm(emptyAircraftValues('N739TA'));
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('Pick the aircraft type from the list.')).toBeVisible();
    expect(submitted).toEqual([]);
  });

  it('fills blank seats from the type picked', async () => {
    const { user } = renderForm();
    await user.type(screen.getByRole('combobox', { name: /^Aircraft type/ }), 'sr22');
    await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS));
    await user.click(await screen.findByRole('option', { name: /^Cirrus SR22/ }));
    expect(screen.getByLabelText('Seats')).toHaveValue('4');
  });

  it('sends the category and airworthiness chosen', async () => {
    const { user, submitted } = renderForm({
      ...emptyAircraftValues('N739TA'),
      type: makeAircraftType(),
    });
    await user.selectOptions(screen.getByLabelText('Category'), 'Glider');
    await user.selectOptions(screen.getByLabelText('Airworthiness'), 'Experimental');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect([submitted[0]?.category, submitted[0]?.airworthiness]).toEqual([
      'glider',
      'experimental',
    ]);
  });

  it('sends the picked type as its id', async () => {
    const { user, submitted } = renderForm(emptyAircraftValues('N739TA'));
    const aircraft = screen.getByRole('group', { name: 'Aircraft' });
    await user.type(within(aircraft).getByRole('combobox', { name: /^Aircraft type/ }), 'sr22');
    await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS));
    await user.click(await screen.findByRole('option', { name: /^Cirrus SR22/ }));
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(submitted[0]?.type_id).toBe(3);
  });
});
