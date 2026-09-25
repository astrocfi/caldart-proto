/**
 * The portal's one client for the report endpoints under `/api/v1/reports/`.
 *
 * Every report is read the same way: `GET /reports` lists those the caller may
 * read, `GET /reports/<slug>/columns` is a report's column registry, and
 * `/reports/<slug>/export.csv` and `export.pdf` are its downloads.  Every
 * export button in the portal takes its href from `reportExportUrl`.
 */
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';

import { API_BASE, api } from '@/portal/api/client';
import type { ReportColumn } from '@/portal/api/types';
import type { ReportFormat, ReportSlug, ReportSummary } from './types';

export const REPORTS_KEY = ['reports'] as const;

/** A report's parameters: a value, a list of values such as the columns, or nothing. */
export type ReportParams = Readonly<Record<string, string | readonly string[] | undefined>>;

/** The list page's own parameter, which no report takes: a report carries every row. */
const PAGE_PARAM = 'page';

/**
 * The href of one report's download, carrying every parameter that is set.
 *
 * An empty or absent value is left out, as is `page`; a list, such as the
 * chosen `columns`, is sent comma-separated and left out when it is empty.
 *
 * @param slug the report, as the server's registry names it.
 * @param format `csv` or `pdf`, which is also the extension of the file.
 * @param params the filters, `ordering`, `columns` and `period` to send.
 * @returns a same-origin path such as `/api/v1/reports/members/export.pdf?dart=3`.
 */
export function reportExportUrl(
  slug: ReportSlug,
  format: ReportFormat,
  params: ReportParams,
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (key === PAGE_PARAM || value === undefined) continue;
    const text = typeof value === 'string' ? value : value.join(',');
    if (text !== '') query.set(key, text);
  }
  const search = query.toString();
  const base = `${API_BASE}/reports/${slug}/export.${format}`;
  return search === '' ? base : `${base}?${search}`;
}

/** The reports the signed-in user may read, via `GET /reports`; a member has none. */
export function useReports(): UseQueryResult<ReportSummary[]> {
  return useQuery({
    queryKey: REPORTS_KEY,
    queryFn: () => api.get<ReportSummary[]>('/reports'),
  });
}

/**
 * Every column one report can carry, in export order, via `GET /reports/<slug>/columns`.
 *
 * A registry never changes while the portal is open, so it is fetched once and kept.
 */
export function useReportColumns(slug: ReportSlug): UseQueryResult<ReportColumn[]> {
  return useQuery({
    queryKey: [...REPORTS_KEY, slug, 'columns'],
    queryFn: () => api.get<ReportColumn[]>(`/reports/${slug}/columns`),
    staleTime: Infinity,
  });
}
