/**
 * The client for the endpoints behind the bulk email editor: the recipient field
 * catalog, `GET /bulk-email/fields`; image uploads, `POST /bulk-email/images`; and
 * one person's copy of a message, `POST /bulk-email/{id}/preview`.
 */
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type { BulkEmailField, BulkEmailImage, BulkEmailPreview } from '@/portal/api/types';
import { BULK_EMAIL_KEY } from './api';

export const BULK_EMAIL_FIELDS_KEY = ['bulk-email-fields'] as const;

/**
 * The recipient fields a message can fill in, in the order the menu lists them.
 * The catalog is fixed in the code, so it is read once a session.
 */
export function useBulkEmailFields(): UseQueryResult<BulkEmailField[]> {
  return useQuery({
    queryKey: BULK_EMAIL_FIELDS_KEY,
    queryFn: () => api.get<BulkEmailField[]>('/bulk-email/fields'),
    staleTime: Infinity,
  });
}

/**
 * Uploads one image for a message, as multipart form data under `image`.
 *
 * @returns the stored image: its absolute URL and its size in pixels.
 * @throws ApiError whose message says why the server refused the file, such as
 * one too large or not a PNG, JPEG, GIF, or WebP image.
 */
export function uploadBulkEmailImage(file: File): Promise<BulkEmailImage> {
  const form = new FormData();
  form.append('image', file);
  return api.post<BulkEmailImage>('/bulk-email/images', form);
}

/**
 * One person's copy of an email's saved message, via `POST /bulk-email/{id}/preview`.
 *
 * The copy is read again whenever `version` changes, which the caller passes as
 * whatever says the saved message or the batch has changed. While it is read again
 * the previous copy stays on the screen.
 *
 * @param id the email.
 * @param recipientId the batch row to preview, or null for the first person.
 * @param version changes whenever the copy may have changed.
 */
export function useBulkEmailPreview(
  id: number,
  recipientId: number | null,
  version: string,
): UseQueryResult<BulkEmailPreview> {
  return useQuery({
    queryKey: [...BULK_EMAIL_KEY, 'preview', id, recipientId, version],
    queryFn: () =>
      api.post<BulkEmailPreview>(`/bulk-email/${id}/preview`, { recipient_id: recipientId }),
    placeholderData: keepPreviousData,
  });
}
