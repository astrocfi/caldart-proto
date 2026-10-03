import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeBulkEmail } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import { ComposeStart } from './ComposeStart';

/** Render Compose with the draft screen behind it as a heading. */
function renderStart() {
  return renderRoutes(
    [
      { path: '/bulk-email/compose', element: <ComposeStart /> },
      { path: '/bulk-email/compose/:id', element: <h1>Draft screen</h1> },
    ],
    { route: '/bulk-email/compose' },
  );
}

describe('ComposeStart', () => {
  it('opens a draft and moves on to it', async () => {
    let opens = 0;
    server.use(
      http.post(`${API}/bulk-email/drafts`, () => {
        opens += 1;
        return HttpResponse.json(makeBulkEmail({ id: 12 }), { status: 201 });
      }),
    );
    const { router } = renderStart();
    await screen.findByRole('heading', { name: 'Draft screen' });
    expect([router.state.location.pathname, opens]).toEqual(['/bulk-email/compose/12', 1]);
  });

  it('says so plainly and offers to try again when the draft cannot be opened', async () => {
    let opens = 0;
    server.use(
      http.post(`${API}/bulk-email/drafts`, () => {
        opens += 1;
        return HttpResponse.json({ detail: 'No.' }, { status: 500 });
      }),
    );
    renderStart();
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be started');
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(opens).toBe(2));
  });
});
