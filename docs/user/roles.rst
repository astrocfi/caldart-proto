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

A user administrator, the treasurer, an account administrator, CalDART management, a
website administrator, and a system administrator must use two-factor sign-in: a
code from an authenticator app on their phone each time they sign in (see
:doc:`member/two-factor`).

These six are the **two-factor roles**. The portal's messages call them the
administrative roles. A user administrator can grant or take away a two-factor role only
if they hold it themselves. One who is also an account administrator can make somebody
else an account administrator. One who isn't the treasurer can't grant or take away
Treasurer. Any user administrator can grant and take away Member, Verifier, and DART
leader. A system administrator can grant and take away every role. Nobody can change their
own roles. That includes a system administrator, so ask another administrator.

This guide works the same way. Its menu and its contents list only the pages for the
screens you can use. If you open the address of any other page, you land on the
guide's front page. A system administrator sees
every page. The links on this page lead to every role's screens, so some of them
may bring you back to the front page too.


Member
======

Every member and every friend of CalDART holds the member role. It opens the
**My account** group of the menu:

* **Dashboard** (:doc:`member/dashboard`): your membership, your profile's state,
  members-only pages, and recent payments.
* **My profile** (:doc:`member/profile`): your contact and aviation details,
  whether you are a member or a friend, and deactivating your account.
* **My aircraft** (:doc:`member/my-aircraft`): the airplanes you fly, from the
  shared register, while your membership is current. A friend doesn't have **My
  aircraft**.
* **My payments** (:doc:`member/payments`): automatic renewal, recurring donations,
  every payment with its receipt, and contribution statements.
* **Donate** (:doc:`member/donate`): a gift, once or on a schedule.
* **Renew** (:doc:`member/renew`): your next term. A friend and a life member don't
  have a **Renew** entry. A life member gives through **Donate**.
* **Change password** (:doc:`member/change-password`) and **Change email**
  (:doc:`member/change-email`).
* **Email to me** (:doc:`member/messages`) and **Email preferences**
  (:doc:`member/email-preferences`): the bulk emails CalDART has sent you, to read again,
  and which types of bulk email it sends you.

A friend also reaches **Become a member** (:doc:`member/become-a-member`). While
your membership is current, the members-only pages of the public site open to you
(:doc:`member/members-only-content`). A donor doesn't hold a role and doesn't have a
portal at all.


Verifier
========

A verifier checks a member's pilot certificate, medical, and photo ID, and an
aircraft's insurance, against the documents, and marks each one verified. The role
adds the **Operations** group:

* **Member check** (:doc:`admin/member-check`): look up a member, read their
  verdict, and press **Verify** to correct and verify their pilot certificate,
  medical, and photo ID in one save. It also downloads the CalDART verification
  report, which lists everything still waiting to be verified.
* **Aircraft check** (:doc:`admin/aircraft-check`): look up an airplane and press
  **Verify** to correct and verify its insurance.

A verifier can't browse the membership list. A DART leader or a user
administrator grants the role from the member check, and a user administrator can
also grant it on the **User record** (:doc:`admin/user-record`). Anyone with a portal
account can be made a verifier, whatever other roles they hold, a treasurer included.
You can't make yourself a verifier, but you may verify your own documents.


DART leader
===========

Before a mission, a DART leader checks whether a member is fit to fly for
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
  and downloads. Only an account administrator opens the member record behind each
  name.

The role also adds part of the **Bulk email** group, for writing to the members and
friends of the leader's own DART, the one on their profile (:doc:`bulk-email/dart-leaders`):
**Compose** (:doc:`bulk-email/compose`), **Drafts and scheduled**
(:doc:`bulk-email/drafts`), and **Sent** (:doc:`bulk-email/sent`). A leader sees only the
emails they wrote. **Callouts** (:doc:`bulk-email/callouts`) collects the answers to the
mission callouts the leader sent and to those sent to their DART. **Email types** sets
which types of email a leader may send. To begin with, those are Operational and Mission
email.

Every role other than member also opens the members-only pages, whether or not the
holder's own membership is current.


User administrator
==================

A user administrator looks after accounts. The role adds:

* **Roles and status** (:doc:`admin/users`): every account, with filters, and the
  **User record** (:doc:`admin/user-record`) behind each: the roles it holds,
  deactivating and reactivating it, blocking it from reactivating, correcting its
  email address, and sending a password reset link or a verification message. The
  screen also downloads the CalDART roles report as a CSV or a PDF.
* **Member check** and **Aircraft check** (:doc:`admin/member-check`,
  :doc:`admin/aircraft-check`): verifying, as a verifier does, and making a member a
  verifier from the member check.
* The **CalDART roles report**: the people who hold each role other than member,
  with a section for each role, Verifier included. An account administrator can have
  it emailed to a user administrator on a schedule (:doc:`admin/subscriptions`).

A user administrator can't grant or take away the system administrator role, or a
two-factor role they don't hold themselves. They can't change their own roles either.


Treasurer
=========

The treasurer looks after the money. The role adds:

* **Accounting**, under **Finance** in the menu (:doc:`finance/index`), with its tabs:
  **Money overview** (the headline figures for a period; :doc:`finance/overview`),
  **Payments** (every payment, and **Record a payment** for a check or cash;
  :doc:`finance/payment-list`, :doc:`finance/record-payment`), **Renewals**
  (every automatic renewal and recurring donation; :doc:`finance/renewals`),
  **Reconciliation** (matching a period against the bank statement;
  :doc:`finance/reconciliation`), **Contributions** (:doc:`finance/contributions`),
  and **Donors** (:doc:`finance/donors`). Opening a payment shows its receipts and
  lets the treasurer refund it (:doc:`finance/payment-record`). A member's
  **Member ledger** (:doc:`finance/member-ledger`) shows everything one person has
  paid.
* **Emailed reports** (:doc:`admin/subscriptions`): the financial reports, and emailing them
  on a schedule.


Account administrator
=====================

An account administrator looks after the membership records. The role adds:

* **Members** (:doc:`admin/members`), **New member** (:doc:`admin/new-member`),
  and each member's record (:doc:`admin/member-record`): the profile, the
  membership terms, granting a term by hand, making a member a friend,
  deactivating and reactivating an account, and deleting a member.
* **Aircraft** (:doc:`admin/aircraft`) and
  each aircraft's record (:doc:`admin/aircraft-record`), and **New aircraft type** on any
  aircraft form, for an aircraft type the FAA has never registered.
* **DARTs** (:doc:`admin/darts`): the teams, their airports, and their leaders.
* **Accounting**: the finance area as the treasurer sees it, without **Donors**
  (:doc:`finance/index`).
* **Reminders** (:doc:`admin/reminders`): every renewal reminder CalDART has sent, and the
  reminder schedule that sets when they go out.
* **Emailed reports** (:doc:`admin/subscriptions`): reports by email, including the CalDART
  roles report, and sending each DART its roster.
* **Notification emails** (:doc:`admin/notifications`): who hears about what by email,
  from a sign-up to a refund.
* **Member check** and **Aircraft check** (:doc:`admin/member-check`,
  :doc:`admin/aircraft-check`), with verifying, just as a verifier has them. An account
  administrator also verifies from each member record and aircraft record.


CalDART management
==================

CalDART management writes to the membership as a whole. The role adds the **Bulk email**
group of the menu:

* **Compose** (:doc:`bulk-email/compose`): build a recipient list with the same filters the
  member list uses, write the message, send yourself a test, read the checks and the
  preview, and send it now or schedule it, with two minutes to cancel.
* **Drafts and scheduled** (:doc:`bulk-email/drafts`): every unsent email, to open,
  cancel, or delete.
* **Sent** (:doc:`bulk-email/sent`): every email sent, and what happened to each person's
  copy. From there you stop or finish a send, retry the failed copies, view one person's
  copy, hide it from **Email to me**, download the results, and start a new draft from an
  email with **Duplicate**.
* **Templates** (:doc:`bulk-email/templates`): saved messages to start an email from,
  such as reminders about an exercise.
* **Recipient groups** (:doc:`bulk-email/groups`): saved sets of people to add to a
  recipient list in one step. A group is either a fixed list or filters that run again
  each time.
* **Callouts** (:doc:`bulk-email/callouts`): the answers to every mission callout, who can
  fly and who hasn't answered. From there you remind the rest or close the answers.

CalDART management can write to anybody. It sees every bulk email and its sender, and
the DART of each DART leader's email. The role doesn't open a member record or a payment. A system
administrator, or a user administrator who is also CalDART management, grants it.


Website administrator
=====================

A website administrator writes the public site in its editing screens, which open
from the site itself: :doc:`pages and their blocks <website/pages-and-blocks>`,
:doc:`news and events <website/news-and-events>`, the :doc:`DART pages
<website/dart-pages>`, the :doc:`members-only pages <website/members-only>`, the
:doc:`site settings and theme <website/settings-and-themes>`, and :doc:`redirects
and documents <website/redirects-and-documents>`. The role doesn't add anything to the
portal's menu beyond the member's screens.


System administrator
====================

A system administrator holds every role above and can do everything those roles do. The
role adds:

* **Health and database** (:doc:`admin/health-database`): the site's health, whether other
  mail systems will trust its email, database backups, and the FAA aircraft data, with a way
  to load it now.
* **Sent emails** (:doc:`admin/sent-emails`): the log of every email CalDART has sent.
* **Email types** (:doc:`bulk-email/email-types`), under **Bulk email**: the types of
  bulk email, who may send each, and whether members may turn each off.
* **Coverage policy** on the **Aircraft** screen (:doc:`admin/aircraft`):
  which aircraft categories and airworthiness categories CalDART's insurance does not
  cover, and the note members read on **My aircraft**.
* **Scheduled tasks** (:doc:`admin/scheduled`): the six jobs that run on a schedule (the
  renewal reminder emails, the automatic renewal charges, the scheduled reports, the
  year-end contribution statements, the bounce check, and the bulk email sender), with a
  way to run each now, and the reminder schedule, which only a system administrator
  changes.
* **Job log** (:doc:`admin/job-log`), from **View log** on each scheduled job's panel and on
  the **Scheduled jobs** health check: every recent run of a scheduled job, how it ended,
  and everything it wrote.

A system administrator grants and takes away every role on every account but their own,
and cannot deactivate their own account or change their own roles.
