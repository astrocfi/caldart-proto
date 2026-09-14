/**
 * `POST /auth/register`.
 *
 * The response body *is* the `user` payload and the call also logs the visitor
 * in, so the wizard seeds the `['auth','me']` cache with what comes back.
 * `auth/useAuth.ts` exports a second `useRegister` that clears the query cache
 * before seeding it.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { api } from '../../api/client';
import { AUTH_ME_KEY } from '../../auth/useAuth';
import type { RegisterPayload, User } from '../../api/types';

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RegisterPayload) => api.post<User>('/auth/register', payload),
    onSuccess: (user) => {
      queryClient.setQueryData(AUTH_ME_KEY, user);
    },
  });
}
