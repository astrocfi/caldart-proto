=============
Notifications
=============

An account administrator can subscribe an email address to any set of
**events**: somebody signed up, a friend became a member, a membership ran out,
a donation arrived, an account was deactivated, an aircraft was added.  When an
event happens, every subscribed address that may hear about it is sent one
short email saying what happened, with a link to the record in the portal.  A
sign-up also goes to the contacts who receive the roster of the DART the person
chose, whether or not they are subscribed.

There is no queue and no worker.  The service that did the thing raises the
event; the notifications app, listening, builds the email at once and sends it
when the service's transaction commits.  The code is in
``backend/apps/notifications/``, the template pair is ``notification`` in
``backend/templates/emails/``, and the endpoints are in
:doc:`api-notifications`.  See :doc:`notification-events` for the catalog of
every event: where it is raised, and what its email carries.


Raising an event
================

``backend/caldart/events.py`` is the one way an event is raised.  It imports no
app, so a service on any layer may use it:

.. code-block:: python

   from caldart.events import emit

   emit("became_member", user=user, how="paid")

``emit(slug, **payload)`` hands the slug and the payload, model instances
included, to every handler registered with ``subscribe(handler)``.  Handlers
run at once, in registration order, inside the caller's transaction.  A slug
outside ``EVENT_SLUGS`` raises ``ValueError`` reading ``Unknown event '<slug>'``
before any handler runs, so a misspelled event fails a test instead of reaching
nobody.  ``unsubscribe(handler)`` removes one, which is how a test's recording
handler cleans up after itself.

A service raises its event once, at the point the thing has definitively
happened, after the change is saved, never in a serializer or a view.  The
payload is the keyword arguments that event documents: ``user``, ``payment``,
``mandate``, ``term``, ``aircraft``, ``actor``, and so on.

The catalog
-----------

``apps/notifications/events.py`` declares every event as a frozen ``Event``
in ``EVENTS``, keyed by slug and in the same order as ``EVENT_SLUGS``:

``slug``
   the name ``emit`` and a subscription's ``events`` use;
``label``
   the words the screen and the email log use, such as ``Sign-up``;
``category``
   one of ``CATEGORIES`` — ``Membership``, ``Money``, ``Accounts`` and
   ``Aircraft`` — the heading the screen groups it under;
``description``
   one sentence saying when it happens, the screen's tooltip;
``roles``
   the role slugs whose holders may receive it.  A system administrator and a
   Django superuser always may.

``backend/tests/test_notification_catalog.py`` holds the catalog and
``EVENT_SLUGS`` to the same slugs in the same order.


Who receives an event
=====================

A ``NotificationSubscription`` (:ref:`data-model-notifications`) names an
address and the events it hears about.  The address is set when the
subscription is set up, much as a report subscription's is
(:doc:`scheduled-reports`):

* When an account holds the address, compared without regard to case, the
  subscription is bound to that account, and every event chosen must be one a
  role of that account may receive.  A treasurer cannot be subscribed to
  sign-ups, for example, and a user administrator cannot hear about money.
* When no account holds it, the account administrator must tick a box
  confirming that the address, outside CalDART, may receive these
  notifications.

One address holds one subscription, stored in lower case.

The rule is applied again at every send (``recipient_may_receive`` in
``apps/notifications/services.py``).  An event goes to a subscription only when
the subscription is active, lists the event, and its recipient may receive it:
a bare address always may, and a bound account must be active and hold a role
the event allows.  An account that may not is skipped for that event, and
nothing is paused, since it may still hear about the other events it lists.  A
bound subscription follows its account to a changed address, and a bare
address an account has since taken is bound to that account
(``refresh_recipient``), so its roles decide from then on.

Editing applies the same rule: adding an event the bound account may not
receive is refused, and so is resuming a paused subscription that lists one.
Removing events is always allowed, so a subscription can be trimmed after its
account loses a role.

A sign-up (``signed_up``) goes, in addition, to every contact in
``dart.roster_recipients()`` when the person chose a DART, whether or not the
contact is subscribed.  Each address hears of one event once, however many
ways it qualifies.


Sending
=======

``apps/notifications/dispatch.py`` holds the handler the app registers in
``NotificationsConfig.ready()``.  For each event it:

1. builds the message with ``apps.notifications.messages.build_message``, while
   the objects the payload names are in hand;
2. reads the roster contacts of the chosen DART, for a sign-up;
3. arranges ``transaction.on_commit`` to send it, so a request that rolls back
   sends nothing.

When the transaction commits it reads the subscriptions, applies the rule
above, and sends one ``send_templated`` per recipient with the purpose
``notification_<slug>``, the bound account as ``user_id``, and the account's
name or the DART contact's name as ``to_name``, so the email log records each
one under ``Notification: <label>`` (:ref:`api-email-log`).  A send that fails,
whatever it raises, is recorded as failed in the email log, logged at ERROR
with the event and the exception class, never the address, and the next
recipient is still tried.  A payload the email cannot be built from is logged with its
traceback and sends nothing.  Nothing a notification does can fail the request
that raised the event.

The email
---------

Every notification is rendered from one template pair,
``emails/notification.{txt,html}``, the HTML on ``report_base.html``.  The
message is a ``Message`` with four parts:

``subject``
   ``<org name>: <headline>``;
``headline``
   one sentence, such as *Pat Quill signed up as a member*;
``lines``
   a few ``(label, value)`` pairs, such as ``Email``, ``DART`` and
   ``Joined as``;
``link``
   the record in the portal: ``SITE_URL`` plus ``/portal/admin/members/<id>``
   for a member or friend, ``/portal/admin/users/<id>`` for an account event,
   ``/portal/admin/payments/<id>`` for a payment, or
   ``/portal/admin/aircraft/<id>`` for an aircraft.  A removed aircraft has
   none.

Names are the account's display name, money is printed in dollars from integer
cents, and a date is ``MM/DD/YYYY`` (``caldart.dates``).  The footer says why the address hears of
it: subscribed to that notification, or listed to receive the DART's roster.


The data
========

``NotificationSubscription`` holds ``recipient_user``, ``recipient_email``,
``events`` (the slugs, in catalog order), ``is_active`` and ``created_by``; see
:ref:`data-model-notifications`.  The demo seed subscribes the account
administrator to every Membership and Accounts event and the treasurer to
every Money event, both set up by the account administrator.


Tests
=====

``backend/tests/test_notifications.py`` covers the model, the recipient rule
across roles, and each event's headline, lines, and link, built from factory
objects.  ``backend/tests/test_notification_sending.py`` covers the email log
purposes, the send on commit, who is sent the event and who is skipped, the
DART roster contacts, one email per address, and a refused send.
``backend/tests/test_notification_api.py`` covers the endpoints and their role
matrix.  A test that checks a service raises its event subscribes a recording
handler through ``caldart.events`` and asserts the slug and the payload; a
test that checks what is sent captures the commit with
``django_capture_on_commit_callbacks(execute=True)`` and reads ``mailoutbox``.
