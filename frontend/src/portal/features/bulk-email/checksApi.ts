/**
 * The client for the checks before a send: what the server finds in an email,
 * `POST /bulk-email/{id}/checks`, and a test copy to the sender,
 * `POST /bulk-email/{id}/test`. A send or a test the checks find errors in is
 * refused with the errors under `checks`, which {@link refusedFindings} reads.
 */
import { useMutation } from '@tanstack/react-query';
import type { UseMutationResult } from '@tanstack/react-query';

import { ApiError, api } from '@/portal/api/client';
import type { BulkEmailFinding, BulkEmailTestResult } from '@/portal/api/types';

/** Runs the checks on one email as it is saved; resolves to every finding. */
export function useBulkEmailChecks(
  id: number,
): UseMutationResult<BulkEmailFinding[], unknown, void> {
  return useMutation({
    mutationFn: () => api.post<BulkEmailFinding[]>(`/bulk-email/${id}/checks`),
  });
}

/** Mails the signed-in sender a test copy of one email; resolves to where it went. */
export function useSendTest(id: number): UseMutationResult<BulkEmailTestResult, unknown, void> {
  return useMutation({
    mutationFn: () => api.post<BulkEmailTestResult>(`/bulk-email/${id}/test`),
  });
}

/** True when `findings` holds an error, which keeps the email from being sent. */
export function hasError(findings: readonly BulkEmailFinding[]): boolean {
  return findings.some((finding) => finding.level === 'error');
}

/**
 * The findings a refused send or test carries under `checks`, or null when the
 * refusal is of another kind.
 */
export function refusedFindings(error: unknown): BulkEmailFinding[] | null {
  if (!(error instanceof ApiError) || error.body === null || typeof error.body !== 'object') {
    return null;
  }
  const checks = (error.body as Record<string, unknown>).checks;
  return Array.isArray(checks) ? (checks as BulkEmailFinding[]) : null;
}
