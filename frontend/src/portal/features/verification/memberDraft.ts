/**
 * The member verification panel's state and the request it sends.
 *
 * A draft holds the five fields a verifier may correct and the items to be verified
 * after the save.  Changing a field unchecks the item that covers it, as the server
 * clears it, so a verifier checks it again only after checking the new value.  An item
 * the person does not hold is never sent as verified.
 */
import type {
  AdminProfile,
  LeaderStatus,
  MedicalType,
  MemberVerificationPayload,
  PhotoIdType,
  PilotCertificateType,
  Profile,
  ProfileVerification,
  VerificationItem,
} from '@/portal/api/types';
import { isItemHeld } from './held';
import { ITEM_SLUGS } from './labels';

export interface MemberVerificationDraft {
  pilot_certificate_type: PilotCertificateType;
  certificate_number: string;
  medical_type: MedicalType;
  /** `YYYY-MM-DD`, or empty for no date. */
  medical_expiration: string;
  photo_id_type: PhotoIdType;
  /** The items checked as verified. */
  verified: VerificationItem[];
}

/** A field the panel edits, which is every draft key but the checked items. */
export type MemberField = Exclude<keyof MemberVerificationDraft, 'verified'>;

/** The item each field belongs to: changing the field clears that item. */
export const FIELD_ITEM: Record<MemberField, VerificationItem> = {
  pilot_certificate_type: 'certificate',
  certificate_number: 'certificate',
  medical_type: 'medical',
  medical_expiration: 'medical',
  photo_id_type: 'photo_id',
};

/** The items verified now, in the order the screens list them. */
function verifiedItems(verification: ProfileVerification): VerificationItem[] {
  return ITEM_SLUGS.filter((slug) => verification[slug].verified);
}

/** The draft a member check's status card opens the panel with. */
export function draftFromStatus(status: LeaderStatus): MemberVerificationDraft {
  return {
    pilot_certificate_type: status.certificate.type,
    certificate_number: status.certificate.number,
    medical_type: status.medical.type,
    medical_expiration: status.medical.expiration ?? '',
    photo_id_type: status.photo_id.type,
    verified: verifiedItems({
      certificate: status.certificate.verification,
      medical: status.medical.verification,
      photo_id: status.photo_id.verification,
    }),
  };
}

/** The draft a member record's profile opens the panel with. */
export function draftFromProfile(profile: Profile | AdminProfile): MemberVerificationDraft {
  return {
    pilot_certificate_type: profile.pilot_certificate_type,
    certificate_number: profile.certificate_number,
    medical_type: profile.medical_type,
    medical_expiration: profile.medical_expiration ?? '',
    photo_id_type: profile.photo_id_type,
    verified: verifiedItems(profile.verification),
  };
}

/**
 * `draft` with `field` set to `value`, and the field's item unchecked when the value
 * differs from the one the panel opened with.
 */
export function editField<Field extends MemberField>(
  draft: MemberVerificationDraft,
  initial: MemberVerificationDraft,
  field: Field,
  value: MemberVerificationDraft[Field],
): MemberVerificationDraft {
  const next = { ...draft, [field]: value };
  if (value === initial[field]) return next;
  const item = FIELD_ITEM[field];
  return { ...next, verified: next.verified.filter((slug) => slug !== item) };
}

/** `draft` with `item` checked or unchecked, keeping the screens' order. */
export function toggleItem(
  draft: MemberVerificationDraft,
  item: VerificationItem,
  checked: boolean,
): MemberVerificationDraft {
  const chosen = new Set(draft.verified);
  if (checked) chosen.add(item);
  else chosen.delete(item);
  return { ...draft, verified: ITEM_SLUGS.filter((slug) => chosen.has(slug)) };
}

/**
 * The request body: the fields that differ from the ones the panel opened with, and
 * the checked items the draft holds.  An untouched field is left out, so it is left
 * alone; a checked item the draft no longer holds is left out, so it ends unverified.
 */
export function memberVerificationPayload(
  initial: MemberVerificationDraft,
  draft: MemberVerificationDraft,
): MemberVerificationPayload {
  const changed = (field: MemberField): boolean => draft[field] !== initial[field];
  const payload: MemberVerificationPayload = {
    verified: draft.verified.filter((item) => isItemHeld(item, draft)),
  };
  if (changed('pilot_certificate_type')) {
    payload.pilot_certificate_type = draft.pilot_certificate_type;
  }
  if (changed('certificate_number')) payload.certificate_number = draft.certificate_number.trim();
  if (changed('medical_type')) payload.medical_type = draft.medical_type;
  if (changed('medical_expiration')) payload.medical_expiration = draft.medical_expiration || null;
  if (changed('photo_id_type')) payload.photo_id_type = draft.photo_id_type;
  return payload;
}
