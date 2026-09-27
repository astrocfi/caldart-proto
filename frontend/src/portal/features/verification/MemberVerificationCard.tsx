/**
 * The Verification card on a member record: the pilot certificate, the medical, and the
 * photo ID, each with whether an authority has checked it, and **Verify** for a verifier.
 *
 * **Verify** swaps the list for the verification panel; a save or Cancel swaps it back.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { AdminProfile, LeaderStatus, VerificationItem } from '@/portal/api/types';
import { CERTIFICATE_LABELS, MEDICAL_LABELS } from '@/portal/choices';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { formatDate } from '@/portal/components/DateText';
import { VerifiedMark } from '@/portal/components/VerifiedMark';
import { MemberVerificationPanel } from './MemberVerificationPanel';
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
}

/** Lists a person's three items with their marks, and opens the panel on **Verify**. */
export function MemberVerificationCard({
  userId,
  profile,
  checkable,
  onSaved: handleSaved,
}: MemberVerificationCardProps): JSX.Element {
  const canVerify = useCanVerify() && checkable;
  const [verifying, setVerifying] = useState(false);

  if (verifying) {
    return (
      <MemberVerificationPanel
        userId={userId}
        initial={draftFromProfile(profile)}
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
        {ITEM_SLUGS.map((item) => (
          <li key={item} className="verification-items__row">
            <span className="verification-items__label">{ITEM_LABELS[item]}</span>
            <span className="verification-items__detail">{itemDetail(item, profile)}</span>
            <VerifiedMark verification={profile.verification[item]} />
          </li>
        ))}
      </ul>
    </Card>
  );
}
