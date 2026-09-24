/** Data access for the DART administration screen. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type { AdminDart, AdminDartPatch } from '@/portal/api/types';
import { DARTS_KEY } from '@/portal/api/queries';

export const ADMIN_DARTS_KEY = ['admin', 'darts'] as const;

/** Every DART, active or retired, in the order the public catalog lists them. */
export function useAdminDarts(): UseQueryResult<AdminDart[]> {
  return useQuery({
    queryKey: ADMIN_DARTS_KEY,
    queryFn: () => api.get<AdminDart[]>('/admin/darts'),
  });
}

/**
 * Invalidate both DART lists after a write.
 *
 * The public catalog behind every "which DART?" dropdown is the same data, so
 * a DART added here has to appear there without a reload.
 */
function useInvalidateDarts() {
  const queryClient = useQueryClient();
  return async () => {
    await queryClient.invalidateQueries({ queryKey: ADMIN_DARTS_KEY });
    await queryClient.invalidateQueries({ queryKey: DARTS_KEY });
  };
}

/** Creates a DART; refreshes both DART lists on success. */
export function useCreateDart(): UseMutationResult<AdminDart, Error, AdminDartPatch> {
  const invalidate = useInvalidateDarts();
  return useMutation({
    mutationFn: (payload: AdminDartPatch) => api.post<AdminDart>('/admin/darts', payload),
    onSuccess: () => invalidate(),
  });
}

export interface DartEdit {
  id: number;
  payload: AdminDartPatch;
}

/** Edits one DART; refreshes both DART lists on success. */
export function useUpdateDart(): UseMutationResult<AdminDart, Error, DartEdit> {
  const invalidate = useInvalidateDarts();
  return useMutation({
    mutationFn: ({ id, payload }: DartEdit) => api.patch<AdminDart>(`/admin/darts/${id}`, payload),
    onSuccess: () => invalidate(),
  });
}

/** Deletes one DART; refreshes both DART lists on success. */
export function useDeleteDart(): UseMutationResult<null, Error, number> {
  const invalidate = useInvalidateDarts();
  return useMutation({
    mutationFn: (id: number) => api.delete<null>(`/admin/darts/${id}`),
    onSuccess: () => invalidate(),
  });
}
