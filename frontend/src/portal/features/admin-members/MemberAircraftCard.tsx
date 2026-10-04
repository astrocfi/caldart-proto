/**
 * The Aircraft card on a member record: each airplane on the member's profile, with its
 * make and model and its insurance, linked to the aircraft record.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { AircraftSummary } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { InsuranceDot } from '@/portal/features/aircraft/InsuranceDot';
import './members.css';

/** The Aircraft card for the airplanes `aircraft` lists. */
export function MemberAircraftCard({ aircraft }: { aircraft: AircraftSummary[] }): JSX.Element {
  return (
    <Card title="Aircraft">
      {aircraft.length === 0 ? (
        <p className="muted">No aircraft on their profile.</p>
      ) : (
        <ul className="member-aircraft">
          {aircraft.map((one) => (
            <li key={one.id}>
              <Link className="num" to={`/admin/aircraft/${one.id}`}>
                {one.n_number}
              </Link>
              <span>{`${one.make} ${one.model}`.trim()}</span>
              <InsuranceDot aircraft={one} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
