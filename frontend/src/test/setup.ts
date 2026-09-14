import '@testing-library/jest-dom/vitest';
import { cleanup, configure } from '@testing-library/react';
import { afterAll, afterEach, beforeAll } from 'vitest'; // codespell:ignore afterall

import { resetCsrfBootstrap } from '../portal/api/client';
import { server } from './server';

// `main.tsx` mounts the portal inside `<StrictMode>`, which runs every effect as
// setup, cleanup, setup. Rendering tests the same way is what catches an effect
// that cannot survive being run twice.
configure({ reactStrictMode: true });

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));

afterEach(() => {
  cleanup();
  server.resetHandlers();
  // Drop the cookies and the client's in-flight bootstrap together, so each test
  // starts with no CSRF token and fetches its own.
  for (const cookie of document.cookie.split(';')) {
    const name = cookie.split('=')[0]?.trim();
    if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
  }
  resetCsrfBootstrap();
});

afterAll(() => server.close()); // codespell:ignore afterall
