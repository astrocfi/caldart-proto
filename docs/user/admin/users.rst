:roles: user_admin

===============
Users and roles
===============

**Users and roles** lists every account on the site: members, friends, donors, and
administrators. Use it to find an account, to see what it may do, and to open it to change
its roles, correct its name or address, or help somebody back in.

A user administrator finds it as **Users and roles** under **Administration** in the menu. A
system administrator can open it too. A user administrator looks after accounts and roles
and does not edit profiles, grant memberships, or see payments, which belong to an account
administrator and the treasurer.


What you see
============

The filters sit at the top, with **Columns**, **Load columns**, **Save columns**, and the
two export buttons on one row at the right under them, and then the table. The table shows
25 accounts at a time, sorted by surname, and the arrow beside **Name** says so. Its caption
counts the accounts your filters match, such as *212 accounts*. When there are more, the
foot of the table reads, for example, *Showing 1–25 of 212*, between **Previous** and
**Next**.

The table shows the same columns as the roles report you download, and **Columns** changes
both (see `Exporting the roles report`_). At first it shows, **Name** first on screen
though the download leads with **Role**:

- **Name**: the person's name, or their address when no name is on file. Click it to open
  the :doc:`user-record`. A deactivated account has *account deactivated* beside it.
- **Role**: the widest role the account holds and how many more, such as *DART leader +1*,
  or *No role*. Rest the pointer on it to read every role.
- **Email**: the address, which is also how they sign in.
- **Phone**: the phone number on their profile.
- **DART**: their team, blank for none.
- **Kind**: **Member**, **Friend**, or **Donor**, as the account's record shows it.
- **Membership**: a colored dot and the membership's state: **Current**, **Expiring soon**,
  **Expired**, **Never expires**, or **Friend**. A donor holds none, and reads *No
  membership*.

**Name** and **Email** sort: click one to sort by it, and again to reverse the order. The
other headings have no arrow and do not sort. On a narrower screen the table leaves out
**Kind**, **Phone**, **DART**, **Role**, and **Email** in turn, while **Name**, **Membership**,
and any column you checked beyond the defaults stay; on a phone a line over the table says when it scrolls sideways,
and the names stay pinned at the left.

Every screen names a role the way a person says it: Member, Verifier, DART leader, User
administrator, Treasurer, Account administrator, CalDART management, Website administrator,
and System administrator.


Finding an account
==================

The filters apply as you set them; a box you type in applies after a short pause. They are
part of the page's address, so a filtered list is a link you can bookmark. **Reset filters**,
at the end of the bar, empties them and puts **Account status** back on **Active only**.

**Search**
   A first name, a last name, or an email address. Every word has to match, so *Ada
   Lovelace* finds one person and leaves out everyone else called Ada.

**Role**
   **Any role**, the first choice, or one role, to list the holders of that role. A line
   under the filters then says what that role lets its holders do.

**Kind**
   **Any kind**, the first choice, **Member**, **Friend**, or **Donor**. This is the kind
   the account was given, as its record shows it.

**Account status**
   **Active only**, the first choice and the one the list opens on, **Active and
   deactivated**, or **Deactivated only**. Choose one of the last two to find an account
   that has been deactivated.

**Email**
   **Any address**, the first choice, **Email bounced**, or **Not bounced**. **Email
   bounced** lists the accounts whose address another mail server has refused for good, so
   you can find each one and correct the address (:doc:`user-record`).

Changing a filter takes you back to the first page. With nothing to show, the table names
the filters in force, such as *No accounts match the Role and Kind filters*. Under that it
reads *Try a shorter search, or reset the filters.* when something is typed in **Search**,
and *Reset the filters to see more accounts.* when nothing is, with a **Reset filters**
button under it.


Exporting the roles report
==========================

**Export CSV** and **Export PDF** download the CalDART roles report: the people who hold
each role other than member, with a section per role from Verifier to System administrator.
A section nobody holds still appears, and the PDF says *Nobody holds this role.* under it. A
person holding two such roles is listed in both sections.

The report lists active accounts only, whatever **Account status** shows, and follows
the **Email** filter. It follows the screen's **Search**, the role chosen under **Role**,
which leaves that one section, and **Member** or **Friend** under **Kind**. The
report's Kind is the account's kind, except that a member whose change to a friend has come
reads Friend there; a member who has not paid yet reads Member, with *Not yet paid*
under Membership.

**Columns** chooses the columns of the table on screen and of the two downloads together.
It starts on Role, Name, Email, Phone, DART, Kind, and Membership, and adds City, County,
and Home airport when you check them. **Load columns** and **Save columns** keep a set of
columns under a name, as :ref:`saved-column-sets` describes.

With **Donor** chosen under **Kind**, or **Member** under **Role**, the report has
nobody to list, so the two export buttons and **Columns** are grayed out, and **Load
columns** and **Save columns** are put away until you choose another kind or role. A line
of its own under the filters says why.

An account administrator can have the same report emailed on a schedule, to themselves or to
a user administrator, from :doc:`subscriptions`.


Donor accounts
==============

A donor gave through the public site without joining. Each gift from a new email address
makes a donor account, and a later gift from the same address goes on the same one. A donor
account keeps the gifts and receipts, holds no password and no role, and cannot sign in.
Donors appear nowhere else outside the treasurer's screens, so this list is where you find
one: choose **Donor** under **Kind**. The usual reason is a receipt sent to a
mistyped address.


What each role opens
====================

- **Member**: the portal's own screens, for somebody with an account.
- **Verifier**: the member check and the aircraft check, to verify a member's pilot
  certificate, medical, and photo ID, and an airplane's insurance.
- **DART leader**: the member check, the aircraft check, and the member list and its report.
  A DART leader verifies too, and can make a member a verifier.
- **User administrator**: this screen, and the member check and the aircraft check, where a
  user administrator verifies and makes members verifiers.
- **Treasurer**: the payment screens and the money reports, and nothing that shows a
  member's medical or certificate.
- **Account administrator**: the member list and records, the aircraft register, the DARTs,
  the payments, the reminders, and the reports, and verifying from the checks and the
  records.
- **CalDART management**: the Bulk email screens, starting with
  :doc:`../bulk-email/compose`, to email members and friends, and nothing that
  shows a member's record.
- **Website administrator**: the website's editor, for pages, images, documents, redirects,
  and site settings.
- **System administrator**: everything above, plus the :doc:`health-database`,
  :doc:`sent-emails`, and :doc:`scheduled` pages.

Every role beyond Member also opens the members-only pages of the website, even when the
holder's own membership has lapsed.


If something looks wrong
========================

If you cannot find an account you are sure exists, search for one word, or for part of the
email address: every word you type has to match, so a middle name or a typo leaves everybody
out. Check **Kind** and **Account status** too, remembering that the list opens
on **Active only**, or press **Reset filters**. If a person has two accounts, open each one
and compare the memberships at the top to decide which to keep, then deactivate the other;
an account administrator can say whether the records need merging. If somebody says a page
shows *You do not have access to this page*, the message names the role the page needs; open
their :doc:`user-record` and check it.
