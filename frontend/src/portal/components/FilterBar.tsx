/**
 * The portal's one filter bar.
 *
 * Every report's list page and the form that subscribes somebody to a report
 * draw their filters through this component, from the report's `FilterField`s
 * in `@/portal/reports/definitions`.  Every control applies itself: a select,
 * a date and a toggle as soon as they change, a text or number box once the
 * typing pauses.  There is no Apply button.  **Clear** empties every field.
 *
 * The bar is one `<form role="search">`.  A bar of one box applies it at once
 * when Enter is pressed, which is how a browser submits a form of one field.
 */
import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, FormEvent, JSX } from 'react';

import { maskDigits } from '@/portal/masks';
import type { FilterField, FilterValues, Option } from '@/portal/reports/types';
import { Button } from './Button';
import { Field } from './Field';
import { MaskedInput } from './MaskedInput';
import { useDebounced } from './useDebounced';

export interface FilterBarProps {
  fields: readonly FilterField[];
  /** The applied values, by field key; a missing key reads as empty. */
  values: FilterValues;
  /** Called with every value the bar holds, the fields' keys all present. */
  onChange: (values: FilterValues) => void;
  /** Choices supplied at run time, by field key, replacing any the field declares. */
  options?: Readonly<Record<string, readonly Option[]>>;
  /** The name of the search landmark the bar is. */
  label?: string;
}

/** The longest number a number field holds: six digits is ample for days and dollars. */
const NUMBER_DIGITS = 6;

/** The value a ticked toggle sends. */
const TOGGLE_ON = 'true';

/**
 * The bar's values with every field present, so the draft and the applied values
 * compare key for key.
 */
function completeValues(fields: readonly FilterField[], values: FilterValues): FilterValues {
  return { ...values, ...Object.fromEntries(fields.map((f) => [f.key, values[f.key] ?? ''])) };
}

/** Whether a field's value is typed, and so applied only once the typing pauses. */
function isTyped(field: FilterField): boolean {
  return field.kind === 'search' || field.kind === 'number';
}

/** Cents as the whole dollars a dollar field shows, or `''` for no bound. */
function dollarsFromCents(cents: string): string {
  if (cents === '') return '';
  return String(Math.floor(Number(cents) / 100));
}

/** Whole dollars typed into a dollar field as the cents its parameter takes. */
function centsFromDollars(dollars: string): string {
  return dollars === '' ? '' : String(Number(dollars) * 100);
}

/**
 * The shared filter bar: one control per `FilterField`, each applying itself.
 *
 * @param fields the report's filter fields, in the order they are drawn.
 * @param values the applied values; a change from outside (the back button, a
 *   link) refreshes the boxes, while a re-render with equal values leaves what
 *   is being typed alone.
 * @param onChange called with the whole set of values whenever one applies.
 * @param options choices supplied at run time, such as the DART or plan list.
 * @param label the name of the search landmark, e.g. `Filter members`.
 */
export function FilterBar({
  fields,
  values,
  onChange,
  options = {},
  label = 'Filters',
}: FilterBarProps): JSX.Element {
  const applied = completeValues(fields, values);
  const appliedKey = JSON.stringify(applied);
  const [draft, setDraft] = useState(applied);
  // The applied values the draft was last reset to.  They are compared by
  // content, so a page re-rendering with an equal object cannot wipe a
  // half-typed box.  The draft follows a real change during the render itself
  // rather than in an effect: an effect would let the settle effect below see
  // the old draft beside the new values for one commit, and send it back.
  const [draftBase, setDraftBase] = useState(appliedKey);
  if (draftBase !== appliedKey) {
    setDraftBase(appliedKey);
    setDraft(applied);
  }
  // The last set of values handed to `onChange` since the applied values last
  // changed, so a settled draft is sent once even if the page does not adopt it
  // exactly, yet is sent again once the page has moved to other values.
  const sentKey = useRef(appliedKey);

  const send = (next: FilterValues): void => {
    sentKey.current = JSON.stringify(next);
    onChange(next);
  };

  useEffect(() => {
    sentKey.current = appliedKey;
  }, [appliedKey]);

  // The typed boxes apply once the draft has held still.  Only a draft that is
  // still what the boxes hold counts, so a burst that Clear has since replaced
  // cannot come back.
  const draftKey = JSON.stringify(draft);
  const settledKey = useDebounced(draftKey);
  useEffect(() => {
    if (settledKey !== draftKey || settledKey === appliedKey) return;
    if (settledKey === sentKey.current) return;
    sentKey.current = settledKey;
    onChange(JSON.parse(settledKey) as FilterValues);
  }, [settledKey, draftKey, appliedKey, onChange]);

  /** Change one value; a control that is not typed applies it straight away. */
  const set = (field: FilterField, value: string): void => {
    const next = { ...draft, [field.key]: value };
    setDraft(next);
    if (!isTyped(field)) send(next);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    send(draft);
  };

  const handleClear = (): void => {
    const cleared = { ...draft, ...Object.fromEntries(fields.map((f) => [f.key, ''])) };
    setDraft(cleared);
    send(cleared);
  };

  return (
    <form className="data-table__filters" role="search" aria-label={label} onSubmit={handleSubmit}>
      {fields.map((field) => (
        <FilterControl
          key={field.key}
          field={field}
          value={draft[field.key] ?? ''}
          options={options[field.key] ?? field.options ?? []}
          onSet={(value) => set(field, value)}
        />
      ))}
      <Button type="button" variant="quiet" small onClick={handleClear}>
        Clear
      </Button>
    </form>
  );
}

interface FilterControlProps {
  field: FilterField;
  value: string;
  options: readonly Option[];
  /** Called with the field's next value, in the units its parameter takes. */
  onSet: (value: string) => void;
}

/** One field of the bar, drawn as its kind asks. */
function FilterControl({
  field,
  value,
  options,
  onSet: handleSet,
}: FilterControlProps): JSX.Element {
  const handleChange = (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>): void => {
    handleSet(event.target.value);
  };

  if (field.kind === 'toggle') {
    const handleToggle = (event: ChangeEvent<HTMLInputElement>): void => {
      handleSet(event.target.checked ? TOGGLE_ON : '');
    };
    return (
      <label className="cluster">
        <input type="checkbox" checked={value === TOGGLE_ON} onChange={handleToggle} />
        {field.label}
      </label>
    );
  }

  const handleNumber = (next: string): void => {
    handleSet(field.isDollars ? centsFromDollars(next) : next);
  };

  return (
    <Field label={field.label} hint={field.hint}>
      {(props) => {
        if (field.kind === 'select') {
          return (
            <select {...props} value={value} onChange={handleChange}>
              <option value="">{field.placeholder ?? 'Any'}</option>
              {options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          );
        }
        if (field.kind === 'number') {
          return (
            <MaskedInput
              {...props}
              inputMode="numeric"
              placeholder={field.placeholder}
              mask={(raw) => maskDigits(raw, NUMBER_DIGITS)}
              value={field.isDollars ? dollarsFromCents(value) : value}
              onValueChange={handleNumber}
            />
          );
        }
        return (
          <input
            {...props}
            type={field.kind}
            placeholder={field.placeholder}
            value={value}
            onChange={handleChange}
          />
        );
      }}
    </Field>
  );
}
