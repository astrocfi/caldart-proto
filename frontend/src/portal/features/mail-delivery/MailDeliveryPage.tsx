/**
 * `/bulk-email/mail-delivery` -- whether other mail systems will trust the email
 * CalDART sends.
 *
 * Each line of the server's check (who may send for the domain, the message signature,
 * what to do with forged mail, the bounce address) shows a dot and a word, what the
 * record is for and what was found, and, when something is wrong, what to ask for. The
 * page is written for a reader who has never heard of SPF, DKIM, or DMARC.
 */
import type { JSX } from 'react';

import type {
  MailDeliveryCheck,
  MailDeliveryFinding,
  MailDeliveryStatus,
} from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { formatDateTime } from '@/portal/components/DateText';
import { Loading } from '@/portal/components/Loading';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusChip';
import type { StatusTone } from '@/portal/components/StatusChip';
import { useMailDeliveryCheck, useRecheckMailDelivery } from './api';
import './mail-delivery.css';

const STATUS_TONE: Record<MailDeliveryStatus, StatusTone> = {
  pass: 'current',
  warn: 'expiring',
  fail: 'expired',
};

const STATUS_WORD: Record<MailDeliveryStatus, string> = {
  pass: 'Good',
  warn: 'Warning',
  fail: 'Problem',
};

/** The one-sentence verdict above the lines, in the words a volunteer would use. */
export function summarize(findings: readonly MailDeliveryFinding[]): string {
  const problems = findings.filter((finding) => finding.status === 'fail').length;
  const warnings = findings.filter((finding) => finding.status === 'warn').length;
  if (problems > 0) {
    return `${problems} of ${findings.length} checks found a problem. Some email may be marked as spam or not arrive until it is fixed.`;
  }
  if (warnings > 0) {
    return `Email can be delivered, but ${warnings} of ${findings.length} checks could be better.`;
  }
  return 'Every check is good. Receiving mail systems have what they need to trust email from CalDART.';
}

function FindingRow({ finding }: { finding: MailDeliveryFinding }): JSX.Element {
  const word = STATUS_WORD[finding.status];
  return (
    <li className="delivery-check__row">
      <h3 className="delivery-check__name">
        <StatusDot tone={STATUS_TONE[finding.status]} label={word} />
        <span aria-hidden="true" className="delivery-check__word">
          {word}
        </span>
        {finding.name}
      </h3>
      <p>{finding.detail}</p>
      {finding.fix === '' ? null : (
        <p className="delivery-check__fix">
          <strong>What to do: </strong>
          {finding.fix}
        </p>
      )}
    </li>
  );
}

function Report({ report }: { report: MailDeliveryCheck }): JSX.Element {
  return (
    <>
      <p role="status">{summarize(report.findings)}</p>
      <ul className="delivery-check stack">
        {report.findings.map((finding) => (
          <FindingRow key={finding.name} finding={finding} />
        ))}
      </ul>
    </>
  );
}

/** The Mail delivery screen. */
export function MailDeliveryPage(): JSX.Element {
  const { data, isPending, isError, error } = useMailDeliveryCheck();
  const recheck = useRecheckMailDelivery();
  const report = recheck.data ?? data;

  return (
    <Page
      title="Mail delivery"
      eyebrow="Bulk Email"
      lede="Whether other mail systems will trust and deliver the email CalDART sends. Do this check before a large send, and again after anyone changes the website's email settings."
    >
      <Card
        title="Can our email be trusted?"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => recheck.mutate()}
              disabled={recheck.isPending}
            >
              {recheck.isPending ? 'Checking…' : 'Check again'}
            </Button>
            {report ? (
              <span className="muted">
                Checked {formatDateTime(report.checked_at)}
                {report.domain === '' ? '' : ` for ${report.domain}`}.
              </span>
            ) : null}
          </>
        }
      >
        {isPending ? <Loading /> : null}
        {isError ? (
          <p className="field__error" role="alert">
            {error instanceof Error ? error.message : 'Could not run the mail delivery check.'}
          </p>
        ) : null}
        {recheck.isError ? (
          <p className="field__error" role="alert">
            The check could not be run again. Try once more in a minute.
          </p>
        ) : null}
        {report ? <Report report={report} /> : null}
      </Card>
    </Page>
  );
}
