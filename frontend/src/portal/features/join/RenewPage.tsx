/**
 * `/renew` — renew an existing membership.
 *
 * The new term starts the day after the current one ends, so renewing early
 * costs nothing, and a lapsed membership's new year starts today; the lede says
 * whichever applies, and the status card above the checkout says exactly what the
 * member has now, at the checkout's own width.  A member whose automatic renewal is on
 * is told what it will charge and when, and that they need do nothing; the checkout
 * waits behind **Renew now anyway**, so nobody pays twice by mistake.  A life member has nothing to renew and
 * gives through Donate like everyone else, so the page sends them to `/donate`.  A
 * friend has no membership to renew either (that includes a member who registered and
 * has not yet paid), so the page sends them on to `/membership/join`.
 */
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';

import { Checkout } from '@/portal/features/checkout';

import { useRenewal } from '@/portal/api/queries';
import type { RenewalMandate } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DateText, formatDate } from '@/portal/components/DateText';
import { formatCents } from '@/portal/components/Money';
import { focusFirstField } from '@/portal/components/focus';
import { Page } from '@/portal/components/Page';
import { MembershipDot, daysUntil } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { JOIN_AS_MEMBER_PATH } from '@/portal/features/dashboard/KindSwitch';
import { useMembership } from '@/portal/features/profile/api';
import { refreshAfterPayment } from './refresh';
import './join.css';

/** Where a life member gives, having no term to renew. */
export const LIFETIME_GIVING_PATH = '/donate';

/** The lede for a membership that is still current. */
const EARLY_LEDE =
  'A renewal starts the day after your current term ends, so there is no penalty for ' +
  'renewing early.';

/** The lede for a membership that has run out. */
const LAPSED_LEDE = 'Your new year starts today.';

/** What the page says about a member's automatic renewal. */
type RenewalState =
  | { kind: 'none' }
  | { kind: 'on'; mandate: RenewalMandate }
  | { kind: 'retrying'; mandate: RenewalMandate }
  | { kind: 'paused'; wasRefused: boolean };

/**
 * What the member's automatic renewal will do, read off the mandate the server sends: an
 * active one charges on its day (`on`), or on its day again after a declined charge
 * (`retrying`, when `failure_count` is above 0); a `paused` one charges nothing, paused
 * after refused charges (`wasRefused`) or because the membership lapsed more than 30 days
 * before; anything else, including a recurring donation, renews
 * nothing (`none`).
 */
export function renewalState(mandate: RenewalMandate | null | undefined): RenewalState {
  if (mandate === null || mandate === undefined || mandate.kind === 'contribution') {
    return { kind: 'none' };
  }
  if (mandate.status === 'paused') return { kind: 'paused', wasRefused: mandate.failure_count > 0 };
  if (mandate.status !== 'active' || mandate.next_charge_on === null) return { kind: 'none' };
  return mandate.failure_count > 0 ? { kind: 'retrying', mandate } : { kind: 'on', mandate };
}

/** Renders the current membership status and a checkout to renew it. */
export function RenewPage(): JSX.Element {
  const membership = useMembership();
  const renewal = useRenewal();
  const [isRenewingAnyway, setIsRenewingAnyway] = useState(false);
  // Renew now anyway goes as the checkout takes its place, so the focus follows into it.
  const checkoutRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (isRenewingAnyway) focusFirstField(checkoutRef.current);
  }, [isRenewingAnyway]);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();

  const status = membership.data ?? null;
  const days = status ? daysUntil(status.expires_on) : null;
  const automatic = renewalState(renewal.data?.mandate);
  // While renewal will charge by itself, the checkout waits behind Renew now anyway.
  const isCovered = automatic.kind === 'on' || automatic.kind === 'retrying';
  const isCheckoutShown = !isCovered || isRenewingAnyway;

  if (status?.status === 'friend') {
    return <Navigate to={JOIN_AS_MEMBER_PATH} replace />;
  }
  if (status?.is_lifetime === true) {
    return <Navigate to={LIFETIME_GIVING_PATH} replace />;
  }

  function handleRenewAnyway(): void {
    setIsRenewingAnyway(true);
  }

  function handleSuccess() {
    refreshAfterPayment(queryClient);
    toast.show('Thank you — your membership is renewed.', 'success');
    void navigate('/');
  }

  return (
    <Page
      title="Renew your membership"
      lede={status?.status === 'expired' ? LAPSED_LEDE : EARLY_LEDE}
    >
      <Card eyebrow="Now" title="Your membership">
        {membership.isPending ? (
          <p className="muted" role="status">
            Checking your membership…
          </p>
        ) : status ? (
          <div className="renew__status">
            <MembershipDot membership={status} />
            {status.expires_on ? (
              <p>
                {status.status === 'current' ? 'Expires ' : 'Expired '}
                <DateText value={status.expires_on} />
                {days !== null && status.status === 'current' ? (
                  <span className="muted">
                    {' '}
                    · {days} day{days === 1 ? '' : 's'} to go
                  </span>
                ) : null}
              </p>
            ) : null}
            {status.plan ? <p className="muted">{status.plan} membership</p> : null}
          </div>
        ) : null}
      </Card>

      {renewal.isPending ? null : (
        <>
          <AutomaticRenewalCard
            state={automatic}
            isCheckoutOpen={isCheckoutShown}
            onRenewAnyway={handleRenewAnyway}
          />
          {isCheckoutShown ? (
            <div ref={checkoutRef}>
              <Card>
                <Checkout
                  mode="renew"
                  onSuccess={handleSuccess}
                  defaultAutoRenew={automatic.kind !== 'none'}
                />
              </Card>
            </div>
          ) : null}
        </>
      )}
    </Page>
  );
}

interface AutomaticRenewalCardProps {
  state: RenewalState;
  /** True once the checkout is open under the card, when **Renew now anyway** goes. */
  isCheckoutOpen: boolean;
  /** Opens the checkout. */
  onRenewAnyway: () => void;
}

/**
 * What automatic renewal will do, above the checkout: it will charge on its day, it is
 * trying again after a declined charge, or it is paused after a refused charge and the
 * member renews here.
 * Nothing when the member has none.
 */
function AutomaticRenewalCard({
  state,
  isCheckoutOpen,
  onRenewAnyway: handleRenewAnyway,
}: AutomaticRenewalCardProps): JSX.Element | null {
  if (state.kind === 'none') return null;
  if (state.kind === 'paused') {
    return (
      <Card title="Automatic renewal is paused">
        <p>
          {state.wasRefused
            ? 'A charge was refused, so CalDART will not renew you by itself.'
            : 'Your membership lapsed, so CalDART will not renew it by itself.'}{' '}
          Renew here, and turn automatic renewal on again below or from Payments.
        </p>
      </Card>
    );
  }
  const { amount_cents: amount, next_charge_on: chargeOn } = state.mandate;
  return (
    <Card title="Automatic renewal is on">
      <p>
        {state.kind === 'retrying'
          ? `The last charge was declined. CalDART will try again on ${formatDate(chargeOn)}, ` +
            `for ${formatCents(amount)}.`
          : `We will charge ${formatCents(amount)} on ${formatDate(chargeOn)}. ` +
            'You do not need to do anything.'}
      </p>
      {isCheckoutOpen ? null : (
        <div className="cluster card__footer">
          <Button variant="secondary" onClick={handleRenewAnyway}>
            Renew now anyway
          </Button>
        </div>
      )}
    </Card>
  );
}
