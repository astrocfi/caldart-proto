import { HttpResponse, http } from 'msw';
import type { HttpHandler } from 'msw';

import type { MembershipStatus, RoleSlug, User } from '../portal/api/types';

export const API = '/api/v1';

/** The value the default `GET /auth/csrf` handler hands out. */
export const TEST_CSRF_TOKEN = 'test-csrf-token';

export const NO_MEMBERSHIP: MembershipStatus = {
  status: 'none',
  expires_on: null,
  plan: null,
  is_lifetime: false,
};

export const CURRENT_MEMBERSHIP: MembershipStatus = {
  status: 'current',
  expires_on: '2027-06-30',
  plan: 'Annual',
  is_lifetime: false,
};

/** Build a `user` payload without repeating every field in each test. */
export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 1,
    email: 'member@example.org',
    first_name: 'Marta',
    last_name: 'Reyes',
    roles: ['member'] as RoleSlug[],
    is_active: true,
    membership: CURRENT_MEMBERSHIP,
    profile_complete: true,
    ...overrides,
  };
}

/** Default handlers: CSRF works, nobody is signed in, renewal is off. */
export const handlers = [
  http.get(
    `${API}/auth/csrf`,
    () =>
      new HttpResponse(null, {
        status: 204,
        headers: { 'Set-Cookie': `csrftoken=${TEST_CSRF_TOKEN}; path=/` },
      }),
  ),
  http.get(`${API}/auth/me`, () =>
    HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 }),
  ),
  // Every screen that carries the renewal state reads this, so the default keeps
  // a suite that is not about renewal from having to declare one.
  http.get(`${API}/me/renewal`, () => HttpResponse.json({ mandate: null })),
];

/** Convenience: make `/auth/me` answer with `user`. */
export function signedInAs(user: User): HttpHandler {
  return http.get(`${API}/auth/me`, () => HttpResponse.json(user));
}
