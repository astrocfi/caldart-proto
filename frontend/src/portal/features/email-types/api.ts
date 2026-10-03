/**
 * Data access for the Email types screen, `/email-types` (system administrators).
 *
 * Every write refreshes the list, and the types a sender may choose from, which are
 * the same rows.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type { EmailType, EmailTypeInput } from '@/portal/api/types';

export const EMAIL_TYPES_KEY = ['email-types'] as const;

/** Every email type, in the order every screen lists them. */
export function useEmailTypes(): UseQueryResult<EmailType[]> {
  return useQuery({
    queryKey: EMAIL_TYPES_KEY,
    queryFn: () => api.get<EmailType[]>('/email-types'),
  });
}

/** Reads every email type list again, the sendable one included. */
function useInvalidateEmailTypes(): () => Promise<void> {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: EMAIL_TYPES_KEY });
}

/** Adds a type; a refusal is an `ApiError` keyed by field (`name`, `sender_roles`). */
export function useCreateEmailType(): UseMutationResult<EmailType, Error, EmailTypeInput> {
  const invalidate = useInvalidateEmailTypes();
  return useMutation({
    mutationFn: (input: EmailTypeInput) => api.post<EmailType>('/email-types', input),
    onSuccess: () => invalidate(),
  });
}

export interface EmailTypeEdit {
  id: number;
  input: EmailTypeInput;
}

/** Replaces one type's settings, with the same refusals as adding one. */
export function useUpdateEmailType(): UseMutationResult<EmailType, Error, EmailTypeEdit> {
  const invalidate = useInvalidateEmailTypes();
  return useMutation({
    mutationFn: ({ id, input }: EmailTypeEdit) => api.put<EmailType>(`/email-types/${id}`, input),
    onSuccess: () => invalidate(),
  });
}

/**
 * Deletes one type. A type a bulk email has used is refused with an `ApiError` whose
 * message says so and what to do instead.
 */
export function useDeleteEmailType(): UseMutationResult<null, Error, number> {
  const invalidate = useInvalidateEmailTypes();
  return useMutation({
    mutationFn: (id: number) => api.delete<null>(`/email-types/${id}`),
    onSuccess: () => invalidate(),
  });
}
