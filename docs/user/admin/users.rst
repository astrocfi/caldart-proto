:roles: user_admin

================
Roles and status
================

**Roles and status** lists every account on the site: members, friends, donors, and
administrators. Use it to find an account and see what it may do. Open an account to change
its roles, change whether it can sign in, or help somebody back in.

A user administrator finds it as **Roles and status** under **Administration** in the menu.
A system administrator can open it too. A user administrator looks after accounts and
roles. Editing profiles, granting memberships, and seeing payments belong to an account
administrator and the treasurer.


What you see
============

The filters are at the top. Under them, on one row at the right, are **Columns**, **Load
columns**, **Save columns**, and the two export buttons. Then comes the table. It shows 25
accounts at a time, sorted by surname, and the arrow beside **Name** shows that. Its caption
counts the accounts that match your filters, such as *212 accounts*. When there are more,
the foot of the table says, for example, *Showing 1–25 of 212*, between **Previous** and
**Next**.

The table shows the same columns as the roles report you download, and **Columns** changes
both (see `Exporting the roles report`_). To begin with, it shows these columns. **Name**
comes first on screen, but the download starts with **Role**.

- **Name**: the person's name, or their address if no name is on file. Click it to open
  the :doc:`user-record`. A deactivated account has *account deactivated* beside it.
- **Role**: the widest role the account holds and how many more, such as *DART leader +1*,
  or *No role*. Rest the pointer on it to see every role.
- **Email**: the address, which they also use to sign in.
- **Phone**: the phone number on their profile.
- **DART**: their team, or blank if they don't have one.
- **Kind**: **Member**, **Friend**, or **Donor**, as the account's record shows it.
- **Membership**: a colored dot and the state of the membership: **Current**, **Expiring
  soon**, **Expired**, **Never expires**, or **Friend**. A donor doesn't hold a membership,
  so a donor shows *No membership*.

You can sort by **Name** and **Email**. Click one to sort by it, and click again to reverse
the order. The other headings don't have an arrow and don't sort. On a narrower screen, the
table drops **Kind**, **Phone**, **DART**, **Role**, and **Email**, in that order. **Name**,
**Membership**, and any column you added to the defaults stay. On a phone, a line above the
table says when it scrolls sideways, and the names stay pinned at the left.

Every screen names a role the way a person says it: Member, Verifier, DART leader, User
administrator, Treasurer, Account administrator, CalDART management, Website administrator,
and System administrator.


Finding an account
==================

The filters apply as you set them, and a box you type in applies after a short pause. The
filters are part of the page's address, so you can bookmark a filtered list. **Reset
filters**, at the end of the bar, clears them and sets **Account status** back to **Active
only**.

**Search**
   A first name, a last name, or an email address. Every word has to match, so *Ada
   Lovelace* finds one person and leaves out everyone else called Ada.

**Role**
   **Any role**, the first choice, or one role, to list the people who hold it. A line
   under the filters then says what that role lets them do.

**Kind**
   **Any kind**, the first choice, **Member**, **Friend**, or **Donor**. This is the kind
   the account was given, as its record shows it.

**Account status**
   **Active only**, the first choice and the one the list opens with, **Active and
   deactivated**, or **Deactivated only**. To find a deactivated account, choose one of the
   last two.

**Email**
   **Any address**, the first choice, **Email bounced**, or **Not bounced**. **Email
   bounced** lists the accounts whose address another mail server has refused for good. You
   can then find each one and ask the person for an address that works
   (:doc:`user-record`).

Changing a filter takes you back to the first page. When nothing matches, the table names
the filters in use, such as *No accounts match the Role and Kind filters*. If you typed
something in **Search**, the next line says *Try a shorter search, or reset the filters.*
If you didn't, it says *Reset the filters to see more accounts.* A **Reset filters** button
appears under it.


Exporting the roles report
==========================

**Export CSV** and **Export PDF** download the CalDART roles report. It lists the people who
hold each role other than member, with a section for each role from Verifier to System
administrator. A role not held by anybody still gets a section, and the PDF says *Nobody
holds this role.* under it. A person with two such roles appears in both sections.

The report lists only active accounts, whatever **Account status** is set to, and it
follows the **Email** filter. It also follows the screen's **Search**, the role chosen under
**Role** (which leaves just that one section), and **Member** or **Friend** under **Kind**.
In the report, Kind is the account's kind, with one exception. A member whose change to
friend has reached its day shows as Friend there. A member who hasn't paid yet shows as
Member, with *Not yet paid* under Membership.

**Columns** chooses the columns for the table on screen and for the two downloads together.
It starts with Role, Name, Email, Phone, DART, Kind, and Membership, and adds City, County,
and Home airport if you check them. **Load columns** and **Save columns** keep a set of
columns under a name, as :ref:`saved-column-sets` describes.

If you choose **Donor** under **Kind**, or **Member** under **Role**, the report doesn't
have anybody to list. The two export buttons and **Columns** are grayed out, and **Load
columns** and **Save columns** are hidden, until you choose another kind or role. A line of
its own under the filters says why.

An account administrator can have the same report emailed on a schedule, to themselves or to
a user administrator, from :doc:`subscriptions`.


Donor accounts
==============

A donor gave through the public site without joining. The first gift from an email address
creates a donor account, and later gifts from the same address go on the same account. A
donor account keeps the gifts and receipts. It doesn't have a password or a role, and it
can't sign in. Outside the treasurer's screens, donors appear only here, so this list is
where you find one: choose **Donor** under **Kind**. If a receipt went to a mistyped
address, an account administrator corrects it on the donor's member record.


What each role opens
====================

- **Member**: the portal's own screens, for somebody with an account.
- **Verifier**: the member check and the aircraft check, to verify a member's pilot
  certificate, medical, and photo ID, and an airplane's insurance.
- **DART leader**: the member check, the aircraft check, and the member list and its report.
  A DART leader verifies too, and can make a member a verifier.
- **User administrator**: this screen, plus the member check and the aircraft check, where a
  user administrator verifies and makes members verifiers.
- **Treasurer**: only the payment screens and the money reports, which never show a
  member's medical or certificate.
- **Account administrator**: the member list and records, the aircraft register, the DARTs,
  the payments, the reminders, and the reports, and verifying from the checks and the
  records.
- **CalDART management**: only the Bulk email screens, starting with
  :doc:`../bulk-email/compose`, to email members and friends. None of them shows a member's
  record.
- **Website administrator**: the website's editor, for pages, images, documents, redirects,
  and site settings.
- **System administrator**: everything above, plus the :doc:`health-database`,
  :doc:`sent-emails`, and :doc:`scheduled` pages.

Every role beyond Member also opens the members-only pages of the website, even if the
person's own membership has lapsed.


If something looks wrong
========================

If you can't find an account you are sure exists, search for one word, or for part of the
email address. Every word you type has to match, so a middle name or a typo leaves everybody
out. Check **Kind** and **Account status** too, and remember that the list opens on
**Active only**. Or press **Reset filters**. If a person has two accounts, open each one and
compare the memberships at the top to decide which to keep, then deactivate the other. An
account administrator can tell you whether the records need merging. If somebody says a
page shows *You do not have access to this page*, the message names the role the page
needs. Open their :doc:`user-record` and check it.
