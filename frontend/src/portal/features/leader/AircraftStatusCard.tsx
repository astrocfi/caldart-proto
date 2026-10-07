/**
 * The aircraft half of the leader check: does CalDART's coverage policy cover
 * this tail number, is its insurance current and verified, who flies it, and how
 * fresh is the record?  A verifier corrects and verifies the insurance from the
 * card's head.  Each pilot carries the member check's own GO or NO-GO and links to
 * their member check card, so the two checks never disagree about one person.
 */
import { useCallback, useRef, useState } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { Aircraft, AircraftDetail } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { DateText } from '@/portal/components/DateText';
import { Money } from '@/portal/components/Money';
import { StatusDot } from '@/portal/components/StatusDot';
import type { StatusTone } from '@/portal/components/StatusDot';
import { VerifiedMark } from '@/portal/components/VerifiedMark';
import { usePanelFocus } from '@/portal/components/focus';
import { InsuranceDot } from '@/portal/features/aircraft/InsuranceDot';
import { ServiceDot } from '@/portal/features/aircraft/ServiceDot';
import { categoryLine } from '@/portal/features/aircraft/categories';
import { OWNER_TYPE_LABELS } from '@/portal/features/aircraft/form';
import { insuranceTone } from '@/portal/features/aircraft/insurance';
import { InsuranceVerificationPanel } from '@/portal/features/verification/InsuranceVerificationPanel';
import { useCanVerify } from '@/portal/features/verification/useCanVerify';
import { contactHref } from './contact';
import { GoMark, isReady } from './LeaderLookup';
import './leader.css';

export interface Verdict {
  word: string;
  why: string;
  /** What the results list's mark reads: *Insured*, *Not verified*, or *Not insured*. */
  mark: string;
  go: boolean;
  /**
   * Nobody has checked yet: the band is amber, as the *Not verified* mark under it is,
   * rather than the red kept for a policy that has failed or lapsed.
   */
  isAwaitingCheck?: boolean;
}

const VERDICT: Record<StatusTone, Verdict> = {
  current: { word: 'INSURED', why: 'Coverage is current', mark: 'Insured', go: true },
  expiring: { word: 'INSURED', why: 'Coverage expires soon', mark: 'Insured', go: true },
  // Unreachable for insurance; kept so the map stays total over the tones.
  new: { word: 'NOT INSURED', why: 'No policy on file', mark: 'Not insured', go: false },
  expired: { word: 'NOT INSURED', why: 'Coverage has expired', mark: 'Not insured', go: false },
  none: { word: 'NOT INSURED', why: 'No policy on file', mark: 'Not insured', go: false },
};

/** A current policy nobody has checked against the documents: not yet a go. */
const NOT_VERIFIED: Verdict = {
  word: 'NOT VERIFIED',
  why: 'Coverage is current but not verified',
  mark: 'Not verified',
  go: false,
  isAwaitingCheck: true,
};

type InsuranceFacts = Pick<
  Aircraft,
  'insurance_is_current' | 'insurance_expiration' | 'insurance_verification'
>;

/**
 * The aircraft check's verdict: INSURED for a current, verified policy (one about
 * to expire included), NOT VERIFIED for a current one nobody has verified, and NOT
 * INSURED for no current policy.  The results list and the card read the same answer.
 */
export function insuranceVerdict(aircraft: InsuranceFacts, today?: Date): Verdict {
  const verdict = VERDICT[insuranceTone(aircraft, today)];
  return verdict.go && !aircraft.insurance_verification.verified ? NOT_VERIFIED : verdict;
}

type CheckFacts = InsuranceFacts & Pick<Aircraft, 'coverage'>;

/** The prefix the server's exclusion reason starts with, which the band's word already says. */
const NOT_COVERED_PREFIX = 'Not covered: ';

/**
 * The aircraft check's verdict: NOT COVERED, with the policy's reason (less its
 * `Not covered: ` prefix, which the word already says), for an aircraft the
 * coverage policy excludes, whatever its insurance; otherwise the insurance
 * verdict.  The results list and the card read the same answer.
 */
export function aircraftVerdict(aircraft: CheckFacts, today?: Date): Verdict {
  if (aircraft.coverage.excluded) {
    const why = aircraft.coverage.reason.replace(NOT_COVERED_PREFIX, '');
    return { word: 'NOT COVERED', why, mark: 'Not covered', go: false };
  }
  return insuranceVerdict(aircraft, today);
}

/** Whether an aircraft's insurance lets it fly: current and verified. */
export function isInsured(aircraft: InsuranceFacts, today?: Date): boolean {
  return insuranceVerdict(aircraft, today).go;
}

export interface InsuranceCheckDotProps {
  aircraft: Pick<Aircraft, 'insurance_is_current' | 'insurance_expiration'>;
  /** Whether an authority has checked the policy against its documents. */
  verified: boolean;
  today?: Date;
}

/**
 * An airplane's insurance as the aircraft check reads it, in one mark: a current policy
 * nobody has verified reads *Not verified* in amber, and anything else reads as the
 * insurance dot does.  Both checks draw this, the aircraft check on its insurance line and
 * the member check on its aircraft rows, so they give the same airplane the same answer.
 */
export function InsuranceCheckDot({
  aircraft,
  verified,
  today,
}: InsuranceCheckDotProps): JSX.Element {
  const tone = insuranceTone(aircraft, today);
  if ((tone === 'current' || tone === 'expiring') && !verified) {
    return <StatusDot tone="expiring" label="Not verified" />;
  }
  return <InsuranceDot aircraft={aircraft} today={today} />;
}

/** The owner's contact as a link when it is an email address or a phone number. */
function OwnerContact({ contact }: { contact: string }): JSX.Element {
  const href = contactHref(contact);
  return href === null ? <>{contact}</> : <a href={href}>{contact}</a>;
}

/** The band's color: green for a go, amber while nobody has checked, red otherwise. */
function bandOf(verdict: Verdict): 'go' | 'wait' | 'nogo' {
  if (verdict.go) return 'go';
  return verdict.isAwaitingCheck === true ? 'wait' : 'nogo';
}

export interface AircraftStatusCardProps {
  aircraft: AircraftDetail;
  today?: Date;
}

/** The aircraft half of the leader check: insurance status and the pilots who fly it. */
export function AircraftStatusCard({ aircraft, today }: AircraftStatusCardProps): JSX.Element {
  const verdict = aircraftVerdict(aircraft, today);
  const canVerify = useCanVerify();
  const [verifying, setVerifying] = useState(false);
  const verifyRef = useRef<HTMLButtonElement>(null);
  const handleCloseVerify = useCallback(() => setVerifying(false), []);
  const panelRef = usePanelFocus(verifying ? 'verify' : null, handleCloseVerify, verifyRef);
  // Only a leader or administrator is sent the pilot list.
  const pilots = aircraft.pilots ?? [];

  return (
    <section className="leader-card" aria-label={`Insurance for ${aircraft.n_number}`}>
      <p className={`leader-verdict leader-verdict--${bandOf(verdict)}`} role="status">
        <span className="leader-verdict__word">{verdict.word}</span>
        <span className="leader-verdict__why">{verdict.why}</span>
      </p>

      <header className="leader-card__head">
        <h2 className="leader-card__name num">{aircraft.n_number}</h2>
        <ServiceDot aircraft={aircraft} />
        <p className="leader-card__meta muted">
          {aircraft.make} {aircraft.model}
          {aircraft.year ? ` · ${aircraft.year}` : ''}
          {aircraft.seats ? ` · ${aircraft.seats} seats` : ''}
        </p>
        {canVerify && !verifying ? (
          <div className="leader-card__actions cluster">
            <Button ref={verifyRef} variant="secondary" small onClick={() => setVerifying(true)}>
              Verify
            </Button>
          </div>
        ) : null}
      </header>

      {verifying ? (
        <div ref={panelRef}>
          <InsuranceVerificationPanel aircraft={aircraft} onClose={handleCloseVerify} />
        </div>
      ) : null}

      <dl className="leader-rows">
        <div className="leader-row">
          <dt>Category</dt>
          <dd>
            <span className="leader-row__detail">{categoryLine(aircraft)}</span>
            {aircraft.coverage.excluded ? (
              <StatusDot tone="expired" label="Not covered" title={aircraft.coverage.reason} />
            ) : null}
          </dd>
        </div>

        <div className="leader-row">
          <dt>Insurance</dt>
          <dd>
            <InsuranceCheckDot
              aircraft={aircraft}
              verified={aircraft.insurance_verification.verified}
              today={today}
            />
            <span className="leader-row__detail">
              {aircraft.insurance_carrier || 'No carrier on file'}
              {aircraft.insurance_expiration ? (
                <>
                  {' · expires '}
                  <DateText value={aircraft.insurance_expiration} />
                </>
              ) : null}
            </span>
            {/* The band above already says NOT VERIFIED; only a stamp adds anything. */}
            {aircraft.insurance_expiration === null ||
            !aircraft.insurance_verification.verified ? null : (
              <VerifiedMark verification={aircraft.insurance_verification} />
            )}
          </dd>
        </div>

        <div className="leader-row">
          <dt>Liability</dt>
          <dd>
            <span className="leader-row__detail">
              <Money cents={aircraft.insurance_liability_per_occurrence_cents} whole /> per
              occurrence · <Money cents={aircraft.insurance_liability_per_person_cents} whole /> per
              person
              {aircraft.insurance_hull_cents !== null ? (
                <>
                  {' · hull '}
                  <Money cents={aircraft.insurance_hull_cents} whole />
                </>
              ) : null}
            </span>
          </dd>
        </div>

        <div className="leader-row">
          <dt>Owner</dt>
          <dd>
            <span className="leader-row__detail">
              {aircraft.owner_name || 'Not recorded'} ({OWNER_TYPE_LABELS[aircraft.owner_type]})
              {aircraft.owner_contact ? (
                <>
                  {' · '}
                  <OwnerContact contact={aircraft.owner_contact} />
                </>
              ) : null}
            </span>
          </dd>
        </div>

        <div className="leader-row">
          <dt>Last updated</dt>
          <dd>
            <span className="leader-row__detail">
              <DateText value={aircraft.updated_at} />
              {aircraft.updated_by == null ? '' : ` by ${aircraft.updated_by.name}`}
            </span>
          </dd>
        </div>
      </dl>

      <h3 className="leader-card__subhead">Pilots who fly it</h3>
      {pilots.length === 0 ? (
        <p className="leader-aircraft-card__limits muted">
          No member lists this aircraft on their profile.
        </p>
      ) : (
        <ul className="leader-aircraft">
          {pilots.map((pilot) => {
            const ready = isReady(pilot.go_no_go);
            return (
              <li key={pilot.user_id} className="leader-aircraft__row">
                <Link className="leader-search__name" to={`/leader?member=${pilot.user_id}`}>
                  {pilot.name}
                </Link>
                <GoMark go={ready} label={ready ? 'Cleared to fly' : 'Not cleared to fly'} />
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
