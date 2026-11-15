/**
 * The **Coverage policy** card on the aircraft register: which aircraft
 * categories and airworthiness classifications CalDART's insurance does not
 * cover, the least liability an aircraft's own policy must carry, and the note
 * members read on My aircraft.  Only a system administrator
 * sees it, on the aircraft register, and edits it in place.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { AircraftCategory, AircraftCoveragePolicy, Airworthiness } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { MultiSelect } from '@/portal/components/MultiSelect';
import { useToast } from '@/portal/components/Toast';
import { useCoveragePolicy, useSaveCoveragePolicy } from '@/portal/features/aircraft/api';
import {
  AIRWORTHINESS_LABELS,
  AIRWORTHINESS_VALUES,
  CATEGORIES,
  CATEGORY_LABELS,
} from '@/portal/features/aircraft/categories';
import { centsToDollars, dollarsToCents } from '@/portal/features/aircraft/insurance';
import { maskDollars } from '@/portal/masks';
import './policy.css';

const CATEGORY_OPTIONS = CATEGORIES.map((value) => ({ value, label: CATEGORY_LABELS[value] }));

const AIRWORTHINESS_OPTIONS = AIRWORTHINESS_VALUES.map((value) => ({
  value,
  label: AIRWORTHINESS_LABELS[value],
}));

/** The longest note the server takes. */
const NOTE_MAX_LENGTH = 1000;

/** `labels` of `values`, joined, or `None` when `values` is empty. */
function listed<Code extends string>(
  values: readonly Code[],
  labels: Record<Code, string>,
): string {
  return values.length === 0 ? 'None' : values.map((value) => labels[value]).join(', ');
}

/** The minimums in words, such as `$1,000,000 per occurrence, $100,000 per person`. */
export function minimumsText(policy: AircraftCoveragePolicy): string {
  const parts = [
    policy.min_liability_per_occurrence_cents > 0
      ? `$${centsToDollars(policy.min_liability_per_occurrence_cents)} per occurrence`
      : null,
    policy.min_liability_per_person_cents > 0
      ? `$${centsToDollars(policy.min_liability_per_person_cents)} per person`
      : null,
  ].filter((part) => part !== null);
  return parts.length === 0 ? 'None' : parts.join(', ');
}

/** The coverage policy, read and edited by a system administrator. */
export function CoveragePolicyCard(): JSX.Element {
  const policy = useCoveragePolicy();
  const [draft, setDraft] = useState<AircraftCoveragePolicy | null>(null);

  if (policy.isPending) {
    return (
      <Card eyebrow="Insurance" title="Coverage policy">
        <p className="muted" role="status">
          Loading the coverage policy…
        </p>
      </Card>
    );
  }

  if (policy.isError) {
    return (
      <Card eyebrow="Insurance" title="Coverage policy">
        <p className="muted">The coverage policy didn&apos;t load. Try again in a moment.</p>
      </Card>
    );
  }

  const stored = policy.data;

  return (
    <Card eyebrow="Insurance" title="Coverage policy">
      {draft === null ? (
        <>
          <dl className="aircraft-policy">
            <div>
              <dt>Excluded categories</dt>
              <dd>{listed(stored.excluded_categories, CATEGORY_LABELS)}</dd>
            </div>
            <div>
              <dt>Excluded airworthiness</dt>
              <dd>{listed(stored.excluded_airworthiness, AIRWORTHINESS_LABELS)}</dd>
            </div>
            <div>
              <dt>Minimum liability</dt>
              <dd>{minimumsText(stored)}</dd>
            </div>
            <div>
              <dt>Note to members</dt>
              <dd>{stored.note === '' ? 'None' : stored.note}</dd>
            </div>
          </dl>
          <Button variant="secondary" small onClick={() => setDraft(stored)}>
            Edit policy
          </Button>
        </>
      ) : (
        <CoveragePolicyForm initial={draft} onDone={() => setDraft(null)} />
      )}
    </Card>
  );
}

interface CoveragePolicyFormProps {
  initial: AircraftCoveragePolicy;
  onDone: () => void;
}

/** The two minimums as typed, in dollars; a blank box is no minimum. */
interface MinimumsDraft {
  perOccurrence: string;
  perPerson: string;
}

/** The policy's edit form: two lists of exclusions, the liability minimums, and the note. */
function CoveragePolicyForm({ initial, onDone: handleDone }: CoveragePolicyFormProps): JSX.Element {
  const [values, setValues] = useState<AircraftCoveragePolicy>(initial);
  const [minimums, setMinimums] = useState<MinimumsDraft>({
    perOccurrence: centsToDollars(initial.min_liability_per_occurrence_cents),
    perPerson: centsToDollars(initial.min_liability_per_person_cents),
  });
  const save = useSaveCoveragePolicy();
  const toast = useToast();
  const errors = save.error instanceof ApiError ? save.error.fieldErrors : {};

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    const policy: AircraftCoveragePolicy = {
      ...values,
      min_liability_per_occurrence_cents: dollarsToCents(minimums.perOccurrence) ?? 0,
      min_liability_per_person_cents: dollarsToCents(minimums.perPerson) ?? 0,
    };
    save.mutate(policy, {
      onSuccess: () => {
        toast.show('Coverage policy saved.', 'success');
        handleDone();
      },
    });
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="stack">
      <Field label="Excluded categories" error={errors.excluded_categories}>
        {(field) => (
          <MultiSelect
            id={field.id}
            aria-describedby={field['aria-describedby']}
            legend="Excluded categories"
            options={CATEGORY_OPTIONS}
            value={values.excluded_categories}
            placeholder="None"
            onChange={(next) =>
              setValues((current) => ({
                ...current,
                excluded_categories: next as AircraftCategory[],
              }))
            }
          />
        )}
      </Field>
      <Field label="Excluded airworthiness" error={errors.excluded_airworthiness}>
        {(field) => (
          <MultiSelect
            id={field.id}
            aria-describedby={field['aria-describedby']}
            legend="Excluded airworthiness"
            options={AIRWORTHINESS_OPTIONS}
            value={values.excluded_airworthiness}
            placeholder="None"
            onChange={(next) =>
              setValues((current) => ({
                ...current,
                excluded_airworthiness: next as Airworthiness[],
              }))
            }
          />
        )}
      </Field>
      <Field
        label="Minimum liability per occurrence"
        hint="In US dollars. An airplane whose policy carries less isn't covered. Leave it blank for no minimum."
        error={errors.min_liability_per_occurrence_cents}
      >
        {(field) => (
          <MaskedInput
            {...field}
            className="num"
            inputMode="decimal"
            mask={maskDollars}
            value={minimums.perOccurrence}
            onValueChange={(next) =>
              setMinimums((current) => ({ ...current, perOccurrence: next }))
            }
          />
        )}
      </Field>
      <Field
        label="Minimum liability per person"
        hint="In US dollars. Leave it blank for no minimum."
        error={errors.min_liability_per_person_cents}
      >
        {(field) => (
          <MaskedInput
            {...field}
            className="num"
            inputMode="decimal"
            mask={maskDollars}
            value={minimums.perPerson}
            onValueChange={(next) => setMinimums((current) => ({ ...current, perPerson: next }))}
          />
        )}
      </Field>
      <Field
        label="Note to members"
        hint={'Shown above the list on every member\'s "My aircraft" page.'}
        error={errors.note}
      >
        {(field) => (
          <textarea
            {...field}
            rows={3}
            maxLength={NOTE_MAX_LENGTH}
            value={values.note}
            onChange={(event) => setValues((current) => ({ ...current, note: event.target.value }))}
          />
        )}
      </Field>
      <div className="cluster">
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? 'Saving…' : 'Save changes'}
        </Button>
        <Button variant="quiet" onClick={handleDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
