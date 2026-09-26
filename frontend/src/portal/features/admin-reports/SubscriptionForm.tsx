/**
 * The form behind **New subscription** and each row's **Edit**: which report,
 * filtered how, with which columns, in which formats, how often, and to whom.
 *
 * Editing changes everything but the report and the recipient, which the
 * server keeps fixed, so the form draws those two as plain text and sends the
 * rest as a `PATCH`.
 *
 * The report's filters are drawn by the one `FilterBar` from the report's own
 * definition, the fields only a subscription offers (the period a dated report
 * covers) included, so a subscription filters exactly as the report's list
 * page does.  The server decides whether the recipient may have the report: an
 * account that may not read it is refused under the address, and an address no
 * account holds must be confirmed with a checkbox that appears once the server
 * has asked for it.
 */
import { useId, useMemo, useState } from 'react';
import type { ChangeEvent, FormEvent, JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import { useDarts, usePlans } from '@/portal/api/queries';
import type { ReportCadence, ReportFormats, ReportSubscription } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { ColumnChooser, defaultColumnKeys } from '@/portal/components/ColumnChooser';
import { Field } from '@/portal/components/Field';
import { FilterBar } from '@/portal/components/FilterBar';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import { useEmailPurposes } from '@/portal/features/system/api';
import {
  useCreateSubscription,
  useReportColumns,
  useReports,
  useUpdateSubscription,
} from '@/portal/reports/api';
import { REPORTS } from '@/portal/reports/definitions';
import type { FilterField, FilterValues, ReportSlug } from '@/portal/reports/types';
import { CADENCE_LABELS, FORMAT_LABELS, WEEKDAY_OPTIONS, recipientLabel } from './labels';

/**
 * The fields an edit shows errors for itself, so the form-level alert leaves
 * them be.  The report and the recipient are fixed text while editing, so a
 * refusal of either reaches the alert.
 */
const EDIT_HANDLED_FIELDS = ['filters', 'columns', 'formats', 'cadence', 'weekday'];

/** The fields a new subscription shows errors for itself. */
const CREATE_HANDLED_FIELDS = ['report', 'recipient_email', 'confirmed', ...EDIT_HANDLED_FIELDS];

const FORMATS: readonly ReportFormats[] = ['csv', 'pdf', 'both'];
const CADENCES: readonly ReportCadence[] = ['weekly', 'monthly', 'quarterly', 'yearly'];

/** Whether `slug` names a report the portal has a definition for. */
function isReportSlug(slug: string): slug is ReportSlug {
  return slug in REPORTS;
}

/** Whether `value` is one of the cadences the form offers. */
function isCadence(value: string): value is ReportCadence {
  return CADENCES.some((cadence) => cadence === value);
}

/**
 * The server's refusals of the report's filters, each led by its field's label:
 * `Period: Choose a valid period.`
 *
 * @param error what the save failed with.
 * @param fields the report's filter fields, which name each key.
 * @returns one line per refused filter, or none.
 */
export function filterErrors(error: unknown, fields: readonly FilterField[]): string[] {
  if (!(error instanceof ApiError)) return [];
  const body = error.body;
  if (typeof body !== 'object' || body === null || !('filters' in body)) return [];
  const refused: unknown = body.filters;
  if (typeof refused !== 'object' || refused === null) return [];
  return Object.entries(refused).map(([key, messages]) => {
    const label = fields.find((field) => field.key === key)?.label ?? key;
    const message = Array.isArray(messages) ? messages.join(' ') : String(messages);
    return `${label}: ${message}`;
  });
}

/** The filter values that are set, which is all a subscription stores. */
function setValues(values: FilterValues): Record<string, string> {
  return Object.fromEntries(Object.entries(values).filter(([, value]) => value !== ''));
}

interface SubscriptionFormProps {
  /** The subscription to edit; without one the form sets up a new subscription. */
  subscription?: ReportSubscription;
  /** Called once the subscription is saved, or when the form is canceled. */
  onDone: () => void;
}

/**
 * Sets up one report subscription, or edits `subscription` when it is given.
 *
 * Editing starts from the subscription's filters, columns, formats, schedule
 * and day; a stored column list that is empty (the report's defaults) fills the
 * chooser with the defaults and is sent back empty unless the chooser changes.
 * A report the portal has no definition for draws no filters or chooser, and
 * Save sends its stored filters and columns back with the schedule and formats.
 */
export function SubscriptionForm({
  subscription,
  onDone: handleDone,
}: SubscriptionFormProps): JSX.Element {
  const isEditing = subscription !== undefined;
  const [slug, setSlug] = useState<ReportSlug | ''>(() =>
    subscription !== undefined && isReportSlug(subscription.report) ? subscription.report : '',
  );
  const [filters, setFilters] = useState<FilterValues>(() => ({ ...subscription?.filters }));
  const [columns, setColumns] = useState<string[] | null>(() =>
    subscription === undefined || subscription.columns.length === 0 ? null : subscription.columns,
  );
  const [formats, setFormats] = useState<ReportFormats>(subscription?.formats ?? 'pdf');
  const [cadence, setCadence] = useState<ReportCadence>(subscription?.cadence ?? 'monthly');
  const [weekday, setWeekday] = useState(subscription?.weekday ?? 0);
  const [email, setEmail] = useState('');
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [needsConfirmation, setNeedsConfirmation] = useState(false);

  const reports = useReports();
  const create = useCreateSubscription();
  const update = useUpdateSubscription();
  const save = isEditing ? update : create;
  const title = isEditing ? 'Edit subscription' : 'New subscription';
  const darts = useDarts();
  const plans = usePlans();
  // Only the emails report's Purpose filter reads these, and only a
  // system administrator can choose that report, so nobody else's form
  // ever sends a request the server would refuse.
  const purposes = useEmailPurposes({ enabled: slug === 'emails' });
  const runtimeOptions = useMemo(
    () => ({
      dart: (darts.data ?? []).map((dart) => ({ value: String(dart.id), label: dart.name })),
      plan: (plans.data ?? []).map((plan) => ({ value: plan.slug, label: plan.name })),
      purpose: purposes.data ?? [],
    }),
    [darts.data, plans.data, purposes.data],
  );

  const definition = slug === '' ? null : REPORTS[slug];
  const refusedFilters = filterErrors(save.error, definition?.filters ?? []);

  const handleReportChange = (event: ChangeEvent<HTMLSelectElement>): void => {
    const next = event.target.value;
    setSlug(isReportSlug(next) ? next : '');
    setFilters({});
    setColumns(null);
    create.reset();
  };

  const handleFiltersChange = (values: FilterValues): void => {
    setFilters(values);
  };

  const handleColumnsChange = (chosen: string[]): void => {
    setColumns(chosen);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (subscription !== undefined) {
      update.mutate(
        {
          id: subscription.id,
          patch: {
            filters: setValues(filters),
            columns: columns ?? [],
            formats,
            cadence,
            weekday,
          },
        },
        { onSuccess: handleDone },
      );
      return;
    }
    if (slug === '') return;
    create.mutate(
      {
        report: slug,
        recipient_email: email,
        filters: setValues(filters),
        columns: columns ?? [],
        formats,
        cadence,
        weekday,
        confirmed: isConfirmed,
      },
      {
        onSuccess: handleDone,
        onError: (error) => {
          if (fieldError(error, 'confirmed') !== null) setNeedsConfirmation(true);
        },
      },
    );
  };

  const recipientError = fieldError(create.error, 'recipient_email');
  const confirmError = fieldError(create.error, 'confirmed');

  return (
    <section className="subscription-form stack">
      <h3>{title}</h3>

      {subscription !== undefined ? (
        <FixedValue label="Report" value={subscription.report_title} />
      ) : (
        <Field label="Report" error={fieldError(create.error, 'report')}>
          {(props) => (
            <select {...props} value={slug} onChange={handleReportChange}>
              <option value="">Choose a report…</option>
              {(reports.data ?? []).map((report) => (
                <option key={report.slug} value={report.slug}>
                  {report.title}
                </option>
              ))}
            </select>
          )}
        </Field>
      )}

      {definition === null ? null : (
        <>
          <FilterBar
            fields={definition.filters}
            values={filters}
            onChange={handleFiltersChange}
            options={runtimeOptions}
            label="Report filters"
          />
          {refusedFilters.length > 0 ? (
            <p className="field__error" role="alert">
              {refusedFilters.join(' ')}
            </p>
          ) : null}
          {definition.choosable ? (
            <SubscriptionColumns
              slug={definition.slug}
              chosen={columns}
              onChange={handleColumnsChange}
            />
          ) : null}
          {fieldError(save.error, 'columns') === null ? null : (
            <p className="field__error" role="alert">
              {fieldError(save.error, 'columns')}
            </p>
          )}
        </>
      )}

      <form aria-label={title} className="stack" onSubmit={handleSubmit}>
        <fieldset>
          <legend>Formats</legend>
          <div className="cluster">
            {FORMATS.map((format) => (
              <label key={format} className="cluster">
                <input
                  type="radio"
                  name="formats"
                  value={format}
                  checked={formats === format}
                  onChange={() => setFormats(format)}
                />
                {FORMAT_LABELS[format]}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="cluster">
          <Field label="Schedule" error={fieldError(save.error, 'cadence')}>
            {(props) => (
              <select
                {...props}
                value={cadence}
                onChange={(event) => {
                  const next = event.target.value;
                  if (isCadence(next)) setCadence(next);
                }}
              >
                {CADENCES.map((option) => (
                  <option key={option} value={option}>
                    {CADENCE_LABELS[option]}
                  </option>
                ))}
              </select>
            )}
          </Field>
          {cadence === 'weekly' ? (
            <Field label="Day" error={fieldError(save.error, 'weekday')}>
              {(props) => (
                <select
                  {...props}
                  value={String(weekday)}
                  onChange={(event) => setWeekday(Number(event.target.value))}
                >
                  {WEEKDAY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          ) : null}
        </div>

        {subscription !== undefined ? (
          <FixedValue label="Recipient" value={recipientLabel(subscription)} />
        ) : (
          <Field label="Recipient email" error={recipientError} required>
            {(props) => (
              <input
                {...props}
                type="email"
                autoComplete="off"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            )}
          </Field>
        )}

        {needsConfirmation ? (
          <div className="field">
            <label className="cluster">
              <input
                type="checkbox"
                checked={isConfirmed}
                onChange={(event) => setIsConfirmed(event.target.checked)}
              />
              This address is outside CalDART and may receive this report
            </label>
            {confirmError === null ? null : (
              <span className="field__error" role="alert">
                {confirmError}
              </span>
            )}
          </div>
        ) : null}

        {refusedFilters.length > 0 ? null : (
          <FormAlert
            error={save.error}
            handled={isEditing ? EDIT_HANDLED_FIELDS : CREATE_HANDLED_FIELDS}
          />
        )}

        <div className="cluster">
          <Button type="submit" disabled={(!isEditing && slug === '') || save.isPending}>
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

interface FixedValueProps {
  label: string;
  value: string;
}

/** A labeled value the form shows but does not let anyone change. */
function FixedValue({ label, value }: FixedValueProps): JSX.Element {
  const id = useId();
  return (
    <div className="field" role="group" aria-labelledby={id}>
      <span className="field__label" id={id}>
        {label}
      </span>
      <span>{value}</span>
    </div>
  );
}

interface SubscriptionColumnsProps {
  slug: ReportSlug;
  /** The chosen keys, or null while the report's defaults stand. */
  chosen: string[] | null;
  onChange: (chosen: string[]) => void;
}

/** The column chooser over one report's registry, starting from its defaults. */
function SubscriptionColumns({
  slug,
  chosen,
  onChange: handleChange,
}: SubscriptionColumnsProps): JSX.Element {
  const registry = useReportColumns(slug);
  const columns = registry.data ?? [];
  return (
    <ColumnChooser
      report={slug}
      columns={columns}
      chosen={chosen ?? defaultColumnKeys(columns)}
      onChange={handleChange}
      legend="Columns to send"
    />
  );
}
