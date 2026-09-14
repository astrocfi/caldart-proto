/**
 * The msw server shared by every frontend test.
 *
 * Handlers here are the defaults; a test overrides them with
 * `server.use(...)` in its own file rather than editing this list.
 */
import { setupServer } from 'msw/node';

import { handlers } from './handlers';

export const server = setupServer(...handlers);
