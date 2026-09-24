/**
 * Keystroke masks: what a field will accept as it is typed.
 *
 * A mask runs on every keystroke and returns the value the input keeps, so a
 * character that cannot belong in the field never appears at all and the
 * punctuation a stored format needs is written for the typist.  Each one is
 * total: it takes whatever the browser hands over, including a paste, and
 * returns a string the field is happy to hold.  They are the first half of the
 * rules in `features/profile/form.ts` and `features/aircraft/form.ts`; those
 * still judge a finished value, because a mask cannot tell a half-typed number
 * from a wrong one.  `isEmailAddress` is the one check that lives here too,
 * because it belongs with the mask that shapes what it reads.
 */

/** The characters a mask counts when it puts the caret back (see `caretAfterMask`). */
const SIGNIFICANT = /[0-9a-z]/i;

/** Digits only, at most `maxDigits` of them. */
export function maskDigits(raw: string, maxDigits: number): string {
  return raw.replace(/\D/g, '').slice(0, maxDigits);
}

/**
 * A phone number as it is stored: `415-555-0100`.
 *
 * Only digits survive, a leading country code `1` is dropped, the dashes are
 * written as the seventh and tenth digits arrive, and the eleventh digit is
 * refused rather than silently ignored later.
 */
export function maskPhone(raw: string): string {
  let digits = raw.replace(/\D/g, '');
  if (digits.length === 11 && digits.startsWith('1')) digits = digits.slice(1);
  digits = digits.slice(0, 10);
  if (digits.length <= 3) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  return `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
}

/** A phone extension: up to six digits. */
export function maskExtension(raw: string): string {
  return maskDigits(raw, 6);
}

/** A five-digit ZIP code. */
export function maskPostalCode(raw: string): string {
  return maskDigits(raw, 5);
}

/**
 * One airport identifier, as this system stores it: three letters or digits.
 *
 * The four-letter ICAO form is the same field with a `K` in front, so that `K`
 * is trimmed as the fourth character arrives: `KCRQ` becomes `CRQ`, and
 * `KKAB` becomes `KAB`.  A three-character identifier that begins with `K` is
 * left alone — Kelso really is `KLS` — because only a fourth character says
 * the `K` was a prefix.  One airport is then written one way everywhere.
 */
export function maskAirportIdentifier(raw: string): string {
  const typed = raw.toUpperCase().replace(/[^A-Z0-9]/g, '');
  const trimmed = typed.length > 3 && typed.startsWith('K') ? typed.slice(1) : typed;
  return trimmed.slice(0, 3);
}

/**
 * A comma-separated list of airport identifiers, such as `CCR, C83`.
 *
 * Each entry follows `maskAirportIdentifier`, so a pasted `KCRQ, KMYF` becomes
 * `CRQ, MYF` as it lands.  The commas and single spaces between them are left
 * where they are typed, so a list can be edited in the middle.
 */
export function maskAirportIdentifiers(raw: string): string {
  return (
    raw
      .toUpperCase()
      .replace(/[^A-Z0-9, ]/g, '')
      .replace(/ {2,}/g, ' ')
      .replace(/,{2,}/g, ',')
      // The separators are captured, so they land back between the entries
      // exactly as they were typed and an edit in the middle stays put.
      .split(/([, ]+)/)
      .map((part, index) => (index % 2 === 1 ? part : maskAirportIdentifier(part)))
      .join('')
  );
}

/**
 * A US registration as the FAA issues them: `N`, digits, then at most two
 * letters, never `I` or `O`.
 *
 * The `N` is written for the typist, so `172SP` becomes `N172SP`, and an
 * emptied field stays empty rather than holding a lone `N`.  A letter
 * typed where a digit belongs, a third trailing letter, a digit after a
 * letter, and a leading zero are all refused as they are typed.
 */
export function maskNNumber(raw: string): string {
  const typed = raw
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '')
    .replace(/^N+/, '');
  if (!typed) return '';
  let digits = '';
  let letters = '';
  for (const character of typed) {
    if (/[0-9]/.test(character)) {
      // Digits belong before the letters, and a registration never starts at zero.
      if (letters.length > 0 || digits.length >= 5) continue;
      if (digits.length === 0 && character === '0') continue;
      digits += character;
    } else {
      if (digits.length === 0 || letters.length >= 2) continue;
      if (character === 'I' || character === 'O') continue;
      if (digits.length + letters.length >= 5) continue;
      letters += character;
    }
  }
  return `N${digits}${letters}`;
}

/**
 * Whole US dollars with thousand separators, as in `1,000,000`.
 *
 * Only digits survive, a leading zero is dropped, and the number is regrouped
 * on every keystroke.  `maxDigits` caps the amount itself, separators aside.
 */
export function maskWholeDollars(raw: string, maxDigits = 12): string {
  const digits = raw
    .replace(/\D/g, '')
    .replace(/^0+(?=\d)/, '')
    .slice(0, maxDigits);
  return digits ? Number(digits).toLocaleString('en-US') : '';
}

/**
 * US dollars with thousand separators and optional cents, as in `2,500.50`.
 *
 * Digits and one decimal point of at most two places; everything else is
 * refused as it is typed.  `maxDigits` caps the dollars, separators aside.
 */
export function maskDollars(raw: string, maxDigits = 12): string {
  const cleaned = raw.replace(/[^0-9.]/g, '');
  const dot = cleaned.indexOf('.');
  if (dot === -1) return maskWholeDollars(cleaned, maxDigits);
  const whole = maskWholeDollars(cleaned.slice(0, dot), maxDigits) || '0';
  const cents = cleaned
    .slice(dot + 1)
    .replace(/\./g, '')
    .slice(0, 2);
  return `${whole}.${cents}`;
}

/**
 * An email address as it is typed: no spaces, one `@`, lower case.
 *
 * Everything an address may not hold is refused at the keyboard -- spaces
 * above all, which is what a copied address drags in -- and the address is
 * lower-cased, because that is how people read one back and sign-in ignores
 * case anyway.  A second `@` is refused; the rest of the shape is
 * `isEmailAddress`'s to judge, once there is something to judge.
 */
export function maskEmail(raw: string): string {
  const cleaned = raw.toLowerCase().replace(/[^a-z0-9.!#$%&'*+/=?^_`{|}~@-]/g, '');
  const at = cleaned.indexOf('@');
  if (at === -1) return cleaned;
  return `${cleaned.slice(0, at)}@${cleaned.slice(at + 1).replace(/@/g, '')}`;
}

/** What every screen says when an address is not one. */
export const EMAIL_MESSAGE = 'Use an email address like name@example.org.';

/**
 * Whether `value` is an address worth sending to: something, one `@`,
 * something, a dot, and a domain ending of at least two letters.
 *
 * Deliberately looser than the server's own check and than the RFC: this
 * catches the typo -- a missing `@`, a trailing comma, `name@example` -- while
 * the server has the last word.
 */
export function isEmailAddress(value: string): boolean {
  return /^[^\s@]+@[^\s@.]+(\.[^\s@.]+)*\.[a-z]{2,}$/i.test(value.trim());
}

/** How many letters and digits `value` holds. */
function countSignificant(value: string): number {
  let count = 0;
  for (const character of value) {
    if (SIGNIFICANT.test(character)) count += 1;
  }
  return count;
}

/**
 * Where the caret belongs in `masked` after the typist changed `raw`.
 *
 * A mask rewrites the whole value, which would otherwise throw the caret to
 * the end on every edit in the middle of a number.  Counting the letters and
 * digits before the caret and finding that many in the masked value keeps it
 * where the typist left it, whichever punctuation the mask added or removed.
 * A mask that writes a character of its own ahead of what was typed, as the
 * `N` of a registration is, moves the caret along with it.
 */
export function caretAfterMask(raw: string, caret: number, masked: string): number {
  // Typing at the end is the common case, and the end is where the caret
  // belongs however the mask rewrote what came before it -- including a
  // separator the typist wrote themselves, such as the comma between two
  // airport identifiers.
  if (caret >= raw.length) return masked.length;
  const typed = countSignificant(raw.slice(0, caret));
  if (typed === 0) return 0;
  const added = Math.max(0, countSignificant(masked) - countSignificant(raw));
  const wanted = typed + added;
  let seen = 0;
  for (let index = 0; index < masked.length; index += 1) {
    if (SIGNIFICANT.test(masked[index] as string)) {
      seen += 1;
      if (seen === wanted) return index + 1;
    }
  }
  return masked.length;
}
