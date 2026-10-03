/**
 * The client for the endpoints behind the bulk email editor: the recipient field
 * catalog, `GET /bulk-email/fields`, and image uploads, `POST /bulk-email/images`.
 */
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type { BulkEmailField, BulkEmailImage } from '@/portal/api/types';

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
