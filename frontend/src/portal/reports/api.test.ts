import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { createElement } from 'react';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';

import type { ReportColumn } from '@/portal/api/types';
import { API } from '@test/handlers';
import { makeTestQueryClient } from '@test/render';
import { server } from '@test/server';
import { reportExportUrl, useReportColumns, useReports } from './api';
import type { ReportSummary } from './types';

/** One provider tree per test, so a cached answer cannot leak between them. */
function makeWrapper() {
  const client = makeTestQueryClient();
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client }, children);
  };
}

const REPORT_LIST: ReportSummary[] = [
  { slug: 'members', title: 'Members', choosable: true, periods: false },
  { slug: 'contributions', title: 'Contributions', choosable: false, periods: true },
];

const MEMBER_COLUMNS: ReportColumn[] = [
  { key: 'name', label: 'Name', default: true },
  { key: 'county', label: 'County', default: false },
];

describe('reportExportUrl', () => {
  it('names the report and the format', () => {
    expect(reportExportUrl('members', 'pdf', {})).toBe('/api/v1/reports/members/export.pdf');
  });

  it('carries every value that is set', () => {
    expect(reportExportUrl('members', 'csv', { dart: '3', county: 'Marin' })).toBe(
      '/api/v1/reports/members/export.csv?dart=3&county=Marin',
    );
  });

  it('leaves out the values that are empty', () => {
    expect(reportExportUrl('aircraft', 'csv', { search: '', make: 'Cessna' })).toBe(
      '/api/v1/reports/aircraft/export.csv?make=Cessna',
    );
  });

  it('leaves out the page, since a report carries every row', () => {
    expect(reportExportUrl('payments', 'csv', { page: '4', status: 'failed' })).toBe(
      '/api/v1/reports/payments/export.csv?status=failed',
    );
  });

  it('joins the chosen columns with commas', () => {
    expect(reportExportUrl('members', 'csv', { columns: ['name', 'email'] })).toBe(
      '/api/v1/reports/members/export.csv?columns=name%2Cemail',
    );
  });

  it('leaves out an empty column choice, so the report keeps its defaults', () => {
    expect(reportExportUrl('members', 'csv', { columns: [] })).toBe(
      '/api/v1/reports/members/export.csv',
    );
  });

  it('leaves out a value that is not given at all', () => {
    expect(reportExportUrl('contributions', 'pdf', { year: undefined, period: 'last_year' })).toBe(
      '/api/v1/reports/contributions/export.pdf?period=last_year',
    );
  });
});

describe('useReports', () => {
  it('reads the reports the caller may read', async () => {
    server.use(http.get(`${API}/reports`, () => HttpResponse.json(REPORT_LIST)));

    const { result } = renderHook(() => useReports(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.data).toEqual(REPORT_LIST));
  });
});

describe('useReportColumns', () => {
  it('reads the column registry of the report it names', async () => {
    server.use(
      http.get(`${API}/reports/:slug/columns`, ({ params }) =>
        HttpResponse.json(params.slug === 'members' ? MEMBER_COLUMNS : []),
      ),
    );

    const { result } = renderHook(() => useReportColumns('members'), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.data).toEqual(MEMBER_COLUMNS));
  });

  it('keeps the registry without asking again, since it never changes', async () => {
    let requests = 0;
    server.use(
      http.get(`${API}/reports/:slug/columns`, () => {
        requests += 1;
        return HttpResponse.json(MEMBER_COLUMNS);
      }),
    );
    const wrapper = makeWrapper();
    const first = renderHook(() => useReportColumns('members'), { wrapper });
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true));

    const second = renderHook(() => useReportColumns('members'), { wrapper });

    expect([second.result.current.data, requests]).toEqual([MEMBER_COLUMNS, 1]);
  });
});
