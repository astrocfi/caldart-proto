/**
 * The compose screen's autosave: the subject and message as typed, saved once the
 * typing pauses, with a state the screen shows as a quiet *Saved* note.
 *
 * There is no Save button to forget. Send calls `flush` first, so the words on
 * the screen are the words that go. Saves run one at a time: a save asked for
 * while another is on its way waits for it, then saves whatever is newest, so two
 * requests never race and an older one never lands last. Words put back to the ones
 * the server holds need no request, and clear any refusal of the words in between.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError } from '@/portal/api/client';
import type { BulkEmailDetail, BulkEmailPatch } from '@/portal/api/types';
import { useDebounced } from '@/portal/components/useDebounced';
import { useUpdateBulkEmail } from './api';

/** How long the typing must pause before the words are saved. */
export const AUTOSAVE_MS = 800;

/**
 * Whether the words on the screen are saved: `idle` before anything was typed,
 * then `saving`, `saved`, or `failed`.
 */
export type SaveState = 'idle' | 'saved' | 'saving' | 'failed';

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
  /** Save what is on the screen now, after any save on its way; true once it is saved. */
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
  const [hasEdited, setHasEdited] = useState(false);
  const [hasFailed, setHasFailed] = useState(false);
  const [inFlight, setInFlight] = useState(0);
  const [errors, setErrors] = useState<Autosave['errors']>({});
  const { mutateAsync } = useUpdateBulkEmail(email.id);

  // The queue's own bookkeeping, read when a queued save runs rather than when it
  // was asked for: what the server holds, the newest words asked to be saved, and
  // the end of the chain of saves.
  const savedRef = useRef(values);
  const newestRef = useRef(values);
  const chainRef = useRef<Promise<boolean>>(Promise.resolve(true));
  const isEditableRef = useRef(isEditable);
  useEffect(() => {
    isEditableRef.current = isEditable;
  }, [isEditable]);

  const saveNewest = useCallback(async (): Promise<boolean> => {
    const next = newestRef.current;
    const patch = changedFields(savedRef.current, next);
    if (!isEditableRef.current) return true;
    if (Object.keys(patch).length === 0) {
      // The words are back to what the server holds, such as a refused field typed
      // and then taken out again: nothing is left to refuse, so the refusal goes too.
      setHasFailed(false);
      setErrors({});
      return true;
    }
    setInFlight((count) => count + 1);
    try {
      await mutateAsync(patch);
    } catch (error) {
      setHasFailed(true);
      setErrors(error instanceof ApiError ? error.fieldErrors : {});
      return false;
    } finally {
      setInFlight((count) => count - 1);
    }
    savedRef.current = next;
    setLastSaved(next);
    setHasFailed(false);
    setErrors({});
    return true;
  }, [mutateAsync]);

  const save = useCallback(
    (next: MessageValues): Promise<boolean> => {
      newestRef.current = next;
      const run = chainRef.current.then(saveNewest);
      chainRef.current = run.catch(() => false);
      return run;
    },
    [saveNewest],
  );

  // Only words that have held still and are still on the screen are saved: a save
  // `flush` made moves the saved words on before the pause has caught up, and the
  // older words the pause still holds must not overwrite them.
  const settled = useDebounced(values, AUTOSAVE_MS);
  const isSettled = settled.subject === values.subject && settled.body === values.body;
  useEffect(() => {
    if (isSettled) void save(settled);
  }, [isSettled, settled, save]);

  const isDirty = values.subject !== lastSaved.subject || values.body !== lastSaved.body;
  const saveState: SaveState = !hasEdited
    ? 'idle'
    : hasFailed
      ? 'failed'
      : isDirty || inFlight > 0
        ? 'saving'
        : 'saved';

  return {
    values,
    setSubject: (subject) => {
      setHasEdited(true);
      setValues((current) => ({ ...current, subject }));
    },
    setBody: (body) => {
      setHasEdited(true);
      setValues((current) => ({ ...current, body }));
    },
    saveState,
    errors,
    flush: () => save(values),
  };
}
