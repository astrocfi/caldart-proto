/**
 * The member list's filter bar.
 *
 * Every control applies itself: the dropdowns as soon as they change, the
 * search as it is typed once the typing pauses, and the day count when the
 * form is submitted.  The whole bar is one `<form>`, which is what makes Enter
 * work from any control.
 */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';

import type { Dart } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { useDebounced } from '@/portal/components/useDebounced';
import { maskDigits } from '@/portal/masks';
import {
  CERTIFICATE_FILTER_CHOICES,
  MEDICAL_FILTER_CHOICES,
  ROLE_CHOICES,
  STATUS_CHOICES,
} from './choices';
import type { MemberFilters } from './types';
import { EMPTY_FILTERS } from './types';

export interface MembersFilterBarProps {
  value: MemberFilters;
  onChange: (next: MemberFilters) => void;
  darts: Dart[];
}

/** Days the "expiring within" box accepts: up to four digits, about ten years. */
const DAY_DIGITS = 4;

/** The member list's filter bar: instant dropdowns and a search that runs as it is typed. */
export function MembersFilterBar({ value, onChange, darts }: MembersFilterBarProps): JSX.Element {
  const [draft, setDraft] = useState(value);

  // Keep the typed boxes in step when the URL changes underneath us (back
  // button, or "Clear filters").
  useEffect(() => setDraft(value), [value]);

  // The list is the suggestion list: it narrows as the name is typed, once the
  // typing pauses, rather than waiting for the form to be submitted.
  const debouncedSearch = useDebounced(draft.search);
  useEffect(() => {
    // Only what is still in the box counts: clearing the filters resets the
    // draft, and a stale debounced term must not put the search back.
    if (debouncedSearch !== draft.search) return;
    if (debouncedSearch !== value.search) onChange({ ...value, search: debouncedSearch });
  }, [debouncedSearch, draft.search, onChange, value]);

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

      {/* "Any" on its own, never "Any status": a filter that is not set takes
          in the members who answered "none" as well as those who answered. */}
      {select('status', 'Membership', 'Any', STATUS_CHOICES)}
      {select('certificate', 'Certificate', 'Any', CERTIFICATE_FILTER_CHOICES)}
      {select('medical', 'Medical', 'Any', MEDICAL_FILTER_CHOICES)}
      {select(
        'dart',
        'DART',
        'Any',
        darts.map((dart) => ({ value: String(dart.id), label: dart.name })),
      )}
      {select('role', 'Role', 'Any', ROLE_CHOICES)}

      {/* The unit goes in the label, not in a hint underneath: a hint would
          make this field taller than its neighbors and lift the input off the
          row the rest of the bar sits on. */}
      <Field label="Expiring within (days)">
        {(props) => (
          <MaskedInput
            {...props}
            inputMode="numeric"
            mask={(raw) => maskDigits(raw, DAY_DIGITS)}
            value={draft.expiring_within}
            onValueChange={(next) => setDraft({ ...draft, expiring_within: next })}
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
