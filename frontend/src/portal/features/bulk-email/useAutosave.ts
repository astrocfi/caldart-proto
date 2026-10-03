/**
 * The compose screen's autosave: the subject and message as typed, saved once the
 * typing pauses, with a state the screen shows as a quiet *Saved* note.
 *
 * There is no Save button to forget. Send calls `flush` first, so the words on
 * the screen are the words that go.
 */
import { useCallback, useEffect, useState } from 'react';

import { ApiError } from '@/portal/api/client';
import type { BulkEmailDetail, BulkEmailPatch } from '@/portal/api/types';
import { useDebounced } from '@/portal/components/useDebounced';
import { useUpdateBulkEmail } from './api';

/** How long the typing must pause before the words are saved. */
export const AUTOSAVE_MS = 800;

/** Whether the words on the screen are saved, being saved, or could not be. */
export type SaveState = 'saved' | 'saving' | 'failed';

/** The two fields the screen saves. */
export interface MessageValues {
  subject: string;
  body: string;
}

export interface Autosave {
  values: MessageValues;
  setSubject: (subject: string) => void;
  setBody: (body: string) => void;
  saveState: SaveState;
  /** The server's complaint about each field, if it refused one. */
  errors: Partial<Record<keyof MessageValues, string>>;
  /** Save what is on the screen now; resolves true once it is saved. */
  flush: () => Promise<boolean>;
}

/**
 * The fields of `next` that differ from `saved`.
 *
 * @param saved what the server holds.
 * @param next what the screen holds.
 */
export function changedFields(saved: MessageValues, next: MessageValues): BulkEmailPatch {
  const patch: BulkEmailPatch = {};
  if (next.subject !== saved.subject) patch.subject = next.subject;
  if (next.body !== saved.body) patch.body = next.body;
  return patch;
}

/**
 * Keep `email`'s subject and message as typed, saving them once the typing pauses.
 *
 * @param email the email as first read; later reads of it do not overwrite what
 *   is being typed.
 * @param isEditable false once the email has started sending; nothing is saved then.
 */
export function useAutosave(email: BulkEmailDetail, isEditable: boolean): Autosave {
  const [values, setValues] = useState<MessageValues>({
    subject: email.subject,
    body: email.body,
  });
  const [lastSaved, setLastSaved] = useState<MessageValues>(values);
  const [hasFailed, setHasFailed] = useState(false);
  const [errors, setErrors] = useState<Autosave['errors']>({});
  const update = useUpdateBulkEmail(email.id);
  const { mutateAsync, isPending } = update;

  const save = useCallback(
    async (next: MessageValues): Promise<boolean> => {
      const patch = changedFields(lastSaved, next);
      if (!isEditable || Object.keys(patch).length === 0) return true;
      try {
        await mutateAsync(patch);
      } catch (error) {
        setHasFailed(true);
        setErrors(error instanceof ApiError ? error.fieldErrors : {});
        return false;
      }
      setLastSaved(next);
      setHasFailed(false);
      setErrors({});
      return true;
    },
    [isEditable, lastSaved, mutateAsync],
  );

  const settled = useDebounced(values, AUTOSAVE_MS);
  useEffect(() => {
    void save(settled);
  }, [settled, save]);

  const isDirty = values.subject !== lastSaved.subject || values.body !== lastSaved.body;
  const saveState: SaveState = hasFailed ? 'failed' : isDirty || isPending ? 'saving' : 'saved';

  return {
    values,
    setSubject: (subject) => setValues((current) => ({ ...current, subject })),
    setBody: (body) => setValues((current) => ({ ...current, body })),
    saveState,
    errors,
    flush: () => save(values),
  };
}
