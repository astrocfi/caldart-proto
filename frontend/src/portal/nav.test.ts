import { describe, expect, it } from 'vitest';

import type { RoleSlug } from './api/types';
import { NAV_ITEMS, groupedNavItems, hasAnyRole, visibleNavItems } from './nav';

const labels = (roles: RoleSlug[]): string[] => visibleNavItems(roles).map((item) => item.label);

describe('hasAnyRole', () => {
  it('grants entries with no role requirement to any user', () => {
    expect(hasAnyRole(['member'], [])).toBe(true);
  });

  it('matches on any one of the required roles', () => {
    expect(hasAnyRole(['account_admin'], ['user_admin', 'account_admin'])).toBe(true);
    expect(hasAnyRole(['member'], ['user_admin', 'account_admin'])).toBe(false);
  });

  it('lets system_admin through everything', () => {
    expect(hasAnyRole(['system_admin'], ['user_admin'])).toBe(true);
    expect(hasAnyRole(['system_admin'], ['dart_leader'])).toBe(true);
  });
});

describe('visibleNavItems', () => {
  it('shows a plain member only the membership entries', () => {
    expect(labels(['member'])).toEqual([
      'Dashboard',
      'My profile',
      'My aircraft',
      'Payments',
      'Renew',
      'Change password',
    ]);
  });

  it('gives every signed-in member their own payments screen', () => {
    expect(visibleNavItems([]).map((item) => item.to)).toContain('/payments');
  });

  it('offers every route the portal can render', () => {
    // A nav entry pointing at nothing, or a screen nothing links to, is the
    // integration bug this catches.
    expect(NAV_ITEMS.map((item) => item.to)).toContain('/change-password');
  });

  it('adds the leader entries for dart_leader', () => {
    const visible = labels(['member', 'dart_leader']);
    expect(visible).toContain('Member check');
    expect(visible).toContain('Aircraft check');
    expect(visible).not.toContain('Users & roles');
  });

  it('gives account_admin the member, aircraft, and payment screens but not users', () => {
    const visible = labels(['member', 'account_admin']);
    expect(visible).toEqual(expect.arrayContaining(['Members', 'Aircraft', 'Payments']));
    expect(visible).not.toContain('Users & roles');
    expect(visible).not.toContain('System');
  });

  it('gives account_admin the reminder log', () => {
    expect(labels(['member', 'account_admin'])).toContain('Reminders');
  });

  it('keeps the reminder log away from dart_leader', () => {
    expect(labels(['member', 'dart_leader'])).not.toContain('Reminders');
  });

  it('files the reminder log under Administration', () => {
    const administration = groupedNavItems(['member', 'account_admin']).find(
      (bucket) => bucket.group === 'Administration',
    );
    expect(administration?.items.map((item) => item.to)).toContain('/admin/reminders');
  });

  it('offers the leader checks to account_admin, as the API and guards do', () => {
    const visible = labels(['member', 'account_admin']);
    expect(visible).toContain('Member check');
    expect(visible).toContain('Aircraft check');
  });

  it('gives a treasurer the finance area', () => {
    expect(labels(['member', 'treasurer'])).toContain('Payments');
  });

  it('keeps the member register away from a treasurer', () => {
    expect(labels(['member', 'treasurer'])).not.toContain('Members');
  });

  it('gives user_admin only the users screen on top of membership', () => {
    const visible = labels(['member', 'user_admin']);
    expect(visible).toContain('Users & roles');
    expect(visible).not.toContain('Members');
  });

  it('shows website_admin nothing extra (Wagtail lives outside the portal)', () => {
    expect(labels(['member', 'website_admin'])).toEqual(labels(['member']));
  });

  it('shows system_admin every entry', () => {
    expect(visibleNavItems(['system_admin'])).toHaveLength(NAV_ITEMS.length);
  });

  it('preserves declaration order', () => {
    const visible = visibleNavItems(['system_admin']).map((item) => item.to);
    expect(visible).toEqual(NAV_ITEMS.map((item) => item.to));
  });
});

describe('groupedNavItems', () => {
  it('drops groups with nothing in them', () => {
    const groups = groupedNavItems(['member']).map((bucket) => bucket.group);
    expect(groups).toEqual(['Membership']);
  });

  it('orders groups consistently for a system admin', () => {
    const groups = groupedNavItems(['system_admin']).map((bucket) => bucket.group);
    expect(groups).toEqual(['Membership', 'Operations', 'Administration', 'System']);
  });
});

describe('nav definition', () => {
  it('has unique paths', () => {
    const paths = NAV_ITEMS.map((item) => item.to);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it('matches exactly the entries a deeper sibling would otherwise mark', () => {
    expect(NAV_ITEMS.filter((item) => item.end).map((item) => item.to)).toEqual([
      '/',
      '/profile',
      '/leader',
    ]);
  });
});
