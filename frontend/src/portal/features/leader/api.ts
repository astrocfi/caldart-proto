/** Queries behind the DART leader check. */
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';

import { api } from '../../api/client';
import type { AircraftDetail, LeaderSearchResult, LeaderStatus } from '../../api/types';

export const LEADER_KEY = 'leader';

/** Searches members by name, email or N-number via `GET /leader/search`. */
export function useLeaderSearch(query: string): UseQueryResult<LeaderSearchResult[]> {
  const term = query.trim();
  return useQuery({
    queryKey: [LEADER_KEY, 'search', term],
    queryFn: () => api.get<LeaderSearchResult[]>('/leader/search', { query: { q: term } }),
    enabled: term.length > 0,
  });
}

/** The pre-flight status card data for one member, via `GET /leader/members/:id/status`. */
export function useMemberStatus(userId: number | null): UseQueryResult<LeaderStatus> {
  return useQuery({
    queryKey: [LEADER_KEY, 'status', userId],
    queryFn: () => api.get<LeaderStatus>(`/leader/members/${userId}/status`),
    enabled: userId !== null,
  });
}

/** Insurance status for one aircraft, via `GET /leader/aircraft`. */
export function useLeaderAircraft(nNumber: string): UseQueryResult<AircraftDetail> {
  const term = nNumber.trim();
  return useQuery({
    queryKey: [LEADER_KEY, 'aircraft', term],
    queryFn: () => api.get<AircraftDetail>('/leader/aircraft', { query: { n_number: term } }),
    enabled: term.length > 0,
    retry: false,
  });
}
