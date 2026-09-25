/**
 * The form behind **New subscription**: which report, filtered how, with which
 * columns, in which formats, how often, and to whom.
 *
 * The report's filters are drawn by the one `FilterBar` from the report's own
 * definition, the fields only a subscription offers (the period a dated report
 * covers) included, so a subscription filters exactly as the report's list
 * page does.  The server decides whether the recipient may have the report: an
 * account that may not read it is refused under the address, and an address no
 * account holds must be confirmed with a checkbox that appears once the server
 * has asked for it.
 */
import { useMemo, useState } from 'react';
import type { ChangeEvent, FormEvent, JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import { useDarts, usePlans } from '@/portal/api/queries';
import type { ReportCadence, ReportFormats } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { ColumnChooser, defaultColumnKeys } from '@/portal/components/ColumnChooser';
import { Field } from '@/portal/components/Field';
import { FilterBar } from '@/portal/components/FilterBar';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import { useCreateSubscription, useReportColumns, useReports } from '@/portal/reports/api';
import { REPORTS } from '@/portal/reports/definitions';
import type { FilterField, FilterValues, ReportSlug } from '@/portal/reports/types';
import { CADENCE_LABELS, FORMAT_LABELS, WEEKDAY_OPTIONS } from './labels';

/** The fields the form shows errors for itself, so the form-level alert leaves them be. */
const HANDLED_FIELDS = [
  'report',
  'recipient_email',
  'confirmed',
  'filters',
  'columns',
  'formats',
  'cadence',
  'weekday',
];

const FORMATS: readonly ReportFormats[] = ['csv', 'pdf', 'both'];
const CADENCES: readonly ReportCadence[] = ['weekly', 'monthly', 'quarterly', 'yearly'];

/** Whether `slug` names a report the portal has a definition for. */
function isReportSlug(slug: string): slug is ReportSlug {
  return slug in REPORTS;
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
  /** Called once the subscription is saved, or when the form is canceled. */
  onDone: () => void;
}

/** Sets up one report subscription. */
export function SubscriptionForm({ onDone: handleDone }: SubscriptionFormProps): JSX.Element {
  const [slug, setSlug] = useState<ReportSlug | ''>('');
  const [filters, setFilters] = useState<FilterValues>({});
  const [columns, setColumns] = useState<string[] | null>(null);
  const [formats, setFormats] = useState<ReportFormats>('pdf');
  const [cadence, setCadence] = useState<ReportCadence>('monthly');
  const [weekday, setWeekday] = useState(0);
  const [email, setEmail] = useState('');
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [needsConfirmation, setNeedsConfirmation] = useState(false);

  const reports = useReports();
  const create = useCreateSubscription();
  const darts = useDarts();
  const plans = usePlans();
  const runtimeOptions = useMemo(
    () => ({
      dart: (darts.data ?? []).map((dart) => ({ value: String(dart.id), label: dart.name })),
      plan: (plans.data ?? []).map((plan) => ({ value: plan.slug, label: plan.name })),
    }),
    [darts.data, plans.data],
  );

  const definition = slug === '' ? null : REPORTS[slug];
  const refusedFilters = filterErrors(create.error, definition?.filters ?? []);

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
      <h3>New subscription</h3>

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
          {fieldError(create.error, 'columns') === null ? null : (
            <p className="field__error" role="alert">
              {fieldError(create.error, 'columns')}
            </p>
          )}
        </>
      )}

      <form aria-label="New subscription" className="stack" onSubmit={handleSubmit}>
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
          <Field label="Schedule" error={fieldError(create.error, 'cadence')}>
            {(props) => (
              <select
                {...props}
                value={cadence}
                onChange={(event) => setCadence(event.target.value as ReportCadence)}
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
            <Field label="Day" error={fieldError(create.error, 'weekday')}>
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
          <FormAlert error={create.error} handled={HANDLED_FIELDS} />
        )}

        <div className="cluster">
          <Button type="submit" disabled={slug === '' || create.isPending}>
            {create.isPending ? 'Saving…' : 'Save'}
          </Button>
          <Button variant="quiet" onClick={handleDone}>
            Cancel
          </Button>
        </div>
      </form>
    </section>
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
      columns={columns}
      chosen={chosen ?? defaultColumnKeys(columns)}
      onChange={handleChange}
      legend="Columns to send"
    />
  );
}
