/**
 * The pre-flight status card.
 *
 * Designed to be read at arm's length on a phone, standing on a ramp: the
 * verdict is a full-width band in words as well as color, and every row
 * answers one question — membership, medical, certificate, insurance.
 */
import type { JSX } from 'react';

import type { LeaderStatus, MembershipState } from '../../api/types';
import { DateText } from '../../components/DateText';
import { StatusChip } from '../../components/StatusChip';
import type { StatusTone } from '../../components/StatusChip';
import { InsuranceChip } from '../aircraft/InsuranceChip';
import { CERTIFICATE_LABELS, IFR_LABELS, MEDICAL_LABELS, ratingLabels } from './labels';
import './leader.css';

const MEMBERSHIP_LABEL: Record<MembershipState, string> = {
  current: 'Current',
  expired: 'Expired',
  none: 'Never joined',
};

const MEMBERSHIP_TONE: Record<MembershipState, StatusTone> = {
  current: 'current',
  expired: 'expired',
  none: 'none',
};

/** Why the member is a no-go, in the order a leader would say them out loud. */
export function noGoReasons(status: LeaderStatus): string[] {
  const reasons: string[] = [];
  if (!status.go_no_go.membership) {
    reasons.push(
      status.membership.status === 'expired' ? 'Membership expired' : 'No CalDART membership',
    );
  }
  if (!status.go_no_go.medical) {
    // A medical can also fail because the member picked a class but never
    // entered the date; saying "expired" would send the leader chasing a
    // renewal that is not due.
    if (status.medical.type === 'none') reasons.push('No medical on file');
    else if (status.medical.expiration === null) reasons.push('No medical expiry on file');
    else reasons.push('Medical expired');
  }
  return reasons;
}

/** A member is a go when their membership and medical are both current. */
export function isGo(status: LeaderStatus): boolean {
  return status.go_no_go.membership && status.go_no_go.medical;
}

export interface MemberStatusCardProps {
  status: LeaderStatus;
  today?: Date;
}

/** The pre-flight status card: go/no-go verdict plus membership, medical and aircraft. */
export function MemberStatusCard({ status, today }: MemberStatusCardProps): JSX.Element {
  const go = isGo(status);
  const reasons = noGoReasons(status);

  return (
    <section className="leader-card" aria-label={`Status for ${status.name}`}>
      <p
        className={`leader-verdict ${go ? 'leader-verdict--go' : 'leader-verdict--nogo'}`}
        role="status"
      >
        <span className="leader-verdict__word">{go ? 'GO' : 'NO-GO'}</span>
        <span className="leader-verdict__why">
          {go ? 'Membership and medical are current' : reasons.join(' · ')}
        </span>
      </p>

      <header className="leader-card__head">
        <h2 className="leader-card__name">{status.name}</h2>
        <p className="leader-card__meta muted">
          {status.dart ?? 'No DART'}
          {status.phone ? (
            <>
              {' · '}
              <a className="mono" href={`tel:${status.phone.replace(/[^\d+]/g, '')}`}>
                {status.phone}
              </a>
            </>
          ) : null}
          {' · '}
          <a href={`mailto:${status.email}`}>{status.email}</a>
        </p>
      </header>

      <dl className="leader-rows">
        <div className="leader-row">
          <dt>Membership</dt>
          <dd>
            <StatusChip
              tone={MEMBERSHIP_TONE[status.membership.status]}
              label={MEMBERSHIP_LABEL[status.membership.status]}
            />
            <span className="leader-row__detail">
              {status.membership.plan ?? '—'}
              {status.membership.status !== 'none' ? (
                status.membership.expires_on ? (
                  <>
                    {' · expires '}
                    <DateText value={status.membership.expires_on} />
                  </>
                ) : (
                  ' · lifetime'
                )
              ) : null}
            </span>
          </dd>
        </div>

        <div className="leader-row">
          <dt>Medical</dt>
          <dd>
            <StatusChip
              tone={
                status.medical.is_current
                  ? 'current'
                  : status.medical.type === 'none'
                    ? 'none'
                    : 'expired'
              }
              label={status.medical.is_current ? 'Current' : 'Not current'}
            />
            <span className="leader-row__detail">
              {MEDICAL_LABELS[status.medical.type]}
              {status.medical.expiration ? (
                <>
                  {' · expires '}
                  <DateText value={status.medical.expiration} />
                </>
              ) : null}
            </span>
          </dd>
        </div>

        <div className="leader-row">
          <dt>Certificate</dt>
          <dd>
            <span className="leader-row__detail">
              {CERTIFICATE_LABELS[status.certificate.type]}
              {status.certificate.number ? (
                <>
                  {' · '}
                  <span className="mono">{status.certificate.number}</span>
                </>
              ) : null}
              {` · ${IFR_LABELS[status.certificate.ifr_rated]}`}
              {status.certificate.ratings.length > 0
                ? ` · ${ratingLabels(status.certificate.ratings)}`
                : ''}
            </span>
          </dd>
        </div>
      </dl>

      <h3 className="leader-card__subhead">Aircraft</h3>
      {status.aircraft.length === 0 ? (
        <p className="muted">No aircraft on this member's profile.</p>
      ) : (
        <ul className="leader-aircraft">
          {status.aircraft.map((aircraft) => (
            <li key={aircraft.id} className="leader-aircraft__row">
              <span className="leader-aircraft__ident mono">{aircraft.n_number}</span>
              <span className="leader-aircraft__name">
                {aircraft.make} {aircraft.model}
              </span>
              <InsuranceChip aircraft={aircraft} today={today} />
              <span className="leader-aircraft__expiry muted">
                {aircraft.insurance_expiration ? (
                  <>
                    {'expires '}
                    <DateText value={aircraft.insurance_expiration} />
                  </>
                ) : (
                  'no policy on file'
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
