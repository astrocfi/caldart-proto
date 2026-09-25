/**
 * Queries and mutations for the aircraft register.
 *
 * Shared by the picker on the profile, the admin register and the leader
 * check, so every screen agrees on the query keys and the filter names the
 * API expects.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { ApiError, api } from '@/portal/api/client';
import type {
  Aircraft,
  AircraftChange,
  AircraftDetail,
  AircraftPatch,
  OwnerType,
  Paginated,
} from '@/portal/api/types';

export type InsuranceState = 'current' | 'expired' | 'missing';

/** Every filter the list endpoint understands. */
export interface AircraftFilters {
  search?: string;
  make?: string;
  owner_type?: OwnerType | '';
  insurance?: InsuranceState | '';
  expiring_within?: string;
  ordering?: string;
  page?: number;
}

export const AIRCRAFT_KEY = 'aircraft';

/** Drop empty values so the query key and the URL stay stable. */
export function aircraftQuery(filters: AircraftFilters): Record<string, string | number> {
  const query: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === '') continue;
    query[key] = value as string | number;
  }
  return query;
}

/**
 * The paginated aircraft list for `/aircraft`, filtered by `filters`.
 *
 * A change of page or filter is a different query, so the page already on screen
 * stands in for the one being fetched: the register holds still instead of
 * collapsing to a spinner and back.  `isPlaceholderData` says which of the two is
 * showing.
 */
export function useAircraftList(
  filters: AircraftFilters,
  enabled = true,
): UseQueryResult<Paginated<Aircraft>> {
  const query = aircraftQuery(filters);
  return useQuery({
    queryKey: [AIRCRAFT_KEY, 'list', query],
    queryFn: () => api.get<Paginated<Aircraft>>('/aircraft', { query }),
    enabled,
    placeholderData: keepPreviousData,
  });
}

/** One aircraft's detail record, or disabled while `id` is null or not a number. */
export function useAircraft(id: number | null): UseQueryResult<AircraftDetail> {
  return useQuery({
    queryKey: [AIRCRAFT_KEY, 'detail', id],
    queryFn: () => api.get<AircraftDetail>(`/aircraft/${id}`),
    enabled: id !== null && Number.isFinite(id),
  });
}

/**
 * One record's change history, newest first, or disabled while `id` is null.
 *
 * Every write to the register invalidates `aircraft`, so the history on screen
 * grows the moment a save on the same record goes through.
 */
export function useAircraftChanges(id: number | null): UseQueryResult<AircraftChange[]> {
  return useQuery({
    queryKey: [AIRCRAFT_KEY, 'changes', id],
    queryFn: () => api.get<AircraftChange[]>(`/aircraft/${id}/changes`),
    enabled: id !== null && Number.isFinite(id),
  });
}

/** An exact N-number match, or `null` when the register has never seen it. */
export async function lookupAircraft(nNumber: string): Promise<AircraftDetail | null> {
  try {
    return await api.get<AircraftDetail>('/aircraft/lookup', { query: { n_number: nNumber } });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 400)) return null;
    throw error;
  }
}

export interface AircraftSearchResult {
  /** The register's one record for this exact N-number, if there is one. */
  exact: AircraftDetail | null;
  matches: Aircraft[];
}

/**
 * The picker's search: try the registration first, then fall back to a
 * fuzzy search over N-number, make, model, and owner.
 */
export async function findAircraft(term: string, limit = 8): Promise<AircraftSearchResult> {
  // An exact registration is shown even when it is out of service, so a
  // member learns why the airplane is not on offer rather than being told
  // "no match" and inventing a duplicate record for it.
  const exact = await lookupAircraft(term);
  if (exact) return { exact, matches: [exact] };
  const page = await api.get<Paginated<Aircraft>>('/aircraft', {
    query: { search: term, page_size: limit, is_active: true },
  });
  return { exact: null, matches: page.results };
}

/** The picker's search results for `term`, disabled while it is blank. */
export function useAircraftSearch(term: string): UseQueryResult<AircraftSearchResult> {
  return useQuery({
    queryKey: [AIRCRAFT_KEY, 'search', term],
    queryFn: () => findAircraft(term),
    enabled: term.trim().length > 0,
  });
}

function useInvalidateAircraft() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: [AIRCRAFT_KEY] });
}

/** Creates an aircraft record; invalidates `aircraft` on success. */
export function useCreateAircraft(): UseMutationResult<AircraftDetail, Error, AircraftPatch> {
  const invalidate = useInvalidateAircraft();
  return useMutation({
    mutationFn: (payload: AircraftPatch) => api.post<AircraftDetail>('/aircraft', payload),
    onSuccess: () => invalidate(),
  });
}

/** Patches one aircraft record; invalidates `aircraft` on success. */
export function useUpdateAircraft(
  id: number,
): UseMutationResult<AircraftDetail, Error, AircraftPatch> {
  const invalidate = useInvalidateAircraft();
  return useMutation({
    mutationFn: (payload: AircraftPatch) => api.patch<AircraftDetail>(`/aircraft/${id}`, payload),
    onSuccess: () => invalidate(),
  });
}

/** Deletes one aircraft record; invalidates `aircraft` on success. */
export function useDeleteAircraft(id: number): UseMutationResult<null, Error, void> {
  const invalidate = useInvalidateAircraft();
  return useMutation({
    mutationFn: () => api.delete<null>(`/aircraft/${id}`),
    onSuccess: () => invalidate(),
  });
}
