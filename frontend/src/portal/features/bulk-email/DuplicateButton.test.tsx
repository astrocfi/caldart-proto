import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeBulkEmail } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import { DuplicateButton } from './DuplicateButton';

/** Answer `POST /bulk-email/7/duplicate` with draft 21, recording each body. */
function answerDuplicate(): unknown[] {
  const bodies: unknown[] = [];
  server.use(
    http.post(`${API}/bulk-email/7/duplicate`, async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json(makeBulkEmail({ id: 21 }), { status: 201 });
    }),
  );
  return bodies;
}

/** The button for email 7, with a stand-in for the compose screen. */
function renderButton(): ReturnType<typeof renderRoutes> {
  return renderRoutes(
    [
      { path: '/', element: <DuplicateButton emailId={7} subject="Hangar day" /> },
      { path: '/bulk-email/compose/:id', element: <p>The compose screen</p> },
    ],
    { route: '/' },
  );
}

describe('DuplicateButton', () => {
  it('asks how to copy before it copies anything', async () => {
    const bodies = answerDuplicate();
    const user = userEvent.setup();
    renderButton();
    await user.click(screen.getByRole('button', { name: 'Duplicate' }));
    expect(screen.getByText(/Start a new draft from "Hangar day"/)).toBeVisible();
    expect(bodies).toEqual([]);
  });

  it.each([
    ['Copy the message', false],
    ['Copy the message and the people', true],
  ])('%s copies with copy_recipients %s and opens the new draft', async (choice, copies) => {
    const bodies = answerDuplicate();
    const user = userEvent.setup();
    const { router } = renderButton();
    await user.click(screen.getByRole('button', { name: 'Duplicate' }));
    await user.click(screen.getByRole('button', { name: choice }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/bulk-email/compose/21'));
    expect(bodies).toEqual([{ copy_recipients: copies }]);
  });
});
