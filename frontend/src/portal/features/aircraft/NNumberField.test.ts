/** How the N-number typeahead describes a registration at the end of its line. */
import { describe, expect, it } from 'vitest';

import { makeRegistration } from '@test/fixtures/registry';
import { registrationMeta } from './NNumberField';

describe('registrationMeta', () => {
  it('names the type, the year, and the registrant', () => {
    expect(registrationMeta(makeRegistration())).toBe('Cessna 172S  2004  PALO ALTO FLYING CLUB');
  });

  it('leaves out a year and a registrant the registry left blank', () => {
    const registration = makeRegistration({ year: null, registrant_name: '  ' });
    expect(registrationMeta(registration)).toBe('Cessna 172S');
  });

  it('leaves out a blank year without doubling the separator', () => {
    expect(registrationMeta(makeRegistration({ year: null }))).toBe(
      'Cessna 172S  PALO ALTO FLYING CLUB',
    );
  });
});
