/**
 * The pre-flight status card.
 *
 * Designed to be read at arm's length on a phone, standing on a ramp: the
 * verdict is a full-width band in words as well as color, and every row
 * answers one question — membership, medical, certificate, photo ID, insurance.
 * A verifier corrects and verifies the certificate, medical, and photo ID from
 * the card's head, and a DART leader or user administrator makes the person a
 * verifier there, after a question that starts on Cancel.
 */
import { useCallback, useRef, useState } from 'react';
import type { JSX } from 'react';

import type { LeaderStatus, MembershipState } from '@/portal/api/types';
import { MEMBERSHIP_STATUS_LABELS } from '@/portal/choices';
import { Button } from '@/portal/components/Button';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { DateText } from '@/portal/components/DateText';
import { StatusDot } from '@/portal/components/StatusDot';
import type { StatusTone } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { VerifiedMark } from '@/portal/components/VerifiedMark';
import { usePanelFocus } from '@/portal/components/focus';
import { MemberVerificationPanel } from '@/portal/features/verification/MemberVerificationPanel';
import { useSetVerifier } from '@/portal/features/verification/api';
import { draftFromStatus } from '@/portal/features/verification/memberDraft';
import { useCanGrantVerifier, useCanVerify } from '@/portal/features/verification/useCanVerify';
import { InsuranceCheckDot } from './AircraftStatusCard';
import { CERTIFICATE_LABELS, MEDICAL_LABELS, PHOTO_ID_LABELS, ratingLabels } from './labels';
import './leader.css';

const MEMBERSHIP_TONE: Record<MembershipState, StatusTone> = {
  current: 'current',
  expired: 'expired',
  friend: 'none',
  none: 'none',
  donor: 'none',
};

/**
 * Why the membership is a no-go, in the words a leader would say out loud: it ran out,
 * the person has not paid their first dues, or they are a friend of CalDART.
 */
function membershipNoGo(state: MembershipState): string {
  if (state === 'expired') return 'Membership expired';
  if (state === 'none') return 'Not yet paid';
  return 'Friend of CalDART, not a member';
}

/**
 * Why the member is a no-go, in the order a leader would say them out loud: the
 * membership, then one reason for each document that stops them.
 *
 * Each document gives at most one reason.  A non-pilot gets *Not a pilot* and nothing
 * about the certificate, medical, or photo ID they need not hold.  A pilot's medical
 * reads *No medical on file*, *No medical expiry on file*, or *Medical expired* before it
 * can read *Medical not verified*, since verifying a lapsed medical clears nobody.  A
 * photo ID of *Not provided* reads *No photo ID on file*, not *Photo ID not verified*.
 */
export function noGoReasons(status: LeaderStatus): string[] {
  const reasons: string[] = [];
  if (!status.go_no_go.membership) {
    reasons.push(membershipNoGo(status.membership.status));
  }
  if (status.certificate.type === 'none') return [...reasons, 'Not a pilot'];
  const medical = medicalNoGo(status);
  if (medical !== null) reasons.push(medical);
  if (!status.certificate.verification.verified) reasons.push('Certificate not verified');
  if (status.photo_id.type === 'not_provided') reasons.push('No photo ID on file');
  else if (!status.photo_id.verification.verified) reasons.push('Photo ID not verified');
  return reasons;
}

/** The medical's one reason for a no-go, or null when it is current and verified. */
function medicalNoGo(status: LeaderStatus): string | null {
  if (status.medical.type === 'none') return 'No medical on file';
  if (!status.go_no_go.medical) {
    // A medical can also fail because the member picked a class but never
    // entered the date; saying "expired" would send the leader chasing a
    // renewal that is not due.
    return status.medical.expiration === null ? 'No medical expiry on file' : 'Medical expired';
  }
  return status.medical.verification.verified ? null : 'Medical not verified';
}

/** The medical's currency chip: none for a member who holds no medical. */
function MedicalDot({ medical }: { medical: LeaderStatus['medical'] }): JSX.Element | null {
  if (medical.is_current) return <StatusDot tone="current" label="Current" />;
  if (medical.type === 'none') return null;
  return (
    <StatusDot tone="expired" label={medical.expiration === null ? 'Not current' : 'Expired'} />
  );
}

/**
 * The line under the name, before the phone and email: the DART, named as one, and each
 * operational role the person holds, such as *Monterey DART · DART leader · Verifier*.
 */
export function cardMeta(status: LeaderStatus): string {
  const dart = status.dart === null ? 'No DART' : `${status.dart} DART`;
  const roles = [
    status.is_dart_leader ? 'DART leader' : null,
    status.is_verifier ? 'Verifier' : null,
  ];
  return [dart, ...roles.filter((role) => role !== null)].join(' · ');
}

/**
 * A member is a go when their membership and medical are current and their
 * certificate, medical, and photo ID are all verified.
 */
export function isGo(status: LeaderStatus): boolean {
  return status.go_no_go.membership && status.go_no_go.medical && status.go_no_go.verified;
}

export interface MemberStatusCardProps {
  /** The person on the card, for the verification writes. */
  userId: number;
  status: LeaderStatus;
  today?: Date;
}

/** The pre-flight status card: go/no-go verdict plus membership, medical, and aircraft. */
export function MemberStatusCard({ userId, status, today }: MemberStatusCardProps): JSX.Element {
  const go = isGo(status);
  const reasons = noGoReasons(status);
  const canVerify = useCanVerify();
  const [verifying, setVerifying] = useState(false);
  const verifyRef = useRef<HTMLButtonElement>(null);
  const handleCloseVerify = useCallback(() => setVerifying(false), []);
  const panelRef = usePanelFocus(verifying ? 'verify' : null, handleCloseVerify, verifyRef);

  return (
    <section className="leader-card" aria-label={`Status for ${status.name}`}>
      <p
        className={`leader-verdict ${go ? 'leader-verdict--go' : 'leader-verdict--nogo'}`}
        role="status"
      >
        <span className="leader-verdict__word">{go ? 'GO' : 'NO-GO'}</span>
        <span className="leader-verdict__why">
          {go ? 'Membership and medical are current and verified' : reasons.join(' · ')}
        </span>
      </p>

      <header className="leader-card__head">
        <h2 className="leader-card__name">{status.name}</h2>
        <p className="leader-card__meta muted">
          {cardMeta(status)}
          {status.phone ? (
            <>
              {' · '}
              <a className="num" href={`tel:${status.phone.replace(/[^\d+]/g, '')}`}>
                {status.phone}
              </a>
            </>
          ) : null}
          {' · '}
          <a href={`mailto:${status.email}`}>{status.email}</a>
        </p>
        <div className="leader-card__actions cluster">
          {canVerify && !verifying ? (
            <Button ref={verifyRef} variant="secondary" small onClick={() => setVerifying(true)}>
              Verify
            </Button>
          ) : null}
          <VerifierButton userId={userId} status={status} />
        </div>
      </header>

      {verifying ? (
        <div ref={panelRef}>
          <MemberVerificationPanel
            userId={userId}
            initial={draftFromStatus(status)}
            onClose={handleCloseVerify}
          />
        </div>
      ) : null}

      <dl className="leader-rows">
        <div className="leader-row">
          <dt>Membership</dt>
          <dd>
            <StatusDot
              tone={MEMBERSHIP_TONE[status.membership.status]}
              label={MEMBERSHIP_STATUS_LABELS[status.membership.status]}
            />
            <span className="leader-row__detail">
              {status.membership.plan ?? '—'}
              {status.membership.expires_on ? (
                <>
                  {' · expires '}
                  <DateText value={status.membership.expires_on} />
                </>
              ) : status.membership.status === 'current' ? (
                // Current with no end date is a lifetime membership; a friend has no date at all.
                ' · lifetime'
              ) : null}
            </span>
          </dd>
        </div>

        <div className="leader-row">
          <dt>Medical</dt>
          <dd>
            <MedicalDot medical={status.medical} />
            <span className="leader-row__detail">
              {MEDICAL_LABELS[status.medical.type]}
              {status.medical.expiration ? (
                <>
                  {' · expires '}
                  <DateText value={status.medical.expiration} />
                </>
              ) : null}
            </span>
            {status.medical.type === 'none' ? null : (
              <VerifiedMark verification={status.medical.verification} />
            )}
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
                  <span className="num">{status.certificate.number}</span>
                </>
              ) : null}
              {status.certificate.ratings.length > 0
                ? ` · ${ratingLabels(status.certificate.ratings)}`
                : ''}
            </span>
            {status.certificate.type === 'none' ? null : (
              <VerifiedMark verification={status.certificate.verification} />
            )}
          </dd>
        </div>

        <div className="leader-row">
          <dt>Photo ID</dt>
          <dd>
            <span className="leader-row__detail">{PHOTO_ID_LABELS[status.photo_id.type]}</span>
            {status.photo_id.type === 'not_provided' ? null : (
              <VerifiedMark verification={status.photo_id.verification} />
            )}
          </dd>
        </div>
      </dl>

      <h3 className="leader-card__subhead">Aircraft</h3>
      {status.aircraft.length === 0 ? (
        <p className="leader-aircraft__row muted">No aircraft on this member's profile.</p>
      ) : (
        <ul className="leader-aircraft">
          {status.aircraft.map((aircraft) => (
            <li key={aircraft.id} className="leader-aircraft__row">
              <span className="leader-aircraft__ident num">{aircraft.n_number}</span>
              <span className="leader-aircraft__name">
                {aircraft.make} {aircraft.model}
              </span>
              {aircraft.coverage.excluded ? (
                <StatusDot tone="expired" label="Not covered" title={aircraft.coverage.reason} />
              ) : (
                <InsuranceCheckDot
                  aircraft={aircraft}
                  verified={aircraft.insurance_verified}
                  today={today}
                />
              )}
              <span className="leader-aircraft__expiry muted">
                {aircraft.insurance_expiration ? (
                  <>
                    {'expires '}
                    <DateText value={aircraft.insurance_expiration} />
                  </>
                ) : (
                  'no policy on file'
                )}
                {aircraft.coverage.reason === '' ? '' : ` · ${aircraft.coverage.reason}`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

interface VerifierButtonProps {
  userId: number;
  status: LeaderStatus;
}

/**
 * *Make a verifier* or *Remove as verifier*, for a DART leader or user administrator.
 *
 * Either one changes the person's roles, so it asks first, with the focus on Cancel,
 * as a role change on Roles waits for Save changes.
 */
function VerifierButton({ userId, status }: VerifierButtonProps): JSX.Element | null {
  const canGrant = useCanGrantVerifier();
  const setVerifier = useSetVerifier(userId);
  const toast = useToast();
  if (!canGrant) return null;

  const wanted = !status.is_verifier;
  const label = wanted ? 'Make a verifier' : 'Remove as verifier';
  const handleChoose = async (): Promise<void> => {
    try {
      await setVerifier.mutateAsync({ verifier: wanted });
    } catch (error) {
      toast.show(error instanceof Error ? error.message : 'The role did not change.', 'error');
      throw error;
    }
    toast.show(
      wanted ? `${status.name} is a verifier.` : `${status.name} is no longer a verifier.`,
      'success',
    );
  };

  return (
    <ConfirmButton
      label={label}
      variant="quiet"
      small
      startOnCancel
      choices={[{ label, onChoose: handleChoose }]}
    >
      <p>
        {wanted
          ? `${status.name} will be able to check and verify the certificate, medical, photo ID, and aircraft insurance of every member.`
          : `${status.name} will no longer be able to verify anyone's documents.`}
      </p>
    </ConfirmButton>
  );
}
