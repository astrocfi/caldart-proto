/**
 * The **Practice run** box beside a job's **Run now**: checked, the run shows what it
 * would do and does nothing.  Several jobs share a screen, so each box is named after
 * its job for a screen reader, after the words everyone sees.
 */
import type { ChangeEvent, JSX } from 'react';

export interface PracticeRunCheckboxProps {
  checked: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  /** The job the box belongs to, such as `scheduled reports`, heard after the label. */
  task: string;
  /** What a practice run leaves undone: `send nothing`, `charge nothing`, ... */
  leaves?: string;
}

/** A checkbox reading *Practice run: show what would happen, send nothing*. */
export function PracticeRunCheckbox({
  checked,
  onChange: handleChange,
  task,
  leaves = 'send nothing',
}: PracticeRunCheckboxProps): JSX.Element {
  return (
    <label className="cluster">
      <input type="checkbox" checked={checked} onChange={handleChange} />
      Practice run: show what would happen, {leaves}
      <span className="visually-hidden"> ({task})</span>
    </label>
  );
}
