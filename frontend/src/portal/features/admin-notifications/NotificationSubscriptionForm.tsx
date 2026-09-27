/**
 * The form behind **New subscription** and each row's **Edit** on
 * `/admin/notifications`: an address, and the events it hears about.
 *
 * Editing changes the events alone; the server keeps the recipient fixed, so
 * the form draws it as plain text and sends the events as a `PATCH`.  The
 * server decides whether the recipient may hear about each event: an account
 * that may not is refused under the events, and an address no account holds
 * must be confirmed with a checkbox that appears once the server has asked for
 * it.
 */
import { useState } from 'react';
import type { FormEvent, JSX } from 'react';

import type { NotificationSubscription } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { FixedValue } from '@/portal/components/FixedValue';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import {
  useCreateNotificationSubscription,
  useNotificationEvents,
  useUpdateNotificationSubscription,
} from './api';
import { EventPicker } from './EventPicker';
import { recipientLabel } from './labels';

/** The fields a new subscription shows errors for itself. */
const CREATE_HANDLED_FIELDS = ['recipient_email', 'events', 'confirmed'];

/** The fields an edit shows errors for itself. */
const EDIT_HANDLED_FIELDS = ['events'];

interface NotificationSubscriptionFormProps {
  /** The subscription to edit; without one the form subscribes a new address. */
  subscription?: NotificationSubscription;
  /** Called once the subscription is saved, or when the form is canceled. */
  onDone: () => void;
}

/**
 * Subscribes one address to the ticked events, or changes the events of
 * `subscription` when it is given, starting from the events it lists.  The
 * events are sent in catalog order, whatever order they were ticked in.
 */
export function NotificationSubscriptionForm({
  subscription,
  onDone: handleDone,
}: NotificationSubscriptionFormProps): JSX.Element {
  const isEditing = subscription !== undefined;
  const [email, setEmail] = useState('');
  const [chosen, setChosen] = useState<Set<string>>(() => new Set(subscription?.events));
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [needsConfirmation, setNeedsConfirmation] = useState(false);

  const catalog = useNotificationEvents();
  const create = useCreateNotificationSubscription();
  const update = useUpdateNotificationSubscription();
  const save = isEditing ? update : create;
  const title = isEditing ? 'Edit subscription' : 'New subscription';
  const events = catalog.data ?? [];

  const handleEventsChange = (next: Set<string>): void => {
    setChosen(next);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const slugs = events.map((entry) => entry.slug).filter((slug) => chosen.has(slug));
    if (subscription !== undefined) {
      update.mutate({ id: subscription.id, patch: { events: slugs } }, { onSuccess: handleDone });
      return;
    }
    create.mutate(
      { recipient_email: email, events: slugs, confirmed: isConfirmed },
      {
        onSuccess: handleDone,
        onError: (error) => {
          if (fieldError(error, 'confirmed') !== null) setNeedsConfirmation(true);
        },
      },
    );
  };

  const eventsError = fieldError(save.error, 'events');
  const confirmError = fieldError(create.error, 'confirmed');

  return (
    <section className="subscription-form stack">
      <h3>{title}</h3>
      <form aria-label={title} className="stack" onSubmit={handleSubmit}>
        {subscription !== undefined ? (
          <FixedValue label="Recipient" value={recipientLabel(subscription)} />
        ) : (
          <Field
            label="Recipient email"
            error={fieldError(create.error, 'recipient_email')}
            required
          >
            {(props) => (
              <input
                {...props}
                type="email"
                autoComplete="off"
                value={email}
                onChange={(change) => setEmail(change.target.value)}
              />
            )}
          </Field>
        )}

        <EventPicker events={events} chosen={chosen} onChange={handleEventsChange} />
        {catalog.isError ? (
          <p className="field__error" role="alert">
            The events could not be loaded.
          </p>
        ) : null}
        {eventsError === null ? null : (
          <p className="field__error" role="alert">
            {eventsError}
          </p>
        )}

        {needsConfirmation ? (
          <div className="field">
            <label className="cluster">
              <input
                type="checkbox"
                checked={isConfirmed}
                onChange={(change) => setIsConfirmed(change.target.checked)}
              />
              This address is outside CalDART and may receive these notifications
            </label>
            {confirmError === null ? null : (
              <span className="field__error" role="alert">
                {confirmError}
              </span>
            )}
          </div>
        ) : null}

        <FormAlert
          error={save.error}
          handled={isEditing ? EDIT_HANDLED_FIELDS : CREATE_HANDLED_FIELDS}
        />

        <div className="cluster">
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : 'Save'}
          </Button>
          <Button variant="quiet" onClick={handleDone}>
            Cancel
          </Button>
        </div>
      </form>
    </section>
  );
}
