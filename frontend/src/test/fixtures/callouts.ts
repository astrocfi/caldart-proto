/**
 * Mission callout objects for the Callouts screens' tests, each a complete API shape
 * with the fields a test cares about given, and a fake server for one callout.  Not
 * shipped.
 */
import { HttpResponse, http } from 'msw';

import type { CalloutDetail, CalloutRecipient, CalloutSummary } from '@/portal/api/types';
import { API } from '../handlers';
import { server } from '../server';

/** One callout as the list shows it: sent, open, three people reached, one answer. */
export function makeCalloutSummary(overrides: Partial<CalloutSummary> = {}): CalloutSummary {
  return {
    id: 7,
    subject: 'Fire near Paradise',
    status: 'sent',
    sender: 'Grace Holloway',
    dart_name: '',
    started_at: '2026-04-06T17:00:00Z',
    sent_at: '2026-04-06T17:01:00Z',
    closes_at: '2026-04-08T15:30:00Z',
    closed_at: null,
    is_open: true,
    counts: { reached: 3, available: 0, limited: 1, unavailable: 0, no_answer: 2 },
    ...overrides,
  };
}

/** One person a callout reached; Ann, with no answer, unless given. */
export function makeCalloutRecipient(overrides: Partial<CalloutRecipient> = {}): CalloutRecipient {
  return {
    user_id: 1,
    name: 'Ann Able',
    email: 'ann@example.org',
    answer: null,
    note: '',
    answered_at: null,
    dart_name: 'Marin DART',
    home_airport: '',
    aircraft: [],
    go_no_go: { membership: true, medical: true, verified: true },
    ...overrides,
  };
}

/** Ann, who answered with limits; Bea and Cy, who have not answered. */
export const RECIPIENTS: CalloutRecipient[] = [
  makeCalloutRecipient({
    answer: 'limited',
    note: 'Saturday only',
    answered_at: '2026-04-06T18:00:00Z',
    home_airport: 'LVK',
    aircraft: ['N123AB'],
  }),
  makeCalloutRecipient({
    user_id: 2,
    name: 'Bea Bell',
    email: 'bea@example.org',
    go_no_go: { membership: false, medical: true, verified: true },
  }),
  makeCalloutRecipient({ user_id: 3, name: 'Cy Cole', email: 'cy@example.org' }),
];

/** One callout with its answers: `makeCalloutSummary`'s, reaching `RECIPIENTS`. */
export function makeCallout(overrides: Partial<CalloutDetail> = {}): CalloutDetail {
  return {
    ...makeCalloutSummary(),
    closed_by: '',
    closed_skipped: 0,
    reminders: [],
    recipients: RECIPIENTS,
    ...overrides,
  };
}

/** What the fake server was asked for. */
export interface CalloutCalls {
  reminds: number;
  closes: number;
}

/**
 * Answer `GET /bulk-email/callouts/{id}` with `callout`, and **Remind** and **Close
 * now** as the server would, recording each.
 */
export function answerCallout(callout: CalloutDetail): CalloutCalls {
  const calls: CalloutCalls = { reminds: 0, closes: 0 };
  let state = callout;
  const base = `${API}/bulk-email/callouts/${callout.id}`;
  server.use(
    http.get(base, () => HttpResponse.json(state)),
    http.post(`${base}/remind`, () => {
      calls.reminds += 1;
      state = {
        ...state,
        reminders: [{ round: 1, requested_at: '2026-04-07T16:00:00Z', count: 2 }],
      };
      return HttpResponse.json(state);
    }),
    http.post(`${base}/close`, () => {
      calls.closes += 1;
      state = {
        ...state,
        is_open: false,
        closed_at: '2026-04-07T16:00:00Z',
        closed_by: 'Grace Holloway',
      };
      return HttpResponse.json(state);
    }),
  );
  return calls;
}
