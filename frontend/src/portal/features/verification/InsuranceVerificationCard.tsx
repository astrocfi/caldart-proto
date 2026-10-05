/**
 * The Verification card on an aircraft record: the insurance on file and whether an
 * authority has checked it, with **Verify** for a verifier.
 *
 * Mirrors `MemberVerificationCard`. **Verify** swaps the list for the verification
 * panel; a save or Cancel swaps it back.
 */
import { useCallback, useRef, useState } from 'react';
import type { JSX } from 'react';

import type { AircraftDetail } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { formatDate } from '@/portal/components/DateText';
import { VerifiedMark } from '@/portal/components/VerifiedMark';
import { usePanelFocus } from '@/portal/components/focus';
import { liabilityLine } from '@/portal/features/aircraft/insurance';
import { InsuranceVerificationPanel } from './InsuranceVerificationPanel';
import { useCanVerify } from './useCanVerify';
import './verification.css';

/** What the record holds for the insurance, in the words the status card uses. */
function insuranceDetail(aircraft: AircraftDetail): string {
  const parts: string[] = [];
  if (aircraft.insurance_carrier !== '') parts.push(aircraft.insurance_carrier);
  if (aircraft.insurance_policy_number !== '') parts.push(aircraft.insurance_policy_number);
  const liability = liabilityLine(aircraft);
  if (liability !== '') parts.push(liability);
  if (aircraft.insurance_expiration !== null) {
    parts.push(`expires ${formatDate(aircraft.insurance_expiration)}`);
  }
  return parts.length === 0 ? 'No insurance on file' : parts.join(' · ');
}

export interface InsuranceVerificationCardProps {
  aircraft: AircraftDetail;
  /** Called with the saved record, so the page can take up any corrected field. */
  onSaved?: (aircraft: AircraftDetail) => void;
}

/**
 * Lists an aircraft's insurance with its mark, and opens the panel on **Verify**.  With
 * no policy on file there is nothing to verify, so there is no mark; a lapsed policy
 * reads *Expired* before its mark.
 */
export function InsuranceVerificationCard({
  aircraft,
  onSaved: handleSaved,
}: InsuranceVerificationCardProps): JSX.Element {
  const canVerify = useCanVerify();
  const [verifying, setVerifying] = useState(false);
  // The panel takes the card's place, Verify with it, so the button gets the focus back
  // as the panel closes.
  const verifyRef = useRef<HTMLButtonElement>(null);
  const handleCloseVerify = useCallback(() => setVerifying(false), []);
  const panelRef = usePanelFocus(verifying ? 'verify' : null, handleCloseVerify, verifyRef);

  if (verifying) {
    return (
      <div ref={panelRef}>
        <InsuranceVerificationPanel
          aircraft={aircraft}
          onSaved={handleSaved}
          onClose={handleCloseVerify}
        />
      </div>
    );
  }

  return (
    <Card
      title="Verification"
      footer={
        canVerify ? (
          <Button ref={verifyRef} variant="secondary" small onClick={() => setVerifying(true)}>
            Verify
          </Button>
        ) : null
      }
    >
      <ul className="verification-items">
        <li className="verification-items__row">
          <span className="verification-items__label">Insurance</span>
          <span className="verification-items__detail">{insuranceDetail(aircraft)}</span>
          {aircraft.insurance_expiration === null ? null : (
            <VerifiedMark
              verification={aircraft.insurance_verification}
              expired={!aircraft.insurance_is_current}
            />
          )}
        </li>
      </ul>
    </Card>
  );
}
