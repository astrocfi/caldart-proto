/**
 * The member list's filter bar.
 *
 * Dropdowns apply as soon as they change; the two typed boxes apply when the
 * form is submitted, so a half-typed name never triggers a query.  The whole
 * bar is one `<form>`, which is what makes Enter work from any control.
 */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';

import type { Dart } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { CERTIFICATE_TYPES, MEDICAL_TYPES, ROLE_CHOICES, STATUS_CHOICES } from './choices';
import type { MemberFilters } from './types';
import { EMPTY_FILTERS } from './types';

export interface MembersFilterBarProps {
  value: MemberFilters;
  onChange: (next: MemberFilters) => void;
  darts: Dart[];
}

/** The member list's filter bar: instant dropdowns and a submit-to-apply search. */
export function MembersFilterBar({ value, onChange, darts }: MembersFilterBarProps): JSX.Element {
  const [draft, setDraft] = useState(value);

  // Keep the typed boxes in step when the URL changes underneath us (back
  // button, or "Clear filters").
  useEffect(() => setDraft(value), [value]);

  /** Apply a dropdown straight away, keeping whatever has been typed. */
  const apply = (patch: Partial<MemberFilters>) => {
    const next = { ...draft, ...patch };
    setDraft(next);
    onChange(next);
  };

  const select = (
    key: keyof MemberFilters,
    label: string,
    anyLabel: string,
    options: { value: string; label: string }[],
  ) => (
    <Field label={label}>
      {(props) => (
        <select
          {...props}
          value={draft[key]}
          onChange={(event) => apply({ [key]: event.target.value })}
        >
          <option value="">{anyLabel}</option>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  );

  return (
    <form
      className="data-table__filters"
      role="search"
      aria-label="Filter members"
      onSubmit={(event) => {
        event.preventDefault();
        onChange(draft);
      }}
    >
      <Field label="Search">
        {(props) => (
          <input
            {...props}
            type="search"
            placeholder="Name, email, phone, or certificate"
            value={draft.search}
            onChange={(event) => setDraft({ ...draft, search: event.target.value })}
          />
        )}
      </Field>

      {select('status', 'Membership', 'Any status', STATUS_CHOICES)}
      {select('certificate', 'Certificate', 'Any certificate', CERTIFICATE_TYPES)}
      {select('medical', 'Medical', 'Any medical', MEDICAL_TYPES)}
      {select(
        'dart',
        'DART',
        'Any DART',
        darts.map((dart) => ({ value: String(dart.id), label: dart.name })),
      )}
      {select('role', 'Role', 'Any role', ROLE_CHOICES)}

      {/* The unit goes in the label, not in a hint underneath: a hint would
          make this field taller than its neighbors and lift the input off the
          row the rest of the bar sits on. */}
      <Field label="Expiring within (days)">
        {(props) => (
          <input
            {...props}
            type="number"
            min={1}
            max={3650}
            inputMode="numeric"
            value={draft.expiring_within}
            onChange={(event) => setDraft({ ...draft, expiring_within: event.target.value })}
          />
        )}
      </Field>

      <Button type="submit" small>
        Apply
      </Button>
      <Button
        type="button"
        variant="quiet"
        small
        onClick={() => {
          setDraft(EMPTY_FILTERS);
          onChange(EMPTY_FILTERS);
        }}
      >
        Clear
      </Button>
    </form>
  );
}
