/**
 * `POST /auth/register` (PLAN §6.1).
 *
 * The endpoint itself is delivered by `feat/auth-portal`; the contract is
 * fixed by the plan — the response body *is* the `user` payload and the call
 * also logs the visitor in — so the wizard codes against it directly and
 * seeds the `['auth','me']` cache with what comes back.
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
