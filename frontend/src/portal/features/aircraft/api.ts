/**
 * Queries and mutations for the aircraft register (PLAN §6.5).
 *
 * Shared by the picker on the profile, the admin register and the leader
 * check, so every screen agrees on the query keys and the filter names the
 * API expects.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { API_BASE, ApiError, api } from '../../api/client';
import type {
  Aircraft,
  AircraftPatch,
  MembershipState,
  OwnerType,
  Paginated,
} from '../../api/types';

export type InsuranceState = 'current' | 'expired' | 'missing';

/** A member who lists an aircraft among the planes they commonly fly. */
export interface AircraftPilot {
  user_id: number;
  name: string;
  email: string;
  membership_status: MembershipState;
  medical_is_current: boolean;
}

/**
 * `GET /aircraft/{id}`, `/aircraft/lookup` and the leader's aircraft card.
 *
 * `pilots` names other members and reports their medical currency, so the
 * server only sends it to a `dart_leader` or `account_admin`; it is absent
 * for a plain member reading the register.
 */
export interface AircraftDetail extends Aircraft {
  pilots?: AircraftPilot[];
}

/** Every filter the list endpoint and both exports understand (PLAN §6.5). */
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

/** A download URL for the CSV/PDF exports, carrying the current filters. */
export function aircraftExportUrl(format: 'csv' | 'pdf', filters: AircraftFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(aircraftQuery(filters))) {
    if (key === 'page') continue;
    params.append(key, String(value));
  }
  const query = params.toString();
  return `${API_BASE}/admin/aircraft/export.${format}${query ? `?${query}` : ''}`;
}

export function useAircraftList(filters: AircraftFilters, enabled = true) {
  const query = aircraftQuery(filters);
  return useQuery({
    queryKey: [AIRCRAFT_KEY, 'list', query],
    queryFn: () => api.get<Paginated<Aircraft>>('/aircraft', { query }),
    enabled,
  });
}

export function useAircraft(id: number | null) {
  return useQuery({
    queryKey: [AIRCRAFT_KEY, 'detail', id],
    queryFn: () => api.get<AircraftDetail>(`/aircraft/${id}`),
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
 * fuzzy search over N-number, make, model and owner (PLAN §6.5).
 */
export async function findAircraft(term: string, limit = 8): Promise<AircraftSearchResult> {
  // An exact registration is shown even when it is out of service, so a
  // member learns why the aeroplane is not on offer rather than being told
  // "no match" and inventing a duplicate record for it.
  const exact = await lookupAircraft(term);
  if (exact) return { exact, matches: [exact] };
  const page = await api.get<Paginated<Aircraft>>('/aircraft', {
    query: { search: term, page_size: limit, is_active: true },
  });
  return { exact: null, matches: page.results };
}

export function useAircraftSearch(term: string) {
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

export function useCreateAircraft() {
  const invalidate = useInvalidateAircraft();
  return useMutation({
    mutationFn: (payload: AircraftPatch) => api.post<AircraftDetail>('/aircraft', payload),
    onSuccess: () => invalidate(),
  });
}

export function useUpdateAircraft(id: number) {
  const invalidate = useInvalidateAircraft();
  return useMutation({
    mutationFn: (payload: AircraftPatch) => api.patch<AircraftDetail>(`/aircraft/${id}`, payload),
    onSuccess: () => invalidate(),
  });
}

export function useDeleteAircraft(id: number) {
  const invalidate = useInvalidateAircraft();
  return useMutation({
    mutationFn: () => api.delete<null>(`/aircraft/${id}`),
    onSuccess: () => invalidate(),
  });
}
