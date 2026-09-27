/** Reading a refused verification save into field messages and one message for the form. */
import { ApiError } from '@/portal/api/client';

export interface SaveErrors {
  /** Messages keyed by the API's field name, each shown under its field. */
  fields: Record<string, string>;
  /** A message that belongs to no field: a refused item, or the request as a whole. */
  form: string | null;
}

/** `error` split into the messages its fields show and the one the form shows. */
export function saveErrors(error: Error | null, formFields: readonly string[]): SaveErrors {
  if (error === null) return { fields: {}, form: null };
  if (!(error instanceof ApiError)) return { fields: {}, form: error.message };
  const all = error.fieldErrors;
  const fields = Object.fromEntries(
    Object.entries(all).filter(([key]) => formFields.includes(key)),
  );
  const rest = Object.entries(all).find(([key]) => !formFields.includes(key));
  if (rest !== undefined) return { fields, form: rest[1] };
  return { fields, form: Object.keys(fields).length > 0 ? null : error.message };
}
