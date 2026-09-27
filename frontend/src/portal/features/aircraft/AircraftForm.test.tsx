/** The aircraft form's Look up on the N-number and its aircraft type picker. */
import { act, screen, waitFor, within } from '@testing-library/react';
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

/** Answer a Look up of `N739TA` with the fixture registration, recording each one asked. */
function registryAnswers(asked: string[] = []) {
  return http.get(`${API}/aircraft/registry/:nNumber`, ({ params }) => {
    asked.push(String(params.nNumber));
    return HttpResponse.json(makeRegistration());
  });
}

function nNumberBox(): HTMLElement {
  return screen.getByLabelText(/^N-number/);
}

describe('<AircraftForm/> Look up', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('fills the airframe and its owner from the registry', async () => {
    server.use(registryAnswers());
    const { user } = renderForm();
    await user.type(nNumberBox(), '739ta');
    await user.click(screen.getByRole('button', { name: 'Look up' }));
    await screen.findByText(/From the FAA registry/);
    const boxes = [
      screen.getByRole('combobox', { name: /^Aircraft type/ }),
      screen.getByLabelText('Year'),
      screen.getByLabelText('Seats'),
      screen.getByLabelText('Owner name'),
      screen.getByLabelText('Owner type'),
    ] as (HTMLInputElement | HTMLSelectElement)[];
    expect(boxes.map((box) => box.value)).toEqual([
      'Cessna 172S',
      '2004',
      '4',
      'PALO ALTO FLYING CLUB',
      'fbo',
    ]);
  });

  it('says which day of the registry the details come from', async () => {
    server.use(registryAnswers());
    const { user } = renderForm();
    await user.type(nNumberBox(), '739ta');
    await user.click(screen.getByRole('button', { name: 'Look up' }));
    expect(await screen.findByText('From the FAA registry as of 2026/09/20')).toBeVisible();
  });

  it('says so when the registry has no such registration, and leaves the form alone', async () => {
    server.use(
      http.get(`${API}/aircraft/registry/:nNumber`, () =>
        HttpResponse.json({ detail: 'No registration for N1 in the registry.' }, { status: 404 }),
      ),
    );
    const { user } = renderForm({ ...emptyAircraftValues(), year: '1999' });
    await user.type(nNumberBox(), '1');
    await user.click(screen.getByRole('button', { name: 'Look up' }));
    expect(await screen.findByText('Not in the FAA registry')).toBeVisible();
    expect(screen.getByLabelText('Year')).toHaveValue('1999');
  });

  it('shows nothing when the lookup fails', async () => {
    let asked = 0;
    server.use(
      http.get(`${API}/aircraft/registry/:nNumber`, () => {
        asked += 1;
        return HttpResponse.error();
      }),
    );
    const { user } = renderForm();
    await user.type(nNumberBox(), '739ta');
    await user.tab();
    await waitFor(() => expect(asked).toBe(1));
    await act(() => vi.advanceTimersByTimeAsync(50));
    expect(screen.queryByText(/FAA registry/)).toBeNull();
  });

  it('looks up a registration when the N-number box is left', async () => {
    const asked: string[] = [];
    server.use(registryAnswers(asked));
    const { user } = renderForm();
    await user.type(nNumberBox(), '739ta');
    await user.tab();
    await screen.findByText(/From the FAA registry/);
    expect(asked).toEqual(['N739TA']);
  });

  it('leaves a box holding no registration without asking', async () => {
    const asked: string[] = [];
    server.use(registryAnswers(asked));
    const { user } = renderForm();
    await user.type(nNumberBox(), 'N');
    await user.tab();
    await act(() => vi.advanceTimersByTimeAsync(50));
    expect(asked).toEqual([]);
  });

  it("does not look up the record's own registration again as the box is passed through", async () => {
    const asked: string[] = [];
    server.use(registryAnswers(asked));
    const { user } = renderForm({
      ...emptyAircraftValues('N739TA'),
      type: makeAircraftType(),
    });
    await user.click(nNumberBox());
    await user.tab();
    await act(() => vi.advanceTimersByTimeAsync(50));
    expect(asked).toEqual([]);
  });

  it('forgets what the registry said once the N-number changes', async () => {
    server.use(registryAnswers());
    const { user } = renderForm();
    await user.type(nNumberBox(), '739ta');
    await user.click(screen.getByRole('button', { name: 'Look up' }));
    await screen.findByText(/From the FAA registry/);
    await user.type(nNumberBox(), '{Backspace}');
    expect(screen.queryByText(/From the FAA registry/)).toBeNull();
  });

  it('drops an answer that arrives after the N-number changed', async () => {
    let release: () => void = () => undefined;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    let asked = 0;
    server.use(
      http.get(`${API}/aircraft/registry/:nNumber`, async () => {
        asked += 1;
        await held;
        return HttpResponse.json(makeRegistration());
      }),
    );
    const { user } = renderForm();
    await user.type(nNumberBox(), '739ta');
    await user.tab();
    await waitFor(() => expect(asked).toBe(1));
    await user.clear(nNumberBox());
    await user.type(nNumberBox(), '456cd');
    release();
    await act(() => vi.advanceTimersByTimeAsync(50));
    const boxes = [
      screen.getByRole('combobox', { name: /^Aircraft type/ }),
      screen.getByLabelText('Year'),
      screen.getByLabelText('Owner name'),
      screen.queryByText(/FAA registry/)?.textContent ?? '',
    ].map((box) => (typeof box === 'string' ? box : (box as HTMLInputElement).value));
    expect(boxes).toEqual(['', '', '', '']);
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
