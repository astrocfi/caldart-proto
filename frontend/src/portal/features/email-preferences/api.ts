/**
 * Data access for email preferences: a person's own, at `/me/email-preferences`, and
 * a member's on their record, at `/admin/members/{id}/email-preferences`.
 *
 * A save sends the one change and answers every preference, which replaces the cached
 * list at once, so the switches never wait on a second request.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type { EmailPreference, EmailPreferenceChange } from '@/portal/api/types';

export const MY_EMAIL_PREFERENCES_KEY = ['me', 'email-preferences'] as const;

/** The cache key of member `memberId`'s preferences. */
export function memberEmailPreferencesKey(memberId: number): readonly unknown[] {
  return ['admin-members', memberId, 'email-preferences'];
}

/** The API path of member `memberId`'s preferences. */
function memberPath(memberId: number): string {
  return `/admin/members/${memberId}/email-preferences`;
}

/** The types the signed-in person may turn off, and whether they have. */
export function useMyEmailPreferences(): UseQueryResult<EmailPreference[]> {
  return useQuery({
    queryKey: MY_EMAIL_PREFERENCES_KEY,
    queryFn: () => api.get<EmailPreference[]>('/me/email-preferences'),
  });
}

/** Saves one of the signed-in person's choices, with the source `profile`. */
export function useSaveMyEmailPreference(): UseMutationResult<
  EmailPreference[],
  Error,
  EmailPreferenceChange
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (change: EmailPreferenceChange) =>
      api.put<EmailPreference[]>('/me/email-preferences', [change]),
    onSuccess: (saved) => queryClient.setQueryData(MY_EMAIL_PREFERENCES_KEY, saved),
  });
}

/** Member `memberId`'s preferences, for the account administrator's member record. */
export function useMemberEmailPreferences(memberId: number): UseQueryResult<EmailPreference[]> {
  return useQuery({
    queryKey: memberEmailPreferencesKey(memberId),
    queryFn: () => api.get<EmailPreference[]>(memberPath(memberId)),
  });
}

/** Saves one of member `memberId`'s choices, with the source `admin`. */
export function useSaveMemberEmailPreference(
  memberId: number,
): UseMutationResult<EmailPreference[], Error, EmailPreferenceChange> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (change: EmailPreferenceChange) =>
      api.put<EmailPreference[]>(memberPath(memberId), [change]),
    onSuccess: (saved) => queryClient.setQueryData(memberEmailPreferencesKey(memberId), saved),
  });
}
