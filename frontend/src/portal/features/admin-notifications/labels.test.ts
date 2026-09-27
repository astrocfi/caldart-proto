import { describe, expect, it } from 'vitest';

import { NOTIFICATION_EVENTS, makeNotificationSubscription } from '@test/handlers';
import { eventLabels, groupEvents, recipientLabel } from './labels';

describe('recipientLabel', () => {
  it("names a bound account's holder", () => {
    expect(recipientLabel(makeNotificationSubscription())).toBe('Ada Admin');
  });

  it('gives the bare address of one outside CalDART', () => {
    const outside = makeNotificationSubscription({
      recipient_user: null,
      recipient_name: '',
      recipient_email: 'board@example.org',
    });
    expect(recipientLabel(outside)).toBe('board@example.org');
  });
});

describe('eventLabels', () => {
  it('joins the labels of the events with commas, in the order given', () => {
    expect(eventLabels(['signed_up', 'donation_received'], NOTIFICATION_EVENTS)).toBe(
      'Sign-up, Donation received',
    );
  });

  it('gives the slug of an event the catalog does not list', () => {
    expect(eventLabels(['signed_up', 'mystery'], NOTIFICATION_EVENTS)).toBe('Sign-up, mystery');
  });

  it('is empty for no events', () => {
    expect(eventLabels([], NOTIFICATION_EVENTS)).toBe('');
  });
});

describe('groupEvents', () => {
  it('groups the catalog under its four categories, in order', () => {
    expect(groupEvents(NOTIFICATION_EVENTS).map((group) => group.category)).toEqual([
      'Membership',
      'Money',
      'Accounts',
      'Aircraft',
    ]);
  });

  it('keeps the catalog order within a category', () => {
    const aircraft = groupEvents(NOTIFICATION_EVENTS).find(
      (group) => group.category === 'Aircraft',
    );
    expect(aircraft?.events.map((event) => event.slug)).toEqual([
      'aircraft_added',
      'aircraft_changed',
      'aircraft_removed',
    ]);
  });

  it('leaves out a category with no events', () => {
    const money = NOTIFICATION_EVENTS.filter((event) => event.category === 'Money');
    expect(groupEvents(money).map((group) => group.category)).toEqual(['Money']);
  });
});
