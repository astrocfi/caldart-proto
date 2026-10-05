/**
 * The member verification panel: correct a person's certificate, medical, and photo ID,
 * and record which of them an authority has checked, in one save.
 *
 * Opened by **Verify** on the member check's status card and on the member record.  On
 * the member record, whose own form edits the fields, it offers the checks alone.
 */
import { useRef, useState } from 'react';
import type { FormEvent, JSX } from 'react';

import type { LeaderStatus, VerificationItem } from '@/portal/api/types';
import { CERTIFICATE_TYPES, MEDICAL_TYPES } from '@/portal/choices';
import type { Choice } from '@/portal/choices';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { RefusedSubmitNote, useRefusedSubmit } from '@/portal/components/RefusedSubmit';
import { useToast } from '@/portal/components/Toast';
import { CERTIFICATE_NUMBER_DIGITS } from '@/portal/features/profile/form';
import { maskDigits } from '@/portal/masks';
import { useVerifyMember } from './api';
import { saveErrors } from './errors';
import { isItemHeld } from './held';
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
  /**
   * Offer only the checks, for a screen whose own form edits the fields: the member
   * record.  The panel then sends no field, only which items are verified.
   */
  checksOnly?: boolean;
  /** What the record holds for each item, shown beside its box when only checks are offered. */
  details?: Partial<Record<VerificationItem, string>>;
}

/**
 * Edits a person's verified fields and checks the items an authority has checked.  Only
 * an item the person holds gets a box: *Not a pilot*, a medical of *None*, and a photo
 * ID of *Not provided* have nothing to verify.
 */
export function MemberVerificationPanel({
  userId,
  initial,
  onSaved,
  onClose: handleClose,
  checksOnly = false,
  details = {},
}: MemberVerificationPanelProps): JSX.Element {
  // Freezes the opening draft so a refetch while the panel is open -- the status
  // card's own query, invalidated by another save -- cannot resend stale values
  // into an edit already in progress here.
  const [draft, setDraft] = useState(() => initial);
  const verify = useVerifyMember(userId);
  const toast = useToast();
  const formRef = useRef<HTMLFormElement>(null);
  const refusal = useRefusedSubmit(formRef, verify.error);
  const errors = saveErrors(verify.error, FORM_FIELDS);
  // An item the person does not hold has nothing to verify, so it gets no box.
  const held = ITEM_SLUGS.filter((item) => isItemHeld(item, draft));

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
      <form ref={formRef} onSubmit={handleSubmit} noValidate>
        {errors.form !== null ? (
          <p role="alert" className="field__error">
            {errors.form}
          </p>
        ) : null}
        {checksOnly ? null : (
          <div className="form-grid">
            {coded('pilot_certificate_type', 'Pilot certificate', CERTIFICATE_TYPES)}
            <Field
              label="Certificate number"
              hint={`${CERTIFICATE_NUMBER_DIGITS} digits`}
              error={errors.fields.certificate_number}
            >
              {(props) => (
                <MaskedInput
                  {...props}
                  className="num"
                  inputMode="numeric"
                  mask={(raw) => maskDigits(raw, CERTIFICATE_NUMBER_DIGITS)}
                  value={draft.certificate_number}
                  onValueChange={(next) => set('certificate_number', next)}
                />
              )}
            </Field>
            {coded('medical_type', 'Medical', MEDICAL_TYPES)}
            <Field label="Medical expires" error={errors.fields.medical_expiration}>
              {(props) => (
                <input
                  {...props}
                  type="date"
                  className="num"
                  value={draft.medical_expiration}
                  onChange={(event) => set('medical_expiration', event.target.value)}
                />
              )}
            </Field>
            {coded('photo_id_type', 'Photo ID', PHOTO_ID_TYPES)}
          </div>
        )}

        <fieldset className="checkbox-set verification-panel__items">
          <legend>Checked against the documents</legend>
          {held.length === 0 ? (
            <p className="muted">
              {checksOnly
                ? 'Nothing to verify yet. Record a pilot certificate, a medical, or a photo ID in the form below first.'
                : 'Nothing to verify yet. Choose a pilot certificate, a medical, or a photo ID above to verify it.'}
            </p>
          ) : null}
          {held.map((item) => (
            <label key={item} className="checkbox">
              <input
                type="checkbox"
                checked={draft.verified.includes(item)}
                onChange={(event) =>
                  setDraft((current) => toggleItem(current, item, event.target.checked))
                }
              />
              <span>
                {ITEM_LABELS[item]} verified
                {checksOnly && details[item] !== undefined ? (
                  <span className="muted"> · {details[item]}</span>
                ) : null}
              </span>
            </label>
          ))}
        </fieldset>

        <div className="cluster">
          <Button type="submit" disabled={verify.isPending}>
            {verify.isPending ? 'Saving…' : 'Save verification'}
          </Button>
          <Button variant="quiet" onClick={handleClose}>
            Cancel
          </Button>
          <RefusedSubmitNote count={refusal.count} />
        </div>
      </form>
    </Card>
  );
}
