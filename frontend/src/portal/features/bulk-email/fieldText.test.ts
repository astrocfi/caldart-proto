import { describe, expect, it } from 'vitest';

import { messageError } from './fieldText';

describe('messageError', () => {
  it('says how to deal with an unknown field shown as a chip', () => {
    expect(
      messageError(
        '{nickname} is not one of the fields. Pick a field from Insert field, or take out ' +
          'the braces.',
      ),
    ).toBe('{nickname} is not one of the fields. Delete it, or click it to choose a field.');
  });

  it('leaves the refusal of a field in a web address as the server wrote it', () => {
    const refusal =
      '{nickname} is not one of the fields. Pick a field from Insert field, or, if the ' +
      'braces belong in the web address, write them as %7B and %7D: %7Bnickname%7D.';

    expect(messageError(refusal)).toBe(refusal);
  });
});
