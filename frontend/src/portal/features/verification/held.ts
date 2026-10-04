/**
 * Whether a person holds an item, and whether a date has passed.
 *
 * An item the person does not hold (a pilot certificate of *Not a pilot*, a medical
 * of *None*, a photo ID of *Not provided*) has nothing to verify, so every screen
 * draws it with no mark and the verification panel offers no box for it.  The
 * server applies the same rule: it never stamps an item that is not held.
 */
import type {
  MedicalType,
  PhotoIdType,
  PilotCertificateType,
  VerificationItem,
} from '@/portal/api/types';
import { daysUntil } from '@/portal/components/StatusDot';

/** The three coded fields that say which items a person holds. */
export interface HeldFacts {
  pilot_certificate_type: PilotCertificateType;
  medical_type: MedicalType;
  photo_id_type: PhotoIdType;
}

/** Each item's coded field, and the value that means the person does not hold it. */
const ITEM_FIELDS = {
  certificate: { key: 'pilot_certificate_type', none: 'none' },
  medical: { key: 'medical_type', none: 'none' },
  photo_id: { key: 'photo_id_type', none: 'not_provided' },
} as const satisfies Record<VerificationItem, { key: keyof HeldFacts; none: string }>;

/**
 * True when `facts` hold `item`, so there is something to verify.
 *
 * @param item - the verified item.
 * @param facts - the person's certificate, medical, and photo ID kinds.
 * @returns false for *Not a pilot*, a medical of *None*, and a photo ID of *Not provided*.
 */
export function isItemHeld(item: VerificationItem, facts: HeldFacts): boolean {
  const { key, none } = ITEM_FIELDS[item];
  return facts[key] !== none;
}

/**
 * True when `iso` names a day before `today`: a medical or a policy that has run out.
 *
 * A date counts as current up to and including its own day, and no date is never
 * lapsed.
 */
export function isLapsed(iso: string | null, today: Date = new Date()): boolean {
  const days = daysUntil(iso, today);
  return days !== null && days < 0;
}
