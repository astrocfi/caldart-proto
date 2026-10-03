import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeBulkEmail } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { BulkEmailPatch } from '@/portal/api/types';
import { ReplyToField, replyToHint } from './ReplyToField';

/** Answer `PATCH /bulk-email/7`, refusing any address without a dot after the @. */
function answerPatches(): BulkEmailPatch[] {
  const patches: BulkEmailPatch[] = [];
  server.use(
    http.patch(`${API}/bulk-email/7`, async ({ request }) => {
      const patch = (await request.json()) as BulkEmailPatch;
      patches.push(patch);
      if (patch.reply_to !== undefined && patch.reply_to !== '' && !/@.+\./.test(patch.reply_to)) {
        return HttpResponse.json({ reply_to: ['Enter a valid email address.'] }, { status: 400 });
      }
      return HttpResponse.json(makeBulkEmail({ reply_to: patch.reply_to ?? '' }));
    }),
  );
  return patches;
}

/** Render the field for email 7, holding `saved`, with a button to move the focus to. */
function renderField(saved = 'grace@example.org'): void {
  renderWithProviders(
    <>
      <ReplyToField emailId={7} saved={saved} defaultReplyTo="ops@example.org" />
      <button type="button">Elsewhere</button>
    </>,
  );
}

describe('replyToHint', () => {
  it('names the default an empty field falls back to', () => {
    expect(replyToHint('ops@example.org')).toBe(
      'When someone replies to this email, the reply goes to this address. Leave it empty ' +
        'to use ops@example.org.',
    );
  });

  it('says only what the field is for when there is no default', () => {
    expect(replyToHint('')).toBe(
      'When someone replies to this email, the reply goes to this address.',
    );
  });
});

describe('ReplyToField', () => {
  it('shows the address it holds, described by its hint', () => {
    renderField();
    expect(screen.getByRole('textbox', { name: 'Reply-To' })).toHaveAccessibleDescription(
      replyToHint('ops@example.org'),
    );
  });

  it('saves the address on its own when the field is left', async () => {
    const patches = answerPatches();
    renderField();
    const field = screen.getByRole('textbox', { name: 'Reply-To' });
    await userEvent.clear(field);
    await userEvent.type(field, 'marin@example.org');
    await userEvent.click(screen.getByRole('button', { name: 'Elsewhere' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Reply-To saved.');
    expect(patches).toEqual([{ reply_to: 'marin@example.org' }]);
  });

  it('saves nothing while the address is being typed', async () => {
    const patches = answerPatches();
    renderField();
    await userEvent.type(screen.getByRole('textbox', { name: 'Reply-To' }), 'x');
    expect(patches).toEqual([]);
  });

  it('saves on Enter', async () => {
    const patches = answerPatches();
    renderField('');
    await userEvent.type(
      screen.getByRole('textbox', { name: 'Reply-To' }),
      'ops@example.org{Enter}',
    );
    await waitFor(() => expect(patches).toEqual([{ reply_to: 'ops@example.org' }]));
  });

  it('names a refused address under the field and marks it', async () => {
    answerPatches();
    renderField();
    const field = screen.getByRole('textbox', { name: 'Reply-To' });
    await userEvent.clear(field);
    await userEvent.type(field, 'marin@');
    await userEvent.click(screen.getByRole('button', { name: 'Elsewhere' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a valid email address.');
    expect(field).toHaveAttribute('aria-invalid', 'true');
  });

  it('sends nothing when the address has not changed', async () => {
    const patches = answerPatches();
    renderField();
    await userEvent.click(screen.getByRole('textbox', { name: 'Reply-To' }));
    await userEvent.click(screen.getByRole('button', { name: 'Elsewhere' }));
    expect(patches).toEqual([]);
  });
});
