/** What the N-number typeahead asks the FAA registry, and what it makes of the answers. */
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeRegistration } from '@test/fixtures/registry';
import { API } from '@test/handlers';
import { server } from '@test/server';
import { searchRegistrations } from './api';

describe('searchRegistrations', () => {
  it('answers the registrations the registry lists', async () => {
    const found = [makeRegistration(), makeRegistration({ n_number: 'N739TB' })];
    server.use(http.get(`${API}/aircraft/registrations`, () => HttpResponse.json(found)));
    expect(await searchRegistrations('N739')).toEqual(found);
  });

  it('asks for the prefix as typed in the q parameter', async () => {
    const asked: (string | null)[] = [];
    server.use(
      http.get(`${API}/aircraft/registrations`, ({ request }) => {
        asked.push(new URL(request.url).searchParams.get('q'));
        return HttpResponse.json([]);
      }),
    );
    await searchRegistrations('N739');
    expect(asked).toEqual(['N739']);
  });
});
