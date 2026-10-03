import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import {
  answerBulkEmail,
  makeBatch,
  makeBulkEmail,
  makePreview,
  makeRow,
} from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { BulkEmailDetail, BulkEmailPreview } from '@/portal/api/types';
import { MessagePreview, previewingLine } from './MessagePreview';

/** Ann and Bea, who both receive the email. */
const TWO = [makeRow(), makeRow({ id: 2, name: 'Bea Bell', email: 'bea@example.org' })];

/** Render the preview of `email`, whose batch holds `rows`. */
function renderPreview(rows = TWO, email: BulkEmailDetail = makeBulkEmail()) {
  const calls = answerBulkEmail({ email, batch: makeBatch(rows) });
  renderWithProviders(<MessagePreview email={email} />);
  return calls;
}

describe('previewingLine', () => {
  it('names the person and their place', () => {
    expect(previewingLine(makePreview({ position: 3, count: 38 }))).toBe(
      'Previewing as Ann Able (3 of 38)',
    );
  });

  it("says when the copy is the sender's own", () => {
    const own: BulkEmailPreview = makePreview({
      recipient: { id: null, name: 'Grace Holloway', email: 'grace@example.org' },
      position: 0,
      count: 0,
    });
    expect(previewingLine(own)).toBe(
      'Previewing as you, Grace Holloway: nobody in the batch receives it yet.',
    );
  });
});

describe('MessagePreview', () => {
  it("starts with the first person's copy", async () => {
    renderPreview();
    expect(await screen.findByText('Previewing as Ann Able (1 of 2)')).toBeVisible();
  });

  it('draws the copy in a sandboxed frame', async () => {
    renderPreview();
    const frame = await screen.findByTitle('The email as Ann Able will receive it');
    expect([frame.getAttribute('sandbox'), frame.getAttribute('srcdoc')]).toEqual([
      '',
      '<html><body><p>Dear Ann,</p></body></html>',
    ]);
  });

  it('steps to the next person and back', async () => {
    const calls = renderPreview();
    await screen.findByText('Previewing as Ann Able (1 of 2)');
    await userEvent.click(screen.getByRole('button', { name: 'Next person' }));
    expect(await screen.findByText('Previewing as Bea Bell (2 of 2)')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Previous person' }));
    await screen.findByText('Previewing as Ann Able (1 of 2)');
    expect(calls.previews).toEqual([
      { recipient_id: null },
      { recipient_id: 2 },
      { recipient_id: 1 },
    ]);
  });

  it('cannot step before the first person', async () => {
    renderPreview();
    await screen.findByText('Previewing as Ann Able (1 of 2)');
    expect(screen.getByRole('button', { name: 'Previous person' })).toBeDisabled();
  });

  it("shows the sender's own copy while nobody receives one", async () => {
    renderPreview([]);
    expect(
      await screen.findByText(
        'Previewing as you, Grace Holloway: nobody in the batch receives it yet.',
      ),
    ).toBeVisible();
  });

  it('says why the preview cannot be shown', async () => {
    renderPreview();
    server.use(
      http.post(`${API}/bulk-email/7/preview`, () =>
        HttpResponse.json({ body: ['{nickname} is not a recipient field.'] }, { status: 400 }),
      ),
    );
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(
        'The preview cannot be shown: {nickname} is not a recipient field.',
      ),
    );
  });
});
