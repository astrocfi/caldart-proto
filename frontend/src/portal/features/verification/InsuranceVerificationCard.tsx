/**
 * The Verification card on an aircraft record: the insurance on file and whether an
 * authority has checked it, with **Verify** for a verifier.
 *
 * Mirrors `MemberVerificationCard`. **Verify** swaps the list for the verification
 * panel; a save or Cancel swaps it back.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { AircraftDetail } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { formatDate } from '@/portal/components/DateText';
import { formatCents } from '@/portal/components/Money';
import { VerifiedMark } from '@/portal/components/VerifiedMark';
import { InsuranceVerificationPanel } from './InsuranceVerificationPanel';
import { useCanVerify } from './useCanVerify';
import './verification.css';

/** What the record holds for the insurance, in the words the status card uses. */
function insuranceDetail(aircraft: AircraftDetail): string {
  const parts: string[] = [];
  if (aircraft.insurance_carrier !== '') parts.push(aircraft.insurance_carrier);
  if (aircraft.insurance_policy_number !== '') parts.push(aircraft.insurance_policy_number);
  if (aircraft.insurance_liability_per_occurrence_cents > 0) {
    const occurrence = formatCents(aircraft.insurance_liability_per_occurrence_cents, {
      whole: true,
    });
    const person = formatCents(aircraft.insurance_liability_per_person_cents, { whole: true });
    parts.push(`${occurrence} / ${person}`);
  }
  if (aircraft.insurance_expiration !== null) {
    parts.push(`expires ${formatDate(aircraft.insurance_expiration)}`);
  }
  return parts.length === 0 ? 'Not on file' : parts.join(' · ');
}

export interface InsuranceVerificationCardProps {
  aircraft: AircraftDetail;
  /** Called with the saved record, so the page can take up any corrected field. */
  onSaved?: (aircraft: AircraftDetail) => void;
}

/** Lists an aircraft's insurance with its mark, and opens the panel on **Verify**. */
export function InsuranceVerificationCard({
  aircraft,
  onSaved: handleSaved,
}: InsuranceVerificationCardProps): JSX.Element {
  const canVerify = useCanVerify();
  const [verifying, setVerifying] = useState(false);

  if (verifying) {
    return (
      <InsuranceVerificationPanel
        aircraft={aircraft}
        onSaved={handleSaved}
        onClose={() => setVerifying(false)}
      />
    );
  }

  return (
    <Card
      title="Verification"
      footer={
        canVerify ? (
          <Button variant="secondary" small onClick={() => setVerifying(true)}>
            Verify
          </Button>
        ) : null
      }
    >
      <ul className="verification-items">
        <li className="verification-items__row">
          <span className="verification-items__label">Insurance</span>
          <span className="verification-items__detail">{insuranceDetail(aircraft)}</span>
          <VerifiedMark verification={aircraft.insurance_verification} />
        </li>
      </ul>
    </Card>
  );
}
