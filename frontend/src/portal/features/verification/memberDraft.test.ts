import { describe, expect, it } from 'vitest';

import { editField, memberVerificationPayload, toggleItem } from './memberDraft';
import type { MemberVerificationDraft } from './memberDraft';

const INITIAL: MemberVerificationDraft = {
  pilot_certificate_type: 'private',
  certificate_number: '3181234',
  medical_type: 'third',
  medical_expiration: '2027-03-01',
  photo_id_type: 'passport',
  verified: ['certificate', 'medical', 'photo_id'],
};

describe('editField', () => {
  it.each([
    ['pilot_certificate_type', 'commercial', ['medical', 'photo_id']],
    ['certificate_number', '9999999', ['medical', 'photo_id']],
    ['medical_type', 'second', ['certificate', 'photo_id']],
    ['medical_expiration', '2028-01-01', ['certificate', 'photo_id']],
    ['photo_id_type', 'drivers_license', ['certificate', 'medical']],
  ] as const)('unticks the item %s belongs to', (field, value, left) => {
    expect(editField(INITIAL, INITIAL, field, value).verified).toEqual(left);
  });

  it('leaves the ticks alone when a field is put back to the value it opened with', () => {
    const edited = toggleItem(
      editField(INITIAL, INITIAL, 'medical_type', 'second'),
      'medical',
      true,
    );
    expect(editField(edited, INITIAL, 'medical_type', 'third').verified).toEqual([
      'certificate',
      'medical',
      'photo_id',
    ]);
  });
});

describe('toggleItem', () => {
  it('keeps the ticked items in the order the screens list them', () => {
    const none = { ...INITIAL, verified: [] };
    const ticked = toggleItem(toggleItem(none, 'photo_id', true), 'certificate', true);
    expect(ticked.verified).toEqual(['certificate', 'photo_id']);
  });

  it('unticks an item', () => {
    expect(toggleItem(INITIAL, 'medical', false).verified).toEqual(['certificate', 'photo_id']);
  });
});

describe('memberVerificationPayload', () => {
  it('sends only the ticked items when no field changed', () => {
    expect(memberVerificationPayload(INITIAL, INITIAL)).toEqual({
      verified: ['certificate', 'medical', 'photo_id'],
    });
  });

  it('sends a changed field, trimmed, beside the items', () => {
    const draft = { ...INITIAL, certificate_number: ' 9999999 ', verified: [] };
    expect(memberVerificationPayload(INITIAL, draft)).toEqual({
      certificate_number: '9999999',
      verified: [],
    });
  });

  it('sends a cleared medical date as null', () => {
    const draft = { ...INITIAL, medical_type: 'none' as const, medical_expiration: '' };
    expect(memberVerificationPayload(INITIAL, draft)).toEqual({
      medical_type: 'none',
      medical_expiration: null,
      verified: ['certificate', 'medical', 'photo_id'],
    });
  });

  it('sends a changed photo ID', () => {
    const draft = { ...INITIAL, photo_id_type: 'other' as const };
    expect(memberVerificationPayload(INITIAL, draft).photo_id_type).toBe('other');
  });
});
