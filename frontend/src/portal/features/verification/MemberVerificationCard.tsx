/**
 * The Verification card on a member record: the pilot certificate, the medical, and the
 * photo ID, each with whether an authority has checked it, and **Verify** for a verifier.
 *
 * **Verify** swaps the list for the verification panel; a save or Cancel swaps it back.
 */
import { useCallback, useRef, useState } from 'react';
import type { JSX } from 'react';

import type { AdminProfile, LeaderStatus, VerificationItem } from '@/portal/api/types';
import { CERTIFICATE_LABELS, MEDICAL_LABELS } from '@/portal/choices';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { formatDate } from '@/portal/components/DateText';
import { VerifiedMark } from '@/portal/components/VerifiedMark';
import { usePanelFocus } from '@/portal/components/focus';
import { MemberVerificationPanel } from './MemberVerificationPanel';
import { isItemHeld, isLapsed } from './held';
import { ITEM_LABELS, ITEM_SLUGS, PHOTO_ID_LABELS } from './labels';
import { draftFromProfile } from './memberDraft';
import { useCanVerify } from './useCanVerify';
import './verification.css';

/** What the record holds for an item, in the words the status card uses. */
function itemDetail(item: VerificationItem, profile: AdminProfile): string {
  if (item === 'certificate') {
    const number = profile.certificate_number;
    const type = CERTIFICATE_LABELS[profile.pilot_certificate_type];
    return number === '' ? type : `${type} · ${number}`;
  }
  if (item === 'medical') {
    const type = MEDICAL_LABELS[profile.medical_type];
    return profile.medical_expiration === null
      ? type
      : `${type} · expires ${formatDate(profile.medical_expiration)}`;
  }
  return PHOTO_ID_LABELS[profile.photo_id_type];
}

/** What the record holds for every item, for the checks-only panel to show beside each box. */
function itemDetails(profile: AdminProfile): Record<VerificationItem, string> {
  return {
    certificate: itemDetail('certificate', profile),
    medical: itemDetail('medical', profile),
    photo_id: itemDetail('photo_id', profile),
  };
}

export interface MemberVerificationCardProps {
  userId: number;
  profile: AdminProfile;
  /**
   * Whether the verification endpoint accepts this member: `checkable_people()`
   * refuses a deactivated account or a donor with a 404, so **Verify** is hidden for
   * one rather than opening a panel whose save can only fail.
   */
  checkable: boolean;
  /** Called with the saved status card, so the page can take up any corrected field. */
  onSaved?: (status: LeaderStatus) => void;
  /** Open the panel with the checks alone, for a page whose own form edits the fields. */
  checksOnly?: boolean;
}

/**
 * Lists a person's three items with their marks, and opens the panel on **Verify**.  An
 * item the person does not hold has no mark, and a lapsed medical reads *Expired* before
 * its mark.
 */
export function MemberVerificationCard({
  userId,
  profile,
  checkable,
  onSaved: handleSaved,
  checksOnly = false,
}: MemberVerificationCardProps): JSX.Element {
  const canVerify = useCanVerify() && checkable;
  const [verifying, setVerifying] = useState(false);
  // The panel takes the card's place, Verify with it, so the button gets the focus back
  // as the panel closes.
  const verifyRef = useRef<HTMLButtonElement>(null);
  const handleCloseVerify = useCallback(() => setVerifying(false), []);
  const panelRef = usePanelFocus(verifying ? 'verify' : null, handleCloseVerify, verifyRef);

  if (verifying) {
    return (
      <div ref={panelRef}>
        <MemberVerificationPanel
          userId={userId}
          initial={draftFromProfile(profile)}
          onSaved={handleSaved}
          onClose={handleCloseVerify}
          checksOnly={checksOnly}
          details={checksOnly ? itemDetails(profile) : undefined}
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
        {ITEM_SLUGS.map((item) => (
          <li key={item} className="verification-items__row">
            <span className="verification-items__label">{ITEM_LABELS[item]}</span>
            <span className="verification-items__detail">{itemDetail(item, profile)}</span>
            {isItemHeld(item, profile) ? (
              <VerifiedMark
                verification={profile.verification[item]}
                expired={item === 'medical' && isLapsed(profile.medical_expiration)}
              />
            ) : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}
