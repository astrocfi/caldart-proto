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

A friend also reaches **Become a member** (:doc:`member/become-a-member`). While
your membership is current, the members-only pages of the public site open to you
(:doc:`member/members-only-content`). A donor holds no role and has no portal at
all.


DART leader
===========

A DART leader checks, before a mission, whether a member is fit to fly for
CalDART. The role adds the **Operations** group and one entry of
**Administration**:

* **Member check** (:doc:`admin/member-check`): look up any member by name, email,
  phone, or N-number and see whether their membership, medical, pilot certificate,
  and aircraft insurance are current.
* **Aircraft check** (:doc:`admin/aircraft-check`): look up an airplane by N-number
  and see its insurance and who flies it.
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
  activating and deactivating it, correcting its email address, and sending a
  password reset link or a verification message.

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
* **Reports** (:doc:`admin/reports`): the financial reports, and emailing them on
  a schedule.


Account administrator
=====================

An account administrator looks after the membership records. The role adds:

* **Members** (:doc:`admin/members`), **New member** (:doc:`admin/new-member`),
  and each member's record (:doc:`admin/member-record`): the profile, the
  membership terms, granting a term by hand, and deleting a member.
* **Aircraft** (the **Aircraft register**; :doc:`admin/aircraft-register`) and
  each aircraft's record (:doc:`admin/aircraft-record`).
* **DARTs** (:doc:`admin/darts`): the teams, their airports, and their leaders.
* **Payments**: the finance area as the treasurer sees it, without **Donors**
  (:doc:`finance/index`).
* **Reminders** (:doc:`admin/reminders`): every renewal reminder CalDART has sent.
* **Reports** (:doc:`admin/reports`): reports by email, and sending each DART its
  roster.
* **Member check** and **Aircraft check** (:doc:`admin/member-check`,
  :doc:`admin/aircraft-check`), as a DART leader has them.


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

* **System** (:doc:`admin/system`): the site's health, database backups, the four
  jobs that run on a timer (renewal reminders, automatic renewals, scheduled
  reports, and year-end contribution statements) with a way to run each now, and
  the log of every email CalDART has sent.

A system administrator cannot deactivate their own account.
