/**
 * Split a DRF error body into the two halves the member forms need.
 *
 * `POST /admin/members` validates a nested serializer, so a bad phone number
 * comes back as `{"profile": {"phone": ["..."]}}` while a duplicate address
 * comes back as `{"email": ["..."]}`.
 */
import { ApiError } from '../../api/client';
import type { FieldErrors } from './MemberFormFields';

export interface SplitErrors {
  account: FieldErrors;
  profile: FieldErrors;
  detail: string | null;
}

const EMPTY: SplitErrors = { account: {}, profile: {}, detail: null };

function firstMessage(value: unknown): string | null {
  if (typeof value === 'string') return value;
  if (Array.isArray(value) && typeof value[0] === 'string') return value[0];
  return null;
}

function flatten(body: unknown): FieldErrors {
  if (!body || typeof body !== 'object') return {};
  const out: FieldErrors = {};
  for (const [key, value] of Object.entries(body as Record<string, unknown>)) {
    const message = firstMessage(value);
    if (message) out[key] = message;
  }
  return out;
}

export function splitErrors(error: unknown): SplitErrors {
  if (!(error instanceof ApiError)) {
    return error ? { ...EMPTY, detail: 'Something went wrong. Please try again.' } : EMPTY;
  }
  const body = error.body;
  if (!body || typeof body !== 'object') return { ...EMPTY, detail: error.message };

  const record = body as Record<string, unknown>;
  const account = flatten(record);
  delete account.profile;
  delete account.detail;

  return {
    account,
    profile: flatten(record.profile),
    detail: typeof record.detail === 'string' ? record.detail : null,
  };
}
