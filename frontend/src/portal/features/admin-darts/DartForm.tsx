/**
 * The DART form, used to add one and to edit one.
 *
 * It asks for the three things a DART is — its name, its airports and its
 * website — then the people who run it, then whether it is active.  On
 * an existing DART it also carries the delete control, because deleting a team
 * is a thing you do while looking at it rather than from a row in a list.
 */
import { useEffect, useId, useRef, useState } from 'react';
import type { JSX } from 'react';

import type { AdminDart, AdminDartContact, AdminDartPatch } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { Field } from '@/portal/components/Field';
import { IconButton } from '@/portal/components/IconButton';
import { MaskedInput } from '@/portal/components/MaskedInput';
import {
  RefusedSubmitNote,
  useFreshErrors,
  useRefusedSubmit,
} from '@/portal/components/RefusedSubmit';
import {
  maskAirportIdentifier,
  maskAirportIdentifiers,
  maskEmail,
  maskPhone,
} from '@/portal/masks';
import './darts.css';

export interface DartFormValues {
  name: string;
  airport_identifiers: string;
  website_url: string;
  is_active: boolean;
  contacts: AdminDartContact[];
}

/**
 * The serializer's message for one contact's field, if it sent one.
 *
 * A nested list comes back keyed by position -- ``contacts["0"].phone`` -- and
 * the form flattens each of those into `contacts.0.phone`.
 */
export function contactError(
  errors: Record<string, string>,
  index: number,
  field: keyof AdminDartContact,
): string | undefined {
  return errors[`contacts.${index}.${field}`];
}

/** A blank row of the contacts table. */
function emptyContact(): AdminDartContact {
  return { name: '', title: '', phone: '', email: '', receives_roster: false };
}

/** Whether a row still waits for the person's name. */
function isNameless(contact: AdminDartContact | undefined): boolean {
  return contact !== undefined && contact.name.trim() === '';
}

/** Why **Add a person** is grayed out while the last row has no name. */
const NAME_FIRST = 'Give the person above a name first';

/** What a row is called aloud: the person's name, or its place in the list. */
function personLabel(contact: AdminDartContact, index: number): string {
  return contact.name.trim() || `Person ${index + 1}`;
}

/** The same name for use mid-sentence, where a nameless row reads "person 2". */
function personInSentence(contact: AdminDartContact, index: number): string {
  return contact.name.trim() || `person ${index + 1}`;
}

export interface DartFormProps {
  initial: DartFormValues;
  submitLabel: string;
  pending?: boolean;
  /** Field errors from the serializer, shown beside the input they belong to. */
  errors?: Record<string, string>;
  /**
   * What `errors` came from, normally the save's `error`: each new one moves the
   * focus to the first field it highlights, and an error for a field goes once the
   * field is edited. Left out, every server error stays until the next save.
   */
  serverError?: unknown;
  onSubmit: (payload: AdminDartPatch) => void;
  onCancel: () => void;
  /**
   * Delete this DART; absent on the add form, which has nothing to delete.
   *
   * A promise lets the form know the attempt is over, whether it worked or not.
   */
  onDelete?: () => void | Promise<unknown>;
  /** What the delete will leave behind, shown in the confirmation. */
  deleteWarning?: string | null;
  /** Whether the delete request is in flight. */
  deletePending?: boolean;
}

/** One identifier as it is stored: three letters or digits. */
const AIRPORT_RE = /^[A-Z0-9]{3}$/;

/** The most airports one DART may list, matching the server's own cap. */
const MAX_AIRPORTS = 12;

/**
 * The identifiers in `typed`, as they are stored, with the blanks dropped.
 *
 * A comma or a space separates one from the next, because a pasted list often
 * carries no commas and no identifier holds a space.
 */
export function splitAirports(typed: string): string[] {
  return typed
    .split(/[, ]+/)
    .map((part) => maskAirportIdentifier(part))
    .filter((part) => part.length > 0);
}

/**
 * What is wrong with an airport list, or `null` when nothing is.
 *
 * Mirrors the serializer so the administrator hears it as they leave the box:
 * every DART flies from somewhere, each identifier is three letters or digits
 * once its ICAO `K` is trimmed, no field is listed twice, and the list stays a
 * list.
 */
export function airportProblem(typed: string): string | null {
  const airports = splitAirports(typed);
  if (airports.length === 0) return 'Give the DART at least one airport.';
  if (airports.length > MAX_AIRPORTS) return `A DART may list at most ${MAX_AIRPORTS} airports.`;
  if (new Set(airports).size !== airports.length) return 'That list names the same airport twice.';
  if (airports.some((airport) => !AIRPORT_RE.test(airport))) {
    return 'Use three-character identifiers, separated by commas, like CCR, C83.';
  }
  return null;
}

/** A blank form, with one empty row ready for the team's leader. */
export function emptyDartValues(): DartFormValues {
  return {
    name: '',
    airport_identifiers: '',
    website_url: '',
    is_active: true,
    contacts: [emptyContact()],
  };
}

/** An existing DART as editable form values. */
export function dartToValues(dart: AdminDart): DartFormValues {
  return {
    name: dart.name,
    airport_identifiers: dart.airport_identifiers,
    website_url: dart.website_url,
    is_active: dart.is_active,
    contacts: dart.contacts.length > 0 ? dart.contacts.map((one) => ({ ...one })) : [],
  };
}

/** Form values as the body `POST /admin/darts` and `PATCH` expect. */
export function dartPayload(values: DartFormValues): AdminDartPatch {
  return {
    name: values.name.trim(),
    airport_identifiers: splitAirports(values.airport_identifiers).join(', '),
    website_url: values.website_url.trim(),
    is_active: values.is_active,
    // A row nobody typed into is not a person: an empty form should not save
    // a nameless contact, and clearing every row really does clear the list.
    contacts: values.contacts
      .filter((contact) => contact.name.trim() || contact.title.trim())
      .map((contact) => ({
        name: contact.name.trim(),
        title: contact.title.trim(),
        phone: contact.phone,
        email: contact.email,
        receives_roster: contact.receives_roster,
      })),
  };
}

/** `items` with the entries at `from` and `to` exchanged. */
function swap<Item>(items: Item[], from: number, to: number): Item[] {
  const next = [...items];
  const moved = next[from];
  const displaced = next[to];
  if (moved === undefined || displaced === undefined) return items;
  next[from] = displaced;
  next[to] = moved;
  return next;
}

/** The add-and-edit form for one DART. */
export function DartForm({
  initial,
  submitLabel,
  pending = false,
  errors = {},
  serverError,
  onSubmit,
  onCancel: handleCancel,
  onDelete: handleDelete,
  deleteWarning = null,
  deletePending = false,
}: DartFormProps): JSX.Element {
  const [values, setValues] = useState<DartFormValues>(initial);
  const [nameError, setNameError] = useState<string | null>(null);
  const [airportError, setAirportError] = useState<string | null>(null);
  const activeHintId = useId();
  const formRef = useRef<HTMLFormElement>(null);
  const refusal = useRefusedSubmit(formRef, serverError);
  // The server's errors for a field go once the field is edited; the rest stay until
  // the next save.
  const freshErrors = useFreshErrors(serverError, values, errors);
  // A row's identity, so React moves its inputs and buttons with it rather than
  // rewriting them in place when the order changes.  A saved person is known by
  // the server's id; one the administrator just added gets a counter.
  const nextRowKey = useRef(0);
  const [rowKeys, setRowKeys] = useState<string[]>(() => initial.contacts.map(contactKey));
  const rowControls = useRef(new Map<string, HTMLSpanElement | null>());
  const [movedKey, setMovedKey] = useState<string | null>(null);
  const [moveAnnouncement, setMoveAnnouncement] = useState('');

  function contactKey(contact: AdminDartContact): string {
    if (contact.id !== undefined) return `saved-${contact.id}`;
    nextRowKey.current += 1;
    return `added-${nextRowKey.current}`;
  }

  // A row that moved keeps the focus, but the control the administrator pressed
  // is disabled once the person reaches an end, so focus lands on the other one.
  useEffect(() => {
    if (movedKey === null) return;
    setMovedKey(null);
    const controls = rowControls.current.get(movedKey);
    if (controls === null || controls === undefined) return;
    if (controls.contains(document.activeElement)) return;
    controls.querySelector<HTMLButtonElement>('button:not([disabled])')?.focus();
  }, [movedKey]);

  const set = <Key extends keyof DartFormValues>(key: Key, next: DartFormValues[Key]): void => {
    setValues((current) => ({ ...current, [key]: next }));
  };

  const setContact = (index: number, patch: Partial<AdminDartContact>): void => {
    setValues((current) => ({
      ...current,
      contacts: current.contacts.map((contact, position) =>
        position === index ? { ...contact, ...patch } : contact,
      ),
    }));
  };

  const handleAddContact = (): void => {
    const blank = emptyContact();
    setRowKeys((current) => [...current, contactKey(blank)]);
    setValues((current) => ({ ...current, contacts: [...current.contacts, blank] }));
  };

  const handleRemoveContact = (index: number): void => {
    setRowKeys((current) => current.filter((_, position) => position !== index));
    setValues((current) => ({
      ...current,
      contacts: current.contacts.filter((_, position) => position !== index),
    }));
  };

  /** Swap the person at `index` with the one at `index + step`. */
  const moveContact = (index: number, step: -1 | 1): void => {
    const target = index + step;
    const moved = values.contacts[index];
    if (moved === undefined || values.contacts[target] === undefined) return;
    setValues((current) => ({ ...current, contacts: swap(current.contacts, index, target) }));
    setRowKeys((current) => swap(current, index, target));
    setMovedKey(rowKeys[index] ?? null);
    setMoveAnnouncement(
      `${personLabel(moved, index)} is now number ${target + 1} of ${values.contacts.length}.`,
    );
  };

  // A nameless row stays where it is: it is not yet a person to put in order,
  // so neither its own arrows nor a neighbor's arrow that would swap with it work.
  const canSwap = (index: number, target: number): boolean =>
    values.contacts[target] !== undefined &&
    !isNameless(values.contacts[index]) &&
    !isNameless(values.contacts[target]);

  const isLastNameless = isNameless(values.contacts.at(-1));

  const airportsError = airportError ?? freshErrors.airport_identifiers;

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    const problem = airportProblem(values.airport_identifiers);
    setNameError(values.name.trim() ? null : 'Give the DART a name.');
    setAirportError(problem);
    if (!values.name.trim() || problem) {
      refusal.refuse();
      return;
    }
    onSubmit(dartPayload(values));
  };

  return (
    <form ref={formRef} onSubmit={handleSubmit} noValidate>
      <div className="form-grid">
        <Field
          label="Name"
          required
          error={nameError ?? freshErrors.name}
          hint="What members will see in the list, such as “Palo Alto”"
        >
          {(props) => (
            <input
              {...props}
              name="name"
              value={values.name}
              onChange={(event) => {
                set('name', event.target.value);
                setNameError(null);
              }}
            />
          )}
        </Field>
        <Field
          label="Airports"
          required
          error={airportsError}
          // Leaving the box checks it, so its error line comes and goes as the focus moves
          // on, to the submit button among others.  An empty line held in its place while
          // there is no error keeps everything below, the button included, from moving.
          status={airportsError ? undefined : <span aria-hidden="true">{'\u00a0'}</span>}
          hint="The fields the team flies from, separated by commas, such as CCR, C83. Leave off the leading K: CRQ, not KCRQ."
        >
          {(props) => (
            <MaskedInput
              {...props}
              className="num"
              name="airport_identifiers"
              mask={maskAirportIdentifiers}
              value={values.airport_identifiers}
              onValueChange={(next) => {
                set('airport_identifiers', next);
                setAirportError(null);
              }}
              onBlur={() => setAirportError(airportProblem(values.airport_identifiers))}
            />
          )}
        </Field>
        <Field
          label="Website"
          error={freshErrors.website_url}
          hint="The team's own site, if it has one, such as https://paloaltodart.org/"
        >
          {(props) => (
            <input
              {...props}
              type="url"
              name="website_url"
              value={values.website_url}
              onChange={(event) => set('website_url', event.target.value)}
            />
          )}
        </Field>
      </div>

      <fieldset className="dart-contacts">
        <legend>DART management</legend>
        <p className="muted small">
          Shown on the team&rsquo;s page in the order you put them in. A title such as DART leader
          says what each person does. A phone number, such as 415-555-0100, and an email address are
          both optional.
        </p>
        {values.contacts.map((contact, index) => (
          <div
            className="dart-contacts__row"
            key={rowKeys[index] ?? `row-${index}`}
            role="group"
            aria-label={personLabel(contact, index)}
          >
            <span
              className="cluster dart-contacts__controls"
              ref={(node) => {
                rowControls.current.set(rowKeys[index] ?? `row-${index}`, node);
              }}
            >
              <IconButton
                icon="arrow-up"
                label={`Move ${personInSentence(contact, index)} up`}
                disabled={!canSwap(index, index - 1)}
                onClick={() => moveContact(index, -1)}
              />
              <IconButton
                icon="arrow-down"
                label={`Move ${personInSentence(contact, index)} down`}
                disabled={!canSwap(index, index + 1)}
                onClick={() => moveContact(index, 1)}
              />
            </span>
            <Field
              label="Name"
              labelSuffix={` of person ${index + 1}`}
              error={contactError(errors, index, 'name')}
            >
              {(props) => (
                <input
                  {...props}
                  value={contact.name}
                  onChange={(event) => setContact(index, { name: event.target.value })}
                />
              )}
            </Field>
            <Field
              label="Title"
              labelSuffix={` of person ${index + 1}`}
              error={contactError(errors, index, 'title')}
            >
              {(props) => (
                <input
                  {...props}
                  value={contact.title}
                  onChange={(event) => setContact(index, { title: event.target.value })}
                />
              )}
            </Field>
            <Field
              label="Phone"
              labelSuffix={` of person ${index + 1}`}
              error={contactError(errors, index, 'phone')}
            >
              {(props) => (
                <MaskedInput
                  {...props}
                  type="tel"
                  inputMode="tel"
                  className="dart-contacts__phone"
                  mask={maskPhone}
                  value={contact.phone}
                  onValueChange={(next) => setContact(index, { phone: next })}
                />
              )}
            </Field>
            <Field
              label="Email"
              labelSuffix={` of person ${index + 1}`}
              error={contactError(errors, index, 'email')}
            >
              {(props) => (
                <MaskedInput
                  {...props}
                  type="email"
                  mask={maskEmail}
                  value={contact.email}
                  onValueChange={(next) => setContact(index, { email: next })}
                />
              )}
            </Field>
            <div className="field dart-contacts__roster">
              {/* The column's heading; the checkbox carries the whole sentence. */}
              <span className="field__label" aria-hidden="true">
                Roster
              </span>
              <input
                type="checkbox"
                aria-label={`${personLabel(contact, index)} receives the roster`}
                checked={contact.receives_roster}
                onChange={(event) => setContact(index, { receives_roster: event.target.checked })}
              />
            </div>
            <DeleteButton
              label={`Remove ${personInSentence(contact, index)}`}
              confirmLabel="Remove"
              onDelete={() => handleRemoveContact(index)}
            />
          </div>
        ))}
        <p aria-live="polite" className="visually-hidden">
          {moveAnnouncement}
        </p>
        <Button
          variant="secondary"
          small
          disabled={isLastNameless}
          title={isLastNameless ? NAME_FIRST : undefined}
          onClick={handleAddContact}
        >
          Add a person
        </Button>
      </fieldset>

      <div className="dart-form__active">
        <label className="checkbox">
          <input
            type="checkbox"
            name="is_active"
            checked={values.is_active}
            aria-describedby={activeHintId}
            onChange={(event) => set('is_active', event.target.checked)}
          />
          <span>Active</span>
        </label>
        <p className="field__hint" id={activeHintId}>
          Uncheck to make the DART inactive without losing its history.
        </p>
      </div>

      {freshErrors.detail ? (
        <p className="field__error" role="alert">
          {freshErrors.detail}
        </p>
      ) : null}

      <div className="cluster card__footer">
        <Button type="submit" disabled={pending}>
          {pending ? 'Saving…' : submitLabel}
        </Button>
        <Button variant="quiet" onClick={handleCancel}>
          Cancel
        </Button>
        <RefusedSubmitNote count={refusal.count} />
        {handleDelete ? (
          <span className="dart-form__danger">
            <DeleteButton
              label="Delete this DART"
              variant="danger"
              small={false}
              disabled={deletePending}
              warning={deleteWarning ?? undefined}
              onDelete={handleDelete}
            >
              Delete this DART
            </DeleteButton>
          </span>
        ) : null}
      </div>
    </form>
  );
}
