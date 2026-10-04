import { describe, expect, it } from 'vitest';

import type { RoleSlug } from './api/types';
import { NAV_ITEMS, groupedNavItems, hasAnyRole, navEyebrow, visibleNavItems } from './nav';
import type { NavReader } from './nav';

const labels = (roles: RoleSlug[], reader: NavReader = {}): string[] =>
  visibleNavItems(roles, reader).map((item) => item.label);

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
  it('shows a plain member the membership entries, their messages, and their preferences', () => {
    expect(labels(['member'])).toEqual([
      'Dashboard',
      'My profile',
      'My aircraft',
      'Payments',
      'Donate',
      'Renew',
      'Change password',
      'Change email',
      'Messages',
      'Email preferences',
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
    expect(visible).not.toContain('Users and roles');
  });

  it.each([['verifier'], ['user_admin']] as const)(
    'gives %s both checks, where a person or an aircraft is verified',
    (role) => {
      const visible = labels(['member', role]);
      expect(visible).toEqual(expect.arrayContaining(['Member check', 'Aircraft check']));
    },
  );

  it('keeps the member list away from a verifier', () => {
    expect(labels(['member', 'verifier'])).not.toContain('Members');
  });

  it('gives account_admin the member, aircraft, and payment screens but not users', () => {
    const visible = labels(['member', 'account_admin']);
    expect(visible).toEqual(expect.arrayContaining(['Members', 'Aircraft register', 'Finance']));
    expect(visible).not.toContain('Users and roles');
    expect(visible).not.toContain('Health and database');
  });

  it('gives account_admin the reminder log', () => {
    expect(labels(['member', 'account_admin'])).toContain('Reminders');
  });

  it('gives dart_leader the member list, filed under Administration', () => {
    const administration = groupedNavItems(['member', 'dart_leader']).find(
      (bucket) => bucket.group === 'Administration',
    );
    expect(administration?.items.map((item) => item.to)).toEqual(['/admin/members']);
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

  it('gives account_admin the reports screen, straight after the reminder log', () => {
    const administration = groupedNavItems(['member', 'account_admin']).find(
      (bucket) => bucket.group === 'Administration',
    );
    const paths = administration?.items.map((item) => item.to) ?? [];
    expect(paths.indexOf('/admin/reports')).toBe(paths.indexOf('/admin/reminders') + 1);
  });

  it('gives account_admin the notifications screen, straight after the reports screen', () => {
    const administration = groupedNavItems(['member', 'account_admin']).find(
      (bucket) => bucket.group === 'Administration',
    );
    const paths = administration?.items.map((item) => item.to) ?? [];
    expect(paths.indexOf('/admin/notifications')).toBe(paths.indexOf('/admin/reports') + 1);
  });

  it.each([['treasurer'], ['user_admin'], ['dart_leader']] as const)(
    'keeps the notifications screen away from %s',
    (role) => {
      expect(labels(['member', role])).not.toContain('Notifications');
    },
  );

  it('gives a treasurer the emailed reports screen', () => {
    expect(labels(['member', 'treasurer'])).toContain('Emailed reports');
  });

  it('keeps the emailed reports screen away from dart_leader', () => {
    expect(labels(['member', 'dart_leader'])).not.toContain('Emailed reports');
  });

  it('offers the leader checks to account_admin, as the API and guards do', () => {
    const visible = labels(['member', 'account_admin']);
    expect(visible).toContain('Member check');
    expect(visible).toContain('Aircraft check');
  });

  it('gives a treasurer the finance area', () => {
    expect(labels(['member', 'treasurer'])).toContain('Finance');
  });

  it('keeps the member register away from a treasurer', () => {
    expect(labels(['member', 'treasurer'])).not.toContain('Members');
  });

  it('gives user_admin only the users screen on top of membership', () => {
    const visible = labels(['member', 'user_admin']);
    expect(visible).toContain('Users and roles');
    expect(visible).not.toContain('Members');
  });

  it('gives CalDART management the bulk email screens and nothing else on top of membership', () => {
    const member = labels(['member']);
    expect(labels(['member', 'management']).filter((label) => !member.includes(label))).toEqual([
      'Compose',
      'Drafts and scheduled',
      'Sent',
      'Templates',
      'Recipient groups',
      'Callouts',
      'Mail delivery',
    ]);
  });

  it('files Mail delivery in the Bulk email group, for management', () => {
    expect(NAV_ITEMS.find((item) => item.to === '/bulk-email/mail-delivery')).toMatchObject({
      group: 'Bulk email',
      roles: ['management'],
    });
  });

  it.each([['account_admin'], ['user_admin'], ['treasurer'], ['dart_leader']] as const)(
    'keeps Mail delivery away from %s',
    (role) => {
      expect(labels(['member', role])).not.toContain('Mail delivery');
    },
  );

  it('shows Mail delivery to a system administrator', () => {
    expect(labels(['member', 'system_admin'])).toContain('Mail delivery');
  });

  it('files the bulk email screens in a Bulk email group of their own', () => {
    const bulk = groupedNavItems(['member', 'management']).find(
      (bucket) => bucket.group === 'Bulk email',
    );
    expect(bulk?.items.map((item) => item.to)).toEqual([
      '/bulk-email/compose',
      '/bulk-email/drafts',
      '/bulk-email/sent',
      '/bulk-email/templates',
      '/bulk-email/groups',
      '/bulk-email/callouts',
      '/bulk-email/mail-delivery',
    ]);
  });

  it('gives a DART leader Compose, Drafts and scheduled, Sent, and Callouts, for their own DART', () => {
    const bulk = groupedNavItems(['member', 'dart_leader']).find(
      (bucket) => bucket.group === 'Bulk email',
    );
    expect(bulk?.items.map((item) => item.to)).toEqual([
      '/bulk-email/compose',
      '/bulk-email/drafts',
      '/bulk-email/sent',
      '/bulk-email/callouts',
    ]);
  });

  it.each([['account_admin'], ['user_admin'], ['treasurer']] as const)(
    'gives %s no Bulk email group',
    (role) => {
      const groups = groupedNavItems(['member', role]).map((bucket) => bucket.group);
      expect(groups).not.toContain('Bulk email');
    },
  );

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

  it('hides Renew from an effective friend, who has no membership to renew', () => {
    expect(labels(['member'], { isEffectiveFriend: true })).not.toContain('Renew');
  });

  it('leaves every other membership entry for an effective friend', () => {
    expect(labels(['member'], { isEffectiveFriend: true })).toEqual([
      'Dashboard',
      'My profile',
      'My aircraft',
      'Payments',
      'Donate',
      'Change password',
      'Change email',
      'Messages',
      'Email preferences',
    ]);
  });

  it('keeps Renew for a member who is not an effective friend', () => {
    expect(labels(['member'], { isEffectiveFriend: false })).toContain('Renew');
  });

  it('offers a lifetime member no Renew, since Donate is where they give', () => {
    expect(labels(['member'], { isLifetime: true })).not.toContain('Renew');
  });

  it('offers a lifetime member no second giving entry beside Donate', () => {
    expect(labels(['member'], { isLifetime: true })).not.toContain('Contribute');
  });

  it('writes every label in sentence case, with "and" rather than "&"', () => {
    const offending = NAV_ITEMS.map((item) => item.label).filter(
      (label) => label.includes('&') || /\s(?!DART)[A-Z]/.test(label),
    );
    expect(offending).toEqual([]);
  });
});

describe('the System group', () => {
  it('lists Health and database, Sent emails, and Scheduled, in that order', () => {
    const system = groupedNavItems(['member', 'system_admin']).find(
      (bucket) => bucket.group === 'System',
    );
    expect(system?.items.map((item) => [item.label, item.to])).toEqual([
      ['Health and database', '/system/health'],
      ['Sent emails', '/system/emails'],
      ['Scheduled', '/system/scheduled'],
    ]);
  });

  it('keeps every System entry to the system administrator', () => {
    const system = NAV_ITEMS.filter((item) => item.group === 'System');
    expect(system.map((item) => item.roles)).toEqual([
      ['system_admin'],
      ['system_admin'],
      ['system_admin'],
    ]);
  });
});

describe('the Bulk email group', () => {
  it('lists every entry in the sidebar order for a system admin', () => {
    const bulk = groupedNavItems(['member', 'system_admin']).find(
      (bucket) => bucket.group === 'Bulk email',
    );
    expect(bulk?.items.map((item) => item.label)).toEqual([
      'Compose',
      'Drafts and scheduled',
      'Sent',
      'Templates',
      'Recipient groups',
      'Callouts',
      'Email types',
      'Mail delivery',
    ]);
  });

  it('declares each entry with its path and the roles that open it', () => {
    expect(
      NAV_ITEMS.filter((item) => item.group === 'Bulk email').map((item) => [
        item.label,
        item.to,
        item.roles,
      ]),
    ).toEqual([
      ['Compose', '/bulk-email/compose', ['management', 'dart_leader']],
      ['Drafts and scheduled', '/bulk-email/drafts', ['management', 'dart_leader']],
      ['Sent', '/bulk-email/sent', ['management', 'dart_leader']],
      ['Templates', '/bulk-email/templates', ['management']],
      ['Recipient groups', '/bulk-email/groups', ['management']],
      ['Callouts', '/bulk-email/callouts', ['management', 'dart_leader']],
      ['Email types', '/bulk-email/types', ['system_admin']],
      ['Mail delivery', '/bulk-email/mail-delivery', ['management']],
    ]);
  });

  it.each([['management'], ['account_admin'], ['dart_leader']] as const)(
    'keeps the email types away from %s',
    (role) => {
      expect(labels(['member', role])).not.toContain('Email types');
    },
  );
});

describe('the Your email group', () => {
  it('gives every signed-in person their messages and email preferences', () => {
    const own = groupedNavItems(['member']).find((bucket) => bucket.group === 'Your email');
    expect(own?.items.map((item) => item.to)).toEqual(['/messages', '/email-preferences']);
  });

  it('keeps the messages and preferences out of the Bulk email group for management', () => {
    const bulk = groupedNavItems(['member', 'management']).find(
      (bucket) => bucket.group === 'Bulk email',
    );
    expect(bulk?.items.map((item) => item.to)).not.toContain('/messages');
  });
});

describe('groupedNavItems', () => {
  it('drops groups with nothing in them', () => {
    const groups = groupedNavItems(['member']).map((bucket) => bucket.group);
    expect(groups).toEqual(['Membership', 'Your email']);
  });

  it('orders groups consistently for a system admin', () => {
    const groups = groupedNavItems(['system_admin']).map((bucket) => bucket.group);
    expect(groups).toEqual([
      'Membership',
      'Your email',
      'Operations',
      'Bulk email',
      'Administration',
      'System',
    ]);
  });
});

describe('navEyebrow', () => {
  it.each([
    ['/', 'Membership'],
    ['/profile/aircraft', 'Membership'],
    ['/change-password', 'Membership'],
    ['/membership/join', 'Membership'],
    ['/messages/12', 'Your email'],
    ['/leader', 'Operations'],
    ['/leader/aircraft', 'Operations'],
    ['/bulk-email/drafts/4', 'Bulk email'],
    ['/admin/members/7', 'Administration'],
    ['/admin/users/3', 'Administration'],
    ['/admin/payments', 'Finance'],
    ['/admin/payments/renewals', 'Finance'],
    ['/admin/payments/members/9', 'Finance'],
    ['/admin/reports', 'Administration'],
    ['/system', 'System'],
    ['/system/health', 'System'],
  ])('heads %s with %s, the menu group it sits under', (path, eyebrow) => {
    expect(navEyebrow(path)).toBe(eyebrow);
  });

  it.each([['/login'], ['/join/profile'], ['/no-such-page']])(
    'gives %s, outside the menu, no eyebrow',
    (path) => {
      expect(navEyebrow(path)).toBeNull();
    },
  );
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
