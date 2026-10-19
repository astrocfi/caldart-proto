/**
 * What the Renewals tab says once a treasurer has closed a charge as failed: whether the
 * member's standing charge is paused (`mandate_paused`) and whether they are emailed so
 * (`member_emailed`), each on its own, and the treasurer is asked to get in touch with
 * them, by the phone number and the address the answer
 * carries, with a link to the member's payment history (and their member record, for an
 * account administrator).
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { RenewalSettleResult } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { MemberRecordLink } from '@/portal/components/MemberRecordLink';
import { MANDATE_KIND_LABELS } from './labels';

export interface ClosedChargeNoticeProps {
  /** The settle call's answer for the charge just closed. */
  result: RenewalSettleResult;
  /** Called when the treasurer dismisses the notice. */
  onDismiss: () => void;
}

/** The result of **Close as failed**, kept on screen until the treasurer dismisses it. */
export function ClosedChargeNotice({
  result,
  onDismiss: handleDismiss,
}: ClosedChargeNoticeProps): JSX.Element {
  const name = result.user_name;
  const kind = MANDATE_KIND_LABELS[result.mandate_kind].toLowerCase();
  return (
    <div className="settle-result stack" role="status">
      <p>
        The charge for {name} is closed
        {result.mandate_paused ? <> and their {kind} is paused</> : null}.{' '}
        {result.member_emailed ? (
          <>They are emailed that it is paused. Please get in touch with them too</>
        ) : (
          <>They aren&rsquo;t emailed about it. Please get in touch with them</>
        )}
        <ContactWays phone={result.user_phone ?? ''} email={result.user_email ?? ''} />.
      </p>
      <p className="cluster">
        <Link to={`/admin/payments/members/${result.user_id}`}>{name}&rsquo;s payment history</Link>
        <MemberRecordLink userId={result.user_id} />
        <Button variant="quiet" small onClick={handleDismiss}>
          Dismiss
        </Button>
      </p>
    </div>
  );
}

/** ": call 415-555-0142 or write to ben@example.org", leaving out whichever is blank. */
function ContactWays({ phone, email }: { phone: string; email: string }): JSX.Element | null {
  const call = phone === '' ? null : <a href={`tel:${phone}`}>{phone}</a>;
  const write = email === '' ? null : <a href={`mailto:${email}`}>{email}</a>;
  if (call === null && write === null) return null;
  return (
    <>
      :{call === null ? null : <> call {call}</>}
      {call !== null && write !== null ? ' or' : null}
      {write === null ? null : <> write to {write}</>}
    </>
  );
}
