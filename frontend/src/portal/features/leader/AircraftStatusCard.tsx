/**
 * The aircraft half of the leader check: does CalDART's coverage policy cover
 * this tail number, is its insurance current and verified, who flies it, and how
 * fresh is the record?  A verifier corrects and verifies the insurance from the
 * card's head.
 */
import { useCallback, useRef, useState } from 'react';
import type { JSX } from 'react';

import type { Aircraft, AircraftDetail } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { DateText } from '@/portal/components/DateText';
import { Money } from '@/portal/components/Money';
import { StatusChip } from '@/portal/components/StatusChip';
import type { StatusTone } from '@/portal/components/StatusChip';
import { VerifiedMark } from '@/portal/components/VerifiedMark';
import { usePanelFocus } from '@/portal/components/focus';
import { InsuranceChip } from '@/portal/features/aircraft/InsuranceChip';
import { ServiceChip } from '@/portal/features/aircraft/ServiceChip';
import { categoryLine } from '@/portal/features/aircraft/categories';
import { OWNER_TYPE_LABELS } from '@/portal/features/aircraft/form';
import { insuranceTone } from '@/portal/features/aircraft/insurance';
import { InsuranceVerificationPanel } from '@/portal/features/verification/InsuranceVerificationPanel';
import { useCanVerify } from '@/portal/features/verification/useCanVerify';
import './leader.css';

export interface Verdict {
  word: string;
  why: string;
  /** What the results list's mark reads: *Insured*, *Not verified*, or *Not insured*. */
  mark: string;
  go: boolean;
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
      <p
        className={`leader-verdict ${verdict.go ? 'leader-verdict--go' : 'leader-verdict--nogo'}`}
        role="status"
      >
        <span className="leader-verdict__word">{verdict.word}</span>
        <span className="leader-verdict__why">{verdict.why}</span>
      </p>

      <header className="leader-card__head">
        <h2 className="leader-card__name mono">{aircraft.n_number}</h2>
        <ServiceChip aircraft={aircraft} />
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
              <StatusChip tone="expired" label="Not covered" title={aircraft.coverage.reason} />
            ) : null}
          </dd>
        </div>

        <div className="leader-row">
          <dt>Insurance</dt>
          <dd>
            <InsuranceChip aircraft={aircraft} today={today} />
            <span className="leader-row__detail">
              {aircraft.insurance_carrier || 'No carrier on file'}
              {aircraft.insurance_expiration ? (
                <>
                  {' · expires '}
                  <DateText value={aircraft.insurance_expiration} />
                </>
              ) : null}
            </span>
            <VerifiedMark verification={aircraft.insurance_verification} />
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
              {aircraft.owner_contact ? ` · ${aircraft.owner_contact}` : ''}
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

      <h3 className="leader-card__subhead">Members who fly it</h3>
      {pilots.length === 0 ? (
        <p className="leader-aircraft-card__limits muted">
          No member lists this aircraft on their profile.
        </p>
      ) : (
        <ul className="leader-aircraft">
          {pilots.map((pilot) => (
            <li key={pilot.user_id} className="leader-aircraft__row">
              <span className="leader-search__name">{pilot.name}</span>
              <StatusChip
                tone={pilot.membership_status === 'current' ? 'current' : 'expired'}
                label={pilot.membership_status === 'current' ? 'Member current' : 'Member expired'}
              />
              <StatusChip
                tone={pilot.medical_is_current ? 'current' : 'expired'}
                label={pilot.medical_is_current ? 'Medical current' : 'Medical not current'}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
