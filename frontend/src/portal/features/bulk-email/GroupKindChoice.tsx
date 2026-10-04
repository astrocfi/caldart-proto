/**
 * The choice between a fixed and a live recipient group, each with one plain
 * sentence saying what it keeps. The new group form and **Save as a group** ask it.
 */
import { useId } from 'react';
import type { JSX } from 'react';

import type { RecipientGroupKind } from '@/portal/api/types';

/** What each kind is called, and what it keeps, in the words the screens use. */
const KINDS: readonly { value: RecipientGroupKind; label: string; description: string }[] = [
  {
    value: 'fixed',
    label: 'Fixed',
    description: 'The same people every time, until you add or remove someone.',
  },
  {
    value: 'live',
    label: 'Live',
    description:
      'The filters, run again each time the group is used, so it follows people joining and leaving.',
  },
];

/** `Fixed` or `Live`: a group's kind in words. */
export function groupKindLabel(kind: RecipientGroupKind): string {
  return KINDS.find((option) => option.value === kind)?.label ?? kind;
}

interface GroupKindChoiceProps {
  value: RecipientGroupKind;
  onChange: (kind: RecipientGroupKind) => void;
  /** Explains a kind that cannot be chosen here, beside the choice. */
  hint?: string;
}

/** Two radio buttons, Fixed and Live, each with its sentence. */
export function GroupKindChoice({
  value,
  onChange: handleChange,
  hint,
}: GroupKindChoiceProps): JSX.Element {
  const id = useId();
  return (
    <fieldset className="stack-tight bulk-email__types">
      <legend>Type of group</legend>
      {KINDS.map((option) => (
        <div key={option.value} className="bulk-email__type">
          <input
            id={`${id}-${option.value}`}
            type="radio"
            name={`group-kind-${id}`}
            value={option.value}
            checked={value === option.value}
            aria-describedby={`${id}-${option.value}-description`}
            onChange={() => handleChange(option.value)}
          />
          <div>
            <label htmlFor={`${id}-${option.value}`} className="bulk-email__type-name">
              {option.label}
            </label>
            <p
              id={`${id}-${option.value}-description`}
              className="muted bulk-email__type-description"
            >
              {option.description}
            </p>
          </div>
        </div>
      ))}
      {hint === undefined ? null : <p className="field__hint">{hint}</p>}
    </fieldset>
  );
}
