import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { BulkEmailCopy, BulkEmailDetail } from '@/portal/api/types';
import { formatDateAt } from '@/portal/components/DateText';
import { EMAIL_FRAME_SANDBOX, emailDocument } from '@/portal/components/EmailFrame';
import { answerBulkEmail, makeBatch, makeBulkEmail, makeRow } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { DeliveryReport, RETRYING_MESSAGE } from './DeliveryReport';

/** A finished send: Ann's copy went, Bea's was refused, Cy's bounced, and Gil was skipped. */
function finished(overrides: Partial<BulkEmailDetail> = {}): BulkEmailDetail {
  return makeBulkEmail({
    status: 'sent',
    can_edit: false,
    started_at: '2026-04-06T17:00:00Z',
    batch_count: 4,
    sent_count: 1,
    failed_count: 1,
    skipped_count: 1,
    bounced_count: 1,
    ...overrides,
  });
}

const ROWS = [
  makeRow({ status: 'sent', tried_at: '2026-04-06T17:00:02Z' }),
  makeRow({
    id: 2,
    name: 'Bea Bell',
    email: 'bea@example.org',
    status: 'failed',
    will_receive: false,
    reason: 'Refused by the mail server',
    tried_at: '2026-04-06T17:00:04Z',
  }),
  makeRow({
    id: 3,
    name: 'Cy Cole',
    email: 'cy@example.org',
    status: 'bounced',
    will_receive: false,
    reason: '5.1.1 User unknown',
    tried_at: '2026-04-06T17:00:06Z',
  }),
  makeRow({
    id: 4,
    name: 'Gil Gone',
    email: 'gil@example.org',
    status: 'skipped',
    will_receive: false,
    reason: 'Account deactivated',
  }),
];

/** Ann's copy, as the server rebuilds it. */
const ANN_COPY: BulkEmailCopy = {
  id: 1,
  name: 'Ann Able',
  email: 'ann@example.org',
  status: 'sent',
  tried_at: '2026-04-06T17:00:02Z',
  subject: 'Hangar day for Ann',
  html: '<html><body><p>Dear Ann,</p></body></html>',
  text: 'Dear Ann,',
};

/** Render the report of `email`, with the fake server answering its batch and actions. */
function renderReport(email: BulkEmailDetail = finished()) {
  const calls = answerBulkEmail({ email, batch: makeBatch(ROWS) });
  const retries: number[] = [];
  server.use(
    http.get(`${API}/bulk-email/${email.id}/recipients/1/copy`, () => HttpResponse.json(ANN_COPY)),
    http.post(`${API}/bulk-email/${email.id}/retry`, () => {
      retries.push(email.id);
      return HttpResponse.json({ ...email, status: 'queued', failed_count: 0, retried_count: 1 });
    }),
  );
  renderWithProviders(<DeliveryReport email={email} />);
  return { calls, retries };
}

describe('DeliveryReport', () => {
  it('counts the copies by result', () => {
    renderReport(finished({ retried_count: 2 }));
    expect(screen.getByLabelText('Copies by result')).toHaveTextContent(
      'Sent2Failed1Skipped1Bounced1Retried2',
    );
  });

  it('lists every person with their result, reason, and time tried', async () => {
    renderReport();
    const row = (await screen.findByText('cy@example.org')).closest('tr');
    // Formatted as the table formats it, so the test reads alike in every time zone.
    expect(row).toHaveTextContent(
      `BouncedView copycy@example.org5.1.1 User unknown${formatDateAt('2026-04-06T17:00:06Z')}`,
    );
  });

  it('narrows the table to one result', async () => {
    renderReport();
    await screen.findByText('bea@example.org');
    await userEvent.selectOptions(screen.getByLabelText('Result'), 'Failed');
    const table = screen.getByRole('table');
    expect(
      within(table)
        .getAllByRole('row')
        .slice(1)
        .map((row) => row.textContent),
    ).toEqual([expect.stringContaining('Bea Bell')]);
  });

  it('says how many of everybody a narrowed table shows', async () => {
    renderReport();
    await screen.findByText('bea@example.org');
    await userEvent.selectOptions(screen.getByLabelText('Result'), 'Failed');
    expect(screen.getByRole('table')).toHaveTextContent('Showing 1 of 4');
  });

  it('offers a copy only for the people whose copy was tried', async () => {
    renderReport();
    await screen.findByText('gil@example.org');
    expect(
      screen
        .getAllByRole('button', { name: /^View the copy sent to / })
        .map((button) => button.getAttribute('aria-label')),
    ).toEqual([
      'View the copy sent to Ann Able',
      'View the copy sent to Bea Bell',
      'View the copy sent to Cy Cole',
    ]);
  });

  it("shows a person's copy as it went, in a sandboxed frame", async () => {
    renderReport();
    await userEvent.click(
      await screen.findByRole('button', { name: 'View the copy sent to Ann Able' }),
    );
    const frame = await screen.findByTitle('The email as Ann Able received it');
    expect([frame.getAttribute('sandbox'), frame.getAttribute('srcdoc')]).toEqual([
      EMAIL_FRAME_SANDBOX,
      emailDocument(ANN_COPY.html),
    ]);
  });

  it('names the copy in a dialog and gives its subject', async () => {
    renderReport();
    await userEvent.click(
      await screen.findByRole('button', { name: 'View the copy sent to Ann Able' }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'The copy sent to Ann Able' });
    expect(await within(dialog).findByText('Hangar day for Ann')).toBeVisible();
  });

  it('puts the focus on Close, and back on View copy once closed', async () => {
    renderReport();
    const view = await screen.findByRole('button', { name: 'View the copy sent to Ann Able' });
    await userEvent.click(view);
    const close = await screen.findByRole('button', { name: 'Close' });
    expect(close).toHaveFocus();
    await userEvent.click(close);
    expect([screen.queryByRole('dialog'), document.activeElement]).toEqual([null, view]);
  });

  describe('in a browser with modal dialogs', () => {
    // jsdom has no modal dialogs; these stand in for the browser's, opening and
    // shutting the dialog as `showModal` and `close` do.
    beforeEach(() => {
      HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
        this.setAttribute('open', '');
      };
      HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
        this.removeAttribute('open');
      };
    });

    afterEach(() => {
      Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal');
      Reflect.deleteProperty(HTMLDialogElement.prototype, 'close');
    });

    it('moves the focus back to View copy only once the modal dialog has shut', async () => {
      renderReport();
      const view = await screen.findByRole('button', { name: 'View the copy sent to Ann Able' });
      // The page behind a modal dialog takes no focus, so the dialog must be shut first.
      const isOpenAtFocus: boolean[] = [];
      vi.spyOn(view, 'focus').mockImplementation(() => {
        isOpenAtFocus.push(document.querySelector('dialog[open]') !== null);
        HTMLElement.prototype.focus.call(view);
      });
      await userEvent.click(view);
      await userEvent.click(await screen.findByRole('button', { name: 'Close' }));
      expect([isOpenAtFocus.includes(true), document.activeElement]).toEqual([false, view]);
    });
  });

  it('closes the copy on Escape', async () => {
    renderReport();
    await userEvent.click(
      await screen.findByRole('button', { name: 'View the copy sent to Ann Able' }),
    );
    await screen.findByRole('dialog');
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('opens the copy as a dialog over the page, which waits until it is shut', async () => {
    renderReport();
    await userEvent.click(
      await screen.findByRole('button', { name: 'View the copy sent to Ann Able' }),
    );
    expect(await screen.findByRole('dialog')).toHaveAttribute('aria-modal', 'true');
  });

  it('retries the failed copies after asking', async () => {
    const { retries } = renderReport();
    await userEvent.click(screen.getByRole('button', { name: 'Retry failed' }));
    const confirm = screen.getByRole('region', { name: 'Retry failed' });
    expect(confirm).toHaveTextContent('the 1 person whose copy the mail server refused');
    await userEvent.click(within(confirm).getByRole('button', { name: 'Retry now' }));
    await waitFor(() => expect(retries).toEqual([7]));
  });

  it('says the failed copies are on their way once retried', async () => {
    renderReport();
    await userEvent.click(screen.getByRole('button', { name: 'Retry failed' }));
    await userEvent.click(screen.getByRole('button', { name: 'Retry now' }));
    expect(await screen.findByText(RETRYING_MESSAGE)).toBeVisible();
  });

  it('cannot retry when nothing failed', () => {
    renderReport(finished({ failed_count: 0 }));
    expect(screen.getByRole('button', { name: 'Retry failed' })).toBeDisabled();
  });

  it('says why there is nothing to retry', () => {
    renderReport(finished({ failed_count: 0 }));
    expect(screen.getByText('No copy failed, so there is nothing to retry.')).toBeVisible();
  });

  it('asks for the rest to be sent before a stopped email retries', () => {
    renderReport(finished({ status: 'stopped' }));
    expect(screen.getByRole('button', { name: 'Retry failed' })).toBeDisabled();
  });

  it('says to send the rest first on a stopped email', () => {
    renderReport(finished({ status: 'stopped' }));
    expect(screen.getByText(/^This email was stopped\. Send the rest first/)).toBeVisible();
  });

  it('lists each retry with its time and who pressed it', () => {
    renderReport(
      finished({
        retried_count: 1,
        retries: [
          { id: 1, requested_at: '2026-04-07T15:00:00Z', requested_by: 'Hollis Grant', count: 1 },
        ],
      }),
    );
    const retries = screen.getByRole('region', { name: 'Retries' });
    expect(retries).toHaveTextContent(
      `${formatDateAt('2026-04-07T15:00:00Z')}: Hollis Grant sent 1 person a fresh copy.`,
    );
  });

  it('offers the results as a download', () => {
    renderReport();
    expect(screen.getByRole('link', { name: 'Download results' })).toHaveAttribute(
      'href',
      '/api/v1/bulk-email/7/recipients.csv',
    );
  });
});
