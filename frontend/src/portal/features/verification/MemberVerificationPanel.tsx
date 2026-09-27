/**
 * The member verification panel: correct a person's certificate, medical, and photo ID,
 * and record which of them an authority has checked, in one save.
 *
 * Opened by **Verify** on the member check's status card and on the member record.
 */
import { useState } from 'react';
import type { FormEvent, JSX } from 'react';

import type { LeaderStatus } from '@/portal/api/types';
import { CERTIFICATE_TYPES, MEDICAL_TYPES } from '@/portal/choices';
import type { Choice } from '@/portal/choices';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { useToast } from '@/portal/components/Toast';
import { useVerifyMember } from './api';
import { saveErrors } from './errors';
import { ITEM_LABELS, ITEM_SLUGS, PHOTO_ID_TYPES } from './labels';
import { editField, memberVerificationPayload, toggleItem } from './memberDraft';
import type { MemberField, MemberVerificationDraft } from './memberDraft';
import '@/portal/features/profile/profile.css';
import './verification.css';

const FORM_FIELDS: readonly MemberField[] = [
  'pilot_certificate_type',
  'certificate_number',
  'medical_type',
  'medical_expiration',
  'photo_id_type',
];

/** The coded fields, which the panel draws as selects. */
type CodedField = 'pilot_certificate_type' | 'medical_type' | 'photo_id_type';

export interface MemberVerificationPanelProps {
  /** The person being verified. */
  userId: number;
  /** The fields and verified items the panel opens with. */
  initial: MemberVerificationDraft;
  /** Called with the saved status card once the save goes through. */
  onSaved?: (status: LeaderStatus) => void;
  /** Closes the panel, after a save or on Cancel. */
  onClose: () => void;
}

/** Edits a person's verified fields and ticks the items an authority has checked. */
export function MemberVerificationPanel({
  userId,
  initial,
  onSaved,
  onClose: handleClose,
}: MemberVerificationPanelProps): JSX.Element {
  // Freezes the opening draft so a refetch while the panel is open -- the status
  // card's own query, invalidated by another save -- cannot resend stale values
  // into an edit already in progress here.
  const [draft, setDraft] = useState(() => initial);
  const verify = useVerifyMember(userId);
  const toast = useToast();
  const errors = saveErrors(verify.error, FORM_FIELDS);

  const set = <Key extends MemberField>(field: Key, value: MemberVerificationDraft[Key]): void =>
    setDraft((current) => editField(current, initial, field, value));

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    verify.mutate(memberVerificationPayload(initial, draft), {
      onSuccess: (status) => {
        toast.show('Verification saved', 'success');
        onSaved?.(status);
        handleClose();
      },
    });
  };

  const coded = <Key extends CodedField>(
    field: Key,
    label: string,
    choices: readonly Choice<MemberVerificationDraft[Key]>[],
  ) => (
    <Field label={label} error={errors.fields[field]}>
      {(props) => (
        <select
          {...props}
          value={draft[field]}
          onChange={(event) => set(field, event.target.value as MemberVerificationDraft[Key])}
        >
          {choices.map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  );

  return (
    <Card title="Verification" className="verification-panel">
      <form onSubmit={handleSubmit} noValidate>
        {errors.form !== null ? (
          <p role="alert" className="field__error">
            {errors.form}
          </p>
        ) : null}
        <div className="form-grid">
          {coded('pilot_certificate_type', 'Pilot certificate', CERTIFICATE_TYPES)}
          <Field label="Certificate number" error={errors.fields.certificate_number}>
            {(props) => (
              <input
                {...props}
                className="mono"
                value={draft.certificate_number}
                onChange={(event) => set('certificate_number', event.target.value)}
              />
            )}
          </Field>
          {coded('medical_type', 'Medical', MEDICAL_TYPES)}
          <Field label="Medical expires" error={errors.fields.medical_expiration}>
            {(props) => (
              <input
                {...props}
                type="date"
                className="mono"
                value={draft.medical_expiration}
                onChange={(event) => set('medical_expiration', event.target.value)}
              />
            )}
          </Field>
          {coded('photo_id_type', 'Photo ID', PHOTO_ID_TYPES)}
        </div>

        <fieldset className="checkbox-set verification-panel__items">
          <legend>Checked against the documents</legend>
          {ITEM_SLUGS.map((item) => (
            <label key={item} className="checkbox">
              <input
                type="checkbox"
                checked={draft.verified.includes(item)}
                onChange={(event) =>
                  setDraft((current) => toggleItem(current, item, event.target.checked))
                }
              />
              <span>{ITEM_LABELS[item]} verified</span>
            </label>
          ))}
        </fieldset>

        <div className="cluster">
          <Button type="submit" disabled={verify.isPending}>
            {verify.isPending ? 'Saving…' : 'Save'}
          </Button>
          <Button variant="quiet" onClick={handleClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}
