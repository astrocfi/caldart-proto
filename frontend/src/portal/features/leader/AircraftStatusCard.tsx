/**
 * The aircraft half of the leader check: is the insurance on this
 * tail number current, and who flies it?
 */
import { DateText } from '../../components/DateText';
import { Money } from '../../components/Money';
import { StatusChip } from '../../components/StatusChip';
import { InsuranceChip } from '../aircraft/InsuranceChip';
import { ServiceChip } from '../aircraft/ServiceChip';
import type { AircraftDetail } from '../../api/types';
import { OWNER_TYPE_LABELS } from '../aircraft/form';
import { insuranceTone } from '../aircraft/insurance';
import './leader.css';

const VERDICT: Record<string, { word: string; why: string; go: boolean }> = {
  current: { word: 'INSURED', why: 'Cover is current', go: true },
  expiring: { word: 'INSURED', why: 'Cover expires soon', go: true },
  expired: { word: 'NOT INSURED', why: 'Cover has expired', go: false },
  none: { word: 'NOT INSURED', why: 'No policy on file', go: false },
};

export interface AircraftStatusCardProps {
  aircraft: AircraftDetail;
  today?: Date;
}

export function AircraftStatusCard({ aircraft, today }: AircraftStatusCardProps) {
  const tone = insuranceTone(aircraft, today);
  const verdict = VERDICT[tone] ?? VERDICT.none!;
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
      </header>

      <dl className="leader-rows">
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
