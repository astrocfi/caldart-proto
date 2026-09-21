/** The list's query parameters, all as strings for the URL. */
export interface MemberFilters {
  search: string;
  status: string;
  certificate: string;
  medical: string;
  dart: string;
  role: string;
  expiring_within: string;
  ordering: string;
}

export const EMPTY_FILTERS: MemberFilters = {
  search: '',
  status: '',
  certificate: '',
  medical: '',
  dart: '',
  role: '',
  expiring_within: '',
  ordering: '',
};

export const FILTER_KEYS = Object.keys(EMPTY_FILTERS) as (keyof MemberFilters)[];
