:roles: treasurer, account_admin

======
Donors
======

The **Donors** tab lists everyone who has given through the public donation page without
joining, and what each of them has given. Only the treasurer has this tab; an account
administrator who is not also the treasurer does not see it.

Who donors are
==============

Anybody can give through the public site's **Donate** page without a portal account.
Each gift is kept against a **donor**, a record the site makes from the giver's email
address the first time they give and finds again by that address every time after. A
donor has no password and cannot sign in. The record holds the giver's name, phone
number, and anything else they chose to give.

A donor's gift is an ordinary contribution with no plan. It appears on the payment list,
in the headline figures, in **Payments by period**, and on the **Contributions** tab like
any other gift, it earns the same receipt the moment it clears, and it is refunded the
same way (see :doc:`payment-record`).

A donor never appears in the member list, a roster (a DART's monthly list of its
members), the member report, or a DART
leader's member check. This tab is the one place you read them. The public page refuses
an address that already belongs to a member or a friend (someone with an account
who is not a member), and asks that person to sign
in and give from the portal, so their gifts stay on their own record.

What you see
============

One row per donor who gave in the range you choose, largest net giver first, so the
list opens with the down arrow on **Net**. With the
columns you start with, each row shows the donor's **Name**, **Email**, **Phone**,
**City**, and **State**, the day of their **First gift** and **Last gift**, how many
**Gifts**, the total **Given**, and the **Net** once anything refunded is taken
off.

A row named **Deleted member** followed by a number, such as **Deleted member 5**,
holds the gifts of a person whose account an account administrator deleted (see
:doc:`../admin/member-record`). The gifts stay in the books under that name, so the
organization's totals do not change, and the row's email address, which ends in
``deleted.invalid``, reaches nobody. A deleted member's gifts beyond their dues are
listed here too, because that name is not a member.

Four more columns start off: **County**, **DART**, **Refunded**, and **Active**, which
reads **Active** or **Deactivated**. Turn them on from **Columns** when a mailing list or
an audit needs them.

On a narrower screen the table leaves out the columns that matter least, one at a time,
so **Given** and **Net** stay in sight: first the place columns, then the **Email**, the
**Phone**, and the dates. On a phone the table scrolls sideways inside the page, a line
above it says so, and the **Name** stays pinned at the left.

What you can do
===============

Filter the list
~~~~~~~~~~~~~~~

* **From** and **To**, the range of gift dates counted.
* **Search**, a name or an email address.
* **County**, one county or several: click the box, tick each county you want, and press
  **Clear** to take them all back.
* **DART**, the donors whose record names that DART.
* **At least** and **At most**, bounds on what a donor gave over the whole range, in
  whole dollars.

Each filter applies as soon as you set it, **Reset filters** clears them all, and the
filters are kept in the page's address. When no donor matches, **Reset filters** appears
under the empty list too. Click a heading with a faint two-way arrow to sort by it, and
click it again to reverse the order; every heading but **Active** sorts.

Choose the columns and download
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Columns**, **Load columns**, and **Save columns**, at the right above the table beside
the export buttons, work exactly as they do on the payment list (see :doc:`payment-list`):
the columns you choose are the table's and the downloads' alike. **Export CSV** gives a file for a mailing list and
**Export PDF** a copy for the board, each with the columns you chose.

The **Subscriptions** screen can send this list on a schedule. There, a **Period** choice of
**This month**, **Last month**, **This year**, or **Last year** picks the dates each
emailed copy covers.

Open a donor's record and delete a donor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are an account administrator as well as the treasurer, or a system administrator,
each donor's name is a link to their :doc:`../admin/member-record`. The record tells you
who the donor is: the name, address, and phone on **Profile**, and every gift on
**Payments**. It is where a donor is deleted, for somebody who asks to be removed or a
record made by a test gift. On **Danger zone**, type the donor's email address and press
**Delete member**. **Back to donors** brings you back here without deleting anybody, and so
does the delete itself. An account administrator who is not the treasurer reaches the same
record from **Member record** on one of the donor's payments; the member record page lists
every way in.

The gifts are the organization's financial record, so the delete keeps them. This list
then shows **Deleted member** and the deleted account's number, such as **Deleted member
41**, in the donor's place, with the same gifts and the same amounts, and the year's
totals do not change. The payment list names the same **Deleted member** on each gift.
A **Deleted member** row is never a link: that record keeps the payments in the books and
cannot be changed or deleted.

A donor's record offers no **Grant a term**: a donor holds no membership, and becomes a
member only by registering on the site with the same address.

A treasurer who is not an account administrator sees the names without links: the member
record is the account administrator's screen.

Other things about donors
~~~~~~~~~~~~~~~~~~~~~~~~~

A donor's giving counts toward the year-end contribution statement, emailed to every
active account that gave (see :doc:`contributions`). A user administrator can find a
donor's account, flagged **Donor**, and correct a mistyped email address.

If something looks wrong
========================

If the list says *No donors match*, widen the dates or press **Reset filters**. If
somebody you know gave is missing, they may have given while signed in as a member or a
friend; their gifts are then on their own record, on the payment list and the
**Contributions** tab. If the line beside the export buttons says *The columns could not
be loaded; the list shows the default ones.*, reload the page.
