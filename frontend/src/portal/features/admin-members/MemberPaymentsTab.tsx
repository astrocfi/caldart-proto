/**
 * The Payments tab of the member record.
 *
 * It reads the finance area's ledger endpoint, so an account administrator
 * looking at one member sees exactly what the finance screens see: the totals,
 * the standing renewal authority, every payment with what came back out of it,
 * and the contribution statements that member can be sent.
 */
import type { JSX } from 'react';

import type { MemberDetail } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { Loading } from '@/portal/components/Loading';
import { useMemberLedger } from '@/portal/features/admin-payments/api';
import { LedgerBody } from '@/portal/features/admin-payments/MemberLedgerPage';

/** The Payments tab: this member's money, read from the ledger endpoint. */
export function MemberPaymentsTab({ member }: { member: MemberDetail }): JSX.Element {
  const ledger = useMemberLedger(member.id);

  if (ledger.isPending) return <Loading />;
  if (ledger.error || !ledger.data) {
    return (
      <Card title="Payments">
        <EmptyState
          title="This member's payments didn't load"
          description="Try again in a moment, or open their ledger in Accounting."
        />
      </Card>
    );
  }

  return <LedgerBody ledger={ledger.data} />;
}
