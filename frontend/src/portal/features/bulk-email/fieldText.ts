/**
 * What the compose screen and the template form say about recipient fields beside
 * the subject and the message.
 */

/**
 * The subject's hint.  It names Insert field rather than a token's braces, which mean
 * nothing to a sender until they see one.
 */
export const SUBJECT_HINT =
  "One line that says what it is about. Insert field adds each person's own details, such " +
  'as their first name.';

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
 * In the message an unknown field is usually a chip, which has no braces to take
 * out, so its refusal reads *{nickname} is not one of the fields. Delete it, or pick a
 * field from Insert field.*, which holds for a chip and for one the editor shows as
 * text alike.  Every other refusal, such as one for braces inside a web address,
 * reads as the server wrote it.
 */
export function messageError(error: string): string {
  const match = UNKNOWN_FIELD_REFUSAL.exec(error);
  if (match === null) return error;
  return `${match[1]} is not one of the fields. Delete it, or pick a field from Insert field.`;
}
