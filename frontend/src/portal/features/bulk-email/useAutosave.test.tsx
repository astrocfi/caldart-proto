import { QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import { delay, HttpResponse, http } from 'msw';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { answerBulkEmail, makeBatch, makeBulkEmail } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { makeTestQueryClient } from '@test/render';
import { server } from '@test/server';
import { AUTOSAVE_MS, changedFields, useAutosave } from './useAutosave';

/** Render the hook for a blank draft, answering its saves. */
function renderAutosave() {
  const email = makeBulkEmail({ subject: '', body: '' });
  const calls = answerBulkEmail({ email, batch: makeBatch([]) });
  const client = makeTestQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const hook = renderHook(() => useAutosave(email, true), { wrapper });
  return { ...hook, calls };
}

/** Let the clock run `ms` and every request and promise it set going settle. */
async function pass(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('changedFields', () => {
  it('names only the fields that differ', () => {
    expect(changedFields({ subject: 'a', body: 'b' }, { subject: 'a', body: 'c' })).toEqual({
      body: 'c',
    });
  });
});

describe('useAutosave', () => {
  it('says nothing about saving before anything is typed', () => {
    const { result } = renderAutosave();
    expect(result.current.saveState).toBe('idle');
  });

  it('saves the words once the typing pauses', async () => {
    const { result, calls } = renderAutosave();
    act(() => result.current.setSubject('Fly-in'));
    await pass(AUTOSAVE_MS + 50);
    expect(calls.patches).toEqual([{ subject: 'Fly-in' }]);
  });

  it('never sends older words over a save made at once', async () => {
    const { result, calls } = renderAutosave();
    act(() => {
      result.current.setSubject('Fly-in');
      result.current.setBody('Bring gloves.');
    });
    await act(async () => {
      await result.current.flush();
    });
    await pass(AUTOSAVE_MS * 2);
    expect(calls.patches).toEqual([{ subject: 'Fly-in', body: 'Bring gloves.' }]);
  });

  it('never has two saves on their way at once, and the newest words land last', async () => {
    const { result, calls } = renderAutosave();
    let inFlight = 0;
    let most = 0;
    server.use(
      http.patch(`${API}/bulk-email/7`, async ({ request }) => {
        inFlight += 1;
        most = Math.max(most, inFlight);
        calls.patches.push(await request.json());
        await delay(500);
        inFlight -= 1;
        return HttpResponse.json(makeBulkEmail());
      }),
    );
    act(() => result.current.setSubject('Fly'));
    await pass(AUTOSAVE_MS + 50);
    act(() => result.current.setSubject('Fly-in'));
    let flushed = false;
    act(() => {
      void result.current.flush().then(() => {
        flushed = true;
      });
    });
    await pass(2000);
    expect([most, flushed, calls.patches.at(-1)]).toEqual([1, true, { subject: 'Fly-in' }]);
  });
});
