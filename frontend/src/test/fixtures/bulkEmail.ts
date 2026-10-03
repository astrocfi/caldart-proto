/**
 * Bulk email objects for the feature's tests, each a complete API shape with
 * the fields a test cares about given, and a fake server for one email's screens.
 * Not shipped.
 */
import { HttpResponse, http } from 'msw';

import type {
  BulkEmailBatch,
  BulkEmailBatchRow,
  BulkEmailDetail,
  BulkEmailSummary,
} from '@/portal/api/types';
import { API } from '../handlers';
import { server } from '../server';

/** A draft with a subject, a message, and one person who will receive it. */
export function makeBulkEmail(overrides: Partial<BulkEmailDetail> = {}): BulkEmailDetail {
  return {
    id: 7,
    subject: 'Hangar day',
    body: 'Bring gloves.',
    status: 'draft',
    sender: 'Grace Holloway',
    sender_id: 3,
    created_at: '2026-04-06T16:00:00Z',
    updated_at: '2026-04-06T16:30:00Z',
    start_at: null,
    scheduled: false,
    confirm_count: null,
    started_at: null,
    sent_at: null,
    stopped_at: null,
    stopped_by: '',
    stop_requested: false,
    sent_count: 0,
    failed_count: 0,
    skipped_count: 0,
    can_edit: true,
    batch_count: 1,
    receiving_count: 1,
    batch_skipped_count: 0,
    remaining: 0,
    estimated_finish_at: null,
    confirm_above: 50,
    undo_seconds: 120,
    ...overrides,
  };
}

/** One row of the drafts or sent list. */
export function makeSummary(overrides: Partial<BulkEmailSummary> = {}): BulkEmailSummary {
  return {
    id: 7,
    subject: 'Hangar day',
    status: 'draft',
    sender: 'Grace Holloway',
    created_at: '2026-04-06T16:00:00Z',
    updated_at: '2026-04-06T16:30:00Z',
    start_at: null,
    scheduled: false,
    started_at: null,
    sent_at: null,
    stopped_at: null,
    stop_requested: false,
    sent_count: 0,
    failed_count: 0,
    skipped_count: 0,
    batch_count: 1,
    remaining: 0,
    ...overrides,
  };
}

/** One person in a batch, who will receive the email. */
export function makeRow(overrides: Partial<BulkEmailBatchRow> = {}): BulkEmailBatchRow {
  return {
    id: 1,
    user_id: 11,
    name: 'Ann Able',
    email: 'ann@example.org',
    kind: 'member',
    dart_name: 'Marin DART',
    added_by: 1,
    status: 'batched',
    will_receive: true,
    reason: '',
    tried_at: null,
    ...overrides,
  };
}

/** A batch of the given rows, with one add and the counts worked out from them. */
export function makeBatch(rows: BulkEmailBatchRow[] = [makeRow()]): BulkEmailBatch {
  const receiving = rows.filter((row) => row.will_receive).length;
  return {
    count: rows.length,
    receiving,
    skipped: rows.length - receiving,
    adds: [
      {
        id: 1,
        label: 'County: Marin',
        filters: { county: 'Marin' },
        added_count: rows.length,
        already_count: 0,
        created_at: '2026-04-06T16:10:00Z',
      },
    ],
    rows,
  };
}

/** What the fake bulk email server was asked to do, in order. */
export interface BulkEmailCalls {
  patches: unknown[];
  adds: unknown[];
  removed: number[];
  clears: number;
  sends: unknown[];
  actions: string[];
}

/** The fake server's state: the email and its batch, which the handlers change. */
export interface BulkEmailState {
  email: BulkEmailDetail;
  batch: BulkEmailBatch;
}

/**
 * Answer the endpoints one email's screens call, from `state`, recording each
 * request in the answer. An add puts Bea Bell in the batch; a removal and a clear
 * take rows out; a send queues the email; cancel, stop, and resume move it.
 */
export function answerBulkEmail(state: BulkEmailState): BulkEmailCalls {
  const calls: BulkEmailCalls = {
    patches: [],
    adds: [],
    removed: [],
    clears: 0,
    sends: [],
    actions: [],
  };
  const base = `${API}/bulk-email/${state.email.id}`;
  const recount = (rows: BulkEmailBatchRow[]): void => {
    state.batch = { ...makeBatch(rows), adds: state.batch.adds };
    state.email = {
      ...state.email,
      batch_count: state.batch.count,
      receiving_count: state.batch.receiving,
      batch_skipped_count: state.batch.skipped,
    };
  };
  server.use(
    http.get(`${API}/darts`, () => HttpResponse.json([])),
    http.get(base, () => HttpResponse.json(state.email)),
    http.patch(base, async ({ request }) => {
      const patch = (await request.json()) as Record<string, string>;
      calls.patches.push(patch);
      state.email = { ...state.email, ...patch };
      return HttpResponse.json(state.email);
    }),
    http.get(`${base}/batch`, () => HttpResponse.json(state.batch)),
    http.post(`${base}/batch/add`, async ({ request }) => {
      calls.adds.push(await request.json());
      recount([
        ...state.batch.rows,
        makeRow({ id: 2, name: 'Bea Bell', email: 'bea@example.org' }),
      ]);
      return HttpResponse.json({ added: 1, already_present: 1, count: state.batch.count });
    }),
    http.delete(`${base}/batch/:rid`, ({ params }) => {
      const rid = Number(params.rid);
      calls.removed.push(rid);
      recount(state.batch.rows.filter((row) => row.id !== rid));
      return new HttpResponse(null, { status: 204 });
    }),
    http.delete(`${base}/batch`, () => {
      calls.clears += 1;
      recount([]);
      return HttpResponse.json(state.batch);
    }),
    http.post(`${base}/send`, async ({ request }) => {
      const body = (await request.json()) as { start_at?: string | null };
      calls.sends.push(body);
      state.email = {
        ...state.email,
        status: 'queued',
        scheduled: body.start_at !== null && body.start_at !== undefined,
        start_at: body.start_at ?? new Date(Date.now() + 120_000).toISOString(),
      };
      return HttpResponse.json(state.email);
    }),
    http.post(`${base}/:action`, ({ params }) => {
      const action = String(params.action);
      calls.actions.push(action);
      const status = action === 'cancel' ? 'draft' : action === 'resume' ? 'queued' : 'sending';
      state.email = { ...state.email, status, stop_requested: action === 'stop' };
      return HttpResponse.json(state.email);
    }),
  );
  return calls;
}
