/**
 * Where the guards sit relative to a route's `lazy` module.
 *
 * The router resolves a matched route's `lazy` module while it navigates, so
 * the guard above it renders only afterwards and a refused visitor has already
 * fetched that page's chunk.  This file pins that, because the developer guide
 * describes the cost and someone reading the route table would guess otherwise.
 *
 * It stands apart from `index.test.tsx` because a `vi.mock` factory runs once
 * per module registry: counting the loads only means anything in a file where
 * one test opens the path.
 */
import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { makeUser, signedInAs } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import { routes } from './index';

const { systemPageLoads } = vi.hoisted(() => ({ systemPageLoads: { count: 0 } }));

vi.mock('../features/system/SystemPage', () => {
  systemPageLoads.count += 1;
  return {
    SystemPage: function SystemPage() {
      return <h1>System</h1>;
    },
  };
});

describe('a guarded route that loads on demand', () => {
  it('has already fetched the page module when the guard refuses', async () => {
    server.use(signedInAs(makeUser({ roles: ['member'] })));

    renderRoutes(routes, { route: '/system' });

    expect(await screen.findByText('You do not have access to this page')).toBeInTheDocument();
    await waitFor(() => expect(systemPageLoads.count).toBe(1));
  });
});
