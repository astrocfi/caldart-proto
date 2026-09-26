==========
Data model
==========

Every model in the project, every field it stores, the constraints, indexes,
and ordering that hold it together, and the two implementations of the one piece
of arithmetic everything else depends on: whether a person's membership is
current.  The endpoints that expose these models are in :doc:`api-reference`,
and :doc:`architecture` shows which app owns each one.

House rules that apply throughout:

- **Money is integer cents in USD.**  There is no ``Decimal`` and no float
  anywhere in the schema.  ``amount_cents = 4500`` is $45.00.
- **Dates are ``DateField``** unless the name ends in ``_at``, which means a
  timezone-aware ``DateTimeField``.  The project timezone is
  ``America/Los_Angeles`` and ``USE_TZ`` is on, so "today" always means
  ``django.utils.timezone.localdate()``.
- **Most models carry ``created_at`` and ``updated_at``**, inherited from the
  abstract ``caldart.models.TimestampedModel``: ``created_at`` is set on insert
  and ``updated_at`` on every save.  ``User`` declares its own pair, because it
  inherits from ``AbstractUser`` instead.  The page models do not, because
  Wagtail's ``Page`` keeps its own dates (``first_published_at``,
  ``last_published_at``, and ``latest_revision_created_at``) alongside the
  revision history behind them.  ``cms.SiteSettings`` carries no dates either,
  so editing the settings overwrites the single row and records nothing about
  when or by whom.  ``aircraft.AircraftChange`` carries its own ``changed_at``
  and no row is ever updated, so the inherited pair would only duplicate it.
- **``DEFAULT_AUTO_FIELD`` is ``BigAutoField``**, so every ``id`` below is a
  ``BigAutoField`` except the page models', which Wagtail keys on its own
  ``AutoField``.

How each model is described
===========================

Each model has a table of every field it stores:

Field
    The column's name as the ORM spells it (a foreign key's column is that name
    with ``_id``).
Type
    The Django field class, with its maximum length where it has one.  A
    relation names the model it points at and its delete rule; a field with a
    choice list links to that list in :ref:`data-model-choices`.
Null, default
    ``null`` when the column accepts ``NULL``, then the default a new row gets:
    ``default ""`` is a text field that may be left blank, ``required`` is a
    field with no default that every write must supply, and ``set on insert``
    and ``set on every save`` are Django's ``auto_now_add`` and ``auto_now``.
Meaning
    What the value is for.  The related name, where there is one, is what the
    other model calls the reverse relation.

The table is followed by the model's constraints, indexes, and ordering, each
under the name the migration gives it, and then by the rules the code keeps
that the database does not.  Those lists name what a model declares in its
``Meta``.  Django adds the rest under generated names: an index on every
foreign-key column, one on ``EmailLog.purpose`` (a ``SlugField``), and a
unique index for every field marked unique in its table.

.. _data-model-diagrams:

Entity relationships
====================

Three diagrams, one per area of the schema: the people, their teams, and their
aircraft; the money; and the records and pages that sit on top of both.  Every
model in an area is drawn in its diagram.  A model drawn in another area
appears as a **dotted box**, so a diagram shows where its edges lead without
repeating that area's detail.

In all three, a **solid arrow** is a foreign key, drawn from the table that
holds the column to the table it references and labeled with the field name and
its delete rule.  A **double line** is a many-to-many.  A line labeled ``1--1``
is a one-to-one.  A **dashed box** is an abstract class with no table of its
own, and an **empty arrowhead** points from a subclass to the class it
inherits.  ``caldart.TimestampedModel`` is left out of the drawings: the field
tables below show ``created_at`` and ``updated_at`` on every model that
inherits it.

Accounts, members, DARTs, and aircraft
--------------------------------------

.. only:: graphviz

   .. graphviz::
      :caption: Accounts, members, DARTs, and aircraft.  ``auth.Group`` holds
                the roles, and ``members.MemberProfile.aircraft`` is the
                many-to-many whose reverse name is ``pilots``.  The payment a
                term links to is drawn with the money.
      :alt: Entity-relationship diagram of the accounts, members, DARTs, and aircraft models

      digraph caldart_people {
          rankdir=TB;
          bgcolor="transparent";
          nodesep=0.3;
          ranksep=0.45;
          node [shape=box, style="rounded", fontname="Helvetica", fontsize=11];
          edge [fontname="Helvetica", fontsize=11];

          AbstractUser [label="auth.AbstractUser\n(abstract)", style="rounded,dashed"];
          User [label="accounts.User"];
          Group [label="auth.Group\n(a role)"];
          Permission [label="auth.Permission"];
          Profile [label="members.MemberProfile"];
          Plan [label="members.MembershipPlan"];
          Membership [label="members.Membership"];
          Dart [label="darts.Dart"];
          Contact [label="darts.DartContact"];
          Aircraft [label="aircraft.Aircraft"];
          Change [label="aircraft.AircraftChange"];
          Payment [label="payments.Payment\n(see payments)", style="rounded,dotted"];

          User -> AbstractUser [arrowhead=empty];
          User -> Group [label="groups\n(m2m)", dir=none, color="black:black"];
          User -> Permission [label="user_permissions\n(m2m)", dir=none, color="black:black"];
          Profile -> User [label="user 1--1\nCASCADE", arrowhead=none];
          Profile -> Dart [label="dart\nSET_NULL"];
          Profile -> Aircraft [label="aircraft (m2m)\npilots", dir=none, color="black:black"];
          Contact -> Dart [label="dart\nCASCADE"];
          Membership -> User [label="user CASCADE\ngranted_by SET_NULL"];
          Membership -> Plan [label="plan\nPROTECT"];
          Membership -> Payment [label="payment 1--1\nSET_NULL", arrowhead=none];
          Aircraft -> User [label="created_by, updated_by\nSET_NULL"];
          Change -> Aircraft [label="aircraft\nCASCADE"];
          Change -> User [label="changed_by\nSET_NULL"];
      }

.. only:: not graphviz

   Install Graphviz and rebuild for a drawn version of this diagram.  The
   drawing and the lists below carry the same models and relations.

   .. code-block:: text

      Models in this area
      -------------------
      accounts.User             the account; inherits auth.AbstractUser (abstract)
      auth.Group                a role, named by its slug
      auth.Permission           Django's per-model permissions
      members.MemberProfile     everything the join form collects
      members.MembershipPlan    a purchasable term
      members.Membership        one paid or granted term
      darts.Dart                a Disaster Airlift Response Team
      darts.DartContact         one named person who runs a DART
      aircraft.Aircraft         one airframe on the register
      aircraft.AircraftChange   one write to a register record

      Drawn with another area
      -----------------------
      payments.Payment          (payments and renewals)

      Edges
      -----
      accounts.User.groups              -> auth.Group              m2m
      accounts.User.user_permissions    -> auth.Permission         m2m
      accounts.User                     inherits auth.AbstractUser
      members.MemberProfile.user        -> accounts.User           1--1, CASCADE
      members.MemberProfile.dart        -> darts.Dart              FK, SET_NULL, nullable
      members.MemberProfile.aircraft    -> aircraft.Aircraft       m2m, related name pilots
      darts.DartContact.dart            -> darts.Dart              FK, CASCADE
      members.Membership.user           -> accounts.User           FK, CASCADE
      members.Membership.granted_by     -> accounts.User           FK, SET_NULL, nullable
      members.Membership.plan           -> members.MembershipPlan  FK, PROTECT
      members.Membership.payment        -> payments.Payment        1--1, SET_NULL, nullable
      aircraft.Aircraft.created_by      -> accounts.User           FK, SET_NULL, nullable
      aircraft.Aircraft.updated_by      -> accounts.User           FK, SET_NULL, nullable
      aircraft.AircraftChange.aircraft  -> aircraft.Aircraft       FK, CASCADE
      aircraft.AircraftChange.changed_by -> accounts.User          FK, SET_NULL, nullable

Payments and renewals
---------------------

.. only:: graphviz

   .. graphviz::
      :caption: Payments and renewals.  The **dotted arrow** from
                ``payments.Payment`` is the provider lookup: a slug in the
                ``provider`` column, resolved by ``get_provider()``, rather than
                a foreign key.  ``payments.Provider`` and its three
                implementations are Python classes with no table.
      :alt: Entity-relationship diagram of the payment and renewal models

      digraph caldart_payments {
          rankdir=TB;
          bgcolor="transparent";
          nodesep=0.3;
          ranksep=0.45;
          node [shape=box, style="rounded", fontname="Helvetica", fontsize=11];
          edge [fontname="Helvetica", fontsize=11];

          Payment [label="payments.Payment"];
          Refund [label="payments.Refund"];
          Mandate [label="payments.RenewalMandate"];
          Attempt [label="payments.RenewalAttempt"];
          Statement [label="payments.YearStatement"];
          Provider [label="payments.Provider\n(abstract, no table)", style="rounded,dashed"];
          Impl [label="StripeProvider (stripe)\nPayPalProvider (paypal)\nMockProvider (mock)"];
          User [label="accounts.User", style="rounded,dotted"];
          Plan [label="members.MembershipPlan", style="rounded,dotted"];
          Membership [label="members.Membership", style="rounded,dotted"];

          Refund -> Payment [label="payment\nPROTECT"];
          Refund -> User [label="requested_by\nSET_NULL"];
          Payment -> User [label="user PROTECT\nreconciled_by,\nrecorded_by\nSET_NULL"];
          Payment -> Plan [label="plan\nPROTECT"];
          Payment -> Provider [label="provider slug", style=dotted];
          Provider -> Impl [dir=back, arrowtail=empty, label="implemented by"];
          Mandate -> User [label="user CASCADE\ncanceled_by SET_NULL"];
          Mandate -> Plan [label="plan\nPROTECT"];
          Attempt -> Mandate [label="mandate\nCASCADE"];
          Attempt -> Membership [label="membership\nCASCADE"];
          Attempt -> Payment [label="payment\nSET_NULL"];
          Attempt -> Attempt [label="retry_of\nSET_NULL"];
          Statement -> User [label="user\nCASCADE"];
      }

.. only:: not graphviz

   Install Graphviz and rebuild for a drawn version of this diagram.  The
   drawing and the lists below carry the same models and relations.

   .. code-block:: text

      Models in this area
      -------------------
      payments.Payment          one attempt to pay for a term, a gift, or both
      payments.Refund           money given back against one payment
      payments.RenewalMandate   a standing authority to charge a saved method
      payments.RenewalAttempt   one scheduled charge against a mandate
      payments.YearStatement    one year-end statement sent to one account

      Classes with no table
      ---------------------
      payments.Provider         abstract: start(payment), confirm(payment, **kwargs),
                                handle_webhook(request); implemented by
                                StripeProvider (stripe), PayPalProvider (paypal),
                                and MockProvider (mock)

      Drawn with another area
      -----------------------
      accounts.User, members.MembershipPlan, members.Membership

      Edges
      -----
      payments.Payment.user             -> accounts.User           FK, PROTECT
      payments.Payment.plan             -> members.MembershipPlan  FK, PROTECT, nullable
      payments.Payment.reconciled_by    -> accounts.User           FK, SET_NULL, nullable
      payments.Payment.recorded_by      -> accounts.User           FK, SET_NULL, nullable
      payments.Payment.provider         -> payments.Provider       slug, via get_provider()
      payments.Refund.payment           -> payments.Payment        FK, PROTECT
      payments.Refund.requested_by      -> accounts.User           FK, SET_NULL, nullable
      payments.RenewalMandate.user      -> accounts.User           FK, CASCADE
      payments.RenewalMandate.plan      -> members.MembershipPlan  FK, PROTECT, nullable
      payments.RenewalMandate.canceled_by -> accounts.User         FK, SET_NULL, nullable
      payments.RenewalAttempt.mandate   -> payments.RenewalMandate FK, CASCADE
      payments.RenewalAttempt.membership -> members.Membership     FK, CASCADE, nullable
      payments.RenewalAttempt.payment   -> payments.Payment        FK, SET_NULL, nullable
      payments.RenewalAttempt.retry_of  -> payments.RenewalAttempt FK, SET_NULL, nullable
      payments.YearStatement.user       -> accounts.User           FK, CASCADE

Mail, reminders, reports, and the CMS pages
-------------------------------------------

.. only:: graphviz

   .. graphviz::
      :caption: Mail, reminders, reports, and the CMS pages.  The four records
                at the top point at the account and the term they concern.
                Below them, every page type inherits the abstract
                ``cms.BasePage``, and ``StandardPage`` and ``NewsPage`` also
                inherit ``cms.MembersOnlyMixin``.  Which page may live under
                which is in :doc:`cms`, not in this diagram.
      :alt: Entity-relationship diagram of the mail, reminder, report, and CMS page models

      digraph caldart_records_and_pages {
          rankdir=TB;
          bgcolor="transparent";
          nodesep=0.25; ranksep=0.4;
          node [shape=box, style="rounded", fontname="Helvetica", fontsize=11];
          edge [fontname="Helvetica", fontsize=11];
      
          User [label="accounts.User", style="rounded,dotted"];
          Membership [label="members.Membership", style="rounded,dotted"];
          Email [label="mail.EmailLog"];
          Reminder [label="reminders.ReminderLog"];
          ColumnSet [label="reports.SavedColumnSet"];
          Subscription [label="reports.ReportSubscription"];
      
          Email -> User [label="user\nSET_NULL"];
          Reminder -> User [label="user\nCASCADE"];
          Reminder -> Membership [label="membership\nCASCADE"];
          ColumnSet -> User [label="user\nCASCADE"];
          Subscription -> User [label="recipient_user,\ncreated_by\nSET_NULL"];
      
          User -> Page [style=invis];
          Membership -> Page [style=invis];
          Page [label="wagtailcore.Page", style="rounded,dotted"];
          BasePage [label="cms.BasePage\n(abstract)", style="rounded,dashed"];
          MembersOnly [label="cms.MembersOnlyMixin\n(abstract)", style="rounded,dashed"];
          Home [label="cms.HomePage"];
          Standard [label="cms.StandardPage"];
          NewsIndex [label="cms.NewsIndexPage"];
          News [label="cms.NewsPage"];
          EventIndex [label="cms.EventIndexPage"];
          Event [label="cms.EventPage"];
          DartIndex [label="cms.DartIndexPage"];
          DartPage [label="cms.DartPage"];
          Contact [label="cms.ContactPage"];
          Donate [label="cms.DonatePage"];
          Settings [label="cms.SiteSettings"];
          Image [label="wagtailimages.Image", style="rounded,dotted"];
          Site [label="wagtailcore.Site", style="rounded,dotted"];
          Dart [label="darts.Dart", style="rounded,dotted"];
      
          Page -> BasePage [dir=back, arrowtail=empty];
          BasePage -> Home [dir=back, arrowtail=empty];
          BasePage -> Contact [dir=back, arrowtail=empty];
          BasePage -> Donate [dir=back, arrowtail=empty];
          BasePage -> NewsIndex [dir=back, arrowtail=empty];
          BasePage -> EventIndex [dir=back, arrowtail=empty];
          BasePage -> DartIndex [dir=back, arrowtail=empty];
          BasePage -> Standard [dir=back, arrowtail=empty];
          NewsIndex -> News [dir=back, arrowtail=empty, style=invis];
          BasePage -> News [dir=back, arrowtail=empty];
          BasePage -> Event [dir=back, arrowtail=empty];
          BasePage -> DartPage [dir=back, arrowtail=empty];
          EventIndex -> Event [style=invis];
          DartIndex -> DartPage [style=invis];
          NewsIndex -> Home [style=invis];
          EventIndex -> Contact [style=invis];
          DartIndex -> Donate [style=invis];
          MembersOnly -> Standard [dir=back, arrowtail=empty];
          MembersOnly -> News [dir=back, arrowtail=empty];
          Home -> Image [label="hero_image\nSET_NULL"];
          News -> Image [label="image\nSET_NULL"];
          DartPage -> Dart [label="dart\nSET_NULL"];
          Donate -> Settings [style=invis];
          Settings -> Site [label="site 1--1\nCASCADE", arrowhead=none];
      }

.. only:: not graphviz

   Install Graphviz and rebuild for a drawn version of this diagram.  The
   drawing and the lists below carry the same models and relations.

   .. code-block:: text

      Models in this area
      -------------------
      mail.EmailLog               one email the installation tried to send
      reminders.ReminderLog       one renewal reminder sent
      reports.SavedColumnSet      a named choice of one report's columns
      reports.ReportSubscription  one report, emailed on a schedule
      cms.HomePage, cms.StandardPage, cms.NewsIndexPage, cms.NewsPage,
      cms.EventIndexPage, cms.EventPage, cms.DartIndexPage, cms.DartPage,
      cms.ContactPage, cms.DonatePage
                                  the page types
      cms.SiteSettings            the organization's details and the theme

      Abstract classes (no table of their own)
      ----------------------------------------
      cms.BasePage                inherits wagtailcore.Page; inherited by every
                                  page type above
      cms.MembersOnlyMixin        mixed into cms.StandardPage and cms.NewsPage

      Drawn with another area, or Wagtail's own
      -----------------------------------------
      accounts.User, members.Membership, darts.Dart, wagtailcore.Page,
      wagtailimages.Image, wagtailcore.Site

      Edges
      -----
      mail.EmailLog.user                   -> accounts.User       FK, SET_NULL, nullable
      reminders.ReminderLog.user           -> accounts.User       FK, CASCADE
      reminders.ReminderLog.membership     -> members.Membership  FK, CASCADE
      reports.SavedColumnSet.user          -> accounts.User       FK, CASCADE
      reports.ReportSubscription.recipient_user -> accounts.User  FK, SET_NULL, nullable
      reports.ReportSubscription.created_by     -> accounts.User  FK, SET_NULL, nullable
      cms.BasePage                         inherits wagtailcore.Page
      cms.<every page type>                inherits cms.BasePage
      cms.StandardPage, cms.NewsPage       also inherit cms.MembersOnlyMixin
      cms.HomePage.hero_image              -> wagtailimages.Image FK, SET_NULL, nullable
      cms.NewsPage.image                   -> wagtailimages.Image FK, SET_NULL, nullable
      cms.DartPage.dart                    -> darts.Dart          FK, SET_NULL, nullable
      cms.SiteSettings.site                -> wagtailcore.Site    1--1, CASCADE

.. _data-model-choices:

Choice lists
============

Every choice list the schema uses, listed once, with the value stored and the
label a screen, an export, or the Django admin shows for it.  Each is a
``TextChoices`` class or a module constant beside the model that uses it.  The
three marked *computed* are never stored: they name the values a service works
out.

.. _choices-account-kind:

``AccountKind`` (``apps/accounts/models.py``)
---------------------------------------------

The kind of person an account belongs to (``User.kind``); see
:ref:`kinds of account <account-kinds>`.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``member``
     - Member
   * - ``friend``
     - Friend
   * - ``donor``
     - Donor

``PERSON_KINDS`` is ``member`` and ``friend``, the kinds registration and an
administrator may choose.

.. _choices-membership-state:

``MembershipState`` (``apps/members/models.py``, computed)
----------------------------------------------------------

The answer ``members.services.membership_status`` gives (see
:ref:`membership-status`).  The labels are what the member list's status
filter, the member report, and the portal's status select show.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``current``
     - Current
   * - ``new``
     - Unpaid
   * - ``expired``
     - Expired
   * - ``none``
     - No membership
   * - ``friend``
     - Friend

.. _choices-membership-status-choices:

``MembershipStatusChoices`` (``apps/members/models.py``)
--------------------------------------------------------

The state stored on one term (``Membership.status``).  ``new`` is a term
joined and not yet paid for; ``suspended`` belongs to an account its holder
deactivated while the term still had time to run.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``new``
     - New
   * - ``active``
     - Active
   * - ``expired``
     - Expired
   * - ``canceled``
     - Canceled
   * - ``suspended``
     - Suspended

.. _choices-membership-source:

``MembershipSource`` (``apps/members/models.py``)
-------------------------------------------------

How a term was come by (``Membership.source``).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``payment``
     - Payment
   * - ``manual``
     - Manual grant
   * - ``seed``
     - Seed data

.. _choices-pilot-certificate-type:

``PilotCertificateType`` (``apps/members/models.py``)
-----------------------------------------------------

``MemberProfile.pilot_certificate_type``.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``none``
     - None
   * - ``student``
     - Student
   * - ``sport``
     - Sport
   * - ``recreational``
     - Recreational
   * - ``private``
     - Private
   * - ``commercial``
     - Commercial
   * - ``atp``
     - Airline Transport Pilot

.. _choices-ifr-rated:

``IfrRated`` (``apps/members/models.py``)
-----------------------------------------

``MemberProfile.ifr_rated``.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``na``
     - Not applicable
   * - ``yes``
     - Yes
   * - ``no``
     - No

.. _choices-medical-type:

``MedicalType`` (``apps/members/models.py``)
--------------------------------------------

``MemberProfile.medical_type``.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``none``
     - None
   * - ``basicmed``
     - BasicMed
   * - ``first``
     - First class
   * - ``second``
     - Second class
   * - ``third``
     - Third class

.. _choices-ratings:

``RATING_CHOICES`` (``apps/members/models.py``)
-----------------------------------------------

The values ``MemberProfile.ratings`` may hold, in the two rows the forms show:
the category and class ratings, then the instructor ones.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``asel``
     - ASEL
   * - ``amel``
     - AMEL
   * - ``ases``
     - ASES
   * - ``ames``
     - AMES
   * - ``helicopter``
     - Helicopter
   * - ``instrument``
     - Instrument
   * - ``cfi``
     - CFI
   * - ``cfii``
     - CFII
   * - ``mei``
     - MEI

.. _choices-us-state:

``US_STATE_CHOICES`` (``apps/members/models.py``)
-------------------------------------------------

``MemberProfile.state``: the two-letter USPS code of each of the fifty states,
the District of Columbia (``DC``), and the five territories with USPS codes
(``AS``, ``GU``, ``MP``, ``PR``, and ``VI``), fifty-six in all.  The value is the
code and the label the full name (``CA``, California).  ``US_STATE_VALUES`` is
the codes alone.

.. _choices-county:

``CALIFORNIA_COUNTIES`` (``apps/members/models.py``)
----------------------------------------------------

``MemberProfile.county``: California's fifty-eight counties, from Alameda to
Yuba, in alphabetical order.  The value and the label are both the county's
name (``Contra Costa``), so the column holds the name as a person reads it.

.. _choices-owner-type:

``OwnerType`` (``apps/aircraft/models.py``)
-------------------------------------------

``Aircraft.owner_type``: who holds title.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``individual``
     - Individual
   * - ``fbo``
     - FBO
   * - ``club``
     - Flying club

.. _choices-aircraft-change-kind:

``AircraftChangeKind`` (``apps/aircraft/models.py``)
----------------------------------------------------

``AircraftChange.kind``.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``created``
     - Created
   * - ``updated``
     - Updated

.. _choices-payment-provider:

``PaymentProvider`` (``apps/payments/models.py``)
-------------------------------------------------

``Payment.provider``: the backend a payment was routed to.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``stripe``
     - Stripe
   * - ``paypal``
     - PayPal
   * - ``mock``
     - Mock
   * - ``manual``
     - Recorded by hand

.. _choices-mandate-provider:

``MandateProvider`` (``apps/payments/models.py``)
-------------------------------------------------

``RenewalMandate.provider``: the members of ``PaymentProvider`` that can charge
again without the person present.  ``manual`` is absent, because a check or cash
cannot be taken a second time without the member.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``stripe``
     - Stripe
   * - ``paypal``
     - PayPal
   * - ``mock``
     - Mock

.. _choices-payment-wallet:

``PaymentWallet`` (``apps/payments/models.py``)
-----------------------------------------------

``Payment.wallet``: how the money was presented, as far as the provider could
say.  ``card``, ``apple_pay``, ``google_pay``, and ``link`` come from the Stripe
charge (:doc:`payments-setup`); ``check``, ``cash``, ``bank_transfer``, and
``other`` are the choices for a payment recorded by hand.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``card``
     - Card
   * - ``apple_pay``
     - Apple Pay
   * - ``google_pay``
     - Google Pay
   * - ``link``
     - Link
   * - ``paypal``
     - PayPal
   * - ``mock``
     - Mock
   * - ``check``
     - Check
   * - ``cash``
     - Cash
   * - ``bank_transfer``
     - Bank transfer
   * - ``other``
     - Other
   * - ``unknown``
     - Unknown

.. _choices-payment-status:

``PaymentStatus`` (``apps/payments/models.py``)
-----------------------------------------------

``Payment.status``.  Only ``succeeded`` buys a membership term.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``pending``
     - Pending
   * - ``succeeded``
     - Succeeded
   * - ``failed``
     - Failed
   * - ``partially_refunded``
     - Partially refunded
   * - ``refunded``
     - Refunded

.. _choices-payment-kind:

``PaymentKind`` (``apps/payments/models.py``, computed)
-------------------------------------------------------

``Payment.kind``, read from the plan and the contribution.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``membership``
     - Membership
   * - ``contribution``
     - Contribution
   * - ``both``
     - Membership and contribution

.. _choices-refund-reason:

``RefundReason`` (``apps/payments/models.py``)
----------------------------------------------

``Refund.reason``: the treasurer picks one when issuing a refund.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``requested_by_member``
     - Requested by the member
   * - ``duplicate``
     - Duplicate payment
   * - ``error``
     - Charged in error
   * - ``fraudulent``
     - Fraudulent
   * - ``other``
     - Other

.. _choices-refund-status:

``RefundStatus`` (``apps/payments/models.py``)
----------------------------------------------

``Refund.status``.  Only ``succeeded`` counts toward ``refunded_cents``.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``pending``
     - Pending
   * - ``succeeded``
     - Succeeded
   * - ``failed``
     - Failed

.. _choices-mandate-status:

``MandateStatus`` (``apps/payments/models.py``)
-----------------------------------------------

``RenewalMandate.status``.  A mandate is ``pending`` from the checkout or the
portal request that creates it until the method is confirmed, and three failed
charges in a row make it ``paused``.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``pending``
     - Pending
   * - ``active``
     - Active
   * - ``paused``
     - Paused
   * - ``canceled``
     - Canceled

.. _choices-mandate-cadence:

``MandateCadence`` (``apps/payments/models.py``)
------------------------------------------------

``RenewalMandate.cadence``.  A renewal is always ``yearly``.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``monthly``
     - Monthly
   * - ``quarterly``
     - Quarterly
   * - ``yearly``
     - Yearly

.. _choices-mandate-kind:

``MandateKind`` (``apps/payments/renewals.py``, computed)
---------------------------------------------------------

What a mandate charges for, which is what every renewal email says.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``renewal``
     - Automatic renewal
   * - ``both``
     - Automatic renewal and contribution
   * - ``contribution``
     - Recurring donation

.. _choices-renewal-outcome:

``RenewalOutcome`` (``apps/payments/models.py``)
------------------------------------------------

``RenewalAttempt.outcome``.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``scheduled``
     - Scheduled
   * - ``succeeded``
     - Succeeded
   * - ``failed``
     - Failed
   * - ``skipped``
     - Skipped

.. _choices-reminder-kind:

``ReminderKind`` (``apps/reminders/models.py``)
-----------------------------------------------

``ReminderLog.kind``: the five reminder stages.  ``REMINDER_OFFSETS`` gives each
one's offset in days from the term's ``ends_on`` (see ``ReminderLog`` below).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``t60``
     - 60 days before expiry
   * - ``t30``
     - 30 days before expiry
   * - ``t7``
     - 7 days before expiry
   * - ``expired``
     - Expired
   * - ``post30``
     - 30 days after expiry

.. _choices-email-status:

``EmailStatus`` (``apps/mail/models.py``)
-----------------------------------------

``EmailLog.status``: ``sent`` when the mail server took the message,
``failed`` when it refused it.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``sent``
     - Sent
   * - ``failed``
     - Failed

.. _choices-report-formats:

``ReportFormats`` (``apps/reports/models.py``)
----------------------------------------------

``ReportSubscription.formats``: which files a subscription attaches.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``csv``
     - CSV
   * - ``pdf``
     - PDF
   * - ``both``
     - Both

.. _choices-cadence:

``Cadence`` (``apps/reports/schedule.py``)
------------------------------------------

``ReportSubscription.cadence``.  ``next_due_after`` turns one into the next day
the daily run sends: ``weekly`` the next ``weekday``, ``monthly`` the first of
the next month, ``quarterly`` the next January, April, July, or October 1, and
``yearly`` the next January 1.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``weekly``
     - Weekly
   * - ``monthly``
     - Monthly
   * - ``quarterly``
     - Quarterly
   * - ``yearly``
     - Yearly

.. _choices-theme:

``THEME_CHOICES`` (``apps/cms/models.py``)
------------------------------------------

``SiteSettings.theme``: the fourteen themes shipped in
``frontend/src/styles/themes/``, described in :doc:`theming`.  ``DEFAULT_THEME``
is ``duty``, and ``THEME_SLUGS`` is the values alone.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Label
   * - ``duty``
     - Duty (default, blue and red)
   * - ``sierra``
     - Sierra (warm paper)
   * - ``pacific``
     - Pacific (cool paper)
   * - ``night``
     - Night (dark)
   * - ``squadron``
     - Squadron (logo blue on white)
   * - ``flight-deck``
     - Flight deck (logo blue, dark)
   * - ``contrail``
     - Contrail (logo blue, sky paper)
   * - ``sectional``
     - Sectional (aeronautical chart)
   * - ``tarmac``
     - Tarmac (concrete and asphalt)
   * - ``coastal``
     - Coastal (fog and ocean teal)
   * - ``slate``
     - Slate (cool corporate)
   * - ``meridian``
     - Meridian (high-contrast civic)
   * - ``monterey-night``
     - Monterey night (charcoal dark)
   * - ``granite``
     - Granite (near-monochrome)

accounts
========

``User``
--------

A custom ``AbstractUser`` in which **email is the login**.  There is no
``username`` field at all (``username = None``), ``USERNAME_FIELD = "email"``
and ``REQUIRED_FIELDS`` is empty, so ``createsuperuser`` asks for an email
address and a password and nothing else.  The table lists every column once,
including the ones inherited from ``AbstractUser`` and the ``AbstractBaseUser``
and ``PermissionsMixin`` classes it builds on.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``password``
     - ``CharField(128)``
     - not null; required
     - inherited from ``AbstractBaseUser``: the salted password hash; an unusable hash for a donor and for an invitation not yet accepted
   * - ``last_login``
     - ``DateTimeField``
     - null; default ``NULL``
     - inherited from ``AbstractBaseUser``: when the account last signed in, null until it has
   * - ``is_superuser``
     - ``BooleanField``
     - not null; default ``False``
     - inherited from ``PermissionsMixin``: Django's superuser flag, kept in step with the ``system_admin`` role by ``accounts.services``
   * - ``is_staff``
     - ``BooleanField``
     - not null; default ``False``
     - inherited from ``AbstractUser``: the Wagtail and Django admin flag, set for a superuser or a ``website_admin``
   * - ``is_active``
     - ``BooleanField``
     - not null; default ``True``
     - inherited from ``AbstractUser``: false for a deactivated account, which cannot sign in until it is reactivated (:ref:`api-deactivation`)
   * - ``date_joined``
     - ``DateTimeField``
     - not null; default ``timezone.now``
     - inherited from ``AbstractUser``: Django's own creation stamp, set beside ``created_at``
   * - ``email``
     - ``EmailField(254)``, unique
     - not null; required
     - the login and the address every email goes to; unique, and unique case-insensitively as well (below)
   * - ``first_name``
     - ``CharField(150)``
     - not null; default ``""``
     - may be blank
   * - ``last_name``
     - ``CharField(150)``
     - not null; default ``""``
     - may be blank
   * - ``created_at``
     - ``DateTimeField``
     - not null; default ``timezone.now``
     - when the account was created; not editable
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``email_verified_at``
     - ``DateTimeField``
     - null; default ``NULL``
     - when the owner last proved the address by following a verification or password link sent to it; null while the address is unverified
   * - ``kind``
     - ``CharField(8)``, choices :ref:`AccountKind <choices-account-kind>`
     - not null; default ``"member"``
     - the kind of person the account belongs to, as stored; see *Kinds of account* below
   * - ``friend_on``
     - ``DateField``
     - null; default ``NULL``
     - the day a member who asked to become a friend becomes one; null when no change is pending
   * - ``groups``
     - ``ManyToManyField`` to ``auth.Group``
     - not null; empty by default
     - inherited from ``PermissionsMixin``: the role groups, and any Wagtail editor group; related name ``user_set``
   * - ``user_permissions``
     - ``ManyToManyField`` to ``auth.Permission``
     - not null; empty by default
     - inherited from ``PermissionsMixin``: per-user Django permissions, which nothing in CalDART grants; related name ``user_set``

**Constraints, indexes, and ordering.**

- Constraint ``accounts_user_email_ci_unique``: unique on ``Lower("email")``.
- Index ``accounts_user_name_idx`` on (``last_name``, ``first_name``).
- Ordering: ``last_name``, ``first_name``, ``email``.

**Relationships.**

- ``groups``: many-to-many to ``auth.Group``; the reverse accessor is ``user_set``.
- ``user_permissions``: many-to-many to ``auth.Permission``; the reverse accessor is ``user_set``.
- Referenced by ``aircraft.Aircraft.created_by``, ``aircraft.Aircraft.updated_by``, ``aircraft.AircraftChange.changed_by``, ``mail.EmailLog.user``, ``members.MemberProfile.user``, ``members.Membership.granted_by``, ``members.Membership.user``, ``payments.Payment.reconciled_by``, ``payments.Payment.recorded_by``, ``payments.Payment.user``, ``payments.Refund.requested_by``, ``payments.RenewalMandate.canceled_by``, ``payments.RenewalMandate.user``, ``payments.YearStatement.user``, ``reminders.ReminderLog.user``, ``reports.ReportSubscription.created_by``, ``reports.ReportSubscription.recipient_user``, ``reports.SavedColumnSet.user``.

**Invariants.**

- Email uniqueness is enforced twice: the field's own ``unique=True``, and
  ``accounts_user_email_ci_unique`` on ``Lower("email")``.  The manager's
  ``get_by_natural_key`` looks up with ``email__iexact``, so
  ``Marta@example.org`` and ``marta@example.org`` are one account for sign-in
  as well as for creation.
- ``UserManager._create_user`` normalizes and strips the address, and an
  account created without a password holds an unusable one.
- ``accounts.services.sync_django_flags`` keeps ``is_superuser`` equal to
  holding ``system_admin``, and ``is_staff`` true for a superuser or a
  ``website_admin``, after every role edit.
- ``accounts.services.update_account`` clears ``email_verified_at`` whenever an
  edit really changes the address (a change of case alone does not), and mails
  the new address a verification link once the transaction commits.  Following
  that link, or a password reset or invitation link, sets it again.
  ``seed_demo`` stamps every seeded account but a donor verified as of its
  ``created_at``.

.. _account-kinds:

**Kinds of account.**  ``kind`` holds one of the three
:ref:`AccountKind <choices-account-kind>` values:

``member``
    Pays dues and is expected to keep paying, or holds a lifetime term.
``friend``
    Holds a portal account and pays no dues.  A friend's membership state is
    always ``friend``, never current and never expired, and a friend is never
    sent a renewal reminder.
``donor``
    Gave through the public site without joining.  A donor holds an unusable
    password and no role, so cannot sign in; login answers the generic
    wrong-credentials refusal, and the password-reset, invitation and
    verification emails are never sent to one.  ``PasswordResetConfirmSerializer``
    refuses a donor's reset link as it refuses a forged one.
    ``payments.donations.donor_for`` finds a donor by email address
    (case-insensitively) for each gift on the public donation page, or makes one
    with ``create_account(kind=donor)`` and a ``MemberProfile`` holding the phone
    and whatever else the giver told us; the email address stays unverified.  A
    donor's gifts are ordinary ``Payment`` rows with no plan (see
    :ref:`api-public-donations`).

``PERSON_KINDS`` (``member`` and ``friend``) are the kinds registration and an
administrator may choose; nobody is made a donor by hand, and a donor changes
kind only by registering and then following the verification link, which
upgrades the account in place.

The **effective kind** adds the pending change: ``members.services.account_kind(user,
today)`` is ``friend`` when ``kind`` is ``friend`` or ``friend_on`` is on or before
``today``, and ``kind`` otherwise.  ``kind_annotation(today)`` is the same rule as a
``Case`` expression, and ``membership_annotations`` carries it as
``effective_kind``.  ``convert_due_friends(today)`` writes the due conversions
down (``kind = friend``, ``friend_on = null``, audit ``account.kind``); the daily
reminder run calls it.  ``accounts.services.set_kind`` is the one way a kind is
written by hand (by an administrator's edit that changes the kind, the
verification link that upgrades a donor, or ``activate_term`` making a friend a
member), and it always clears ``friend_on``.  ``convert_due_friends`` writes each
row only while it still qualifies, so a member whose payment cleared
``friend_on`` after the list was read stays a member.

A member sets ``friend_on`` themselves with ``POST /me/kind/friend``
(:ref:`api-kind-switch`): ``members.services.become_friend(user, today)`` stores
the day after a current membership's unbroken coverage ends, or makes a member
with nothing current a friend at once, and ``undo_become_friend`` clears a date
still ahead.  ``become_friend`` refuses a donor, a current life member, and a
friend; ``undo_become_friend`` refuses anybody with nothing pending, a donor
included.  ``payments.renewals.switch_to_friend`` wraps
``become_friend`` with the end of the automatic renewal (see
:ref:`renewals-friend-switch`).

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
    Delegates to ``members.services.membership_status``; see
    :ref:`membership-status` below.
``can_access_members_content``
    ``True`` when the user is a superuser, **or** their membership is current,
    **or** they hold any role other than plain ``member``.  A friend is never
    current, so a friend without a staff role is refused.  This is the test
    the CMS members-only wall and ``GET /site/config`` both use.  A DART leader
    whose own membership has lapsed still reads members-only pages.
``display_name``
    Full name, falling back to the email address.
``email_verified``
    ``True`` when ``email_verified_at`` is set.

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
     - a member or a friend with a portal account: own profile, own payments
       and membership, join and renew, and members-only content while the
       membership is current
   * - ``dart_leader``
     - \+ look up any member and see membership, medical, certificate, and
       aircraft insurance currency; read the full member list, filterable by
       DART or county, and download its report
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

- ``member`` is granted at registration, to members and friends alike; a donor
  holds no role at all (``accounts.services.create_account`` decides by kind).
  The account administrator's member list is every ``User`` row, narrowed by
  ``?role=``.
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

A local Disaster Airlift Response Team (DART).

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``name``
     - ``CharField(120)``, unique
     - not null; required
     - the team's name, unique
   * - ``airport_identifiers``
     - ``CharField(120)``
     - not null; required
     - every field the team flies from, stored as ``"CCR, C83"`` (below)
   * - ``website_url``
     - ``URLField(200)``
     - not null; default ``""``
     - the team's own site, if it has one
   * - ``is_active``
     - ``BooleanField``
     - not null; default ``True``
     - false for a team that has stood down; it leaves the public catalog and the pickers
   * - ``roster_sent_at``
     - ``DateTimeField``
     - null; default ``NULL``
     - when the team's monthly roster last went out to its ticked contacts, or null when none has; only the roster sender writes it

**Constraints, indexes, and ordering.**

- Index ``darts_dart_active_idx`` on (``is_active``, ``name``).
- Ordering: ``name``.

Ordered by ``name`` everywhere: a reader looking for their own team scans for
its name, and no hand-kept ordering can go stale.

**Relationships.**

- Referenced by ``cms.DartPage.dart``, ``darts.DartContact.dart``, ``members.MemberProfile.dart``.

**Airports.**  ``airport_identifiers`` is every field the team flies from,
comma-separated and stored in the canonical ``"CCR, C83"`` form that ``save()``
writes: a DART is organized around its airports and several cover more than
one, so Contra Costa is ``CCR, C83`` and San Diego lists nine.  Each identifier
is exactly three letters or digits, and a list holds at most
``MAX_AIRPORT_IDENTIFIERS`` (12).  The four-letter ICAO form is the same field
with a ``K`` in front, and that ``K`` is trimmed on the way in (``KCRQ`` is
stored as ``CRQ``), so one airport is written one way everywhere; a
three-character identifier that begins with ``K`` is left alone, because Kelso
really is ``KLS``.  ``airports`` gives the list, ``home_airport`` its first
entry, which is what a single-line summary shows, and ``roster_recipients()``
the contacts ticked to receive the roster who have an address.  ``__str__`` is
``"Contra Costa (CCR, C83)"``.

Sixteen are seeded from ``DARTS`` in ``apps/members/seed.py``, each with the
handful of example contacts ``seed_darts`` generates, the leader and the
deputy leader ticked to receive the roster.  ``cms.DartPage`` points at this
table with a nullable ``SET_NULL`` foreign key, so deleting a DART leaves its
page in place with no DART attached, and the airports are never retyped in the
CMS.  A DART is identified by the fields it flies from, so it carries no town of
its own.

``DartContact``
---------------

One named volunteer who runs a DART, and how to reach them.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``dart``
     - ``ForeignKey`` to ``darts.Dart``, ``CASCADE``
     - not null; required
     - the team this person runs
   * - ``name``
     - ``CharField(120)``
     - not null; required
     - the person's name
   * - ``title``
     - ``CharField(80)``
     - not null; required
     - the job, such as DART leader
   * - ``phone``
     - ``CharField(12)``
     - not null; default ``""``
     - optional, stored as ``XXX-XXX-XXXX``
   * - ``email``
     - ``EmailField(254)``
     - not null; default ``""``
     - optional
   * - ``sort_order``
     - ``PositiveIntegerField``
     - not null; default ``0``
     - the listing order within the team
   * - ``receives_roster``
     - ``BooleanField``
     - not null; default ``False``
     - whether the person is sent the team's roster; a ticked person with no email address is skipped

**Constraints, indexes, and ordering.**

- Ordering: ``sort_order``, ``pk``.

**Relationships.**

- ``dart``: foreign key to ``darts.Dart``, ``CASCADE``; the reverse accessor is ``contacts``.

``save()`` stores the phone number as ``XXX-XXX-XXXX``.  A DART lists any
number of contacts, and a person without an email address may be ticked to
receive the roster, to be skipped when it goes out.  The foreign key cascades,
so a contact has no life without its DART.

This is deliberately not a link to a member account: the person an emergency
manager asks for by name may hold no account at all, and the listing outlives
whoever holds the job this year.

members
=======

``MemberProfile``
-----------------

Everything the join form collects, one row per account, plus two fields only
administrators see.  Deleting the account deletes the profile.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``user``
     - ``OneToOneField`` to ``accounts.User``, ``CASCADE``
     - not null; required
     - the account the profile belongs to; related name ``profile``
   * - ``phone``
     - ``CharField(12)``
     - not null; default ``""``
     - the member's own number, stored as ``XXX-XXX-XXXX``; required by the profile form
   * - ``phone_extension``
     - ``CharField(6)``
     - not null; default ``""``
     - up to six digits
   * - ``phone_alt``
     - ``CharField(12)``
     - not null; default ``""``
     - a second number, ``XXX-XXX-XXXX``
   * - ``phone_alt_extension``
     - ``CharField(6)``
     - not null; default ``""``
     - up to six digits
   * - ``address_line1``
     - ``CharField(200)``
     - not null; default ``""``
     - street address
   * - ``address_line2``
     - ``CharField(200)``
     - not null; default ``""``
     - second address line
   * - ``city``
     - ``CharField(120)``
     - not null; default ``""``
     - city
   * - ``state``
     - ``CharField(2)``, choices :ref:`US_STATE_CHOICES <choices-us-state>`
     - not null; default ``"CA"``
     - two-letter USPS code
   * - ``postal_code``
     - ``CharField(5)``
     - not null; default ``""``
     - five-digit ZIP code
   * - ``county``
     - ``CharField(120)``, choices :ref:`CALIFORNIA_COUNTIES <choices-county>`
     - not null; default ``""``
     - the California county a DART would call on; blank for a member outside California
   * - ``emergency_contact_name``
     - ``CharField(160)``
     - not null; default ``""``
     - who to call in an emergency
   * - ``emergency_contact_phone``
     - ``CharField(12)``
     - not null; default ``""``
     - ``XXX-XXX-XXXX``
   * - ``emergency_contact_phone_extension``
     - ``CharField(6)``
     - not null; default ``""``
     - up to six digits
   * - ``home_airport_identifier``
     - ``CharField(3)``
     - not null; default ``""``
     - three characters, never a leading ``K``
   * - ``home_airport_city``
     - ``CharField(120)``
     - not null; default ``""``
     - the town the home airport serves
   * - ``dart``
     - ``ForeignKey`` to ``darts.Dart``, ``SET_NULL``
     - null; default ``NULL``
     - the DART the member belongs to; related name ``members``
   * - ``air_care_alliance_number``
     - ``CharField(40)``
     - not null; default ``""``
     - the member's Air Care Alliance number
   * - ``pilot_certificate_type``
     - ``CharField(16)``, choices :ref:`PilotCertificateType <choices-pilot-certificate-type>`
     - not null; default ``"none"``
     - the pilot certificate held, ``none`` for a non-pilot
   * - ``certificate_number``
     - ``CharField(40)``
     - not null; default ``""``
     - required by the serializer when a certificate is held
   * - ``ifr_rated``
     - ``CharField(4)``, choices :ref:`IfrRated <choices-ifr-rated>`
     - not null; default ``"na"``
     - whether the pilot holds an instrument rating
   * - ``ratings``
     - ``JSONField``
     - not null; default ``[]``
     - a JSON list of rating values (below)
   * - ``medical_type``
     - ``CharField(16)``, choices :ref:`MedicalType <choices-medical-type>`
     - not null; default ``"none"``
     - the medical certificate held, ``none`` for none on file
   * - ``medical_expiration``
     - ``DateField``
     - null; default ``NULL``
     - required by the serializer when a medical is held; BasicMed and class medicals both use it
   * - ``flight_review_date``
     - ``DateField``
     - null; default ``NULL``
     - the last flight review
   * - ``total_hours``
     - ``PositiveIntegerField``
     - null; default ``NULL``
     - logged hours, at most ``MAX_TOTAL_HOURS`` (99,999)
   * - ``flies_rented_aircraft``
     - ``BooleanField``
     - not null; default ``False``
     - the member rents or borrows, so has no airframe of their own to list
   * - ``vol_mission_pilot``
     - ``BooleanField``
     - not null; default ``False``
     - volunteer interest: mission pilot
   * - ``vol_ground_team``
     - ``BooleanField``
     - not null; default ``False``
     - volunteer interest: ground support
   * - ``vol_exercise_training``
     - ``BooleanField``
     - not null; default ``False``
     - volunteer interest: exercises and training
   * - ``vol_member_support``
     - ``BooleanField``
     - not null; default ``False``
     - volunteer interest: member support
   * - ``vol_fundraising``
     - ``BooleanField``
     - not null; default ``False``
     - volunteer interest: fundraising
   * - ``vol_social_media``
     - ``BooleanField``
     - not null; default ``False``
     - volunteer interest: social media
   * - ``vol_newsletter``
     - ``BooleanField``
     - not null; default ``False``
     - volunteer interest: newsletter
   * - ``member_since``
     - ``DateField``
     - null; default ``NULL``
     - the day this person first joined, stamped with the first term and never moved by a renewal or a gap
   * - ``profile_updated_at``
     - ``DateTimeField``
     - null; default ``NULL``
     - when profile information was last written (below)
   * - ``notes``
     - ``TextField``
     - not null; default ``""``
     - administrators' notes; not in the member-facing serializer
   * - ``how_heard``
     - ``CharField(200)``
     - not null; default ``""``
     - how the member heard of CalDART; administrators only
   * - ``aircraft``
     - ``ManyToManyField`` to ``aircraft.Aircraft``
     - not null; empty by default
     - "planes commonly flown"; related name ``pilots``

**Constraints, indexes, and ordering.**

- Index ``members_prof_medexp_idx`` on (``medical_expiration``).
- Index ``members_prof_cert_idx`` on (``pilot_certificate_type``).
- Ordering: ``user__last_name``, ``user__first_name``.

**Relationships.**

- ``user``: one-to-one to ``accounts.User``, ``CASCADE``; the reverse accessor is ``profile``.
- ``dart``: foreign key to ``darts.Dart``, ``SET_NULL``, nullable; the reverse accessor is ``members``.
- ``aircraft``: many-to-many to ``aircraft.Aircraft``; the reverse accessor is ``pilots``.

**Groups of fields.**  The contact fields come first: ``save()`` stores
``phone``, ``phone_alt``, and ``emergency_contact_phone`` as ``XXX-XXX-XXXX``
(``PHONE_FIELDS``), and each number carries its own extension, so nobody appends
one to the number and breaks the format every other screen relies on.  The
aviation fields follow, then the seven ``vol_*`` volunteer interests, then
``member_since`` and ``profile_updated_at``.  ``notes`` and ``how_heard`` are
administrator-only: neither is in the member-facing serializer, and both appear
on ``GET /admin/members/{id}``.

``profile_updated_at`` is when profile information was last written: a member's
own edit, an administrator's edit to the profile or to the account's name or
email, an aircraft attached or detached, or the profile's creation.  It stays
``NULL`` until one of those happens, so a seeded profile nobody has touched
answers ``NULL``, and it never moves for a payment, a membership grant or
renewal, a reminder, or a role change.  ``apps.members.services.touch_profile``
is its only writer.

``ratings`` is a ``JSONField(default=list)`` of
:ref:`RATING_CHOICES <choices-ratings>` values.  The database does not police
its contents; the serializer does, refusing unknown values, removing duplicates,
and preserving the order given.

**Invariants**, all enforced in the API serializers rather than the model, so
that the message a person reads can be specific:

- ``phone`` is required, and every number is ten digits; an extension is up to
  six digits.
- A ``medical_type`` other than ``none`` requires a ``medical_expiration``.
- A ``pilot_certificate_type`` other than ``none`` requires a
  ``certificate_number``.
- ``postal_code`` is five digits; ``home_airport_identifier`` is three letters
  or digits, the ICAO ``K`` trimmed.
- Cross-field rules are evaluated against the row **as it would be after the
  write**, so a one-field ``PATCH`` is judged on the whole profile.

**Derived properties.**

``medical_is_current``
    ``False`` when ``medical_type`` is ``none`` **or** ``medical_expiration``
    is ``NULL``; otherwise ``medical_expiration >= today``.  BasicMed and class
    medicals both use the same stored date; the model does not try to compute
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

A purchasable term.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``name``
     - ``CharField(80)``, unique
     - not null; required
     - what the plan is called, unique
   * - ``slug``
     - ``SlugField(80)``, unique
     - not null; required
     - the identifier the checkout names, unique
   * - ``price_cents``
     - ``PositiveIntegerField``
     - not null; required
     - the dues, in cents
   * - ``duration_days``
     - ``PositiveIntegerField``
     - null; default ``NULL``
     - the length of a term; null means lifetime
   * - ``is_active``
     - ``BooleanField``
     - not null; default ``True``
     - false hides the plan from ``GET /plans`` and the checkout
   * - ``sort_order``
     - ``PositiveIntegerField``
     - not null; default ``0``
     - the order plans are offered in
   * - ``description``
     - ``TextField``
     - not null; default ``""``
     - a sentence shown beside the plan

**Constraints, indexes, and ordering.**

- Ordering: ``sort_order``, ``name``.

**Relationships.**

- Referenced by ``members.Membership.plan``, ``payments.Payment.plan``, ``payments.RenewalMandate.plan``.

Two are seeded: **Annual**, ``annual``, 4500 cents, 365 days; and **Life**,
``life``, 65000 cents, no duration.  ``is_lifetime`` is
``duration_days is None``, and ``price_display`` is the price as ``$45.00``.
``GET /plans`` and the checkout only offer active plans.

``Membership``
--------------

One row per paid or granted term.  A member with a long history has many rows,
and the current one is worked out rather than flagged.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``user``
     - ``ForeignKey`` to ``accounts.User``, ``CASCADE``
     - not null; required
     - whose term it is; related name ``memberships``
   * - ``plan``
     - ``ForeignKey`` to ``members.MembershipPlan``, ``PROTECT``
     - not null; required
     - the plan bought or granted; a plan with terms against it cannot be deleted
   * - ``starts_on``
     - ``DateField``
     - not null; required
     - the first day covered
   * - ``ends_on``
     - ``DateField``
     - null; default ``NULL``
     - the last day covered, inclusive; null means lifetime
   * - ``status``
     - ``CharField(12)``, choices :ref:`MembershipStatusChoices <choices-membership-status-choices>`
     - not null; default ``"active"``
     - the stored state of the term
   * - ``source``
     - ``CharField(12)``, choices :ref:`MembershipSource <choices-membership-source>`
     - not null; default ``"payment"``
     - how the term was come by
   * - ``payment``
     - ``OneToOneField`` to ``payments.Payment``, ``SET_NULL``
     - null; default ``NULL``
     - the payment that bought it; related name ``membership``
   * - ``granted_by``
     - ``ForeignKey`` to ``accounts.User``, ``SET_NULL``
     - null; default ``NULL``
     - who granted a ``manual`` term; related name ``memberships_granted``
   * - ``note``
     - ``CharField(255)``
     - not null; default ``""``
     - free text, shown in the admin history

**Constraints, indexes, and ordering.**

- Index ``members_mship_user_end_idx`` on (``user``, ``-ends_on``).
- Index ``members_mship_status_idx`` on (``status``, ``ends_on``).
- Ordering: ``-starts_on``, ``-id``.

Newest first.

**Relationships.**

- ``user``: foreign key to ``accounts.User``, ``CASCADE``; the reverse accessor is ``memberships``.
- ``plan``: foreign key to ``members.MembershipPlan``, ``PROTECT``; the reverse accessor is ``memberships``.
- ``payment``: one-to-one to ``payments.Payment``, ``SET_NULL``, nullable; the reverse accessor is ``membership``.
- ``granted_by``: foreign key to ``accounts.User``, ``SET_NULL``, nullable; the reverse accessor is ``memberships_granted``.
- Referenced by ``payments.RenewalAttempt.membership``, ``reminders.ReminderLog.membership``.

``covers(on_date=None)`` is the row-level test: the term is ``active``, it has
started, and either it is lifetime or it has not run out.

A ``suspended`` term belongs to an account its holder deactivated
(:ref:`api-deactivation`).  Deactivating suspends every ``active`` term that is
lifetime or ends on or after that day (the covering term and any renewal
already paid for), and reactivating, by the person or by an administrator
ticking the account active again, turns each back to ``active``, or to
``expired`` if its end passed in the meantime.  While suspended, a term counts
for nothing: it never covers a day and is never the past term an expired member
is reported from, and the renewal reminders skip it.

.. _membership-status:

Membership status
=================

"Is this person a current member?" is the question the whole system turns on,
and it is answered in two places that must agree.

The service
-----------

``apps.members.services.membership_status(user, on_date=None)`` returns::

    {
        "status": "current" | "new" | "expired" | "none" | "friend",
        "expires_on": date | None,     # None for lifetime and for a friend
        "plan": str | None,
        "is_lifetime": bool,
    }

``friend``
    The account's effective kind on ``on_date`` is friend (see
    :ref:`kinds of account <account-kinds>`).  Decided before any term is looked at, so a friend's
    past terms — or a live one — never make them current or expired.
    ``expires_on`` and ``plan`` are ``None`` and ``is_lifetime`` is ``False``.
``current``
    Some active term covers ``on_date``.
``expired``
    No term covers ``on_date``, but at least one term that is neither canceled,
    ``new``, nor suspended has started.  ``expires_on`` and ``plan`` come from the most
    recent such term.
``new``
    Nothing has ever covered them and nothing paid has started, but a term is
    on file stored as ``new``: they joined and have not paid.  Somebody who
    lapsed and has since started an unpaid term stays ``expired``, because the
    history is what this value distinguishes.
``none``
    Nothing at all — which is also what an account whose only terms are
    suspended reads as while it is deactivated.  Everything else is ``None`` /
    ``False``.

Those five values are ``apps.members.models.MembershipState``, a
``TextChoices`` nothing stores: it is the computed answer, as against
``MembershipStatusChoices``, which is the state written on a term.  Every
serializer that offers the status, the ``?status=`` filter on the member list
and the payload builders take their values from it, so the backend spells them
in exactly one place.  The portal's ``MembershipState`` union, in
``frontend/src/portal/api/types.ts``, is the same five values.

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
5. Makes the account a member: a friend becomes one, and a member with a
   pending ``friend_on`` keeps being one, the date cleared
   (``accounts.services.set_kind``, audited ``account.kind`` when the kind
   really changes).  Paying dues, or an administrator's grant, is what
   membership is.  A donor's kind is left alone.

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
    Terms that are neither canceled, ``new``, nor suspended with
    ``starts_on <= today``, ordered by ``ends_on``
    descending with ``NULL`` first and then ``starts_on`` descending.  The
    first row is what ``membership_status`` reports for an expired member.

``joined_on``
    The earliest ``starts_on`` across all of the user's terms, canceled ones
    included.

``effective_kind``
    ``kind_annotation(today)``: ``friend`` when ``kind`` is ``friend`` or
    ``friend_on <= today``, else ``kind``.  ``membership_payload`` answers
    ``friend`` from it before reading any term annotation, and the member
    list's ``?status=`` filter puts every effective friend under ``friend`` and
    under no other status.

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
``apps/members/filters.py``:

``full_name``
    ``first_name`` and ``last_name`` concatenated, so ``?search=`` matches a
    full name in one ``icontains``.

``effective_expiry``
    ``coverage_end`` when ``covers_today``, else ``past_end``.  This is what
    ``?ordering=expires_on`` sorts on, with ``NULL`` — lifetime members and
    people who never joined — forced to the end in both directions.

.. important::

   Two implementations of one rule drift.  ``backend/tests/
   test_members_admin_status.py`` builds twenty deliberately awkward
   histories — early renewals, three-term chains, gaps, overlaps,
   cancellations, a lifetime plan bought to follow an annual one, a term ending
   exactly today, friends with lapsed and live terms, and conversions to friend
   due today and still ahead — and asserts the service and the SQL agree on every one.  If
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
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``n_number``
     - ``CharField(12)``, unique
     - not null; required
     - the registration, normalized on save (below)
   * - ``make``
     - ``CharField(60)``
     - not null; default ``""``
     - manufacturer
   * - ``model``
     - ``CharField(60)``
     - not null; default ``""``
     - model
   * - ``year``
     - ``PositiveIntegerField``
     - null; default ``NULL``
     - model year
   * - ``owner_type``
     - ``CharField(12)``, choices :ref:`OwnerType <choices-owner-type>`
     - not null; default ``"individual"``
     - who holds title
   * - ``owner_name``
     - ``CharField(160)``
     - not null; default ``""``
     - the owner's name
   * - ``owner_contact``
     - ``CharField(200)``
     - not null; default ``""``
     - email address or phone number, free text
   * - ``seats``
     - ``PositiveSmallIntegerField``
     - null; default ``NULL``
     - seats aboard
   * - ``insurance_carrier``
     - ``CharField(120)``
     - not null; default ``""``
     - the insurer
   * - ``insurance_policy_number``
     - ``CharField(60)``
     - not null; default ``""``
     - the policy number
   * - ``insurance_liability_per_occurrence_cents``
     - ``PositiveBigIntegerField``
     - not null; default ``0``
     - liability limit per occurrence, in cents
   * - ``insurance_liability_per_person_cents``
     - ``PositiveBigIntegerField``
     - not null; default ``0``
     - liability limit per person, in cents
   * - ``insurance_hull_cents``
     - ``PositiveBigIntegerField``
     - null; default ``NULL``
     - hull value, in cents
   * - ``insurance_expiration``
     - ``DateField``
     - null; default ``NULL``
     - the day the policy runs out
   * - ``notes``
     - ``TextField``
     - not null; default ``""``
     - free text
   * - ``created_by``
     - ``ForeignKey`` to ``accounts.User``, ``SET_NULL``
     - null; default ``NULL``
     - who added the record; related name ``aircraft_created``
   * - ``updated_by``
     - ``ForeignKey`` to ``accounts.User``, ``SET_NULL``
     - null; default ``NULL``
     - who last wrote the record; related name ``aircraft_updated``
   * - ``is_active``
     - ``BooleanField``
     - not null; default ``True``
     - "in service"

**Constraints, indexes, and ordering.**

- Index ``aircraft_insexp_idx`` on (``insurance_expiration``).
- Index ``aircraft_make_model_idx`` on (``make``, ``model``).
- Index ``aircraft_active_idx`` on (``is_active``).
- Ordering: ``n_number``.

**Relationships.**

- ``created_by``: foreign key to ``accounts.User``, ``SET_NULL``, nullable; the reverse accessor is ``aircraft_created``.
- ``updated_by``: foreign key to ``accounts.User``, ``SET_NULL``, nullable; the reverse accessor is ``aircraft_updated``.
- Referenced by ``aircraft.AircraftChange.aircraft``, ``members.MemberProfile.aircraft``.

**N-number normalization** is the invariant that makes the register usable.
``normalize_n_number()`` strips everything that is not a letter or a digit,
upper-cases what is left, and prefixes ``N`` when the result starts with a
digit.  ``save()`` applies it, so ``12345``, ``n12345``, ``N-12345``, and
``n-12345`` are all stored as ``N12345`` and collide on the unique constraint
as they should.  A mark that already begins with a letter keeps it, so
``c-gabc`` becomes ``CGABC``.

The API normalizes in ``NNumberField.to_internal_value``, *before* the
uniqueness validator runs, which is what makes a duplicate typed in a different
shape a clean 400 rather than a database error.  ``GET /aircraft/lookup``
normalizes the query term the same way.

**Derived properties.**

``insurance_is_current``
    ``False`` when ``insurance_expiration`` is ``NULL``; otherwise
    ``insurance_expiration >= today``.  "No policy on file" and "policy
    expired" are different states in the UI but both fail this test.
``insurance_summary``
    ``"$1,000,000 / $100,000 · exp 2027-03-01"``: per-occurrence over
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
history is what lets an administrator tell a correction from a renewal.  It
does not inherit ``TimestampedModel``: ``changed_at`` is its only date, and no
row is ever updated.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``aircraft``
     - ``ForeignKey`` to ``aircraft.Aircraft``, ``CASCADE``
     - not null; required
     - the record written; related name ``changes``, so deleting the record deletes its history
   * - ``changed_by``
     - ``ForeignKey`` to ``accounts.User``, ``SET_NULL``
     - null; default ``NULL``
     - who wrote it; null for a change no signed-in account made; related name ``aircraft_changes``
   * - ``changed_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the write happened
   * - ``kind``
     - ``CharField(8)``, choices :ref:`AircraftChangeKind <choices-aircraft-change-kind>`
     - not null; required
     - whether the write put the record there or altered it
   * - ``fields``
     - ``JSONField``
     - not null; default ``[]``
     - the column names the write moved; empty on a ``created`` row and on a save that altered nothing

**Constraints, indexes, and ordering.**

- Index ``aircraft_change_idx`` on (``aircraft``, ``-changed_at``).
- Ordering: ``-changed_at``, ``-id``.

Newest first, the primary key breaking a tie between two changes written in the
same instant.

**Relationships.**

- ``aircraft``: foreign key to ``aircraft.Aircraft``, ``CASCADE``; the reverse accessor is ``changes``.
- ``changed_by``: foreign key to ``accounts.User``, ``SET_NULL``, nullable; the reverse accessor is ``aircraft_changes``.

``aircraft.services.record_change()`` writes the row and stamps ``updated_by``
on the record in the same call, and the register's create and update handlers
are its only callers, so no write can leave the trail behind.
:doc:`api-aircraft` covers ``GET /aircraft/{id}/changes``, which is
``account_admin`` only.

payments
========

``Payment``
-----------

One attempt to pay for a membership term, make a contribution, or both.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``user``
     - ``ForeignKey`` to ``accounts.User``, ``PROTECT``
     - not null; required
     - who paid; the payment outlives the account; related name ``payments``
   * - ``plan``
     - ``ForeignKey`` to ``members.MembershipPlan``, ``PROTECT``
     - null; default ``NULL``
     - the plan bought; null for a pure donation; related name ``payments``
   * - ``amount_cents``
     - ``PositiveIntegerField``
     - not null; required
     - the total charged, never taken from the client
   * - ``plan_amount_cents``
     - ``PositiveIntegerField``
     - not null; default ``0``
     - the plan's share, 0 for a donation
   * - ``contribution_cents``
     - ``PositiveIntegerField``
     - not null; default ``0``
     - the donation added at checkout, or the whole of a gift
   * - ``currency``
     - ``CharField(3)``
     - not null; default ``"usd"``
     - always ``usd``
   * - ``provider``
     - ``CharField(12)``, choices :ref:`PaymentProvider <choices-payment-provider>`
     - not null; required
     - which backend took the money
   * - ``wallet``
     - ``CharField(16)``, choices :ref:`PaymentWallet <choices-payment-wallet>`
     - not null; default ``"unknown"``
     - how the member paid: from the Stripe charge (:doc:`payments-setup`), ``paypal``, ``mock``, the treasurer's choice for a payment recorded by hand, or ``unknown`` when the provider does not say
   * - ``provider_ref``
     - ``CharField(128)``
     - not null; default ``""``
     - the PaymentIntent id or PayPal order id
   * - ``status``
     - ``CharField(20)``, choices :ref:`PaymentStatus <choices-payment-status>`
     - not null; default ``"pending"``
     - where the attempt got to; only ``succeeded`` buys a term
   * - ``completed_at``
     - ``DateTimeField``
     - null; default ``NULL``
     - set when the payment succeeds
   * - ``fee_cents``
     - ``PositiveIntegerField``
     - not null; default ``0``
     - the provider's fee, as the provider reported it
   * - ``net_cents``
     - ``PositiveIntegerField``
     - not null; default ``0``
     - what reached CalDART's balance, as the provider reported it
   * - ``receipt_sent_at``
     - ``DateTimeField``
     - null; default ``NULL``
     - when CalDART's own receipt was last emailed
   * - ``received_on``
     - ``DateField``
     - null; default ``NULL``
     - for a payment recorded by hand, the day the money arrived
   * - ``reconciled_on``
     - ``DateField``
     - null; default ``NULL``
     - the day a treasurer matched it to a bank statement
   * - ``reconciled_by``
     - ``ForeignKey`` to ``accounts.User``, ``SET_NULL``
     - null; default ``NULL``
     - who matched it; related name ``payments_reconciled``
   * - ``note``
     - ``CharField(255)``
     - not null; default ``""``
     - a treasurer's note: the check number, the reason for a manual entry
   * - ``recorded_by``
     - ``ForeignKey`` to ``accounts.User``, ``SET_NULL``
     - null; default ``NULL``
     - the administrator who recorded a payment taken by hand; related name ``payments_recorded``
   * - ``raw``
     - ``JSONField``
     - not null; default ``{}``
     - the last provider payload, for forensics
   * - ``donor_fields``
     - ``JSONField``
     - not null; default ``{}``
     - a public gift's details, kept here until the payment settles; empty for every other payment (:doc:`api-payments`)

**Constraints, indexes, and ordering.**

- Constraint ``payments_provider_ref_unique``: unique on (``provider``, ``provider_ref``) where ``provider_ref`` is not blank.
- Index ``payments_user_created_idx`` on (``user``, ``-created_at``).
- Index ``payments_status_idx`` on (``status``, ``-completed_at``).
- Index ``payments_provider_idx`` on (``provider``, ``status``).
- Ordering: ``-created_at``, ``-id``.

Newest first.

**Relationships.**

- ``user``: foreign key to ``accounts.User``, ``PROTECT``; the reverse accessor is ``payments``.
- ``plan``: foreign key to ``members.MembershipPlan``, ``PROTECT``, nullable; the reverse accessor is ``payments``.
- ``reconciled_by``: foreign key to ``accounts.User``, ``SET_NULL``, nullable; the reverse accessor is ``payments_reconciled``.
- ``recorded_by``: foreign key to ``accounts.User``, ``SET_NULL``, nullable; the reverse accessor is ``payments_recorded``.
- Referenced by ``members.Membership.payment``, ``payments.Refund.payment``, ``payments.RenewalAttempt.payment``.

**Derived, not stored.**  ``refunded_cents`` is the sum of the payment's
succeeded refunds; ``kind`` is a :ref:`PaymentKind <choices-payment-kind>`
value read from the plan and the contribution; ``paid_on`` is the ledger date,
which is ``received_on`` for a payment recorded by hand and the local date of
``completed_at`` for every other provider; ``receipt_number`` is ``CALDART-``
followed by the id padded to six digits; and ``description`` names the plan,
the contribution, or both, for the provider's own record of the charge.

**Invariants.**

- ``payments_provider_ref_unique`` maps one Stripe PaymentIntent or PayPal order
  to one payment row, while the many pending rows that never got a reference do
  not collide.
- ``amount_cents`` is **never** taken from the client.  ``create_checkout``
  recomputes it as ``plan.price_cents + contribution_cents`` and refuses a
  total of zero.  The checkout serializers refuse a contribution above
  ``MAX_CONTRIBUTION_CENTS`` ($99,999.00).
- ``user`` is ``PROTECT``, which makes the payment table the ledger the
  accounts can rely on: revenue and donations for a closed period cannot
  disappear because somebody tidied up a departed member.  Deleting an account
  that has any payment raises ``ProtectedError``, whether the delete comes from
  the API, the Django admin, a management command or a shell.
  ``payment_deletion_refusal(user)`` words the refusal, and
  ``DELETE /admin/members/{user_id}`` turns it into a **403** pointing at
  deactivation (:doc:`api-members`); deactivating keeps the member, the profile,
  the terms, and the payments and only stops the sign-in.
- The two ways the Wagtail admin deletes an account, the delete view at
  ``/admin/users/delete/<id>/`` and the ``Delete`` bulk action on the users
  listing, are stopped before they write, by the ``before_delete_user`` and
  ``before_bulk_action`` hooks in ``apps/payments/wagtail_hooks.py``.  Each
  sends the operator back to the users listing with that same sentence as an
  error message; one protected account refuses a whole bulk batch, because the
  bulk delete is a single query that cannot succeed in part.
- ``partially_refunded`` and ``refunded`` say how much of the payment has been
  given back; the ``Refund`` rows beneath it carry the amounts, and
  ``refunded_cents`` adds the succeeded ones up.  The refund service writes
  both (:doc:`api-refunds`).

Contribution tiers are a module constant, not a table:
``CONTRIBUTION_TIERS`` in ``apps/payments/models.py`` (No contribution,
Participating $20, Bronze $100, Silver $300, Gold $1,000, Diamond $3,000, and
Platinum $10,000), served by ``GET /payments/config``.  The checkout also
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
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``payment``
     - ``ForeignKey`` to ``payments.Payment``, ``PROTECT``
     - not null; required
     - the payment given back against; related name ``refunds``
   * - ``amount_cents``
     - ``PositiveIntegerField``
     - not null; required
     - what was given back
   * - ``reason``
     - ``CharField(24)``, choices :ref:`RefundReason <choices-refund-reason>`
     - not null; required
     - why, as the treasurer chose
   * - ``note``
     - ``CharField(255)``
     - not null; default ``""``
     - the treasurer's own sentence
   * - ``status``
     - ``CharField(12)``, choices :ref:`RefundStatus <choices-refund-status>`
     - not null; default ``"pending"``
     - where the refund got to; only ``succeeded`` counts
   * - ``provider_ref``
     - ``CharField(128)``
     - not null; default ``""``
     - the Stripe or PayPal refund id; blank for a manual or mock refund
   * - ``requested_by``
     - ``ForeignKey`` to ``accounts.User``, ``SET_NULL``
     - null; default ``NULL``
     - the administrator who issued it; null when it was issued in the provider's own dashboard and reached CalDART by webhook; related name ``refunds_requested``
   * - ``refunded_at``
     - ``DateTimeField``
     - null; default ``NULL``
     - set when the provider confirms it
   * - ``raw``
     - ``JSONField``
     - not null; default ``{}``
     - the provider's refund payload

**Constraints, indexes, and ordering.**

- Index ``payments_refund_pay_idx`` on (``payment``, ``-created_at``).
- Index ``payments_refund_status_idx`` on (``status``, ``-refunded_at``).
- Ordering: ``-created_at``, ``-id``.

Newest first.

**Relationships.**

- ``payment``: foreign key to ``payments.Payment``, ``PROTECT``; the reverse accessor is ``refunds``.
- ``requested_by``: foreign key to ``accounts.User``, ``SET_NULL``, nullable; the reverse accessor is ``refunds_requested``.

**Invariants.**

- A payment's succeeded refunds never total more than its ``amount_cents``.
  The rule lives in the refund service rather than in the database, because it
  is a sum across rows.
- ``payment`` is ``PROTECT`` for the same reason ``Payment.user`` is: a refund
  is a financial record, and the payment it reverses cannot be deleted out from
  under it.

``RenewalMandate``
------------------

One person's standing authority for CalDART to charge a saved payment method on
a schedule.  With a plan it is an automatic renewal, charged once a year for
the dues and any contribution beside them; with no plan it is a recurring
donation, charged monthly, quarterly or yearly for the contribution alone, which
a member, a life member, and a friend may each hold.  The provider is always one
that can charge off-session.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``user``
     - ``ForeignKey`` to ``accounts.User``, ``CASCADE``
     - not null; required
     - whose authority it is; related name ``renewal_mandates``
   * - ``plan``
     - ``ForeignKey`` to ``members.MembershipPlan``, ``PROTECT``
     - null; default ``NULL``
     - the plan that renews, which always has a duration; null for a recurring donation; related name ``renewal_mandates``
   * - ``contribution_cents``
     - ``PositiveIntegerField``
     - not null; default ``0``
     - taken beside the dues, or on its own for a recurring donation
   * - ``cadence``
     - ``CharField(12)``, choices :ref:`MandateCadence <choices-mandate-cadence>`
     - not null; default ``"yearly"``
     - how often it charges; a renewal is always ``yearly``
   * - ``next_charge_on``
     - ``DateField``
     - not null; required
     - the day of the next charge (below)
   * - ``provider``
     - ``CharField(12)``, choices :ref:`MandateProvider <choices-mandate-provider>`
     - not null; required
     - the backend holding the saved method
   * - ``customer_ref``
     - ``CharField(128)``
     - not null; default ``""``
     - Stripe customer id / PayPal payer id
   * - ``method_ref``
     - ``CharField(128)``
     - not null; required
     - Stripe payment method id / PayPal vault id
   * - ``method_brand``
     - ``CharField(32)``
     - not null; default ``""``
     - the card brand; blank for PayPal
   * - ``method_last4``
     - ``CharField(4)``
     - not null; default ``""``
     - the card's last four digits; blank for PayPal
   * - ``method_exp_month``
     - ``PositiveSmallIntegerField``
     - null; default ``NULL``
     - the card's expiry month; null for PayPal
   * - ``method_exp_year``
     - ``PositiveSmallIntegerField``
     - null; default ``NULL``
     - the card's expiry year; null for PayPal
   * - ``method_label``
     - ``CharField(128)``
     - not null; required
     - what the member sees: "Visa ending 4242, expires 03/2028"
   * - ``status``
     - ``CharField(12)``, choices :ref:`MandateStatus <choices-mandate-status>`
     - not null; default ``"pending"``
     - ``pending`` from checkout until the method is confirmed, ``paused`` once the retries run out
   * - ``failure_count``
     - ``PositiveSmallIntegerField``
     - not null; default ``0``
     - consecutive failed charges; reset on success
   * - ``canceled_at``
     - ``DateTimeField``
     - null; default ``NULL``
     - when it was turned off
   * - ``canceled_by``
     - ``ForeignKey`` to ``accounts.User``, ``SET_NULL``
     - null; default ``NULL``
     - the member themselves, or the administrator who turned it off; related name ``renewal_mandates_canceled``
   * - ``last_charged_at``
     - ``DateTimeField``
     - null; default ``NULL``
     - the last successful charge
   * - ``raw``
     - ``JSONField``
     - not null; default ``{}``
     - the provider's payload for the saved method

**Constraints, indexes, and ordering.**

- Constraint ``renewal_mandate_one_plan_per_user``: unique on (``user``) where ``plan`` is set.
- Constraint ``renewal_mandate_one_donation_per_user``: unique on (``user``) where ``plan`` is null.
- Index ``payments_mandate_status_idx`` on (``status``, ``-created_at``).
- Ordering: ``-created_at``, ``-id``.

The two conditional constraints hold a person to one mandate of each kind.
Newest first.

**Relationships.**

- ``user``: foreign key to ``accounts.User``, ``CASCADE``; the reverse accessor is ``renewal_mandates``.
- ``plan``: foreign key to ``members.MembershipPlan``, ``PROTECT``, nullable; the reverse accessor is ``renewal_mandates``.
- ``canceled_by``: foreign key to ``accounts.User``, ``SET_NULL``, nullable; the reverse accessor is ``renewal_mandates_canceled``.
- Referenced by ``payments.RenewalAttempt.mandate``.

``next_charge_on`` has no database default: the code that creates a mandate
sets it to the day the membership runs out for a renewal and to today for a
donation, and every successful charge rolls it forward, to the end of the term
bought or by the cadence.

``RenewalAttempt``
------------------

One scheduled charge against a mandate, and the row every renewal email is
keyed on.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``mandate``
     - ``ForeignKey`` to ``payments.RenewalMandate``, ``CASCADE``
     - not null; required
     - the authority charged; related name ``attempts``
   * - ``membership``
     - ``ForeignKey`` to ``members.Membership``, ``CASCADE``
     - null; default ``NULL``
     - the term whose expiry this charge renews; null for a recurring donation; related name ``renewal_attempts``
   * - ``scheduled_on``
     - ``DateField``
     - not null; required
     - the day the charge is due
   * - ``retry_of``
     - ``ForeignKey`` to ``payments.RenewalAttempt``, ``SET_NULL``
     - null; default ``NULL``
     - the attempt this one retries; related name ``retries``
   * - ``outcome``
     - ``CharField(12)``, choices :ref:`RenewalOutcome <choices-renewal-outcome>`
     - not null; default ``"scheduled"``
     - where the charge got to
   * - ``payment``
     - ``ForeignKey`` to ``payments.Payment``, ``SET_NULL``
     - null; default ``NULL``
     - the payment the charge made; null until it is made; related name ``renewal_attempts``
   * - ``error``
     - ``CharField(255)``
     - not null; default ``""``
     - the provider's decline reason, in the words the member is shown
   * - ``noticed_at``
     - ``DateTimeField``
     - null; default ``NULL``
     - when the advance-warning email went out
   * - ``attempted_at``
     - ``DateTimeField``
     - null; default ``NULL``
     - when the charge was tried
   * - ``result_emailed_at``
     - ``DateTimeField``
     - null; default ``NULL``
     - when the charged or failed email went out

**Constraints, indexes, and ordering.**

- Constraint ``renewal_attempt_one_scheduled_per_mandate``: unique on (``mandate``) where ``outcome`` is ``scheduled``.
- Index ``payments_attempt_man_idx`` on (``mandate``, ``-scheduled_on``).
- Index ``payments_attempt_out_idx`` on (``outcome``, ``scheduled_on``).
- Ordering: ``-scheduled_on``, ``-id``.

A mandate waits on one charge at a time, so two scans running at once can never
each write, and then each take, the same charge.  Newest first.

**Relationships.**

- ``mandate``: foreign key to ``payments.RenewalMandate``, ``CASCADE``; the reverse accessor is ``attempts``.
- ``membership``: foreign key to ``members.Membership``, ``CASCADE``, nullable; the reverse accessor is ``renewal_attempts``.
- ``retry_of``: foreign key to ``payments.RenewalAttempt``, ``SET_NULL``, nullable; the reverse accessor is ``retries``.
- ``payment``: foreign key to ``payments.Payment``, ``SET_NULL``, nullable; the reverse accessor is ``renewal_attempts``.
- Referenced by ``payments.RenewalAttempt.retry_of``.

The three timestamps are what make the scanner idempotent: an email goes out
only when its own stamp is still ``NULL``, so a scan that runs twice in one day
sends nothing twice.

.. _data-model-year-statement:

``YearStatement``
-----------------

One row per account, per calendar year, written once the year-end contribution
statement email has gone out (:doc:`statements`): the record that keeps a
rerun for a year already sent from reaching an account twice.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``user``
     - ``ForeignKey`` to ``accounts.User``, ``CASCADE``
     - not null; required
     - the account sent the statement; related name ``year_statements``
   * - ``year``
     - ``PositiveSmallIntegerField``
     - not null; required
     - the calendar year the statement covers
   * - ``sent_at``
     - ``DateTimeField``
     - not null; required
     - when the email went out

**Constraints, indexes, and ordering.**

- Constraint ``year_statement_unique``: unique on (``user``, ``year``).
- Ordering: ``-year``, ``user_id``.

**Relationships.**

- ``user``: foreign key to ``accounts.User``, ``CASCADE``; the reverse accessor is ``year_statements``.

**Invariants.**

- ``year_statement_unique``: one statement per account, per year.
- Written only after the email is confirmed sent, never before: a send the
  mail server refuses leaves no row, so the account is retried the next run.

reminders
=========

``ReminderLog``
---------------

One row per reminder email sent: the record that makes the scanner idempotent.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``user``
     - ``ForeignKey`` to ``accounts.User``, ``CASCADE``
     - not null; required
     - who was reminded; related name ``reminder_logs``
   * - ``membership``
     - ``ForeignKey`` to ``members.Membership``, ``CASCADE``
     - not null; required
     - the term the reminder was about; related name ``reminder_logs``
   * - ``kind``
     - ``CharField(12)``, choices :ref:`ReminderKind <choices-reminder-kind>`
     - not null; required
     - the reminder stage
   * - ``sent_at``
     - ``DateTimeField``
     - not null; required
     - when the send was attempted
   * - ``to_email``
     - ``EmailField(254)``
     - not null; required
     - the address written to

**Constraints, indexes, and ordering.**

- Constraint ``reminders_once_per_kind``: unique on (``user``, ``membership``, ``kind``).
- Index ``reminders_kind_sent_idx`` on (``kind``, ``-sent_at``).
- Index ``reminders_user_sent_idx`` on (``user``, ``-sent_at``).
- Ordering: ``-sent_at``, ``-id``.

**Relationships.**

- ``user``: foreign key to ``accounts.User``, ``CASCADE``; the reverse accessor is ``reminder_logs``.
- ``membership``: foreign key to ``members.Membership``, ``CASCADE``; the reverse accessor is ``reminder_logs``.

Because of ``reminders_once_per_kind`` a second run writes nothing, and the log
row is written and committed before the send is attempted; a failure deletes
it by hand rather than recording an email that never left.  The reminder is
then still due, and a later run retries it for as long as the term stays in
that stage's span.

``kind`` and its offset in days from the membership's ``ends_on``
(``REMINDER_OFFSETS``), with the span of expiry dates it covers on a scan run
on day D:

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
twice (:ref:`reminders-stages`).  Lifetime members are skipped, as are
deactivated accounts, accounts with no email address, and members whose
unbroken coverage runs past the term in question, which is what stops an
early renewal being nagged about the term it replaced.  See :doc:`reminders`.

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
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``to_email``
     - ``EmailField(254)``
     - not null; required
     - the address written to
   * - ``to_name``
     - ``CharField(200)``
     - not null; default ``""``
     - the recipient's name as it was at send time; blank for a bare address nobody named
   * - ``user``
     - ``ForeignKey`` to ``accounts.User``, ``SET_NULL``
     - null; default ``NULL``
     - the account the email concerned; null for an address with no account behind it, or one since deleted; related name ``email_logs``
   * - ``purpose``
     - ``SlugField(64)``
     - not null; required
     - the template the body came from: ``reminder_t30``, ``receipt``, ``password_reset`` and the rest
   * - ``subject``
     - ``CharField(255)``
     - not null; required
     - the subject line as it was sent
   * - ``sent_at``
     - ``DateTimeField``
     - not null; required
     - when the send was attempted
   * - ``status``
     - ``CharField(6)``, choices :ref:`EmailStatus <choices-email-status>`
     - not null; default ``"sent"``
     - whether the mail server took the message
   * - ``error``
     - ``CharField(100)``
     - not null; default ``""``
     - the exception class of a refusal; blank on a send that went out
   * - ``attachments``
     - ``CharField(255)``
     - not null; default ``""``
     - the filenames that rode along, comma-separated; blank when none did

**Constraints, indexes, and ordering.**

- Index ``mail_purpose_sent_idx`` on (``purpose``, ``-sent_at``).
- Index ``mail_user_sent_idx`` on (``user``, ``-sent_at``).
- Ordering: ``-sent_at``, ``-id``.

Nothing reads the table to decide what to do next, so it carries no
constraint: a member who is written to twice has two rows.  ``ReminderLog`` is
the key that keeps a reminder from repeating; this is the record of the
message.

**Relationships.**

- ``user``: foreign key to ``accounts.User``, ``SET_NULL``, nullable; the reverse accessor is ``email_logs``.

A reminder's own ``ReminderLog`` row is deleted by hand when the send fails,
so the reminder stays due, but the send itself leaves a ``failed`` row here
regardless, the same as any other refused email.

``caldart.mail.send_templated`` takes an optional ``to_name`` and writes it as
given: the DART roster sender passes the ticked contact's own name, for a
recipient who may hold no account at all.  A caller that names an account
(``user_id``) but no ``to_name`` has the account's ``display_name`` written in
instead, so the row keeps the name its recipient had at send time even after
the account is later renamed.  ``EmailLog.recipient_name`` reads ``to_name``,
falling back to the linked account's current ``display_name`` when ``to_name``
is blank, and to ``""`` when there is no account either; it is what
``GET /system/emails``' ``user_name`` (:ref:`api-email-log`) and the email log
report's ``Name`` column read.

.. _data-model-reports:

reports
=======

A report itself is not a row: it is a spec its app declares (see :doc:`reports`),
and the rows here name one by its slug: ``members``, ``aircraft``,
``payments``, ``reconciliation``, ``contributions``, ``donors``, or ``emails``.

``SavedColumnSet``
------------------

A named choice of one report's columns, kept for the account that saved it.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``user``
     - ``ForeignKey`` to ``accounts.User``, ``CASCADE``
     - not null; required
     - the account the set belongs to; related name ``saved_column_sets``
   * - ``report``
     - ``CharField(32)``
     - not null; required
     - the report's slug, at most ``REPORT_SLUG_LENGTH`` (32) characters
   * - ``name``
     - ``CharField(60)``
     - not null; required
     - the set's name
   * - ``columns``
     - ``JSONField``
     - not null; default ``[]``
     - JSON list of the report's column keys, in the order it prints them; at least one, none repeated, every one in the report's registry

**Constraints, indexes, and ordering.**

- Constraint ``reports_column_set_unique_name``: unique on (``user``, ``report``, ``name``).
- Ordering: ``name``.

**Relationships.**

- ``user``: foreign key to ``accounts.User``, ``CASCADE``; the reverse accessor is ``saved_column_sets``.

``reports_column_set_unique_name`` compares the name exactly, so ``Roster`` and
``roster`` are two sets; saving under a name already in use replaces that set's
columns.  A report whose columns are fixed keeps no sets.

``ReportSubscription``
----------------------

One report, emailed to one address on a schedule (see
:doc:`scheduled-reports`).

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``created_at``
     - ``DateTimeField``
     - not null; set on insert
     - when the row was inserted
   * - ``updated_at``
     - ``DateTimeField``
     - not null; set on every save
     - when the row was last saved
   * - ``report``
     - ``CharField(32)``
     - not null; required
     - the report's slug
   * - ``recipient_user``
     - ``ForeignKey`` to ``accounts.User``, ``SET_NULL``
     - null; default ``NULL``
     - the account the report goes to; null for a confirmed address outside CalDART; related name ``report_subscriptions``
   * - ``recipient_email``
     - ``EmailField(254)``
     - not null; required
     - always filled: the account's address when the subscription was set up, or the address typed
   * - ``filters``
     - ``JSONField``
     - not null; default ``{}``
     - JSON object of the params the report takes, ``period`` included
   * - ``columns``
     - ``JSONField``
     - not null; default ``[]``
     - JSON list of column keys; empty means the report's defaults
   * - ``formats``
     - ``CharField(4)``, choices :ref:`ReportFormats <choices-report-formats>`
     - not null; required
     - which files ride along
   * - ``cadence``
     - ``CharField(9)``, choices :ref:`Cadence <choices-cadence>`
     - not null; required
     - how often it goes
   * - ``weekday``
     - ``PositiveSmallIntegerField``
     - not null; default ``0``
     - 0 (Monday) to 6 (Sunday); read by ``weekly`` alone
   * - ``is_active``
     - ``BooleanField``
     - not null; default ``True``
     - false pauses it; the sender pauses a subscription whose account may no longer read the report
   * - ``created_by``
     - ``ForeignKey`` to ``accounts.User``, ``SET_NULL``
     - null; default ``NULL``
     - who set it up; related name ``created_report_subscriptions``
   * - ``last_sent_at``
     - ``DateTimeField``
     - null; default ``NULL``
     - when it last went out, or null
   * - ``next_due_on``
     - ``DateField``
     - not null; required
     - the first day the daily run sends it

**Constraints, indexes, and ordering.**

- Index ``reports_sub_due_idx`` on (``is_active``, ``next_due_on``).
- Ordering: ``report``, ``recipient_email``.

``reports_sub_due_idx`` answers the daily run's question: which active
subscriptions are due.

**Relationships.**

- ``recipient_user``: foreign key to ``accounts.User``, ``SET_NULL``, nullable; the reverse accessor is ``report_subscriptions``.
- ``created_by``: foreign key to ``accounts.User``, ``SET_NULL``, nullable; the reverse accessor is ``created_report_subscriptions``.

A DART's roster needs no row of its own: who receives it is
``DartContact.receives_roster`` and when it last went is
``Dart.roster_sent_at``.

cms
===

The Wagtail models are described in full, with their templates and editing
rules, in :doc:`cms`; this section is their schema.  Every page type is a
multi-table child of Wagtail's ``Page``: its own table holds ``page_ptr`` and the
fields in its table below, and the columns every page shares live in
``wagtailcore_page``.

``wagtailcore.Page``
--------------------

Wagtail's own model, listed once here because every page type carries its
columns.  Wagtail writes most of them; CalDART's code reads ``title``,
``slug``, ``live``, ``show_in_menus``, and the tree position.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Field
     - Meaning
   * - ``id``
     - ``AutoField`` primary key, which each page type's ``page_ptr`` points at
   * - ``path``, ``depth``, ``numchild``
     - the page's place in the tree (``path`` is unique)
   * - ``title``, ``draft_title``, ``slug``, ``url_path``
     - the title shown, the title of the latest draft, the URL segment, and the
       full path Wagtail builds from the slugs
   * - ``seo_title``, ``search_description``
     - the promote tab's title and description
   * - ``show_in_menus``
     - whether the public navigation lists the page
   * - ``live``, ``has_unpublished_changes``, ``first_published_at``,
       ``last_published_at``, ``go_live_at``, ``expire_at``, ``expired``
     - publishing state and scheduling
   * - ``latest_revision``, ``live_revision``, ``latest_revision_created_at``
     - the revision history behind the page
   * - ``locked``, ``locked_at``, ``locked_by``
     - an editor's lock
   * - ``owner``
     - the account that created the page
   * - ``content_type``
     - which page type the row is
   * - ``locale``, ``translation_key``, ``alias_of``
     - Wagtail's localization and alias support, which CalDART does not use

``BasePage`` and ``MembersOnlyMixin``
-------------------------------------

Two abstract classes with no table of their own.

``BasePage`` is what every page type inherits.  It supplies
``RestrictedBlocksPageForm``, which hides the raw-HTML block from editors who
may not use it, ``body_headings``, the H2 headings of ``body`` used to build
the "on this page" rail, and ``show_on_this_page``, true once there are at
least three of them.

``MembersOnlyMixin`` adds one field, ``members_only`` (``BooleanField``, default
``False``), and overrides ``serve``: when the flag is set and the reader does
not pass ``user_can_access_members_content`` (the test behind
``User.can_access_members_content``), it renders
``cms/members_only_wall.html`` with **HTTP 403** and a call to action chosen
from the visitor's state: sign in, renew (naming the date), or join.
``StandardPage`` and ``NewsPage`` mix it in.

``HomePage``
------------

The site root: the welcome box, featured news, the missions flown, and the
sidebar.  It may live only under the tree root.  The home page also shows the
three latest news posts and the three soonest events, which it reads rather
than stores.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``page_ptr``
     - ``OneToOneField`` to ``wagtailcore.Page``, ``CASCADE``
     - not null; the parent row's ``id``
     - the row in ``wagtailcore_page`` this page extends (multi-table inheritance)
   * - ``hero_heading``
     - ``CharField(200)``
     - not null; default ``""``
     - the welcome box's heading
   * - ``hero_lede``
     - ``TextField``
     - not null; default ``""``
     - the sentence under it
   * - ``hero_image``
     - ``ForeignKey`` to ``wagtailimages.Image``, ``SET_NULL``
     - null; default ``NULL``
     - the welcome box's picture
   * - ``hero_image_caption``
     - ``CharField(200)``
     - not null; default ``""``
     - its caption
   * - ``urgent_cta_label``
     - ``CharField(60)``
     - not null; default ``"Request air support"``
     - the first button, in the alert color; a blank label hides it
   * - ``urgent_cta_url``
     - ``CharField(200)``
     - not null; default ``""``
     - where it goes; blank goes to ``/contact/``
   * - ``primary_cta_label``
     - ``CharField(60)``
     - not null; default ``"Join CalDART"``
     - the second button; a blank label hides it
   * - ``primary_cta_url``
     - ``CharField(200)``
     - not null; default ``"/portal/join"``
     - where it goes; blank goes to ``/portal/join``
   * - ``secondary_cta_label``
     - ``CharField(60)``
     - not null; default ``""``
     - the third button; a blank label hides it
   * - ``secondary_cta_url``
     - ``CharField(200)``
     - not null; default ``""``
     - where it goes; blank goes to the site root
   * - ``mission_statement``
     - ``RichTextField``
     - not null; default ``""``
     - set off inside the welcome box
   * - ``welcome_body``
     - ``RichTextField``
     - not null; default ``""``
     - the paragraphs under the mission statement
   * - ``missions_heading``
     - ``CharField(200)``
     - not null; default ``"Missions flown"``
     - the heading over the missions list
   * - ``missions_flown``
     - ``StreamField`` of ``MissionStreamBlock``
     - not null; default ``""``
     - ``mission`` blocks: what CalDART has carried, newest first
   * - ``tax_status``
     - ``RichTextField``
     - not null; default ``""``
     - the 501(c)(3) note in the membership box

**Constraints, indexes, and ordering.**

- Ordering: none of its own (Wagtail orders pages by their place in the tree).

**Relationships.**

- ``hero_image``: foreign key to ``wagtailimages.Image``, ``SET_NULL``, nullable; no reverse accessor.

The welcome box holds ``hero_heading``, ``hero_lede``, the captioned
``hero_image``, ``mission_statement``, ``welcome_body``, and the three calls to
action (the urgent, primary, and secondary buttons, each a label and a URL).
``missions_heading`` titles the ``missions_flown`` list, a StreamField of
``mission`` blocks.

``StandardPage``
----------------

A general content page, and the members-only page when ``members_only`` is set.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``page_ptr``
     - ``OneToOneField`` to ``wagtailcore.Page``, ``CASCADE``
     - not null; the parent row's ``id``
     - the row in ``wagtailcore_page`` this page extends (multi-table inheritance)
   * - ``members_only``
     - ``BooleanField``
     - not null; default ``False``
     - from ``MembersOnlyMixin``: serve the page only to readers who pass the members-only wall
   * - ``intro``
     - ``TextField``
     - not null; default ``""``
     - one or two sentences under the title
   * - ``body``
     - ``StreamField`` of ``ContentStreamBlock``
     - not null; default ``""``
     - the page's content

**Constraints, indexes, and ordering.**

- Ordering: none of its own (Wagtail orders pages by their place in the tree).

**Relationships.**

- None.

``NewsIndexPage`` and ``NewsPage``
----------------------------------

The news section: an index whose only children are posts.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``page_ptr``
     - ``OneToOneField`` to ``wagtailcore.Page``, ``CASCADE``
     - not null; the parent row's ``id``
     - the row in ``wagtailcore_page`` this page extends (multi-table inheritance)
   * - ``intro``
     - ``TextField``
     - not null; default ``""``
     - the sentence over the list of posts

**Constraints, indexes, and ordering.**

- Ordering: none of its own (Wagtail orders pages by their place in the tree).

A ``NewsPage`` may only live under a ``NewsIndexPage`` and takes no children.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``page_ptr``
     - ``OneToOneField`` to ``wagtailcore.Page``, ``CASCADE``
     - not null; the parent row's ``id``
     - the row in ``wagtailcore_page`` this page extends (multi-table inheritance)
   * - ``members_only``
     - ``BooleanField``
     - not null; default ``False``
     - from ``MembersOnlyMixin``, as on ``StandardPage``
   * - ``date``
     - ``DateField``
     - not null; required
     - the post date, which orders the news newest first
   * - ``intro``
     - ``TextField``
     - not null; default ``""``
     - the summary shown in lists
   * - ``image``
     - ``ForeignKey`` to ``wagtailimages.Image``, ``SET_NULL``
     - null; default ``NULL``
     - the post's picture
   * - ``body``
     - ``StreamField`` of ``ContentStreamBlock``
     - not null; default ``""``
     - the post

**Constraints, indexes, and ordering.**

- Ordering: ``-date``.

**Relationships.**

- ``image``: foreign key to ``wagtailimages.Image``, ``SET_NULL``, nullable; no reverse accessor.

``EventIndexPage`` and ``EventPage``
------------------------------------

The events calendar: an index that lists everything upcoming and paginates
what has passed, and whose only children are events.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``page_ptr``
     - ``OneToOneField`` to ``wagtailcore.Page``, ``CASCADE``
     - not null; the parent row's ``id``
     - the row in ``wagtailcore_page`` this page extends (multi-table inheritance)
   * - ``intro``
     - ``TextField``
     - not null; default ``""``
     - the sentence over the calendar

**Constraints, indexes, and ordering.**

- Ordering: none of its own (Wagtail orders pages by their place in the tree).

An ``EventPage`` may only live under an ``EventIndexPage`` and takes no
children.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``page_ptr``
     - ``OneToOneField`` to ``wagtailcore.Page``, ``CASCADE``
     - not null; the parent row's ``id``
     - the row in ``wagtailcore_page`` this page extends (multi-table inheritance)
   * - ``date``
     - ``DateField``
     - not null; required
     - the event date
   * - ``time``
     - ``CharField(60)``
     - not null; default ``""``
     - when it runs, such as 9 am to 1 pm
   * - ``location``
     - ``CharField(160)``
     - not null; default ``""``
     - the airport and town, or who it is for
   * - ``intro``
     - ``TextField``
     - not null; default ``""``
     - one line, shown in the calendar
   * - ``body``
     - ``StreamField`` of ``ContentStreamBlock``
     - not null; default ``""``
     - the details

**Constraints, indexes, and ordering.**

- Ordering: none of its own (Wagtail orders pages by their place in the tree).

``DartIndexPage`` and ``DartPage``
----------------------------------

The DART directory: an index whose only children are the teams' pages.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``page_ptr``
     - ``OneToOneField`` to ``wagtailcore.Page``, ``CASCADE``
     - not null; the parent row's ``id``
     - the row in ``wagtailcore_page`` this page extends (multi-table inheritance)
   * - ``intro``
     - ``TextField``
     - not null; default ``""``
     - the sentence over the directory
   * - ``body``
     - ``StreamField`` of ``ContentStreamBlock``
     - not null; default ``""``
     - content under the directory's introduction

**Constraints, indexes, and ordering.**

- Ordering: none of its own (Wagtail orders pages by their place in the tree).

A ``DartPage`` may only live under a ``DartIndexPage`` and takes no children.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``page_ptr``
     - ``OneToOneField`` to ``wagtailcore.Page``, ``CASCADE``
     - not null; the parent row's ``id``
     - the row in ``wagtailcore_page`` this page extends (multi-table inheritance)
   * - ``dart``
     - ``ForeignKey`` to ``darts.Dart``, ``SET_NULL``
     - null; default ``NULL``
     - the DART the page describes, whose airports it reads; related name ``pages``
   * - ``leader_name``
     - ``CharField(120)``
     - not null; default ``""``
     - the leader named on the page
   * - ``leader_contact``
     - ``CharField(200)``
     - not null; default ``""``
     - an email address or phone number
   * - ``body``
     - ``StreamField`` of ``ContentStreamBlock``
     - not null; default ``""``
     - the page's content

**Constraints, indexes, and ordering.**

- Ordering: none of its own (Wagtail orders pages by their place in the tree).

**Relationships.**

- ``dart``: foreign key to ``darts.Dart``, ``SET_NULL``, nullable; the reverse accessor is ``pages``.

The airport identifiers are read from the linked ``darts.Dart``, never retyped.

``ContactPage``
---------------

The contact page.  It takes no children.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``page_ptr``
     - ``OneToOneField`` to ``wagtailcore.Page``, ``CASCADE``
     - not null; the parent row's ``id``
     - the row in ``wagtailcore_page`` this page extends (multi-table inheritance)
   * - ``intro``
     - ``RichTextField``
     - not null; default ``""``
     - the words above the contact details, which come from site settings
   * - ``body``
     - ``StreamField`` of ``ContentStreamBlock``
     - not null; default ``""``
     - content under them

**Constraints, indexes, and ordering.**

- Ordering: none of its own (Wagtail orders pages by their place in the tree).

``DonatePage``
--------------

The public donation page: ``intro`` and ``thanks`` are both rich text, and the
donation form sits between them.  It may live under the home page or a
standard page, and takes no children (see :ref:`cms-donate-page`).

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``page_ptr``
     - ``OneToOneField`` to ``wagtailcore.Page``, ``CASCADE``
     - not null; the parent row's ``id``
     - the row in ``wagtailcore_page`` this page extends (multi-table inheritance)
   * - ``intro``
     - ``RichTextField``
     - not null; default ``""``
     - the words above the public donation form
   * - ``thanks``
     - ``RichTextField``
     - not null; default ``""``
     - the words shown in the form's place once a gift has gone through

**Constraints, indexes, and ordering.**

- Ordering: none of its own (Wagtail orders pages by their place in the tree).

``SiteSettings``
----------------

The organization's details and the active theme: a Wagtail ``BaseSiteSetting``,
so there is one row per Wagtail site, and editing it overwrites that row.

.. list-table::
   :header-rows: 1
   :widths: 22 26 18 34

   * - Field
     - Type
     - Null, default
     - Meaning
   * - ``id``
     - ``BigAutoField``
     - not null; assigned by the database
     - primary key
   * - ``site``
     - ``OneToOneField`` to ``wagtailcore.Site``, ``CASCADE``
     - not null; required
     - the Wagtail site these settings belong to
   * - ``org_name``
     - ``CharField(120)``
     - not null; default ``"The California DART Network"``
     - the organization's name, on every public page, in the portal, and in every email
   * - ``tagline``
     - ``CharField(200)``
     - not null; default ``"Volunteer disaster air transportation for California"``
     - the line under the name in the public masthead
   * - ``contact_email``
     - ``EmailField(254)``
     - not null; default ``"info@caldart.example.org"``
     - the address the contact page, the footer, the members-only wall, and every email give for questions
   * - ``duty_phone``
     - ``CharField(32)``
     - not null; default ``""``
     - the duty officer's number, shown in the masthead and on the contact page as the number to call about a mission
   * - ``mailing_address``
     - ``TextField``
     - not null; default ``""``
     - the postal address, in the masthead, the footer, and the contact page
   * - ``ein``
     - ``CharField(20)``
     - not null; default ``""``
     - the Employer Identification Number, in the footer and on the contact page
   * - ``donate_url``
     - ``CharField(200)``
     - not null; default ``""``
     - where the home page's **Donate** button goes; blank hides the button
   * - ``facebook_url``
     - ``URLField(200)``
     - not null; default ``""``
     - the footer's Facebook link
   * - ``twitter_url``
     - ``URLField(200)``
     - not null; default ``""``
     - the footer's Twitter link
   * - ``theme``
     - ``CharField(20)``, choices :ref:`THEME_CHOICES <choices-theme>`
     - not null; default ``"duty"``
     - the active theme (:doc:`theming`)
   * - ``footer_text``
     - ``TextField``
     - not null; default ``"CalDART is a 501(c)(3) non-profit. Contributions are tax deductible."``
     - the footer's closing sentence

**Constraints, indexes, and ordering.**

- Ordering: none of its own (Wagtail orders pages by their place in the tree).

**Relationships.**

- ``site``: one-to-one to ``wagtailcore.Site``, ``CASCADE``.

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
