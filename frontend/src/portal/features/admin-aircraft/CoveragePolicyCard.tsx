/**
 * The **Coverage policy** card on the aircraft register: which aircraft
 * categories and airworthiness classifications CalDART's insurance does not
 * cover, and the note members read on My aircraft.  Only a system administrator
 * sees it, on the aircraft register, and edits it in place.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { AircraftCategory, AircraftCoveragePolicy, Airworthiness } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { MultiSelect } from '@/portal/components/MultiSelect';
import { useToast } from '@/portal/components/Toast';
import { useCoveragePolicy, useSaveCoveragePolicy } from '@/portal/features/aircraft/api';
import {
  AIRWORTHINESS_LABELS,
  AIRWORTHINESS_VALUES,
  CATEGORIES,
  CATEGORY_LABELS,
} from '@/portal/features/aircraft/categories';

const CATEGORY_OPTIONS = CATEGORIES.map((value) => ({ value, label: CATEGORY_LABELS[value] }));

const AIRWORTHINESS_OPTIONS = AIRWORTHINESS_VALUES.map((value) => ({
  value,
  label: AIRWORTHINESS_LABELS[value],
}));

/** The longest note the server takes. */
const NOTE_MAX_LENGTH = 1000;

/** `labels` of `values`, joined, or `None` when there are none. */
function listed<Code extends string>(
  values: readonly Code[],
  labels: Record<Code, string>,
): string {
  return values.length === 0 ? 'None' : values.map((value) => labels[value]).join(', ');
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
        <p className="muted">The coverage policy could not be loaded.</p>
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

/** The policy's edit form: two lists of exclusions and the note. */
function CoveragePolicyForm({ initial, onDone: handleDone }: CoveragePolicyFormProps): JSX.Element {
  const [values, setValues] = useState<AircraftCoveragePolicy>(initial);
  const save = useSaveCoveragePolicy();
  const toast = useToast();
  const errors = save.error instanceof ApiError ? save.error.fieldErrors : {};

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    save.mutate(values, {
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
        label="Note to members"
        hint="Shown above the list on every member's My aircraft page."
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
          {save.isPending ? 'Saving…' : 'Save policy'}
        </Button>
        <Button variant="quiet" onClick={handleDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
