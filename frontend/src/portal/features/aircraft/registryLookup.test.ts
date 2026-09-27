/** What a Look up on an N-number answers for each thing the registry can say. */
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeRegistration } from '@test/fixtures/registry';
import { API } from '@test/handlers';
import { server } from '@test/server';
import { lookupRegistration } from './api';

describe('lookupRegistration', () => {
  it('answers the registration the registry holds', async () => {
    const registration = makeRegistration();
    server.use(http.get(`${API}/aircraft/registry/N739TA`, () => HttpResponse.json(registration)));
    expect(await lookupRegistration('N739TA')).toEqual({ status: 'found', registration });
  });

  it('asks for the registration in its one written form', async () => {
    const asked: string[] = [];
    server.use(
      http.get(`${API}/aircraft/registry/:nNumber`, ({ params }) => {
        asked.push(String(params.nNumber));
        return HttpResponse.json(makeRegistration());
      }),
    );
    await lookupRegistration('n-739ta');
    expect(asked).toEqual(['N739TA']);
  });

  it('says the registry has no such registration on a 404', async () => {
    server.use(
      http.get(`${API}/aircraft/registry/N1`, () =>
        HttpResponse.json({ detail: 'No registration for N1 in the registry.' }, { status: 404 }),
      ),
    );
    expect(await lookupRegistration('N1')).toEqual({ status: 'missing' });
  });

  it('reports a failure for anything else the server answers', async () => {
    server.use(
      http.get(`${API}/aircraft/registry/N1`, () =>
        HttpResponse.json({ detail: 'Server error.' }, { status: 500 }),
      ),
    );
    expect(await lookupRegistration('N1')).toEqual({ status: 'failed' });
  });

  it('reports a failure when the network drops the request', async () => {
    server.use(http.get(`${API}/aircraft/registry/N1`, () => HttpResponse.error()));
    expect(await lookupRegistration('N1')).toEqual({ status: 'failed' });
  });
});
