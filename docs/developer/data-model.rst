==========
Data model
==========

Every model in the project, its fields, the rules that hold it together, and
the two implementations of the one piece of arithmetic everything else depends
on: whether a person's membership is current.  The endpoints that expose these
models are in :doc:`api-reference`, and :doc:`architecture` shows which app
owns each one.

House rules that apply throughout:

- **Money is integer cents in USD.**  There is no ``Decimal`` and no float
  anywhere in the schema.  ``amount_cents = 4500`` is $45.00.
- **Dates are ``DateField``** unless the name ends in ``_at``, which means a
  timezone-aware ``DateTimeField``.  The project timezone is
  ``America/Los_Angeles`` and ``USE_TZ`` is on, so "today" always means
  ``django.utils.timezone.localdate()``.
- **Most models carry ``created_at`` and ``updated_at``**, inherited from
  ``caldart.models.TimestampedModel`` (``User`` declares its own pair,
  because it inherits from ``AbstractUser`` instead).  ``cms.BasePage`` does
  not, because Wagtail's ``Page`` keeps its own dates: ``first_published_at``
  , ``last_published_at``, and ``latest_revision_created_at``, alongside the
  revision history behind them.  ``cms.SiteSettings`` carries no dates either,
  and Wagtail's ``BaseSiteSetting`` adds only the one-to-one to
  ``wagtailcore.Site``, so editing the settings overwrites the single row and
  records nothing about when or by whom.  ``aircraft.AircraftChange`` carries its
  own ``changed_at`` and no row is ever updated, so the inherited pair would only
  duplicate it.
- **``DEFAULT_AUTO_FIELD`` is ``BigAutoField``.**

Entity relationships
====================

Two diagrams: the domain schema, and the Wagtail page models layered on top of
it.  The only edge between them is ``cms.DartPage.dart``, which appears in
both.

Domain schema
-------------

.. only:: graphviz

   .. graphviz::
      :caption: The domain schema.  A **solid arrow** is a foreign key, drawn
                from the table that holds the column to the table it
                references and labeled with the field name and its delete
                rule.  A **double line** is a many-to-many.  A line labeled
                ``1--1`` is a one-to-one.  A **dotted arrow** is the provider
                lookup, a slug in a column rather than a foreign key.  A
                **dashed box** is an abstract model with no table of its own,
                and an **empty arrowhead** points from a subclass to the
                abstract model it inherits.  ``TimestampedModel`` is drawn
                once rather than eight times: ``Dart``, ``DartContact``,
                ``MemberProfile``, ``MembershipPlan``, ``Membership``,
                ``Aircraft``, ``Payment``, ``Refund``, ``RenewalMandate``,
                ``RenewalAttempt``, ``ReminderLog``, and ``EmailLog`` all
                inherit it.
      :alt: Entity-relationship diagram of the CalDART domain models

      digraph caldart_domain {
          rankdir=LR;
          bgcolor="transparent";
          node [shape=box, style="rounded", fontname="Helvetica", fontsize=10];
          edge [fontname="Helvetica", fontsize=9];

          Timestamped [label="caldart.TimestampedModel (abstract)\l  created_at, updated_at\l", style="rounded,dashed"];
          Provider [label="payments.Provider (abstract)\l  start(payment)\l  confirm(payment, **kwargs)\l  handle_webhook(request)\l", style="rounded,dashed"];
          Stripe [label="StripeProvider\l  slug = stripe\l"];
          PayPal [label="PayPalProvider\l  slug = paypal\l"];
          Mock [label="MockProvider\l  slug = mock\l"];

          User [label="accounts.User\l  email (unique, ci)\l  first_name, last_name\l  is_active, is_superuser\l  roles: derived from groups\l"];
          Group [label="auth.Group\l  name = role slug\l"];
          Profile [label="members.MemberProfile\l  phone, address_line1, city,\l  state, postal_code\l  aviation, volunteer, admin notes\l"];
          Dart [label="darts.Dart\l  name (unique), airport_identifiers\l  website_url, is_active\l  roster_sent_at\l"];
          Contact [label="darts.DartContact\l  name, title, phone, email\l  sort_order, receives_roster\l"];
          Plan [label="members.MembershipPlan\l  name (unique), slug (unique)\l  price_cents, duration_days\l"];
          Membership [label="members.Membership\l  starts_on, ends_on\l  status, source\l"];
          Payment [label="payments.Payment\l  amount_cents, fee_cents, net_cents\l  provider, wallet, status, provider_ref\l  received_on, reconciled_on, note\l"];
          Refund [label="payments.Refund\l  amount_cents, reason, note\l  status, provider_ref, refunded_at\l"];
          Mandate [label="payments.RenewalMandate\l  provider, method_ref, method_label\l  status, failure_count\l  contribution_cents, next_charge_on\l"];
          Attempt [label="payments.RenewalAttempt\l  scheduled_on, outcome, error\l  noticed_at, attempted_at\l  result_emailed_at\l"];
          Aircraft [label="aircraft.Aircraft\l  n_number (unique)\l  make, model, insurance_*\l"];
          AircraftChange [label="aircraft.AircraftChange\l  changed_at, kind\l  fields (JSON)\l"];
          Reminder [label="reminders.ReminderLog\l  kind, sent_at, to_email\l  (user, membership, kind) unique\l"];
          Email [label="mail.EmailLog\l  to_email, purpose, subject\l  sent_at, status, error, attachments\l"];
          DartPage [label="cms.DartPage\l  leader_name, leader_contact, body\l"];

          User -> Group [label="groups (m2m)", dir=none, color="black:black"];
          Profile -> User [label="user  1--1, CASCADE", arrowhead=none];
          Profile -> Dart [label="dart (null, SET_NULL)"];
          Profile -> Aircraft [label="aircraft (m2m)\lrelated: pilots", dir=none, color="black:black"];
          Membership -> User [label="user (CASCADE)"];
          Membership -> User [label="granted_by (null, SET_NULL)"];
          Membership -> Plan [label="plan (PROTECT)"];
          Membership -> Payment [label="payment  1--1 (null, SET_NULL)", arrowhead=none];
          Payment -> User [label="user (PROTECT)"];
          Payment -> Plan [label="plan (null, PROTECT)"];
          Payment -> User [label="reconciled_by, recorded_by (null, SET_NULL)"];
          Refund -> Payment [label="payment (PROTECT)\lrelated: refunds"];
          Refund -> User [label="requested_by (null, SET_NULL)"];
          Mandate -> User [label="user  1--1, CASCADE", arrowhead=none];
          Mandate -> Plan [label="plan (null, PROTECT)"];
          Attempt -> Mandate [label="mandate (CASCADE)\lrelated: attempts"];
          Attempt -> Membership [label="membership (CASCADE)"];
          Attempt -> Payment [label="payment (null, SET_NULL)"];
          Attempt -> Attempt [label="retry_of (null, SET_NULL)"];
          Aircraft -> User [label="created_by, updated_by (null, SET_NULL)"];
          AircraftChange -> Aircraft [label="aircraft (CASCADE)\lrelated: changes"];
          AircraftChange -> User [label="changed_by (null, SET_NULL)"];
          Reminder -> User [label="user (CASCADE)"];
          Reminder -> Membership [label="membership (CASCADE)"];
          Email -> User [label="user (null, SET_NULL)"];
          Contact -> Dart [label="dart (CASCADE)\lrelated: contacts"];
          DartPage -> Dart [label="dart (null, SET_NULL)"];

          Payment -> Provider [label="provider slug, via get_provider()", style=dotted];
          Stripe -> Provider [arrowhead=empty];
          PayPal -> Provider [arrowhead=empty];
          Mock -> Provider [arrowhead=empty];
      }

.. only:: not graphviz

   Install Graphviz and rebuild for a drawn version of this diagram.  The
   drawing, the node list and the edge list below carry the same models
   , fields, and relations.

   .. code-block:: text

      Abstract models (dashed boxes in the drawn version; no table of their own)
      -------------------------------------------------------------------------
      caldart.TimestampedModel   created_at, updated_at
                                 inherited by Dart, DartContact, MemberProfile,
                                 MembershipPlan, Membership, Aircraft
                                 , Payment, Refund, RenewalMandate
                                 , RenewalAttempt, ReminderLog, and EmailLog
      payments.Provider          start(payment), confirm(payment, **kwargs),
                                 handle_webhook(request)
                                 implemented by StripeProvider (slug stripe),
                                 PayPalProvider (slug paypal) and
                                 MockProvider (slug mock)

      The tables
      ----------
                           auth.Group  (name = role slug)
                                |
                                | groups (m2m); User.roles is derived from it
                                |
                          accounts.User
             1--1  .------------+------------.  created_by
                   |            |            |
          members.MemberProfile |      aircraft.Aircraft
             |         |        |            ^
             | dart    |        |            | aircraft (m2m,
             |         '--------|------------'   "planes commonly flown",
             v                  |                related name: pilots)
          darts.Dart          +-------------------.
             ^                  |                   |
             | dart             |                   |
          cms.DartPage    members.Membership   payments.Payment ....> Provider
                             |  |  |     '--- 1--1 ---'  |  ^
                             |  |  '-> members.MembershipPlan <-'  |
                             |  |                                  | payment
                             |  '--- granted_by --> accounts.User   '- payments.Refund
                             |
                             '--- reminders.ReminderLog --> accounts.User

          mail.EmailLog --- user --> accounts.User

          payments.RenewalMandate --- 1--1 --- accounts.User
                 ^          '--------> members.MembershipPlan
                 | mandate
          payments.RenewalAttempt --- membership --> members.Membership
                 |  '-------- payment --> payments.Payment
                 '----------- retry_of --> payments.RenewalAttempt

      Nodes and their key fields
      --------------------------
      accounts.User           email (unique, case-insensitive), first_name,
                              last_name, is_active, is_superuser;
                              roles is derived from groups
      auth.Group              name = role slug
      members.MemberProfile   phone, address_line1, city, state, postal_code,
                              the aviation and volunteer fields, admin notes
      darts.Dart              name (unique), airport_identifiers,
                              website_url, is_active, roster_sent_at
      members.MembershipPlan  name (unique), slug (unique), price_cents,
                              duration_days
      members.Membership      starts_on, ends_on, status, source
      payments.Payment        amount_cents, fee_cents, net_cents, provider,
                              wallet, status, provider_ref, received_on,
                              reconciled_on, note
      payments.Refund         amount_cents, reason, note, status,
                              provider_ref, refunded_at
      payments.RenewalMandate provider, method_ref, method_label, status,
                              failure_count, contribution_cents, next_charge_on
      payments.RenewalAttempt scheduled_on, outcome, error, noticed_at,
                              attempted_at, result_emailed_at
      aircraft.Aircraft       n_number (unique), make, model, insurance_*
      aircraft.AircraftChange changed_at, kind (created | updated),
                              fields (JSON list of column names)
      reminders.ReminderLog   kind, sent_at, to_email;
                              (user, membership, kind) unique together
      mail.EmailLog           to_email, purpose, subject, sent_at, status,
                              error, attachments
      darts.DartContact       name, title, phone, email, sort_order,
                              receives_roster
      cms.DartPage            leader_name, leader_contact, body

      Edges
      -----
      members.MemberProfile.user     -> accounts.User            1--1, CASCADE
      members.MemberProfile.dart     -> darts.Dart               FK, SET_NULL, nullable
      darts.DartContact.dart         -> darts.Dart               FK, CASCADE
      members.MemberProfile.aircraft -> aircraft.Aircraft        m2m, related name pilots
      accounts.User.groups           -> auth.Group               m2m
      members.Membership.user        -> accounts.User            FK, CASCADE
      members.Membership.granted_by  -> accounts.User            FK, SET_NULL, nullable
      members.Membership.plan        -> members.MembershipPlan   FK, PROTECT
      members.Membership.payment     -> payments.Payment         1--1, SET_NULL, nullable
      payments.Payment.user          -> accounts.User            FK, PROTECT
      payments.Payment.plan          -> members.MembershipPlan   FK, PROTECT, nullable
      payments.Payment.provider      -> payments.Provider        slug, via get_provider()
      payments.Payment.reconciled_by -> accounts.User            FK, SET_NULL, nullable
      payments.Payment.recorded_by   -> accounts.User            FK, SET_NULL, nullable
      payments.Refund.payment        -> payments.Payment         FK, PROTECT, related name refunds
      payments.Refund.requested_by   -> accounts.User            FK, SET_NULL, nullable
      payments.RenewalMandate.user   -> accounts.User            1--1, CASCADE
      payments.RenewalMandate.plan   -> members.MembershipPlan   FK, PROTECT, nullable
      payments.RenewalAttempt.mandate    -> payments.RenewalMandate  FK, CASCADE, related name attempts
      payments.RenewalAttempt.membership -> members.Membership       FK, CASCADE
      payments.RenewalAttempt.payment    -> payments.Payment         FK, SET_NULL, nullable
      payments.RenewalAttempt.retry_of   -> payments.RenewalAttempt  FK, SET_NULL, nullable
      aircraft.Aircraft.created_by   -> accounts.User            FK, SET_NULL, nullable
      aircraft.Aircraft.updated_by   -> accounts.User            FK, SET_NULL, nullable
      aircraft.AircraftChange.aircraft   -> aircraft.Aircraft    FK, CASCADE, related name changes
      aircraft.AircraftChange.changed_by -> accounts.User        FK, SET_NULL, nullable
      reminders.ReminderLog.user     -> accounts.User            FK, CASCADE
      reminders.ReminderLog.membership -> members.Membership     FK, CASCADE
      mail.EmailLog.user             -> accounts.User            FK, SET_NULL, nullable
      cms.DartPage.dart              -> darts.Dart               FK, SET_NULL, nullable

CMS page models
---------------

.. only:: graphviz

   .. graphviz::
      :caption: The Wagtail page models.  A **dashed box** is an abstract model
                with no table of its own, and an **empty arrowhead** points
                from a subclass to the class it inherits.  A **solid arrow** is
                a foreign key labeled with its field name and delete rule, and
                a line labeled ``1--1`` is a one-to-one.  Which page may live
                under which is in :doc:`cms`, not in this diagram.
      :alt: Inheritance and foreign keys of the CalDART Wagtail page models

      digraph caldart_cms {
          rankdir=LR;
          bgcolor="transparent";
          node [shape=box, style="rounded", fontname="Helvetica", fontsize=10];
          edge [fontname="Helvetica", fontsize=9];

          Page [label="wagtailcore.Page\l  title, slug, live, path\l"];
          BasePage [label="cms.BasePage (abstract)\l  base_form_class =\l    RestrictedBlocksPageForm\l  body_headings\l  show_on_this_page\l", style="rounded,dashed"];
          MembersOnly [label="cms.MembersOnlyMixin (abstract)\l  members_only\l  serve(): members-only wall, 403\l", style="rounded,dashed"];

          Home [label="cms.HomePage\l  hero_heading, hero_lede,\l  hero_image_caption, CTAs,\l  mission, welcome_body,\l  missions_flown, tax status\l"];
          Standard [label="cms.StandardPage\l  intro, body\l"];
          NewsIndex [label="cms.NewsIndexPage\l  intro\l"];
          News [label="cms.NewsPage\l  date, intro, body\l"];
          EventIndex [label="cms.EventIndexPage\l  intro\l"];
          Event [label="cms.EventPage\l  date, time, location,\l  intro, body\l"];
          DartIndex [label="cms.DartIndexPage\l  intro, body\l"];
          DartPage [label="cms.DartPage\l  leader_name, leader_contact, body\l"];
          Contact [label="cms.ContactPage\l  intro, body\l"];
          Settings [label="cms.SiteSettings\l  (wagtail BaseSiteSetting)\l  org_name, tagline, contact_email,\l  duty_phone, ein, donate_url,\l  theme, footer_text\l"];

          Image [label="wagtailimages.Image"];
          Site [label="wagtailcore.Site"];
          Dart [label="darts.Dart"];

          BasePage -> Page [arrowhead=empty];
          Home -> BasePage [arrowhead=empty];
          Standard -> BasePage [arrowhead=empty];
          Standard -> MembersOnly [arrowhead=empty];
          NewsIndex -> BasePage [arrowhead=empty];
          News -> BasePage [arrowhead=empty];
          News -> MembersOnly [arrowhead=empty];
          EventIndex -> BasePage [arrowhead=empty];
          Event -> BasePage [arrowhead=empty];
          DartIndex -> BasePage [arrowhead=empty];
          DartPage -> BasePage [arrowhead=empty];
          Contact -> BasePage [arrowhead=empty];

          Home -> Image [label="hero_image (null, SET_NULL)"];
          News -> Image [label="image (null, SET_NULL)"];
          Contact -> Dart [label="dart (CASCADE)\lrelated: contacts"];
          DartPage -> Dart [label="dart (null, SET_NULL)"];
          Settings -> Site [label="site  1--1, CASCADE", arrowhead=none];
      }

.. only:: not graphviz

   Install Graphviz and rebuild for a drawn version of this diagram.  The
   drawing, the node list and the edge list below carry the same models
   , fields, and relations.

   .. code-block:: text

      Abstract models (dashed boxes in the drawn version; no table of their own)
      -------------------------------------------------------------------------
      cms.BasePage           base_form_class = RestrictedBlocksPageForm,
                             body_headings, show_on_this_page
                             inherits wagtailcore.Page; inherited by HomePage,
                             StandardPage, NewsIndexPage, NewsPage,
                             EventIndexPage, EventPage, DartIndexPage,
                             DartPage, and ContactPage
      cms.MembersOnlyMixin   members_only; serve() renders the members-only
                             wall with HTTP 403
                             mixed into StandardPage and NewsPage

      The page types
      --------------
                        wagtailcore.Page
                               ^
                               | inherits
                        cms.BasePage (abstract)     cms.MembersOnlyMixin
                               ^                       (abstract)
          .--------.-----------+-----------.--------.       ^
          |        |           |           |        |       |
       HomePage  NewsIndexPage |      DartIndexPage |       |
          |        |           |           |        |       |
          |     NewsPage ------|-----------|--------|-------'
          |        |           |           |        |
          |        |      StandardPage ----|--------'
          |        |                       |
          |        |                    DartPage --> darts.Dart
          |        |                                 (dart, SET_NULL)
          |        |
          |     EventIndexPage, EventPage, and ContactPage inherit
          |     cms.BasePage too, with no members-only mixin
          |        '--> wagtailimages.Image  (image, SET_NULL)
          '-----------> wagtailimages.Image  (hero_image, SET_NULL)

                     ContactPage  (intro, body; details from site settings)

                     cms.SiteSettings --- 1--1 ---> wagtailcore.Site

      Nodes and their key fields
      --------------------------
      wagtailcore.Page     title, slug, live, path
      cms.HomePage         hero_heading, hero_lede, hero_image_caption, the
                           three CTAs, mission, welcome_body, missions_flown,
                           tax status
      cms.StandardPage     intro, body
      cms.NewsIndexPage    intro
      cms.NewsPage         date, intro, body
      cms.EventIndexPage   intro
      cms.EventPage        date, time, location, intro, body
      cms.DartIndexPage    intro, body
      cms.DartPage         leader_name, leader_contact, body
      cms.ContactPage      intro, body
      cms.SiteSettings     org_name, tagline, contact_email, duty_phone,
                           mailing_address, ein,
                           donate_url, facebook_url, twitter_url, theme,
                           footer_text

      Edges
      -----
      cms.BasePage             inherits wagtailcore.Page
      cms.HomePage             inherits cms.BasePage
      cms.StandardPage         inherits cms.BasePage, cms.MembersOnlyMixin
      cms.NewsIndexPage        inherits cms.BasePage
      cms.NewsPage             inherits cms.BasePage, cms.MembersOnlyMixin
      cms.EventIndexPage       inherits cms.BasePage
      cms.EventPage            inherits cms.BasePage
      cms.DartIndexPage        inherits cms.BasePage
      cms.DartPage             inherits cms.BasePage
      cms.ContactPage          inherits cms.BasePage
      cms.HomePage.hero_image  -> wagtailimages.Image   FK, SET_NULL, nullable
      cms.NewsPage.image       -> wagtailimages.Image   FK, SET_NULL, nullable
      cms.DartPage.dart        -> darts.Dart          FK, SET_NULL, nullable
      cms.SiteSettings.site    -> wagtailcore.Site      1--1, CASCADE

accounts
========

``User``
--------

A custom ``AbstractUser`` in which **email is the login**.  There is no
``username`` field at all (``username = None``), ``USERNAME_FIELD = "email"``
and ``REQUIRED_FIELDS`` is empty, so ``createsuperuser`` asks for an email
address and a password and nothing else.

.. list-table::
   :header-rows: 1
   :widths: 30 22 48

   * - Field
     - Type
     - Notes
   * - ``email``
     - ``EmailField``
     - unique, and unique **case-insensitively** — see below
   * - ``first_name``, ``last_name``
     - ``CharField(150)``
     - both may be blank
   * - ``is_active``
     - ``BooleanField``
     - from ``AbstractUser``; a deactivated account cannot sign in
   * - ``is_staff``, ``is_superuser``
     - ``BooleanField``
     - kept in step with the ``website_admin`` / ``system_admin`` roles
   * - ``created_at``, ``updated_at``
     - ``DateTimeField``
     - ``created_at`` defaults to ``timezone.now`` and is not editable

**Invariants.**

- Email uniqueness is enforced twice: the field's own ``unique=True``, and a
  ``UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique")``.
  The manager's ``get_by_natural_key`` looks up with ``email__iexact``, so
  ``Marta@example.org`` and ``marta@example.org`` are one account for sign-in
  as well as for creation.
- ``save()`` strips surrounding whitespace from the email.
- Default ordering is ``["last_name", "first_name", "email"]``, with a matching
  index.

**Derived properties.**

``roles``
    The role slugs the user holds, as a list in privilege order.  Computed from
    ``self.groups`` intersected with the known slugs, so a group that is not a
    role (a Wagtail editor group, say) never shows up as one.
``has_role(slug)`` / ``has_any_role(*slugs)``
    Role tests in which **``system_admin`` implies every other role**.
``add_role`` / ``remove_role`` / ``set_roles``
    ``set_roles`` replaces exactly the role groups, keeping any non-role group
    the user is in.
``membership_status``
    Delegates to ``members.services.membership_status`` — see
    :ref:`membership-status` below.
``can_access_members_content``
    ``True`` when the user is a superuser, **or** their membership is current,
    **or** they hold any role other than plain ``member``.  This is the gate
    the CMS members-only wall and ``GET /site/config`` both use.  A DART leader
    whose own membership has lapsed still reads members-only pages.
``display_name``
    Full name, falling back to the email address.

Roles
-----

**Roles are Django ``Group`` rows whose ``name`` is the role slug.**  There is
no ``Role`` model.  That makes adding a role a data change, and it lets Wagtail
reuse the same groups for editor permissions.  The slugs and their
descriptions live in ``apps/accounts/roles.py``:

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Slug
     - Grants
   * - ``member``
     - own profile, own payments and membership, join and renew, and
       members-only content while the membership is current
   * - ``dart_leader``
     - \+ look up any member and see membership, medical, certificate, and
       aircraft insurance currency
   * - ``user_admin``
     - \+ list users, assign roles, activate or deactivate accounts, trigger
       password resets
   * - ``treasurer``
     - \+ see every payment, fee, refund, and renewal; issue refunds, record
       payments taken by hand, reconcile periods, and run the financial
       reports
   * - ``account_admin``
     - \+ create, edit, and delete members and profiles, grant or extend
       memberships manually, manage aircraft, and run payment, membership and
       aircraft reports
   * - ``website_admin``
     - \+ the Wagtail admin: create, edit, delete, and publish pages, images,
       documents, redirects, and site settings
   * - ``system_admin``
     - everything above, plus backups, health, reminder runs and Django
       superuser access

Rules:

- ``member`` is granted at registration, so "members" and "accounts" are the
  same population.  The account administrator's member list is every ``User``
  row, narrowed by ``?role=``.
- Roles are additive; ``ROLE_SLUGS`` is ordered least to most privileged, and
  that order is what ``GET /roles`` and ``User.roles`` return.
- ``system_admin`` passes every role check in the API, as does any Django
  superuser; the three payment-confirmation endpoints are owner-only for
  everybody (see :ref:`api-permission-matrix`).
- ``accounts.services.effective_roles`` is the role set the account guards
  compare: the account's own slugs, plus ``system_admin`` whenever
  ``is_superuser`` is set.  ``createsuperuser`` sets that flag without adding
  the role group, so the two are one kind of account to the member delete guard,
  to the guard on moving the ``system_admin`` role, and to the account-edit
  guard (:ref:`account-edit-guard`), which lets an administrator change another
  account's ``email`` or ``is_active`` only while holding every role that account
  holds.
- ``STAFF_ROLE_SLUGS`` is every slug except ``member``, and is what
  ``can_access_members_content`` tests.
- ``manage.py seed_roles`` creates the groups and is idempotent.  It is also
  called from the ``accounts.0002_seed_roles`` data migration, so a freshly
  migrated database already has them.

darts
=====

``Dart``
--------

A local Disaster Airlift Response Team.

``name`` (unique), ``airport_identifiers``, ``website_url``,
``is_active``, ``roster_sent_at``.  Ordered by ``name``, everywhere: a reader
looking for their own team scans for its name, and no hand-kept ordering can
go stale.  ``__str__`` is ``"Angwin (2O3)"``.  ``roster_sent_at`` is when the
team's monthly roster last went out to its people, or null when none has; the
roster sender stamps it and nothing else writes it.

``airport_identifiers`` is every field the team flies from, comma-separated
and stored in the canonical ``"CCR, C83"`` form that ``save()`` writes: a
DART is organized around its airports and several cover more than one, so
Contra Costa is ``CCR, C83`` and San Diego lists nine.  Each identifier is
exactly three letters or digits.  The four-letter ICAO form is the same field
with a ``K`` in front, and that ``K`` is trimmed on the way in -- ``KCRQ`` is
stored as ``CRQ`` -- so one airport is written one way everywhere; a
three-character identifier that begins with ``K`` is left alone, because Kelso
really is ``KLS``.  ``airports`` gives the list and ``home_airport`` its first
entry, which is what a single-line summary shows.

Sixteen are seeded from ``DARTS`` in ``apps/members/seed.py``, each with the
handful of example contacts ``seed_darts`` generates, the leader and the
deputy leader ticked to receive the roster.  ``cms.DartPage``
points at this table with a nullable ``SET_NULL`` foreign key, so deleting a
DART leaves its page in place with no DART attached, and the airports are
never retyped in the CMS.  A DART is identified by the fields it flies from,
so it carries no town of its own.

``DartContact``
---------------

One named volunteer who runs a DART, and how to reach them: ``name``,
``title``, optional ``phone`` (stored as ``XXX-XXX-XXXX``) and optional
``email``, ordered by ``sort_order``, and ``receives_roster`` (default
false), whether the person is sent the team's roster.  A DART lists any
number of them, and a person without an email address may be ticked, to be
skipped when the roster goes out.  The foreign key cascades, so a contact has
no life without its DART.

This is deliberately not a link to a member account: the person an emergency
manager asks for by name may hold no account at all, and the listing outlives
whoever holds the job this year.

members
=======

``MemberProfile``
-----------------

A ``OneToOneField`` to ``User`` with ``related_name="profile"``, holding
everything the join form collects.  Deleting the user cascades.

*Contact*
    ``phone``, ``phone_extension``, ``phone_alt``, ``phone_alt_extension``,
    ``address_line1``, ``address_line2``, ``city``, ``state`` (2 characters,
    default ``CA``), ``postal_code``, ``county``, ``emergency_contact_name``,
    ``emergency_contact_phone``, ``emergency_contact_phone_extension``.  Every
    number is stored as ``XXX-XXX-XXXX`` and each carries its own extension.

*Aviation*
    ``home_airport_identifier`` (3 characters, never a leading ``K``),
    ``home_airport_city``, ``dart``
    (``SET_NULL``, nullable), ``air_care_alliance_number``,
    ``pilot_certificate_type``, ``certificate_number``, ``ifr_rated``,
    ``ratings``, ``medical_type``, ``medical_expiration``,
    ``flight_review_date``, ``total_hours``, and ``aircraft`` — a
    ``ManyToManyField`` to ``aircraft.Aircraft`` labeled "planes commonly
    flown", with ``related_name="pilots"``.

*Volunteer interests*
    Seven booleans: ``vol_mission_pilot``, ``vol_ground_team``,
    ``vol_exercise_training``, ``vol_member_support``, ``vol_fundraising``,
    ``vol_social_media``, ``vol_newsletter``.

*Membership*
    ``member_since`` — the day this person first joined, stamped once and
    never moved by a renewal or a gap.  ``profile_updated_at`` — when profile
    information was last written: a member's own edit, an administrator's
    edit to the profile or to the account's name or email, an aircraft
    attached or detached, or the profile's creation.  ``NULL`` until one of
    those happens, so a seeded profile nobody has touched answers ``NULL``;
    never moved by a payment, a membership grant or renewal, a reminder, or a
    role change.  Written by ``apps.members.services.touch_profile``.

*Admin only*
    ``notes`` (text) and ``how_heard``.  Neither is in the member-facing
    serializer; both appear on ``GET /admin/members/{id}``.

**Choice sets.**

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Field
     - Values
   * - ``pilot_certificate_type``
     - ``none``, ``student``, ``sport``, ``recreational``, ``private``,
       ``commercial``, ``atp``
   * - ``ifr_rated``
     - ``na``, ``yes``, ``no``
   * - ``medical_type``
     - ``none``, ``basicmed``, ``first``, ``second``, ``third``
   * - ``ratings``
     - a JSON list drawn from ``instrument``, ``multi_engine``, ``cfi``,
       ``cfii``, ``mei``, ``seaplane``, ``helicopter``, ``glider``

``ratings`` is a ``JSONField(default=list)``.  The database does not police its
contents; the serializer does, rejecting unknown values, removing duplicates
and preserving the order given.

**Invariants**, all enforced in the API serializers rather than the model, so
that the message a person reads can be specific:

- A ``medical_type`` other than ``none`` requires a ``medical_expiration``.
- A ``pilot_certificate_type`` other than ``none`` requires a
  ``certificate_number``.
- ``state`` is two letters, stored upper-case; ``postal_code`` is ``#####`` or
  ``#####-####``.
- Cross-field rules are evaluated against the row **as it would be after the
  write**, so a one-field ``PATCH`` is judged on the whole profile.

**Derived properties.**

``medical_is_current``
    ``False`` when ``medical_type`` is ``none`` **or** ``medical_expiration``
    is ``NULL``; otherwise ``medical_expiration >= today``.  BasicMed and class
    medicals both use the same stored date — the model does not try to compute
    a BasicMed expiry from the exam date.
``is_complete``
    ``True`` when every field in ``MemberProfile.COMPLETE_FIELDS`` has a
    value: ``phone``, ``address_line1``, ``city``, ``state``,
    ``postal_code``, and ``pilot_certificate_type``.  ``state`` defaults to
    ``CA`` and so never blocks the check on its own.  This is the single
    definition of "complete": the accounts ``UserSerializer`` delegates
    to it for the ``profile_complete`` flag that drives the dashboard nudge and
    the join wizard's step gating, and the portal form's
    ``REQUIRED_PROFILE_FIELDS`` (``frontend/src/portal/features/profile/form.ts``)
    mirrors the same list, so a profile the form accepts is a profile the
    server calls complete.  See :ref:`profile-completeness`.
``display_name``
    Full name, falling back to the email address.

``MembershipPlan``
------------------

A purchasable term.  ``name`` (unique), ``slug`` (unique), ``price_cents``,
``duration_days`` (**nullable — ``NULL`` means lifetime**), ``is_active``,
``sort_order``, ``description``.

Two are seeded: **Annual**, ``annual``, 4500 cents, 365 days; and **Life**,
``life``, 65000 cents, no duration.  ``is_lifetime`` is
``duration_days is None``.  ``GET /plans`` and the checkout only offer active
plans.

``Membership``
--------------

One row per paid or granted term.  A member with a long history has many rows,
and the current one is worked out rather than flagged.

.. list-table::
   :header-rows: 1
   :widths: 24 20 56

   * - Field
     - Type
     - Notes
   * - ``user``
     - FK, ``CASCADE``
     - ``related_name="memberships"``
   * - ``plan``
     - FK, ``PROTECT``
     - a plan with terms against it cannot be deleted
   * - ``starts_on``
     - date
     - required
   * - ``ends_on``
     - date, nullable
     - ``NULL`` means lifetime
   * - ``status``
     - choice
     - ``active``, ``expired``, ``canceled``
   * - ``source``
     - choice
     - ``payment``, ``manual``, ``seed``
   * - ``payment``
     - ``OneToOneField``, ``SET_NULL``
     - ``related_name="membership"``; the link back to what paid for it
   * - ``granted_by``
     - FK User, ``SET_NULL``
     - who granted a ``manual`` term
   * - ``note``
     - ``CharField(255)``
     - free text, shown in the admin history

Ordered ``["-starts_on", "-id"]`` — newest first — with indexes on
``(user, -ends_on)`` and ``(status, ends_on)``.

``covers(on_date=None)`` is the row-level test: the term is ``active``, it has
started, and either it is lifetime or it has not run out.

.. _membership-status:

Membership status
=================

"Is this person a current member?" is the question the whole system turns on,
and it is answered in two places that must agree.

The service
-----------

``apps.members.services.membership_status(user, on_date=None)`` returns::

    {
        "status": "current" | "new" | "expired" | "none",
        "expires_on": date | None,     # None for lifetime
        "plan": str | None,
        "is_lifetime": bool,
    }

``current``
    Some active term covers ``on_date``.
``expired``
    No term covers ``on_date``, but at least one term that is neither canceled
    nor ``new`` has started.  ``expires_on`` and ``plan`` come from the most
    recent such term.
``new``
    Nothing has ever covered them and nothing paid has started, but a term is
    on file stored as ``new``: they joined and have not paid.  Somebody who
    lapsed and has since started an unpaid term stays ``expired``, because the
    history is what this value distinguishes.
``none``
    Nothing at all.  Everything else is ``None`` / ``False``.

Those four values are ``apps.members.models.MembershipState``, a
``TextChoices`` nothing stores: it is the computed answer, as against
``MembershipStatusChoices``, which is the state written on a term.  Every
serializer that offers the status, the ``?status=`` filter on the member list
and the payload builders take their values from it, so the backend spells them
in exactly one place.  The portal's ``MembershipState`` union, in
``frontend/src/portal/api/types.ts``, is the same four values.

The subtlety is ``expires_on`` for a current member.  Renewing early creates a
term that starts the day *after* the present one ends, and the member is
entitled to see next year's date immediately.  So ``_coverage()`` does not stop
at the covering term: it walks forward through the chain of back-to-back active
terms — each one starting no later than the day after the previous one ends and
reaching further into the future — and reports the end of the walk.  A lifetime
term anywhere in the chain wins, and ``expires_on`` becomes ``None``.

``activate_term``
-----------------

``activate_term(user, plan, *, source, payment=None, granted_by=None,
starts_on=None, note="")`` is the **only** way a ``Membership`` row is created
outside the seed.  It is wrapped in ``transaction.atomic`` and:

1. **Is idempotent on ``payment``.**  If a term already exists for that
   payment it is returned unchanged, so a client confirmation and a webhook
   racing each other cannot produce two terms.
2. Computes ``starts_on`` when the caller does not supply one:

   - already a lifetime member → today (a second term is harmless);
   - current, with a latest expiry on or after today → **that expiry plus one
     day**;
   - otherwise → today.

3. Computes ``ends_on`` as ``starts_on + duration_days - 1``, or ``None`` for a
   lifetime plan.  A 365-day term bought today therefore ends 364 days from
   today, inclusive of both ends.
4. Creates the row with ``status="active"``.

``expire_lapsed_memberships(on_date=None)`` flips ``active`` terms whose
``ends_on`` has passed to ``expired`` and returns how many it changed.  The
reminder scanner runs it first; the seed runs it to keep demo data honest.
Note that ``membership_status`` does not depend on it — a term that has run out
but has not been flipped still reads as expired, because ``_current_term``
tests the dates, not the flag.

.. _membership-status-sql:

The same rules in SQL
---------------------

The account administrator's member list filters and orders on membership
status *before* paginating.  Recomputing the service's answer per row would be
a query per member, and could not be filtered or sorted in the database at all.
So ``apps/members/services.py`` restates the identical rules as correlated
subqueries in ``membership_annotations()``, beside the Python it mirrors.

The translation, term by term:

``covers_today``
    ``Exists`` an active term with ``starts_on <= today`` and (``ends_on IS
    NULL`` or ``ends_on >= today``).  This is ``_current_term``.

``coverage_end``
    ``_coverage`` walks forward from the covering term.  In SQL that walk is
    replaced by its endpoint: **the earliest active term ending on or after
    today that no other active term continues**.  A *follower* is an active
    term for the same user starting no later than ``ends_on + 1 day`` and
    reaching further (``ends_on IS NULL`` or ``ends_on > ends_on``).

    .. code-block:: text

       boundaries = active terms
                    WHERE user = this user
                      AND ends_on IS NOT NULL
                      AND ends_on >= today
                      AND NOT EXISTS (follower)
                    ORDER BY ends_on
       coverage_end = first(boundaries).ends_on

    That endpoint is the same date the Python walk stops at: any term *inside*
    a chain has a follower by definition, and any term in a *later* chain ends
    after the gap, so the earliest boundary and the end of the walk coincide.
    ``NULL`` means the chain reaches a lifetime term, or that nothing covers
    today — which is why ``coverage_plan`` and ``lifetime_plan`` are separate
    annotations, and ``membership_payload`` reads the lifetime one when
    ``coverage_end`` is ``NULL``.

``has_started_term`` / ``past_end`` / ``past_plan``
    Non-canceled terms with ``starts_on <= today``, ordered by ``ends_on``
    descending with ``NULL`` first and then ``starts_on`` descending.  The
    first row is what ``membership_status`` reports for an expired member.

``joined_on``
    The earliest ``starts_on`` across all of the user's terms, canceled ones
    included.

``with_membership(queryset, today=None)`` hangs the lot on any ``User``
queryset, and ``today`` is read when it is called, so a queryset built inside a
view answers for the day of the request rather than the day the process
started.

``membership_payload(user)`` reads those annotations back in exactly the shape
``membership_status`` returns, so a caller cannot tell which implementation
answered.  ``membership_of(user)`` chooses between the two: the annotations
when the row carries them, ``membership_status`` when it does not.

Every list that shows a membership status reads it from these annotations, so
its query count does not depend on how many rows it returns: the member list
and its exports, ``GET /admin/users``, the DART leader's search, and the
``pilots`` attached to an aircraft record.

The account administrator's list adds two annotations of its own, in
``apps/members/api/admin_filters.py``:

``full_name``
    ``first_name`` and ``last_name`` concatenated, so ``?search=`` matches a
    full name in one ``icontains``.

``effective_expiry``
    ``coverage_end`` when ``covers_today``, else ``past_end``.  This is what
    ``?ordering=expires_on`` sorts on, with ``NULL`` — lifetime members and
    people who never joined — forced to the end in both directions.

.. important::

   Two implementations of one rule drift.  ``backend/tests/
   test_members_admin_status.py`` builds fourteen deliberately awkward
   histories — early renewals, three-term chains, gaps, overlaps,
   cancellations, a lifetime plan bought to follow an annual one, a term ending
   exactly today — and asserts the service and the SQL agree on every one.  If
   you change either, change both and add a history to that file.

aircraft
========

``Aircraft``
------------

One airframe, shared by every member who flies it.  There is one register, not
one list per member: ``MemberProfile.aircraft`` attaches an existing row rather
than copying it, so an insurance renewal entered once is right for everybody.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Field
     - Notes
   * - ``n_number``
     - ``CharField(12)``, **unique**, normalized on save
   * - ``make``, ``model``, ``year``
     - ``year`` nullable
   * - ``owner_type``
     - ``individual``, ``fbo``, ``club``
   * - ``owner_name``, ``owner_contact``
     - ``owner_contact`` is free text — email or phone
   * - ``seats``
     - nullable small integer
   * - ``insurance_carrier``, ``insurance_policy_number``
     - free text
   * - ``insurance_liability_per_occurrence_cents``
     - ``PositiveBigIntegerField``, default 0
   * - ``insurance_liability_per_person_cents``
     - ``PositiveBigIntegerField``, default 0
   * - ``insurance_hull_cents``
     - nullable
   * - ``insurance_expiration``
     - nullable date
   * - ``notes``
     - text
   * - ``created_by``
     - FK User, ``SET_NULL``; who added the record
   * - ``updated_by``
     - FK User, ``SET_NULL``; who last wrote the record, beside the inherited
       ``updated_at``
   * - ``is_active``
     - "in service"

**N-number normalization** is the invariant that makes the register usable.
``normalize_n_number()`` strips everything that is not a letter or a digit,
upper-cases what is left, and prefixes ``N`` when the result starts with a
digit.  ``save()`` applies it, so ``12345``, ``n12345``, ``N-12345``, and
``n-12345`` are all stored as ``N12345`` and collide on the unique constraint
as they should.  A mark that already begins with a letter keeps it, so
``c-gabc`` becomes ``CGABC``.

The API normalizes in ``NNumberField.to_internal_value`` — *before* the
uniqueness validator runs, which is what makes a duplicate typed in a different
shape a clean 400 rather than a database error.  ``GET /aircraft/lookup``
normalizes the query term the same way.

**Derived properties.**

``insurance_is_current``
    ``False`` when ``insurance_expiration`` is ``NULL``; otherwise
    ``insurance_expiration >= today``.  "No policy on file" and "policy
    expired" are different states in the UI but both fail this test.
``insurance_summary``
    ``"$1,000,000 / $100,000 · exp 2027-03-01"`` — per-occurrence over
    per-person, then the expiry.  ``"No insurance on file"`` when there is
    neither a liability limit nor an expiry.
``display_name``
    ``"N12345 — Cessna 172S"``.

**Who may change one.**  Any signed-in member may create an aircraft, and
``created_by`` is set from the session.  The member who created it may edit it;
an ``account_admin`` may edit any; **only** an ``account_admin`` may delete
one, creator or not.  A record whose ``created_by`` is ``NULL`` is
administrator-only.

``AircraftChange``
------------------

One write to a register record.  A record is shared by every member who flies
the airframe, so an edit to its insurance is an edit to everybody's answer; the
history is what lets an administrator tell a correction from a renewal.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Field
     - Notes
   * - ``aircraft``
     - FK Aircraft, ``CASCADE``, related name ``changes``; deleting the record
       deletes its history
   * - ``changed_by``
     - FK User, ``SET_NULL``; ``NULL`` for a change no signed-in account made
   * - ``changed_at``
     - set on insert
   * - ``kind``
     - ``created`` or ``updated``
   * - ``fields``
     - ``JSONField``, the column names the write moved; empty on a ``created``
       row and on a save that altered nothing

``aircraft.services.record_change()`` writes the row and stamps ``updated_by``
on the record in the same call, and the register's create and update handlers
are its only callers, so no write can leave the trail behind.  Rows read newest
first, the primary key breaking a tie between two written in the same instant.
:doc:`api-aircraft` covers ``GET /aircraft/{id}/changes``, which is
``account_admin`` only.

payments
========

``Payment``
-----------

One attempt to pay for a membership term, make a contribution, or both.

.. list-table::
   :header-rows: 1
   :widths: 36 64

   * - Field
     - Notes
   * - ``user``
     - FK, ``PROTECT`` — the payment outlives the account
   * - ``plan``
     - FK, ``PROTECT``, **nullable** — ``NULL`` is a pure donation
   * - ``amount_cents``
     - the total charged
   * - ``plan_amount_cents``
     - the plan's share, 0 for a donation
   * - ``contribution_cents``
     - the optional donation added at checkout
   * - ``currency``
     - ``"usd"``
   * - ``provider``
     - ``stripe``, ``paypal``, ``mock``, ``manual`` (recorded by hand)
   * - ``wallet``
     - how the member paid: ``card``, ``apple_pay``, ``google_pay``, or
       ``link`` from the Stripe charge (:doc:`payments-setup`), ``paypal``
       for PayPal, ``mock`` for the mock provider, ``check``, ``cash``,
       ``bank_transfer`` or ``other`` for a payment recorded by hand, and
       ``unknown`` (the default) when the provider does not say
   * - ``provider_ref``
     - PaymentIntent id or PayPal order id
   * - ``status``
     - ``pending``, ``succeeded``, ``failed``, ``partially_refunded``,
       ``refunded``
   * - ``completed_at``
     - nullable datetime, set when the payment succeeds
   * - ``fee_cents``
     - the provider's fee, as the provider reported it
   * - ``net_cents``
     - what reached CalDART's balance, as the provider reported it
   * - ``receipt_sent_at``
     - nullable datetime — when CalDART's own receipt was last emailed
   * - ``received_on``
     - nullable date — for a payment recorded by hand, the day the money
       arrived
   * - ``reconciled_on``
     - nullable date — when a treasurer matched it to a bank statement
   * - ``reconciled_by``
     - FK ``User``, ``SET_NULL``, nullable — who matched it
   * - ``note``
     - a treasurer's note: the check number, the reason for a manual entry
   * - ``recorded_by``
     - FK ``User``, ``SET_NULL``, nullable — the administrator who recorded a
       payment taken by hand
   * - ``raw``
     - ``JSONField`` — the last provider payload, for forensics

**Derived, not stored.**  ``refunded_cents`` is the sum of the payment's
succeeded refunds; ``kind`` is ``membership``, ``contribution`` or ``both``,
read from the plan and the contribution; ``paid_on`` is the ledger date, which
is ``received_on`` for a payment recorded by hand and the local date of
``completed_at`` for every other provider; and ``receipt_number`` is
``CALDART-`` followed by the id padded to six digits.

**Invariants.**

- ``UniqueConstraint(fields=["provider", "provider_ref"])`` with the condition
  ``~Q(provider_ref="")``.  One Stripe PaymentIntent maps to one payment row,
  but the many pending rows that never got a reference do not collide.
- ``amount_cents`` is **never** taken from the client.  ``create_checkout``
  recomputes it as ``plan.price_cents + contribution_cents`` and refuses a
  total of zero.
- ``user`` is ``PROTECT``, which makes the payment table the ledger the
  accounts can rely on: revenue and donations for a closed period cannot
  disappear because somebody tidied up a departed member.  Deleting an account
  that has any payment raises ``ProtectedError``, whether the delete comes from
  the API, the Django admin, a management command or a shell.
  ``DELETE /admin/members/{user_id}`` turns that into a **403** with a message
  pointing at deactivation (:doc:`api-members`); deactivating keeps the member,
  the profile, the terms and the payments and only stops the sign-in.
- The two ways the Wagtail admin deletes an account — the delete view at
  ``/admin/users/delete/<id>/`` and the ``Delete`` bulk action on the users
  listing — are stopped before they write, by the ``before_delete_user`` and
  ``before_bulk_action`` hooks in ``apps/payments/wagtail_hooks.py``.  Each
  sends the operator back to the users listing with that same sentence as an
  error message; one protected account refuses a whole bulk batch, because the
  bulk delete is a single query that cannot succeed in part.
- ``partially_refunded`` and ``refunded`` say how much of the payment has been
  given back; the ``Refund`` rows beneath it carry the amounts, and
  ``refunded_cents`` adds the succeeded ones up.  Both are values the schema
  accepts and nothing yet writes: the service that issues a refund is described
  in :doc:`roadmap`.

Contribution tiers are a module constant, not a table:
``CONTRIBUTION_TIERS`` in ``apps/payments/models.py`` — No contribution,
Participating $20, Bronze $100, Silver $300, Gold $1,000, Diamond $3,000,
Platinum $10,000 — served by ``GET /payments/config``.  The checkout also
accepts any other amount.

**The service layer** (``apps/payments/services.py``) is the only thing that
changes a payment's state:

``create_checkout(user, plan_slug, contribution_cents, provider)``
    Validates the provider and the plan, recomputes the total, and creates a
    ``pending`` row.
``mark_succeeded(payment, *, wallet, raw, provider_ref)``
    Takes ``SELECT … FOR UPDATE``, returns immediately if the payment is
    already ``succeeded``, otherwise records the outcome and calls
    ``activate_term`` when there is a plan.  **Idempotent**, which is what lets
    the client confirmation and the webhook race safely.
``mark_failed(payment, raw)``
    Never downgrades a succeeded payment.
``record_provider_event(payment, payload)``
    Files a notification under ``raw["last_webhook"]`` without changing state.
    The PayPal webhook is a recorder; the capture call is the authority.

``Refund``
----------

Money given back against one payment, in whole or in part.  A payment may carry
several.

.. list-table::
   :header-rows: 1
   :widths: 36 64

   * - Field
     - Notes
   * - ``payment``
     - FK, ``PROTECT``, related name ``refunds``
   * - ``amount_cents``
     - what was given back
   * - ``reason``
     - ``requested_by_member``, ``duplicate``, ``error``, ``fraudulent``,
       ``other``
   * - ``note``
     - the treasurer's own sentence, blank by default
   * - ``status``
     - ``pending``, ``succeeded``, ``failed``
   * - ``provider_ref``
     - the Stripe or PayPal refund id; blank for a manual or mock refund
   * - ``requested_by``
     - FK ``User``, ``SET_NULL``, nullable — ``NULL`` when the refund was
       issued in the provider's own dashboard and reached CalDART by webhook
   * - ``refunded_at``
     - nullable datetime, set when the provider confirms it
   * - ``raw``
     - ``JSONField`` — the provider's refund payload

**Invariants.**

- A payment's succeeded refunds never total more than its ``amount_cents``.
  The rule lives in the refund service rather than in the database, because it
  is a sum across rows.
- ``payment`` is ``PROTECT`` for the same reason ``Payment.user`` is: a refund
  is a financial record, and the payment it reverses cannot be deleted out from
  under it.

``RenewalMandate``
------------------

One member's standing authority for CalDART to charge a saved payment method
once a year: their membership renewal, a contribution, or both.
``OneToOneField`` on the user, related name ``renewal_mandate``, so a member
holds at most one.

.. list-table::
   :header-rows: 1
   :widths: 36 64

   * - Field
     - Notes
   * - ``user``
     - one-to-one, ``CASCADE``
   * - ``plan``
     - FK, ``PROTECT``, nullable — a plan with a duration, since a lifetime plan
       never renews, or null when the member already holds a lifetime term and
       the authority is over the contribution alone
   * - ``contribution_cents``
     - renewed alongside the dues
   * - ``next_charge_on``
     - the day the member chose to be charged on, which defaults to the day their
       membership runs out; rolled forward by every successful charge
   * - ``provider``
     - ``stripe``, ``paypal`` or ``mock``
   * - ``customer_ref``
     - Stripe customer id / PayPal payer id
   * - ``method_ref``
     - Stripe payment method id / PayPal vault id
   * - ``method_brand``, ``method_last4``, ``method_exp_month``,
       ``method_exp_year``
     - the card's details; blank and ``NULL`` for PayPal
   * - ``method_label``
     - what the member sees: "Visa ending 4242, expires 03/2028"
   * - ``status``
     - ``pending`` (created at checkout), ``active``, ``paused`` (the retries
       ran out), ``canceled``
   * - ``failure_count``
     - consecutive failed charges; reset on success
   * - ``canceled_at``, ``canceled_by``
     - who turned it off: the member themselves, or an administrator
   * - ``last_charged_at``
     - the last successful charge
   * - ``raw``
     - ``JSONField`` — the provider's payload for the saved method

``RenewalAttempt``
------------------

One scheduled charge against a mandate, and the row every renewal email is
keyed on.

.. list-table::
   :header-rows: 1
   :widths: 36 64

   * - Field
     - Notes
   * - ``mandate``
     - FK, ``CASCADE``, related name ``attempts``
   * - ``membership``
     - FK, ``CASCADE`` — the term whose expiry this charge renews
   * - ``scheduled_on``
     - the day the charge is due
   * - ``retry_of``
     - FK to another attempt, ``SET_NULL``, nullable — the attempt this one
       retries
   * - ``outcome``
     - ``scheduled``, ``succeeded``, ``failed``, ``skipped``
   * - ``payment``
     - FK ``Payment``, ``SET_NULL``, nullable until the charge is made
   * - ``error``
     - the provider's decline reason, in the words the member is shown
   * - ``noticed_at``
     - when the advance-warning email went out
   * - ``attempted_at``
     - when the charge was tried
   * - ``result_emailed_at``
     - when the charged or failed email went out

The three timestamps are what make the scanner idempotent: an email goes out
only when its own stamp is still ``NULL``, so a scan that runs twice in one day
sends nothing twice.

reminders
=========

``ReminderLog``
---------------

One row per reminder email sent — the record that makes the scanner
idempotent.

``user`` (FK), ``membership`` (FK), ``kind``, ``sent_at`` (datetime),
``to_email``.  Ordered ``["-sent_at", "-id"]``.

The invariant is a single constraint::

    UniqueConstraint(fields=["user", "membership", "kind"],
                     name="reminders_once_per_kind")

so a second run writes nothing, and the log row is written and committed
before the send is attempted; a failure deletes it by hand rather than
recording an email that never left.  The reminder is then still due, and a
later run retries it for as long as the term stays in that stage's span.

``kind`` and its offset in days from the membership's ``ends_on``, with the span
of expiry dates it covers on a scan run on day D:

.. list-table::
   :header-rows: 1
   :widths: 16 16 68

   * - Kind
     - Offset
     - Sent when
   * - ``t60``
     - -60
     - the term ends between D+31 and D+60
   * - ``t30``
     - -30
     - the term ends between D+8 and D+30
   * - ``t7``
     - -7
     - the term ends between D+1 and D+7
   * - ``expired``
     - 0
     - the term ended between D-6 and D
   * - ``post30``
     - +30
     - the term ended between D-60 and D-30

Each kind is a stage covering a span of the calendar rather than one date, so
every term passes through it whichever day it ends; the spans come from
``apps.reminders.services.stage_span`` and never overlap, and the unique
constraint keeps a term that sits in one stage for days from being written to
twice (:ref:`reminders-stages`).  Lifetime members are
skipped, as are deactivated accounts,
accounts with no email address, and members whose unbroken coverage now runs
past the term in question — which is what stops an early renewal being nagged
about the term it replaced.  See :doc:`reminders`.

.. _data-model-email-log:

mail
====

``EmailLog``
------------

One row per email the installation tried to send, written by
``caldart.mail.send_templated`` after the send.  It is the record of what the
system said to whom, which is what ``GET /system/emails`` reads
(:ref:`api-email-log`).

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Field
     - Meaning
   * - ``to_email``
     - the address written to
   * - ``user``
     - FK ``User``, ``SET_NULL``, nullable: the account the email concerned,
       null for an address with no account behind it
   * - ``purpose``
     - the template the body came from, so ``reminder_t30``, ``receipt``,
       ``password_reset`` and the rest
   * - ``subject``
     - the subject line as it was sent
   * - ``sent_at``
     - when the send was attempted
   * - ``status``
     - ``sent`` for a message the mail server took, ``failed`` for one it
       refused
   * - ``error``
     - the exception class of a refusal, blank on a send that went out
   * - ``attachments``
     - the filenames that rode along, comma-separated, blank when none did

Ordered ``["-sent_at", "-id"]``, indexed on ``(purpose, -sent_at)`` and
``(user, -sent_at)``.  Nothing reads the table to decide what to do next, so it
carries no constraint: a member who is written to twice has two rows, which is
the honest record.  ``ReminderLog`` is the key that keeps a reminder from
repeating; this is the record of the message.

A reminder's own ``ReminderLog`` row is deleted by hand when the send fails,
so the reminder stays due, but the send itself leaves a ``failed`` row here
regardless -- the same as any other refused email.

cms
===

The Wagtail models are documented in full in :doc:`cms`; this is the shape of
them.

**Page types**, all inheriting ``BasePage`` (which supplies the
``RestrictedBlocksPageForm`` that hides the raw-HTML block from editors who may
not use it, and the ``body_headings`` used to build the "on this page" rail):

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Model
     - Notes
   * - ``HomePage``
     - the welcome box (heading, lede, captioned image, mission statement
       , ``welcome_body``, and three CTAs), ``missions_flown`` (a StreamField
       of ``mission`` blocks), tax status, the three latest news posts, and
       the three soonest events.  Only under the tree root.
   * - ``StandardPage``
     - ``intro`` plus a ``body`` StreamField.  Members-only capable.
   * - ``NewsIndexPage`` / ``NewsPage``
     - ``NewsPage`` adds ``date``, ``intro``, ``image``, ``body``, and may only
       live under a ``NewsIndexPage``.  Members-only capable.
   * - ``EventIndexPage`` / ``EventPage``
     - ``EventPage`` adds ``date``, ``time``, ``location``, ``intro``, and
       ``body``, and may only live under an ``EventIndexPage``.  The index
       lists everything upcoming and paginates what has passed.
   * - ``DartIndexPage`` / ``DartPage``
     - ``DartPage`` has a nullable ``SET_NULL`` FK to ``darts.Dart`` —
       the airport identifiers are read from it — plus ``leader_name``
       , ``leader_contact``, and a body.
   * - ``ContactPage``
     - ``intro`` and ``body``; the contact details come from site settings.

``MembersOnlyMixin`` adds one field, ``members_only``, and overrides ``serve``:
when the flag is set and ``request.user.can_access_members_content`` is false,
it renders ``cms/members_only_wall.html`` with **HTTP 403** and a call to
action chosen from the visitor's state — sign in, renew (naming the date), or
join.

``SiteSettings`` (a Wagtail ``BaseSiteSetting``) carries ``org_name``,
``tagline``, ``contact_email``, ``duty_phone``,
``mailing_address``, ``ein``, ``donate_url``,
``facebook_url``, ``twitter_url``, ``theme`` (one of the slugs listed in
:doc:`theming`; default ``duty``) and ``footer_text``.

sysadmin
========

``apps.sysadmin`` has **no models**.  It is commands and an API over the file
system and the database connection: ``db_backup``, ``db_restore``,
``db_reset``, ``health``, and the ``/system/...`` endpoints.  See
:doc:`backup-restore`.

Migrations
==========

This is a prototype and keeps no backwards compatibility.  Change a model and
**regenerate** its migration rather than stacking a fix-up on top; there is no
data to migrate and no external consumer to keep stable.  ``make reset``
rebuilds a development database from nothing in a few seconds.

Two migrations do more than create tables and are worth knowing about:

- ``accounts.0002_seed_roles`` runs the same ``seed_roles`` function, so every
  role group exists in any migrated database;
- ``cms.0003_website_admin_permissions`` grants the ``website_admin`` group its
  Wagtail permissions, and ``seed_content`` calls the same function, so the
  grant is applied whichever route you take.

``make check`` runs ``manage.py makemigrations --check --dry-run``, and CI runs
``make check``, so a model change without its migration fails the build.
