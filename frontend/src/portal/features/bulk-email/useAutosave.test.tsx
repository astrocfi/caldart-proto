import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';

import { answerBulkEmail, makeBatch, makeBulkEmail } from '@test/fixtures/bulkEmail';
import { makeTestQueryClient } from '@test/render';
import { QueryClientProvider } from '@tanstack/react-query';
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

describe('changedFields', () => {
  it('names only the fields that differ', () => {
    expect(changedFields({ subject: 'a', body: 'b' }, { subject: 'a', body: 'c' })).toEqual({
      body: 'c',
    });
  });
});

describe('useAutosave', () => {
  it('saves the words once the typing pauses', async () => {
    const { result, calls } = renderAutosave();
    act(() => result.current.setSubject('Fly-in'));
    await waitFor(() => expect(calls.patches).toEqual([{ subject: 'Fly-in' }]), {
      timeout: AUTOSAVE_MS * 3,
    });
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
    await new Promise((settle) => setTimeout(settle, AUTOSAVE_MS * 2));
    expect(calls.patches).toEqual([{ subject: 'Fly-in', body: 'Bring gloves.' }]);
  });
});
