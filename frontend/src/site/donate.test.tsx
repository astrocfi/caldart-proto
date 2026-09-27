import { HttpResponse, http } from 'msw';
import type * as ReactDOMClient from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { waitFor } from '@testing-library/react';

import { clearUrlPrefix, stampUrlPrefix } from '@test/render';
import { server } from '@test/server';

// The config request the mounted form makes keeps retrying after the 503 below, so an
// unmounted-but-not-torn-down root goes on firing it into whichever test runs next.
// Wrapping `createRoot` lets `afterEach` unmount every root the page created.
const mountedRoots: ReactDOMClient.Root[] = [];

vi.mock('react-dom/client', async (importOriginal) => {
  const actual = await importOriginal<typeof ReactDOMClient>();
  return {
    ...actual,
    createRoot: (...args: Parameters<typeof actual.createRoot>) => {
      const root = actual.createRoot(...args);
      mountedRoots.push(root);
      return root;
    },
  };
});

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
    mountedRoots.splice(0).forEach((root) => root.unmount());
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
