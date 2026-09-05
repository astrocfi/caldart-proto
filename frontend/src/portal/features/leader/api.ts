/** Queries behind the DART leader check (PLAN §6.6). */
import { useQuery } from '@tanstack/react-query';

import { api } from '../../api/client';
import type { LeaderSearchResult, LeaderStatus } from '../../api/types';
import type { AircraftDetail } from '../aircraft/api';

export const LEADER_KEY = 'leader';

export function useLeaderSearch(query: string) {
  const term = query.trim();
  return useQuery({
    queryKey: [LEADER_KEY, 'search', term],
    queryFn: () => api.get<LeaderSearchResult[]>('/leader/search', { query: { q: term } }),
    enabled: term.length > 0,
  });
}

export function useMemberStatus(userId: number | null) {
  return useQuery({
    queryKey: [LEADER_KEY, 'status', userId],
    queryFn: () => api.get<LeaderStatus>(`/leader/members/${userId}/status`),
    enabled: userId !== null,
  });
}

export function useLeaderAircraft(nNumber: string) {
  const term = nNumber.trim();
  return useQuery({
    queryKey: [LEADER_KEY, 'aircraft', term],
    queryFn: () => api.get<AircraftDetail>('/leader/aircraft', { query: { n_number: term } }),
    enabled: term.length > 0,
    retry: false,
  });
}
