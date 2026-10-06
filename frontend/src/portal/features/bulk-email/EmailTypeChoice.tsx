/**
 * The type choice at the top of **What it says**: what type of email this is.
 *
 * One radio button per type the sender may send, each with the sentence saying what
 * the type is for; a mission callout offers the Mission type alone. Choosing one saves it at once, and the batch is read again, since
 * whoever turned that type off is now skipped. While a choice saves the buttons stay
 * enabled, so the keyboard focus stays on them, and a further choice is ignored. Until a type is chosen the choice says
 * *Choose what type of email this is*, and Send is refused with *Choose a type.*
 * Changing the type of a scheduled email takes it back to the drafts, since who has
 * turned the type off changes the count that was confirmed, and the screen says so.
 */
import { useId, useState } from 'react';
import type { JSX } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { ApiError } from '@/portal/api/client';
import type { BulkEmailDetail, SendableEmailType } from '@/portal/api/types';
import { useToast } from '@/portal/components/Toast';
import { batchKey, emailKey, useSendableEmailTypes, useUpdateBulkEmail } from './api';

/** What the screen says when a change of type took a scheduled email back to the drafts. */
export const TYPE_CHANGED_MESSAGE =
  'The type changed, so this email is back in your drafts. Press Send or Schedule again when it is ready.';

/** True when an email that was queued came back from a change as a draft. */
export function wasUnqueued(before: BulkEmailDetail | undefined, after: BulkEmailDetail): boolean {
  return before?.status === 'queued' && after.status === 'draft';
}

/** The hint shown until a type is chosen. */
export const NO_TYPE_HINT = 'Choose what type of email this is.';

/** What a callout's choice says when the sender may send no Mission type. */
export const NO_MISSION_TYPE =
  'A mission callout goes as the Mission type, which you may not send. Ask a system administrator.';

interface EmailTypeChoiceProps {
  emailId: number;
  /** The chosen type's id, or null while none is chosen. */
  emailType: number | null;
  /** The chosen type's name, shown as it is once the email can no longer change. */
  emailTypeName: string;
  /** True for a mission callout, which offers the Mission type only. */
  isCallout: boolean;
  isEditable: boolean;
}

/** The radio list of sendable types, saving the choice the moment it is made. */
export function EmailTypeChoice({
  emailId,
  emailType,
  emailTypeName,
  isCallout,
  isEditable,
}: EmailTypeChoiceProps): JSX.Element {
  const types = useSendableEmailTypes();
  const update = useUpdateBulkEmail(emailId);
  const queryClient = useQueryClient();
  const toast = useToast();
  const hintId = useId();
  // The type being saved, shown as chosen until the server answers; a refusal puts
  // the choice back to the saved one.
  const [saving, setSaving] = useState<number | null>(null);
  const chosen = saving ?? emailType;

  const handleChoose = (id: number | null): void => {
    // The radios stay enabled while a choice saves, so the keyboard focus stays on
    // them; a second choice made before the first is saved is ignored. The compose
    // screen offers no choice of no type.
    if (update.isPending || id === null) return;
    setSaving(id);
    const before = queryClient.getQueryData<BulkEmailDetail>(emailKey(emailId));
    update.mutate(
      { email_type: id },
      {
        onSuccess: (saved) => {
          if (wasUnqueued(before, saved)) toast.show(TYPE_CHANGED_MESSAGE, 'info');
          void queryClient.invalidateQueries({ queryKey: batchKey(emailId) });
        },
        onSettled: () => setSaving(null),
      },
    );
  };

  if (!isEditable) {
    return (
      <p>
        <strong>Type:</strong> {emailTypeName === '' ? 'None' : emailTypeName}
      </p>
    );
  }

  const options = (types.data ?? []).filter((type) => !isCallout || type.is_mission);
  const error = update.error instanceof ApiError ? update.error.message : null;

  return (
    <fieldset
      className="stack-tight bulk-email__types"
      aria-describedby={chosen === null ? hintId : undefined}
    >
      <legend>Type of email</legend>
      {chosen === null ? (
        <p id={hintId} className="field__hint">
          {NO_TYPE_HINT} People who have turned that type of email off are skipped.
        </p>
      ) : null}
      {types.isPending ? <p role="status">Loading the types…</p> : null}
      {types.isError ? (
        <p className="field__error" role="alert">
          The types of email didn&apos;t load. Try again in a moment.
        </p>
      ) : null}
      {types.isSuccess && options.length === 0 ? (
        <p className="field__error" role="alert">
          {isCallout
            ? NO_MISSION_TYPE
            : 'There is no type of email you may send. Ask a system administrator.'}
        </p>
      ) : null}
      <TypeRadios
        name={`email-type-${emailId}`}
        options={options}
        chosen={chosen}
        onChoose={handleChoose}
      />
      {error === null ? null : (
        <p className="field__error" role="alert">
          {error}
        </p>
      )}
    </fieldset>
  );
}

/** One type a radio list offers: an id, or null for no type, with its words. */
export type TypeOption = Pick<SendableEmailType, 'name' | 'description'> & { id: number | null };

interface TypeRadiosProps {
  /** The radio group's name, unique on the page. */
  name: string;
  options: readonly TypeOption[];
  /** The chosen type's id, null for none. */
  chosen: number | null;
  onChoose: (id: number | null) => void;
}

/**
 * One radio button per type, each with the sentence saying what the type is for: the
 * list both the compose screen and the template form choose a type from.
 */
export function TypeRadios({
  name,
  options,
  chosen,
  onChoose: handleChoose,
}: TypeRadiosProps): JSX.Element {
  const id = useId();
  return (
    <>
      {options.map((option) => {
        const optionId = `${id}-${option.id ?? 'none'}`;
        return (
          <div key={option.id ?? 'none'} className="bulk-email__type">
            <input
              id={optionId}
              type="radio"
              name={name}
              value={option.id ?? ''}
              checked={chosen === option.id}
              aria-describedby={option.description === '' ? undefined : `${optionId}-description`}
              onChange={() => handleChoose(option.id)}
            />
            <div>
              <label htmlFor={optionId} className="bulk-email__type-name">
                {option.name}
              </label>
              {option.description === '' ? null : (
                <p id={`${optionId}-description`} className="muted bulk-email__type-description">
                  {option.description}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </>
  );
}
