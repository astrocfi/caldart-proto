import { describe, expect, it } from 'vitest';

import {
  caretAfterMask,
  maskAirportIdentifier,
  maskDigits,
  maskDollars,
  maskExtension,
  maskNNumber,
  maskPhone,
  maskPostalCode,
  maskWholeDollars,
} from './masks';

describe('maskPhone', () => {
  it('writes the dashes as the digits arrive', () => {
    expect(maskPhone('415555')).toBe('415-555');
  });

  it('formats a whole number as it is stored', () => {
    expect(maskPhone('4155550100')).toBe('415-555-0100');
  });

  it('drops every character that is not a digit', () => {
    expect(maskPhone('(415) abc 555.0100')).toBe('415-555-0100');
  });

  it('drops a leading country code', () => {
    expect(maskPhone('+1 415 555 0100')).toBe('415-555-0100');
  });

  it('refuses an eleventh digit', () => {
    expect(maskPhone('41555501009')).toBe('415-555-0100');
  });
});

describe('maskExtension', () => {
  it('keeps at most six digits', () => {
    expect(maskExtension('x4021789')).toBe('402178');
  });
});

describe('maskPostalCode', () => {
  it('keeps five digits and no more', () => {
    expect(maskPostalCode('95035-1234')).toBe('95035');
  });
});

describe('maskDigits', () => {
  it('caps the count of digits it keeps', () => {
    expect(maskDigits('1,250 hours', 5)).toBe('1250');
  });
});

describe('maskAirportIdentifier', () => {
  it('upper-cases what was typed', () => {
    expect(maskAirportIdentifier('pao')).toBe('PAO');
  });

  it('keeps a digit, as E16 has', () => {
    expect(maskAirportIdentifier('e16')).toBe('E16');
  });

  it('drops the ICAO K typed in front of a full identifier', () => {
    expect(maskAirportIdentifier('KPAO')).toBe('PAO');
  });

  it('keeps a K that is part of the identifier', () => {
    expect(maskAirportIdentifier('KLS')).toBe('KLS');
  });

  it('drops only the prefix from an identifier that starts with K', () => {
    expect(maskAirportIdentifier('KKAB')).toBe('KAB');
  });

  it('refuses a fourth character', () => {
    expect(maskAirportIdentifier('SQLX')).toBe('SQL');
  });
});

describe('maskNNumber', () => {
  it('writes the N for the typist', () => {
    expect(maskNNumber('172sp')).toBe('N172SP');
  });

  it('stays empty when the field is cleared', () => {
    expect(maskNNumber('')).toBe('');
  });

  it('refuses a letter before the digits', () => {
    expect(maskNNumber('NX172')).toBe('N172');
  });

  it('refuses a digit typed after a letter', () => {
    expect(maskNNumber('N172S2')).toBe('N172S');
  });

  it('refuses a third trailing letter', () => {
    expect(maskNNumber('N12ABC')).toBe('N12AB');
  });

  it('refuses I and O, which read as 1 and 0', () => {
    expect(maskNNumber('N12IO')).toBe('N12');
  });

  it('refuses a leading zero', () => {
    expect(maskNNumber('N0172')).toBe('N172');
  });

  it('refuses a sixth character after the N', () => {
    expect(maskNNumber('N123456')).toBe('N12345');
  });
});

describe('maskDollars', () => {
  it('groups thousands as the amount is typed', () => {
    expect(maskDollars('1000000')).toBe('1,000,000');
  });

  it('keeps the cents of a pasted amount, and regroups the dollars', () => {
    expect(maskDollars('$1,000.99')).toBe('1,000.99');
  });

  it('refuses a third decimal place and a second point', () => {
    expect(maskDollars('12.5.678')).toBe('12.56');
  });

  it('refuses a letter typed into an amount', () => {
    expect(maskDollars('1k000')).toBe('1,000');
  });

  it('stays empty when the field is cleared', () => {
    expect(maskDollars('')).toBe('');
  });
});

describe('maskWholeDollars', () => {
  it('refuses a decimal point where only whole dollars belong', () => {
    expect(maskWholeDollars('99.99')).toBe('9,999');
  });

  it('caps the number of digits it keeps', () => {
    expect(maskWholeDollars('123456', 5)).toBe('12,345');
  });
});

describe('caretAfterMask', () => {
  it('leaves the caret after the digits already typed', () => {
    expect(caretAfterMask('4155', 4, '415-5')).toBe(5);
  });

  it('keeps the caret in the middle of an edited number', () => {
    expect(caretAfterMask('4165550100', 3, '416-555-0100')).toBe(3);
  });

  it('moves past a character the mask wrote itself', () => {
    expect(caretAfterMask('4', 1, 'N4')).toBe(2);
  });

  it('stays after a separator the typist wrote', () => {
    expect(caretAfterMask('CCR,', 4, 'CCR,')).toBe(4);
  });

  it('stays at the end when the mask refused the last character', () => {
    expect(caretAfterMask('415a', 4, '415')).toBe(3);
  });

  it('puts the caret at the start when nothing precedes it', () => {
    expect(caretAfterMask('415-555-0100', 0, '415-555-0100')).toBe(0);
  });
});
