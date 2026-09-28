import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { useState } from 'react';
import type { JSX } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { makeAircraftType } from '@test/fixtures/profile';
import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { AircraftType, RoleSlug } from '@/portal/api/types';
import { SEARCH_DEBOUNCE_MS } from '@/portal/components/useDebounced';
import { AircraftTypePicker, aircraftTypeName } from './AircraftTypePicker';

/** The picker with its value held in state, as a form holds it, and read back below it. */
function Harness({ initial = null }: { initial?: AircraftType | null }): JSX.Element {
  const [value, handleChange] = useState(initial);
  return (
    <form onSubmit={(event) => event.preventDefault()}>
      <AircraftTypePicker value={value} onChange={handleChange} />
      <output aria-label="Picked">{value === null ? 'none' : String(value.id)}</output>
      <button type="button" onClick={() => handleChange(makeAircraftType({ id: 3 }))}>
        Set from outside
      </button>
    </form>
  );
}

/** A userEvent instance whose internal waits advance the fake clock instead of sleeping. */
function setupUser() {
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
}

/** Sign in with `roles`, render the picker, and hand back a user to drive it. */
function renderPicker(roles: RoleSlug[] = ['member'], initial: AircraftType | null = null) {
  server.use(signedInAs(makeUser({ roles })));
  const user = setupUser();
  renderWithProviders(<Harness initial={initial} />);
  return user;
}

/** Type into the Aircraft type box, then settle the debounce with the fake clock. */
async function search(user: ReturnType<typeof setupUser>, text: string): Promise<void> {
  await user.type(screen.getByRole('combobox', { name: /^Aircraft type/ }), text);
  await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS));
}

function picked(): string | null {
  return screen.getByRole('status', { name: 'Picked' }).textContent;
}

describe('<AircraftTypePicker/>', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('lists the types the search finds, with their seats', async () => {
    const user = renderPicker();
    await search(user, 'cessna');
    expect(await screen.findByRole('option', { name: 'Cessna 172S 4 seats' })).toBeVisible();
  });

  it('sets the type picked from the list', async () => {
    const user = renderPicker();
    await search(user, 'sr22');
    await user.click(await screen.findByRole('option', { name: /^Cirrus SR22/ }));
    expect(picked()).toBe('3');
  });

  it('writes the picked type into the box', async () => {
    const user = renderPicker();
    await search(user, 'sr22');
    await user.click(await screen.findByRole('option', { name: /^Cirrus SR22/ }));
    expect(screen.getByRole('combobox', { name: /^Aircraft type/ })).toHaveValue('Cirrus SR22');
  });

  it('starts with the type the record already has', () => {
    renderPicker(['member'], makeAircraftType());
    expect(screen.getByRole('combobox', { name: /^Aircraft type/ })).toHaveValue(
      'Cessna 182T Skylane',
    );
  });

  it('drops the type once the box is typed in, so only a pick sets it', async () => {
    const user = renderPicker(['member'], makeAircraftType());
    await user.type(screen.getByRole('combobox', { name: /^Aircraft type/ }), 'x');
    expect(picked()).toBe('none');
  });

  it('shows a type set from outside, such as by a registration picked', async () => {
    const user = renderPicker();
    await user.click(screen.getByRole('button', { name: 'Set from outside' }));
    expect(screen.getByRole('combobox', { name: /^Aircraft type/ })).toHaveValue(
      'Cessna 182T Skylane',
    );
  });

  it('offers a member no way to add a type the search cannot find', async () => {
    const user = renderPicker(['member']);
    await search(user, 'zzzz');
    await waitFor(() => expect(screen.getByText('No aircraft type matches that.')).toBeVisible());
    expect(screen.queryByRole('button', { name: 'Add a type' })).toBeNull();
  });

  it('offers an account administrator Add a type when the search finds nothing', async () => {
    const user = renderPicker(['account_admin']);
    await search(user, 'zzzz');
    expect(await screen.findByRole('button', { name: 'Add a type' })).toBeVisible();
  });

  it('keeps the focus in the box when Add a type is pressed', async () => {
    // Leaving the box marks it, and the mark pushes the button down under the
    // pointer; the press must not move the focus, or its click lands elsewhere.
    const user = renderPicker(['account_admin']);
    await search(user, 'zzzz');
    const add = await screen.findByRole('button', { name: 'Add a type' });
    expect(fireEvent.mouseDown(add)).toBe(false);
  });

  it('offers Add a type to a system administrator too', async () => {
    const user = renderPicker(['system_admin']);
    await search(user, 'zzzz');
    expect(await screen.findByRole('button', { name: 'Add a type' })).toBeVisible();
  });

  it('keeps Add a type out of the way while the search finds something', async () => {
    const user = renderPicker(['account_admin']);
    await search(user, 'cessna');
    await screen.findByRole('option', { name: /^Cessna 172S/ });
    expect(screen.queryByRole('button', { name: 'Add a type' })).toBeNull();
  });

  it('adds the type and picks it at once', async () => {
    const posted: unknown[] = [];
    server.use(
      http.post(`${API}/aircraft/types`, async ({ request }) => {
        posted.push(await request.json());
        return HttpResponse.json(
          { id: 99, make: 'Aeropro', model: 'Eurofox 3K', seats: 2, engines: 1, is_custom: true },
          { status: 201 },
        );
      }),
    );
    const user = renderPicker(['account_admin']);
    await search(user, 'zzzz');
    await user.click(await screen.findByRole('button', { name: 'Add a type' }));
    await user.type(screen.getByLabelText(/^Make/), 'Aeropro');
    await user.type(screen.getByLabelText(/^Model/), 'Eurofox 3K');
    await user.type(screen.getByLabelText(/^Seats/), '2');
    await user.type(screen.getByLabelText(/^Engines/), '1');
    await user.click(screen.getByRole('button', { name: 'Add type' }));
    await waitFor(() => expect(picked()).toBe('99'));
    expect(posted).toEqual([{ make: 'Aeropro', model: 'Eurofox 3K', seats: 2, engines: 1 }]);
  });

  it('leaves seats and engines out of the request when they are blank', async () => {
    const posted: unknown[] = [];
    server.use(
      http.post(`${API}/aircraft/types`, async ({ request }) => {
        posted.push(await request.json());
        return HttpResponse.json(makeAircraftType({ id: 98, is_custom: true }), { status: 201 });
      }),
    );
    const user = renderPicker(['account_admin']);
    await search(user, 'zzzz');
    await user.click(await screen.findByRole('button', { name: 'Add a type' }));
    await user.type(screen.getByLabelText(/^Make/), 'Aeropro');
    await user.type(screen.getByLabelText(/^Model/), 'Eurofox');
    await user.click(screen.getByRole('button', { name: 'Add type' }));
    await waitFor(() => expect(picked()).toBe('98'));
    expect(posted).toEqual([{ make: 'Aeropro', model: 'Eurofox' }]);
  });

  it('asks for the make and the model before it adds anything', async () => {
    const user = renderPicker(['account_admin']);
    await search(user, 'zzzz');
    await user.click(await screen.findByRole('button', { name: 'Add a type' }));
    await user.click(screen.getByRole('button', { name: 'Add type' }));
    expect(screen.getByText('Enter the model.')).toBeVisible();
  });

  it("shows the server's refusal under the model", async () => {
    server.use(
      http.post(`${API}/aircraft/types`, () =>
        HttpResponse.json({ model: ['That aircraft type is already listed.'] }, { status: 400 }),
      ),
    );
    const user = renderPicker(['account_admin']);
    await search(user, 'zzzz');
    await user.click(await screen.findByRole('button', { name: 'Add a type' }));
    await user.type(screen.getByLabelText(/^Make/), 'Cessna');
    await user.type(screen.getByLabelText(/^Model/), '172S');
    await user.click(screen.getByRole('button', { name: 'Add type' }));
    expect(await screen.findByText('That aircraft type is already listed.')).toBeVisible();
  });

  it('adds the type on Enter without submitting the form around it', async () => {
    const handleSubmit = vi.fn((event: React.FormEvent) => event.preventDefault());
    server.use(
      signedInAs(makeUser({ roles: ['account_admin'] })),
      http.post(`${API}/aircraft/types`, () =>
        HttpResponse.json(makeAircraftType({ id: 97, is_custom: true }), { status: 201 }),
      ),
    );
    const user = setupUser();
    function Outer(): JSX.Element {
      const [value, handleChange] = useState<AircraftType | null>(null);
      return (
        <form onSubmit={handleSubmit}>
          <AircraftTypePicker value={value} onChange={handleChange} />
          <output aria-label="Picked">{value === null ? 'none' : String(value.id)}</output>
        </form>
      );
    }
    renderWithProviders(<Outer />);
    await search(user, 'zzzz');
    await user.click(await screen.findByRole('button', { name: 'Add a type' }));
    await user.type(screen.getByLabelText(/^Make/), 'Aeropro');
    await user.type(screen.getByLabelText(/^Model/), 'Eurofox{Enter}');
    await waitFor(() => expect(picked()).toBe('97'));
    expect(handleSubmit).not.toHaveBeenCalled();
  });

  it('closes the add form on Cancel', async () => {
    const user = renderPicker(['account_admin']);
    await search(user, 'zzzz');
    await user.click(await screen.findByRole('button', { name: 'Add a type' }));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByLabelText(/^Make/)).toBeNull();
  });
});

describe('aircraftTypeName', () => {
  it('reads as the make and the model', () => {
    expect(aircraftTypeName(makeAircraftType())).toBe('Cessna 182T Skylane');
  });
});
