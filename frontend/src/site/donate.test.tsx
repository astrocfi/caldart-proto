import { HttpResponse, http } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';
import { waitFor } from '@testing-library/react';

import { clearUrlPrefix, stampUrlPrefix } from '@test/render';
import { server } from '@test/server';

/** Serve the donation config at any base and record each path it was asked for. */
function recordConfigRequests(): string[] {
  const paths: string[] = [];
  server.use(
    http.get('*/api/v1/donations/config', ({ request }) => {
      paths.push(new URL(request.url).pathname);
      return HttpResponse.json({}, { status: 503 });
    }),
  );
  return paths;
}

describe('the donation page script', () => {
  afterEach(() => {
    document.body.innerHTML = '';
    clearUrlPrefix();
  });

  it('reads the config the mount names', async () => {
    stampUrlPrefix('/x');
    document.body.innerHTML =
      '<div id="donate-app" data-config-url="/x/api/v1/donations/config"></div>';
    const paths = recordConfigRequests();

    await import('./donate');

    await waitFor(() => expect(paths).toEqual(['/x/api/v1/donations/config']));
  });

  it('falls back to the config under the URL prefix when the mount names none', async () => {
    stampUrlPrefix('/x');
    document.body.innerHTML = '<div id="donate-app"></div>';
    const paths = recordConfigRequests();

    await import('./donate');

    await waitFor(() => expect(paths).toEqual(['/x/api/v1/donations/config']));
  });
});
