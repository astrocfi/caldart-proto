/**
 * What the compose screen and the template form say about recipient fields beside
 * the subject and the message.
 */

/**
 * The subject's hint.  The subject is a plain line, so a field shows there as its
 * token, in braces, where the message shows a chip.
 */
export const SUBJECT_HINT =
  "One line that says what it is about. A field such as {first_name} fills in each person's " +
  'own value.';

/**
 * The server's refusal of a token it does not know, as `fields.UNKNOWN_FIELD_MESSAGE`
 * in `backend/apps/bulk_email/fields.py` words it for a token outside a web address.
 */
const UNKNOWN_FIELD_REFUSAL = new RegExp(
  '^(\\{[a-z][a-z0-9_]*\\}) is not one of the fields\\. ' +
    'Pick a field from Insert field, or take out the braces\\.$',
);

/**
 * The server's refusal of the message `error` as the message's own error line says it.
 *
 * In the message an unknown field is a chip, which has no braces to take out, so its
 * refusal says how to deal with the chip instead: *{nickname} is not one of the
 * fields. Delete it, or click it to choose a field.*  Every other refusal, such as one
 * for braces inside a web address, reads as the server wrote it.
 */
export function messageError(error: string): string {
  const match = UNKNOWN_FIELD_REFUSAL.exec(error);
  if (match === null) return error;
  return `${match[1]} is not one of the fields. Delete it, or click it to choose a field.`;
}
