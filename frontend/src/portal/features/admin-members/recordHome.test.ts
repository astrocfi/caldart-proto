import { describe, expect, it } from 'vitest';

import { recordHome } from './recordHome';

describe('recordHome', () => {
  it("leads a treasurer from a donor's record back to the donors report", () => {
    expect(recordHome({ kind: 'donor' }, ['member', 'treasurer', 'account_admin'])).toEqual({
      to: '/admin/payments/donors',
      label: 'Back to donors',
    });
  });

  it("leads a system administrator from a donor's record back to the donors report", () => {
    expect(recordHome({ kind: 'donor' }, ['member', 'system_admin']).to).toBe(
      '/admin/payments/donors',
    );
  });

  it("leads a reader without the donors report from a donor's record to the members", () => {
    expect(recordHome({ kind: 'donor' }, ['member', 'account_admin'])).toEqual({
      to: '/admin/members',
      label: 'Back to members',
    });
  });

  it("leads a treasurer from a member's record to the members", () => {
    expect(recordHome({ kind: 'member' }, ['member', 'treasurer', 'account_admin']).to).toBe(
      '/admin/members',
    );
  });

  it("leads a treasurer from a friend's record to the members", () => {
    expect(recordHome({ kind: 'friend' }, ['member', 'treasurer', 'account_admin']).to).toBe(
      '/admin/members',
    );
  });
});
