/**
 * One switch per kind of bulk email, on when the person receives it.
 *
 * Both the person's own Email preferences screen and the member record show these.
 * A switch saves the moment it moves; while that save is under way every switch
 * waits, and the line under them says *Saved.* once it lands, or what went wrong.
 * The switches read the list the server answered the save with, so a refused change
 * puts its switch straight back.
 */
import { useId, useState } from 'react';
import type { JSX } from 'react';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import type { EmailPreference, EmailPreferenceChange } from '@/portal/api/types';
import { EmptyState } from '@/portal/components/EmptyState';

import './email-preferences.css';

export interface EmailPreferenceSwitchesProps {
  /** The preferences to show. */
  preferences: UseQueryResult<EmailPreference[]>;
  /** The save one switch triggers. */
  save: UseMutationResult<EmailPreference[], Error, EmailPreferenceChange>;
  /** Names the group of switches for a screen reader. */
  label: string;
}

/** The switches, their loading and empty states, and the saved-or-failed line. */
export function EmailPreferenceSwitches({
  preferences,
  save,
  label,
}: EmailPreferenceSwitchesProps): JSX.Element {
  const [notice, setNotice] = useState<string | null>(null);

  if (preferences.isPending) return <p role="status">Loading…</p>;
  if (preferences.isError) {
    return (
      <p className="field__error" role="alert">
        The email preferences could not be loaded.
      </p>
    );
  }
  if (preferences.data.length === 0) {
    return (
      <EmptyState
        title="There is nothing to turn off"
        description="No kind of bulk email can be turned off at the moment."
      />
    );
  }

  const handleToggle = (preference: EmailPreference, isReceiving: boolean): void => {
    setNotice(null);
    save.mutate(
      { email_type: preference.email_type, opted_out: !isReceiving },
      {
        onSuccess: () => setNotice('Saved.'),
        onError: (error) => setNotice(error.message || 'That change was not saved.'),
      },
    );
  };

  return (
    <div className="stack">
      <ul className="email-switches" aria-label={label}>
        {preferences.data.map((preference) => (
          <EmailPreferenceSwitch
            key={preference.email_type}
            preference={preference}
            isDisabled={save.isPending}
            onToggle={handleToggle}
          />
        ))}
      </ul>
      <p role="status" className="muted email-switches__notice">
        {notice}
      </p>
    </div>
  );
}

interface EmailPreferenceSwitchProps {
  preference: EmailPreference;
  isDisabled: boolean;
  onToggle: (preference: EmailPreference, isReceiving: boolean) => void;
}

/** One type's switch, named by the type and described by what it is for. */
function EmailPreferenceSwitch({
  preference,
  isDisabled,
  onToggle: handleToggle,
}: EmailPreferenceSwitchProps): JSX.Element {
  const id = useId();
  const descriptionId = `${id}-description`;
  return (
    <li className="email-switch">
      <input
        id={id}
        type="checkbox"
        role="switch"
        checked={!preference.opted_out}
        disabled={isDisabled}
        aria-describedby={descriptionId}
        onChange={(event) => handleToggle(preference, event.target.checked)}
      />
      <div>
        <label htmlFor={id} className="email-switch__name">
          {preference.name}
        </label>{' '}
        {/* The switch announces its own state; the word is for the eye. */}
        <span className="email-switch__state" aria-hidden="true">
          {preference.opted_out ? 'Off' : 'On'}
        </span>
        <p id={descriptionId} className="muted email-switch__description">
          {preference.description}
        </p>
      </div>
    </li>
  );
}
