=====
Roles
=====

Every account holds one or more **roles**, and each role opens a set of screens.
The portal's menu shows only the screens your roles open, so two people can see
different menus. Roles add up: an account administrator who is also a DART leader
has both sets of screens. A user administrator grants roles; if a screen you need
is missing, ask one.

If you open a screen your roles do not reach, the portal shows **Not allowed** and
names the role the screen needs.

This guide works the same way. It shows each reader the screens their roles reach:
its menu and its contents list only the pages you can use, and the address of any
other page brings you back to the guide's front page. A system administrator sees
every page. The links on this page lead to every role's screens, so some of them
may bring you back to the front page too.


Member
======

Every member and every friend of CalDART holds the member role. It opens the
**Membership** group of the menu:

* **Dashboard** (:doc:`member/dashboard`): your membership, your profile's state,
  members-only pages, and recent payments.
* **My profile** (:doc:`member/profile`): your contact and aviation details,
  whether you are a member or a friend, and deactivating your account.
* **My aircraft** (:doc:`member/my-aircraft`): the airplanes you fly, from the
  shared register.
* **Payments** (:doc:`member/payments`): automatic renewal, recurring donations,
  every payment with its receipt, and contribution statements.
* **Donate** (:doc:`member/donate`): a gift, once or on a schedule.
* **Renew** (:doc:`member/renew`): your next term. A friend has no **Renew** entry.
* **Change password** (:doc:`member/change-password`) and **Change email**
  (:doc:`member/change-email`).

Every signed-in person also has **Email preferences** (:doc:`member/email-preferences`),
under **Bulk Email** in the menu: which kinds of bulk email CalDART sends them.

A friend also reaches **Become a member** (:doc:`member/become-a-member`). While
your membership is current, the members-only pages of the public site open to you
(:doc:`member/members-only-content`). A donor holds no role and has no portal at
all.


Verifier
========

A verifier checks a member's pilot certificate, medical, and photo ID, and an
aircraft's insurance, against the documents, and marks each one verified. The role
adds the **Operations** group:

* **Member check** (:doc:`admin/member-check`): look up a member, read their
  verdict, and press **Verify** to correct and verify their pilot certificate,
  medical, and photo ID in one save. It also downloads the CalDART verification
  report of everything nobody has verified yet.
* **Aircraft check** (:doc:`admin/aircraft-check`): look up an airplane and press
  **Verify** to correct and verify its insurance.

A verifier does not browse the membership list. A DART leader or a user
administrator grants the role from the member check, and a user administrator can
also grant it on the **User record** (:doc:`admin/user-record`). You may verify your
own documents.


DART leader
===========

A DART leader checks, before a mission, whether a member is fit to fly for
CalDART. The role adds the **Operations** group and one entry of
**Administration**:

* **Member check** (:doc:`admin/member-check`): look up any member by name, email,
  phone, or N-number and see whether their membership and medical are current, whether
  their pilot certificate, medical, and photo ID are verified, and whether their
  aircraft insurance is current and verified. A DART leader verifies there as a
  verifier does, and makes a member a verifier with **Make a verifier**.
* **Aircraft check** (:doc:`admin/aircraft-check`): look up an airplane by N-number,
  see its insurance and who flies it, and verify the insurance.
* **Members** (:doc:`admin/members`): the whole membership list, with its filters
  and downloads. The member record behind each name stays the account
  administrator's.

Every role beyond member also opens the members-only pages, whatever the holder's
own membership.


User administrator
==================

A user administrator looks after accounts. The role adds:

* **Users & roles** (:doc:`admin/users`): every account, with filters, and the
  **User record** (:doc:`admin/user-record`) behind each: the roles it holds,
  deactivating and reactivating it, blocking it from reactivating, correcting its
  email address, and sending a password reset link or a verification message. The screen also downloads the
  CalDART roles report as a CSV or a PDF.
* **Member check** and **Aircraft check** (:doc:`admin/member-check`,
  :doc:`admin/aircraft-check`): verifying, as a verifier does, and making a member a
  verifier from the member check.
* The **CalDART roles report**: the people who hold each role other than member,
  in a section per role, Verifier among them. An account administrator can have it emailed to a user
  administrator on a schedule (:doc:`admin/subscriptions`).

A user administrator cannot grant or take away the system administrator role.


Treasurer
=========

The treasurer looks after the money. The role adds:

* **Payments**, the finance area (:doc:`finance/index`), with its tabs:
  **Overview** (the headline figures for a period; :doc:`finance/overview`),
  **Payments** (every payment, and **Record a payment** for a check or cash;
  :doc:`finance/payment-list`, :doc:`finance/record-payment`), **Renewals**
  (every automatic renewal and recurring donation; :doc:`finance/renewals`),
  **Reconciliation** (matching a period against the bank statement;
  :doc:`finance/reconciliation`), **Contributions** (:doc:`finance/contributions`),
  and **Donors** (:doc:`finance/donors`). Opening a payment shows its receipts and
  lets the treasurer refund it (:doc:`finance/payment-record`). A member's
  **Member ledger** (:doc:`finance/member-ledger`) shows everything one person has
  paid.
* **Subscriptions** (:doc:`admin/subscriptions`): the financial reports, and emailing them on
  a schedule.


Account administrator
=====================

An account administrator looks after the membership records. The role adds:

* **Members** (:doc:`admin/members`), **New member** (:doc:`admin/new-member`),
  and each member's record (:doc:`admin/member-record`): the profile, the
  membership terms, granting a term by hand, making a member a friend,
  deactivating and reactivating an account, and deleting a member.
* **Aircraft** (the **Aircraft register**; :doc:`admin/aircraft-register`) and
  each aircraft's record (:doc:`admin/aircraft-record`), and **Add a type** on any
  aircraft form, for an aircraft type the FAA has never registered.
* **DARTs** (:doc:`admin/darts`): the teams, their airports, and their leaders.
* **Payments**: the finance area as the treasurer sees it, without **Donors**
  (:doc:`finance/index`).
* **Reminders** (:doc:`admin/reminders`): every renewal reminder CalDART has sent, and the
  reminder schedule that dates them.
* **Subscriptions** (:doc:`admin/subscriptions`): reports by email, the CalDART roles report
  among them, and sending each DART its roster.
* **Notifications** (:doc:`admin/notifications`): who hears about what by email,
  from a sign-up to a refund.
* **Member check** and **Aircraft check** (:doc:`admin/member-check`,
  :doc:`admin/aircraft-check`), with verifying, as a verifier has them. An account
  administrator also verifies from each member record and aircraft record.


CalDART management
==================

CalDART management writes to the membership as a whole. The role adds the **Bulk Email**
group of the menu:

* **Compose** (:doc:`bulk-email/compose`): build a batch of people with the same filters the
  member list uses, write the message, and send it now or schedule it, with two minutes to
  cancel.
* **Drafts & scheduled** (:doc:`bulk-email/drafts`): every email not yet sent, to open,
  cancel, or delete.
* **Sent** (:doc:`bulk-email/sent`): every email sent, with the result for each person, to
  stop or finish a send, to download as a CSV, and to start a new draft from with
  **Duplicate**.
* **Templates** (:doc:`bulk-email/templates`): the messages kept to start an email from,
  such as the monthly newsletter.
* **Recipient groups** (:doc:`bulk-email/groups`): the people kept to add to a batch in one
  step, either a fixed list or filters run again each time.
* **Mail delivery** (:doc:`bulk-email/mail-delivery`): check that other mail systems will
  trust and deliver the email CalDART sends, and what to ask for when they will not.

The role opens no member record and no payment. A user administrator grants it.


Website administrator
=====================

A website administrator writes the public site in its editing screens, which open
from the site itself: :doc:`pages and their blocks <website/pages-and-blocks>`,
:doc:`news and events <website/news-and-events>`, the :doc:`DART pages
<website/dart-pages>`, the :doc:`members-only pages <website/members-only>`, the
:doc:`site settings and theme <website/settings-and-themes>`, and :doc:`redirects
and documents <website/redirects-and-documents>`. The role adds nothing to the
portal's menu beyond the member's screens.


System administrator
====================

A system administrator holds every role above and can do everything they can. The
role adds:

* **Health & Database** (:doc:`admin/health-database`): the site's health, database
  backups, and the aircraft database loaded from the FAA registry, with a way to load
  it now.
* **Sent Emails** (:doc:`admin/sent-emails`): the log of every email CalDART has sent.
* **Email types** (:doc:`bulk-email/email-types`), under **Bulk Email**: the kinds of
  bulk email, who may send each, and whether members may turn each off.
* **Coverage policy** on the **Aircraft register** (:doc:`admin/aircraft-register`):
  which aircraft categories and airworthiness categories CalDART's insurance does not
  cover, and the note members read on **My aircraft**.
* **Scheduled** (:doc:`admin/scheduled`): the four jobs that run on a schedule (the
  renewal reminder emails, the automatic renewal charges, the scheduled reports, and
  the year-end contribution statements), with a way to run each now, and the reminder
  schedule, which only a system administrator changes.

A system administrator cannot deactivate their own account.
