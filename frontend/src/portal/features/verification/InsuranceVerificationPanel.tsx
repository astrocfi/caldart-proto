/**
 * The insurance verification panel: correct an aircraft's policy and record whether an
 * authority has checked it, in one save.
 *
 * Opened by **Verify** on the aircraft check's card and on the aircraft record.
 */
import { useRef, useState } from 'react';
import type { FormEvent, JSX } from 'react';

import type { AircraftDetail } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { RefusedSubmitNote, useRefusedSubmit } from '@/portal/components/RefusedSubmit';
import { useToast } from '@/portal/components/Toast';
import { maskDollars } from '@/portal/masks';
import { useVerifyInsurance } from './api';
import { saveErrors } from './errors';
import {
  MONEY_FIELDS,
  draftFromAircraft,
  editInsurance,
  insurancePayload,
  validateInsurance,
} from './insuranceDraft';
import type { InsuranceField } from './insuranceDraft';
import '@/portal/features/aircraft/aircraft.css';
import '@/portal/features/profile/profile.css';
import './verification.css';

/** The API's names for the fields this panel sends, for reading a refused save. */
const API_FIELDS: readonly string[] = [
  'insurance_carrier',
  'insurance_policy_number',
  'insurance_expiration',
  ...Object.values(MONEY_FIELDS),
];

const MONEY_LABELS: Record<keyof typeof MONEY_FIELDS, string> = {
  liability_per_occurrence: 'Liability per occurrence',
  liability_per_person: 'Liability per person',
  hull: 'Hull',
};

export interface InsuranceVerificationPanelProps {
  aircraft: AircraftDetail;
  /** Called with the saved aircraft once the save goes through. */
  onSaved?: (aircraft: AircraftDetail) => void;
  /** Closes the panel, after a save or on Cancel. */
  onClose: () => void;
}

/** Edits an aircraft's insurance and ticks whether an authority has checked it. */
export function InsuranceVerificationPanel({
  aircraft,
  onSaved,
  onClose: handleClose,
}: InsuranceVerificationPanelProps): JSX.Element {
  const [initial] = useState(() => draftFromAircraft(aircraft));
  const [draft, setDraft] = useState(initial);
  const [submitted, setSubmitted] = useState(false);
  const verify = useVerifyInsurance(aircraft.id);
  const toast = useToast();
  const formRef = useRef<HTMLFormElement>(null);
  const refusal = useRefusedSubmit(formRef, verify.error);

  const refused = saveErrors(verify.error, API_FIELDS);
  const local = submitted ? validateInsurance(draft) : {};

  const set = (field: InsuranceField, value: string): void =>
    setDraft((current) => editInsurance(current, initial, field, value));

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setSubmitted(true);
    if (Object.keys(validateInsurance(draft)).length > 0) {
      refusal.refuse();
      return;
    }
    verify.mutate(insurancePayload(initial, draft), {
      onSuccess: (saved) => {
        toast.show('Verification saved', 'success');
        onSaved?.(saved);
        handleClose();
      },
    });
  };

  const text = (field: InsuranceField, label: string, options: { type?: 'date' } = {}) => (
    <Field label={label} error={refused.fields[field]}>
      {(props) => (
        <input
          {...props}
          type={options.type ?? 'text'}
          className={field === 'insurance_carrier' ? undefined : 'mono'}
          value={draft[field]}
          onChange={(event) => set(field, event.target.value)}
        />
      )}
    </Field>
  );

  return (
    <Card title="Verification" className="verification-panel">
      <form ref={formRef} onSubmit={handleSubmit} noValidate>
        {refused.form !== null ? (
          <p role="alert" className="field__error">
            {refused.form}
          </p>
        ) : null}
        <div className="aircraft-form__grid">
          {text('insurance_carrier', 'Carrier')}
          {text('insurance_policy_number', 'Policy number')}
          {(Object.keys(MONEY_FIELDS) as (keyof typeof MONEY_FIELDS)[]).map((field) => (
            <Field
              key={field}
              label={MONEY_LABELS[field]}
              hint="US dollars; commas write themselves."
              error={local[field] ?? refused.fields[MONEY_FIELDS[field]]}
            >
              {(props) => (
                <MaskedInput
                  {...props}
                  className="mono"
                  inputMode="decimal"
                  mask={maskDollars}
                  value={draft[field]}
                  onValueChange={(next) => set(field, next)}
                />
              )}
            </Field>
          ))}
          {text('insurance_expiration', 'Insurance expires', { type: 'date' })}
        </div>

        <label className="checkbox verification-panel__items">
          <input
            type="checkbox"
            checked={draft.verified}
            onChange={(event) =>
              setDraft((current) => ({ ...current, verified: event.target.checked }))
            }
          />
          <span>Insurance verified</span>
        </label>

        <div className="cluster">
          <Button type="submit" disabled={verify.isPending}>
            {verify.isPending ? 'Saving…' : 'Save'}
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
