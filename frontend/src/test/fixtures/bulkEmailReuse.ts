/**
 * Saved templates and recipient groups for the bulk email tests, each a complete API
 * shape with the fields a test cares about given. Not shipped.
 */
import type { EmailTemplate, GroupPerson, RecipientGroup } from '@/portal/api/types';

/** The monthly newsletter template, Operational, saved by Grace Holloway. */
export function makeTemplate(overrides: Partial<EmailTemplate> = {}): EmailTemplate {
  return {
    id: 3,
    name: 'Monthly newsletter',
    subject: 'News for {first_name}',
    body: '<p>The hangar is open.</p>',
    email_type: 1,
    email_type_name: 'Operational',
    reply_to: '',
    created_by: 'Grace Holloway',
    created_at: '2026-04-01T16:00:00Z',
    updated_at: '2026-04-05T17:30:00Z',
    ...overrides,
  };
}

/** The Board, a fixed group of two. */
export function makeGroup(overrides: Partial<RecipientGroup> = {}): RecipientGroup {
  return {
    id: 5,
    name: 'Board',
    kind: 'fixed',
    count: 2,
    needs_fixing: false,
    filter_sets: [],
    created_by: 'Grace Holloway',
    created_at: '2026-04-01T16:00:00Z',
    updated_at: '2026-04-05T17:30:00Z',
    ...overrides,
  };
}

/** Ann Able, a friend in the Marin DART. */
export function makeGroupPerson(overrides: Partial<GroupPerson> = {}): GroupPerson {
  return {
    user_id: 12,
    name: 'Ann Able',
    email: 'ann@example.org',
    kind: 'friend',
    dart_name: 'Marin DART',
    is_active: true,
    ...overrides,
  };
}
