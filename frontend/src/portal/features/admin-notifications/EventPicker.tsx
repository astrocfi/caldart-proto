/**
 * The events of a notification subscription as checkboxes, grouped under the
 * catalog's categories, each group with **Select all** and **Clear**.
 */
import type { JSX } from 'react';

import type { NotificationEvent } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { groupEvents } from './labels';

import './admin-notifications.css';

interface EventPickerProps {
  /** The catalog, in its order. */
  events: readonly NotificationEvent[];
  /** The ticked slugs. */
  chosen: ReadonlySet<string>;
  /** Called with the ticked slugs after every change. */
  onChange: (chosen: Set<string>) => void;
}

/**
 * Draws one fieldset per category, its legend the category's name, holding a
 * box per event labeled with the event's name and titled with its description.
 */
export function EventPicker({
  events,
  chosen,
  onChange: handleChange,
}: EventPickerProps): JSX.Element {
  const handleToggle = (slug: string, isChecked: boolean): void => {
    const next = new Set(chosen);
    if (isChecked) next.add(slug);
    else next.delete(slug);
    handleChange(next);
  };

  const handleGroup = (slugs: readonly string[], isChecked: boolean): void => {
    const next = new Set(chosen);
    for (const slug of slugs) {
      if (isChecked) next.add(slug);
      else next.delete(slug);
    }
    handleChange(next);
  };

  return (
    <div className="event-picker">
      {groupEvents(events).map(({ category, events: members }) => {
        const slugs = members.map((event) => event.slug);
        return (
          <fieldset key={category} className="event-picker__group">
            <legend>{category}</legend>
            <div className="cluster">
              <Button variant="quiet" small onClick={() => handleGroup(slugs, true)}>
                Select all
              </Button>
              <Button variant="quiet" small onClick={() => handleGroup(slugs, false)}>
                Clear
              </Button>
            </div>
            {members.map((event) => (
              <label key={event.slug} className="event-picker__option" title={event.description}>
                <input
                  type="checkbox"
                  name={event.slug}
                  checked={chosen.has(event.slug)}
                  onChange={(change) => handleToggle(event.slug, change.target.checked)}
                />
                {event.label}
              </label>
            ))}
          </fieldset>
        );
      })}
    </div>
  );
}
