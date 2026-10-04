/**
 * A link for a contact written as free text, such as an aircraft owner's: an email
 * address opens the mail program and a phone number dials, as the member check's own
 * contact details do.
 */

/** An address with something either side of one `@` and a dot in the domain. */
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Fewer digits than this is no phone number anybody could dial. */
const MIN_PHONE_DIGITS = 7;

/** Anything a phone number may be written with: digits, spaces, and punctuation. */
const PHONE = /^\+?[\d\s().-]+$/;

/**
 * The `mailto:` or `tel:` link for `text`, or null when it is neither.
 *
 * @param text - the contact as written, surrounding spaces ignored.
 * @returns `mailto:<address>` for an email address, `tel:<digits>` (a leading `+`
 *   kept) for a phone number of at least seven digits, or null for anything else.
 */
export function contactHref(text: string): string | null {
  const trimmed = text.trim();
  if (EMAIL.test(trimmed)) return `mailto:${trimmed}`;
  if (!PHONE.test(trimmed)) return null;
  const digits = trimmed.replace(/[^\d+]/g, '');
  return digits.replace('+', '').length >= MIN_PHONE_DIGITS ? `tel:${digits}` : null;
}
