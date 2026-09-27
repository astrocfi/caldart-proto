import { act, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import type { JSX } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { makeAircraftType } from '@test/fixtures/profile';
import { renderWithProviders } from '@test/render';
import type { AircraftType } from '@/portal/api/types';
import { SEARCH_DEBOUNCE_MS } from '@/portal/components/useDebounced';
import { AircraftTypeSelect, aircraftTypeLabel } from './AircraftTypeSelect';

/** The picker with its value held in state, as a form holds it. */
function Harness({ initial }: { initial: AircraftType | null }): JSX.Element {
  const [value, handleChange] = useState(initial);
  return <AircraftTypeSelect value={value} onChange={handleChange} />;
}

/** A userEvent instance whose internal waits advance the fake clock instead of sleeping. */
function setupUser() {
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
}

/** Type into the search box, then settle the debounce with the fake clock. */
async function search(user: ReturnType<typeof setupUser>, text: string): Promise<void> {
  await user.type(screen.getByLabelText(/^Find the aircraft type/), text);
  await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS));
}

describe('<AircraftTypeSelect/>', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('lists the types the search finds', async () => {
    const user = setupUser();
    renderWithProviders(<Harness initial={null} />);
    await search(user, 'cessna');
    expect(await screen.findByRole('option', { name: 'Cessna 172S · 4 seats' })).toBeVisible();
  });

  it('sets the type picked from the list', async () => {
    const user = setupUser();
    renderWithProviders(<Harness initial={null} />);
    await search(user, 'sr22');
    const select = screen.getByLabelText(/^Aircraft type/);
    await user.selectOptions(select, await screen.findByRole('option', { name: /^Cirrus SR22/ }));
    expect(select).toHaveDisplayValue('Cirrus SR22 · 4 seats');
  });

  it('keeps the picked type on offer while a search finds others', async () => {
    const user = setupUser();
    renderWithProviders(<Harness initial={makeAircraftType()} />);
    await search(user, 'piper');
    await screen.findByRole('option', { name: /^Piper PA-28-181/ });
    expect(screen.getByLabelText(/^Aircraft type/)).toHaveDisplayValue(
      'Cessna 182T Skylane · 4 seats',
    );
  });
});

describe('aircraftTypeLabel', () => {
  it('leaves the seats out when the registry does not say', () => {
    expect(aircraftTypeLabel(makeAircraftType({ seats: null }))).toBe('Cessna 182T Skylane');
  });
});
