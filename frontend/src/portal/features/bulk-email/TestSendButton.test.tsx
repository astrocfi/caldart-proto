import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { TestSendButton } from './TestSendButton';

/** Answer the test endpoint of email 7 with `response`, counting the presses. */
function answerTest(response: () => Response): { presses: number } {
  const count = { presses: 0 };
  server.use(
    http.post(`${API}/bulk-email/7/test`, () => {
      count.presses += 1;
      return response();
    }),
  );
  return count;
}

/** Render the button for email 7, saving first with `isSaved` as the outcome. */
function renderButton(isSaved = true): void {
  renderWithProviders(<TestSendButton emailId={7} onBeforeSend={() => Promise.resolve(isSaved)} />);
}

describe('TestSendButton', () => {
  it('says where the test went', async () => {
    answerTest(() => HttpResponse.json({ to: 'pat@example.org' }));
    renderButton();
    await userEvent.click(screen.getByRole('button', { name: 'Send me a test' }));
    expect(await screen.findByRole('status')).toHaveTextContent('A test went to pat@example.org.');
  });

  it('sends one more test on every press', async () => {
    const count = answerTest(() => HttpResponse.json({ to: 'pat@example.org' }));
    renderButton();
    const button = screen.getByRole('button', { name: 'Send me a test' });
    await userEvent.click(button);
    await screen.findByRole('status');
    await userEvent.click(button);
    await waitFor(() => expect(count.presses).toBe(2));
  });

  it("shows the server's words when the mail server refused the test", async () => {
    answerTest(() =>
      HttpResponse.json(
        { detail: 'The mail server refused the test. Try again in a minute.' },
        { status: 503 },
      ),
    );
    renderButton();
    await userEvent.click(screen.getByRole('button', { name: 'Send me a test' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The mail server refused the test. Try again in a minute.',
    );
  });

  it('lists the errors the checks found instead of sending', async () => {
    answerTest(() =>
      HttpResponse.json(
        { checks: [{ code: 'no_subject', level: 'error', message: 'Write a subject.' }] },
        { status: 400 },
      ),
    );
    renderButton();
    await userEvent.click(screen.getByRole('button', { name: 'Send me a test' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No test was sent. Fix these first:Write a subject.',
    );
  });

  it('sends nothing when the latest words could not be saved', async () => {
    const count = answerTest(() => HttpResponse.json({ to: 'pat@example.org' }));
    renderButton(false);
    await userEvent.click(screen.getByRole('button', { name: 'Send me a test' }));
    expect([(await screen.findByRole('alert')).textContent, count.presses]).toEqual([
      'Your latest changes could not be saved, so no test was sent. Try again in a moment.',
      0,
    ]);
  });
});
