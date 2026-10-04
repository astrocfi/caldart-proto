/**
 * One switch per type of bulk email, on when the person receives it.
 *
 * Both the person's own Email preferences screen and the member record show these.
 * A switch saves the moment it moves; while that save is under way every switch
 * waits, and a toast says *Mission turned off.* once it lands, or what went wrong, and
 * the focus stays on the switch that moved.
 * The switches read the list the server answered the save with, so a refused change
 * puts its switch straight back. Enter moves a switch as Space does. On the member
 * record each type turned off also says who turned it off and when.
 */
import { useId, useRef } from 'react';
import type { JSX, KeyboardEvent } from 'react';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import type { EmailPreference, EmailPreferenceChange } from '@/portal/api/types';
import { formatDate } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { useToast } from '@/portal/components/Toast';
import { useFocusAfterSave } from '@/portal/components/focus';

import './email-preferences.css';

export interface EmailPreferenceSwitchesProps {
  /** The preferences to show. */
  preferences: UseQueryResult<EmailPreference[]>;
  /** The save one switch triggers. */
  save: UseMutationResult<EmailPreference[], Error, EmailPreferenceChange>;
  /** Names the group of switches for a screen reader. */
  label: string;
  /** Say under each type turned off who turned it off and when, as the member record does. */
  showsWhoTurnedOff?: boolean;
}

/**
 * Who turned `preference` off and when, in words: *Turned off by the member on
 * 10/03/2026 (unsubscribe link).*, or null for a type left on.
 */
export function turnedOffLine(preference: EmailPreference): string | null {
  if (!preference.opted_out || preference.opted_out_source === '') return null;
  const when = formatDate(preference.opted_out_at);
  if (preference.opted_out_source === 'admin') {
    return `Turned off by an account administrator on ${when}.`;
  }
  const where =
    preference.opted_out_source === 'unsubscribe' ? 'unsubscribe link' : 'Email preferences';
  return `Turned off by the member on ${when} (${where}).`;
}

/** The switches, and their loading and empty states. */
export function EmailPreferenceSwitches({
  preferences,
  save,
  label,
  showsWhoTurnedOff = false,
}: EmailPreferenceSwitchesProps): JSX.Element {
  const toast = useToast();
  // The switch that moved, which keeps the focus while every switch waits on its save.
  const movedRef = useRef<HTMLElement | null>(null);
  useFocusAfterSave(movedRef, save.isPending);

  if (preferences.isPending) return <p role="status">Loading…</p>;
  if (preferences.isError) {
    return (
      <p className="field__error" role="alert">
        The email preferences didn&apos;t load. Try again in a moment.
      </p>
    );
  }
  if (preferences.data.length === 0) {
    return (
      <EmptyState
        title="There is nothing to turn off"
        description="No type of bulk email can be turned off at the moment."
      />
    );
  }

  const handleToggle = (
    preference: EmailPreference,
    isReceiving: boolean,
    control: HTMLInputElement,
  ): void => {
    movedRef.current = control;
    save.mutate(
      { email_type: preference.email_type, opted_out: !isReceiving },
      {
        onSuccess: () =>
          toast.show(`${preference.name} turned ${isReceiving ? 'on' : 'off'}.`, 'success'),
        onError: (error) => toast.show(error.message || 'That change was not saved.', 'error'),
      },
    );
  };

  return (
    <ul className="email-switches" aria-label={label}>
      {preferences.data.map((preference) => (
        <EmailPreferenceSwitch
          key={preference.email_type}
          preference={preference}
          isDisabled={save.isPending}
          showsWhoTurnedOff={showsWhoTurnedOff}
          onToggle={handleToggle}
        />
      ))}
    </ul>
  );
}

interface EmailPreferenceSwitchProps {
  preference: EmailPreference;
  isDisabled: boolean;
  showsWhoTurnedOff: boolean;
  /** Saves the switch's new position; `control` is the switch, which keeps the focus. */
  onToggle: (preference: EmailPreference, isReceiving: boolean, control: HTMLInputElement) => void;
}

/** One type's switch, named by the type and described by what it is for. */
function EmailPreferenceSwitch({
  preference,
  isDisabled,
  showsWhoTurnedOff,
  onToggle: handleToggle,
}: EmailPreferenceSwitchProps): JSX.Element {
  const id = useId();
  const descriptionId = `${id}-description`;
  const whoLine = showsWhoTurnedOff ? turnedOffLine(preference) : null;

  // A checkbox moves on Space alone; a switch moves on Enter too, as a reader expects.
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>): void => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    if (!isDisabled) handleToggle(preference, preference.opted_out, event.currentTarget);
  };

  return (
    <li className="email-switch">
      <input
        id={id}
        type="checkbox"
        role="switch"
        checked={!preference.opted_out}
        disabled={isDisabled}
        aria-describedby={descriptionId}
        onChange={(event) => handleToggle(preference, event.target.checked, event.currentTarget)}
        onKeyDown={handleKeyDown}
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
        {whoLine === null ? null : <p className="muted email-switch__description">{whoLine}</p>}
      </div>
    </li>
  );
}
