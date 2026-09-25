/**
 * The wording of an aircraft record's history.
 *
 * A history entry names the columns a write moved, and the column names are the
 * table's, not the form's; this module turns them back into the words the form
 * uses, so a line reads "updated carrier, insurance expiry" rather than
 * "updated insurance_carrier, insurance_expiration".
 */
import type { AircraftActor, AircraftChange } from '@/portal/api/types';
import { formatDate, formatDateTime } from '@/portal/components/DateText';

/**
 * The register columns a history entry can name, in the words the record's own
 * form puts on them, lower-cased for the middle of a sentence.  Money columns
 * lose the `_cents` the API carries, because the form asks for dollars.
 */
const FIELD_LABELS: Record<string, string> = {
  n_number: 'N-number',
  make: 'make',
  model: 'model',
  year: 'year',
  seats: 'seats',
  owner_type: 'owner type',
  owner_name: 'owner name',
  owner_contact: 'owner contact',
  insurance_carrier: 'carrier',
  insurance_policy_number: 'policy number',
  insurance_liability_per_occurrence_cents: 'liability per occurrence',
  insurance_liability_per_person_cents: 'liability per person',
  insurance_hull_cents: 'hull',
  insurance_expiration: 'insurance expiry',
  notes: 'notes',
  is_active: 'in service',
};

/**
 * The words for one register column.
 *
 * A column the labels do not cover reads as its own name with the underscores
 * taken out, so a field added to the register is legible here before anybody
 * writes a label for it.
 */
export function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field.replace(/_/g, ' ');
}

/** The name of the account behind a write, or `the seed` when there is none. */
export function actorName(actor: AircraftActor | null): string {
  return actor === null ? 'the seed' : actor.name;
}

/**
 * One history entry as a single line.
 *
 * Reads `2026/09/01 12:34 · Dana Fiske · created` for a creation, where the
 * whole record is the change, and `… · updated carrier, insurance expiry` for a
 * write, naming every column that moved.  A write that names no column at all
 * reads `updated` on its own.
 */
export function changeLine(change: AircraftChange): string {
  const labels = change.fields.map(fieldLabel).join(', ');
  const updated = labels.length === 0 ? 'updated' : `updated ${labels}`;
  const what = change.kind === 'created' ? 'created' : updated;
  return `${formatDateTime(change.changed_at)} · ${actorName(change.changed_by)} · ${what}`;
}

/**
 * The eyebrow over a record's details: `Last updated 2026/09/01 by Dana Fiske`.
 *
 * The name is left off when no account is recorded against the last write,
 * rather than blaming the seed for a record nobody has touched since.
 */
export function lastUpdatedLine(updatedAt: string, updatedBy: AircraftActor | null): string {
  const date = formatDate(updatedAt);
  return updatedBy === null ? `Last updated ${date}` : `Last updated ${date} by ${updatedBy.name}`;
}
