/**
 * `/bulk-email/callouts/:id`: one mission callout and everybody's answer.
 *
 * At the top are the answers counted by kind, with **Remind non-responders** (which
 * sends the callout again to everybody who has not answered, after asking), **Close
 * now** (which stops the answers, after asking), and **Download answers**. Then one
 * line per person the callout reached, narrowed by answer or by a name, with their
 * answer and GO or NO-GO as the member check reads them now, then their note, when
 * they answered, their DART, home airport, and aircraft. A narrowed table's caption
 * says how many of everybody it shows. The page is read again every half minute while
 * the callout takes answers.
 */
import { useMemo, useState } from 'react';
import type { JSX } from 'react';
import { Link, useParams } from 'react-router-dom';

import { isNotFound } from '@/portal/api/client';
import type {
  CalloutAnswerKind,
  CalloutDetail,
  CalloutRecipient,
  LeaderGoNoGo,
} from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText, formatDate } from '@/portal/components/DateText';
import { clearedValues, FilterBar } from '@/portal/components/FilterBar';
import { Loading } from '@/portal/components/Loading';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { DROP_ORDER } from '@/portal/features/bulk-email/dropOrder';
import { scheduledWords } from '@/portal/features/bulk-email/schedule';
import { actionError } from '@/portal/features/bulk-email/SendStatus';
import { resultsCaption } from '@/portal/features/bulk-email/DeliveryReport';
import { people } from '@/portal/features/bulk-email/status';
import { GoMark, isReady } from '@/portal/features/leader/LeaderLookup';
import type { FilterField, FilterValues } from '@/portal/reports/types';
import { answersCsvUrl, useCallout, useCalloutAction } from './api';
import './callouts.css';
import { ANSWER_LABELS, answerLabel, answerTone } from './labels';

/** What the screen says once the reminders are queued. */
export const REMINDING_MESSAGE = 'The reminders will be sent within a minute.';

/** What the screen says once the callout is closed. */
export const CLOSED_MESSAGE =
  "The callout is closed. Its buttons don't record anything from now on.";

/** The answers a reader can narrow the table to, then no answer. */
const ANSWER_CHOICES: readonly CalloutAnswerKind[] = ['available', 'limited', 'unavailable'];

/** The menu's value for the people who have not answered. */
const NO_ANSWER = 'none';

/**
 * The answers table's filters: the answer, blank for any, and a search over names and
 * addresses.  They narrow the rows on screen; the callout's answers all arrive at once.
 */
const ANSWER_FILTERS: readonly FilterField[] = [
  {
    key: 'answer',
    label: 'Answer',
    kind: 'select',
    placeholder: 'Any answer',
    options: [
      ...ANSWER_CHOICES.map((choice) => ({ value: choice, label: ANSWER_LABELS[choice] })),
      { value: NO_ANSWER, label: 'No answer yet' },
    ],
  },
  { key: 'search', label: 'Find a person', kind: 'search', placeholder: 'Name or email' },
];

const NO_FILTERS: FilterValues = { answer: '', search: '' };

/** One callout's page. */
export function CalloutDetailPage(): JSX.Element {
  const id = Number(useParams().id);
  const callout = useCallout(id);

  if (callout.isError) {
    return (
      <Page title="Callout">
        <p className="field__error" role="alert">
          {isNotFound(callout.error)
            ? "This callout isn't here. It may have been deleted."
            : "This callout didn't load. Try again in a moment."}{' '}
          <Link to="/bulk-email/callouts">Back to callouts</Link>.
        </p>
      </Page>
    );
  }
  if (callout.data === undefined) return <Loading />;
  const shown = callout.data;

  return (
    <Page
      title={shown.subject || 'Callout'}
      lede={calloutLede(shown)}
      actions={<Link to="/bulk-email/callouts">Back to callouts</Link>}
    >
      <Card title="Answers">
        <div className="stack">
          {shown.closed_skipped === 0 ? null : (
            <p className="callouts__notice" role="status">
              {people(shown.closed_skipped)} {shown.closed_skipped === 1 ? 'was' : 'were'} not sent
              the callout because its answers had closed.
            </p>
          )}
          <AnswerCounts callout={shown} />
          <CalloutActions callout={shown} />
          <Answers rows={shown.recipients} />
          <div className="cluster">
            <a className="button button--quiet" href={answersCsvUrl(shown.id)} download>
              Download answers
            </a>
            <Link to={`/bulk-email/sent/${shown.id}`}>See the email and who it went to</Link>
          </div>
          <Reminders callout={shown} />
        </div>
      </Card>
    </Page>
  );
}

/**
 * The line under the title: who sent it and when, and when answers close, or that
 * they have closed.
 *
 * @param callout the callout shown.
 */
export function calloutLede(callout: CalloutDetail): string {
  const sent = `Sent ${formatDate(callout.started_at)}${callout.sender ? ` by ${callout.sender}` : ''}.`;
  if (callout.is_open) return `${sent} Answers close ${scheduledWords(callout.closes_at)}.`;
  if (callout.closed_at !== null) {
    const by = callout.closed_by ? ` by ${callout.closed_by}` : '';
    return `${sent} Closed ${scheduledWords(callout.closed_at)}${by}.`;
  }
  return `${sent} Answers closed ${scheduledWords(callout.closes_at)}.`;
}

/** `Available 3 · With limits 1 · Not available 2 · No answer 4`, as a list of terms. */
function AnswerCounts({ callout }: { callout: CalloutDetail }): JSX.Element {
  const counts: [string, number][] = [
    ['Available', callout.counts.available],
    ['With limits', callout.counts.limited],
    ['Not available', callout.counts.unavailable],
    ['No answer', callout.counts.no_answer],
  ];
  return (
    <dl className="callouts__counts" aria-label="Answers by kind">
      {counts.map(([label, count]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{count}</dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * Why **Remind non-responders** cannot be pressed now, or null when it can.
 *
 * @param callout the callout shown.
 */
export function remindBlocked(callout: CalloutDetail): string | null {
  if (!callout.is_open) return 'This callout has closed, so nobody can answer it now.';
  if (callout.status === 'stopped') {
    return 'This callout was stopped. Send the rest first, then remind the others.';
  }
  if (callout.status !== 'sent') return 'You can remind the others once sending finishes.';
  if (callout.counts.no_answer === 0) return 'Everybody has answered.';
  return null;
}

/** **Remind non-responders** and **Close now**, each behind a confirmation. */
function CalloutActions({ callout }: { callout: CalloutDetail }): JSX.Element {
  const remind = useCalloutAction(callout.id, 'remind');
  const close = useCalloutAction(callout.id, 'close');
  const toast = useToast();
  const reason = remindBlocked(callout);
  const failed = remind.isError ? remind.error : close.isError ? close.error : null;

  return (
    <div className="stack-tight">
      <div className="cluster">
        <ConfirmButton
          label="Remind non-responders"
          disabled={reason !== null}
          choices={[
            {
              label: 'Send reminders',
              onChoose: () =>
                remind.mutateAsync().then(() => toast.show(REMINDING_MESSAGE, 'success')),
            },
          ]}
        >
          <p>
            This sends the callout again to the {people(callout.counts.no_answer)} who have not
            answered, each with their own buttons. Nobody who has answered is sent it. It starts
            within a minute.
          </p>
        </ConfirmButton>
        {callout.is_open ? (
          <ConfirmButton
            label="Close now"
            choices={[
              {
                label: 'Close the callout',
                variant: 'danger',
                onChoose: () =>
                  close.mutateAsync().then(() => toast.show(CLOSED_MESSAGE, 'success')),
              },
            ]}
          >
            <p>
              Nobody can answer or change an answer after this. The answers already given stay. This
              cannot be undone.
            </p>
          </ConfirmButton>
        ) : null}
      </div>
      {reason === null ? null : <p className="muted">{reason}</p>}
      {failed === null ? null : (
        <p className="field__error" role="alert">
          {actionError(failed)}
        </p>
      )}
    </div>
  );
}

/** The answer menu, a search box, and one line per person with their answer. */
function Answers({ rows }: { rows: CalloutRecipient[] }): JSX.Element {
  const [filters, setFilters] = useState<FilterValues>(NO_FILTERS);
  const answer = filters.answer ?? '';
  const search = filters.search ?? '';
  const shown = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return rows.filter(
      (row) =>
        (answer === '' || (answer === NO_ANSWER ? row.answer === null : row.answer === answer)) &&
        (needle === '' ||
          row.name.toLowerCase().includes(needle) ||
          row.email.toLowerCase().includes(needle)),
    );
  }, [rows, search, answer]);

  const handleFilterChange = (next: FilterValues): void => {
    setFilters(next);
  };
  const isFiltered = answer !== '' || search.trim() !== '';

  return (
    <DataTable
      singleLine
      columns={ANSWER_COLUMNS}
      rows={shown}
      rowKey={(row) => row.user_id}
      caption={resultsCaption(shown.length, rows.length, 'Answers')}
      filters={
        <FilterBar
          fields={ANSWER_FILTERS}
          values={filters}
          onChange={handleFilterChange}
          label="Filter the answers"
        />
      }
      emptyTitle="Nobody to show"
      emptyDescription={isFiltered ? 'Nobody matches these filters.' : undefined}
      emptyAction={
        isFiltered ? (
          <Button
            variant="secondary"
            onClick={() => setFilters(clearedValues(ANSWER_FILTERS, filters))}
          >
            Reset filters
          </Button>
        ) : undefined
      }
    />
  );
}

/**
 * The answers table's columns: the person, their answer, and the member check's GO or
 * NO-GO, so all three stay in sight on a phone; then their note, which wraps, and when
 * they answered. Their DART, home airport, and aircraft give way first when the table
 * would not fit its card.
 */
export const ANSWER_COLUMNS: Column<CalloutRecipient>[] = [
  {
    key: 'name',
    header: 'Name',
    minWidth: '10rem',
    isIdentity: true,
    render: (row) => row.name,
    sortValue: (row) => row.name,
  },
  {
    key: 'answer',
    header: 'Answer',
    width: '11rem',
    render: (row) => (
      <span className="callouts__state">
        <StatusDot tone={answerTone(row.answer)} label={answerLabel(row.answer)} />
      </span>
    ),
    sortValue: (row) => (row.answer === null ? '' : ANSWER_LABELS[row.answer]),
  },
  {
    key: 'go_no_go',
    header: 'Go/no-go',
    width: '7.5rem',
    render: (row) => <GoCell goNoGo={row.go_no_go} />,
    sortValue: (row) => (isReady(row.go_no_go) ? 1 : 0),
  },
  {
    key: 'note',
    header: 'Note',
    minWidth: '10rem',
    wrap: true,
    render: (row) => row.note || '—',
    sortValue: (row) => row.note,
  },
  {
    key: 'answered_at',
    header: 'Answered',
    width: '11.5rem',
    render: (row) => <DateText value={row.answered_at} withTime />,
    sortValue: (row) => row.answered_at,
  },
  {
    key: 'dart_name',
    header: 'DART',
    width: '7rem',
    dropOrder: DROP_ORDER.dart,
    render: (row) => row.dart_name || '—',
    sortValue: (row) => row.dart_name,
  },
  {
    key: 'home_airport',
    header: 'Home airport',
    width: '6.5rem',
    dropOrder: DROP_ORDER.homeAirport,
    render: (row) => row.home_airport || '—',
    sortValue: (row) => row.home_airport,
  },
  {
    key: 'aircraft',
    header: 'Aircraft',
    width: '8rem',
    dropOrder: DROP_ORDER.aircraft,
    render: (row) => (row.aircraft.length === 0 ? '—' : row.aircraft.join(', ')),
    sortValue: (row) => row.aircraft.join(', '),
  },
];

/** GO or NO-GO, by the member check's own rule. */
function GoCell({ goNoGo }: { goNoGo: LeaderGoNoGo }): JSX.Element {
  const go = isReady(goNoGo);
  return <GoMark go={go} label={go ? 'Cleared to fly' : 'Not cleared to fly'} />;
}

/** Each round of reminders, with when it went and to how many. */
function Reminders({ callout }: { callout: CalloutDetail }): JSX.Element | null {
  if (callout.reminders.length === 0) return null;
  return (
    <section className="stack-tight" aria-labelledby="callout-reminders">
      <h3 id="callout-reminders">Reminders</h3>
      <ul className="callouts__reminders">
        {callout.reminders.map((reminder) => (
          <li key={reminder.round}>
            <DateText value={reminder.requested_at} withTime />
            {`: reminded ${people(reminder.count)}.`}
          </li>
        ))}
      </ul>
    </section>
  );
}
