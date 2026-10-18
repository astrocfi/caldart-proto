:roles: treasurer, account_admin

======
Donors
======

The **Donors** tab lists everyone who has given through the public donation page without
joining, and what each of them has given. Only the treasurer has this tab. An account
administrator who isn't also the treasurer doesn't see it.

Who donors are
==============

Anybody can give through the public site's **Donate** page without a portal account.
Each gift is kept on a **donor** record. The site makes the record from the giver's email
address the first time they give, and finds it again by that address every time after. A
donor doesn't have a password and can't sign in. The record holds the giver's name, phone
number, and anything else they chose to give.

A donor's gift is an ordinary contribution without a plan. It appears on the payment list,
in the headline figures, in **Payments by period**, and on the **Contributions** tab like
any other gift. It earns the same receipt the moment it clears, and it is refunded the same
way (see :doc:`payment-record`).

A donor never appears in the member list, a roster (a DART's monthly list of its members),
the member report, or a DART leader's member check. This tab is the only place you see
them. The public page refuses an address that already belongs to a member or a friend
(someone with an account who isn't a member). It asks that person to sign in and give from
the portal, so their gifts stay on their own record.

What you see
============

There is one row for each donor who gave in the range you choose. The largest net giver
comes first, so the list opens with the down arrow on **Net**. With the starting columns,
each row shows the donor's **Name**, **Email**, **Phone**, **City**, and **State**, the day
of their **First gift** and **Last gift**, how many **Gifts**, the total **Given**, and the
**Net** once anything refunded is taken off.

A row named **Deleted member** and a number, such as **Deleted member 5**, holds the gifts of
a person whose account an account administrator deleted (see
:doc:`../admin/member-record`). The gifts stay in the books under that name, so the
organization's totals don't change. The row's email address ends in ``deleted.invalid`` and
doesn't reach anybody. A deleted member's gifts beyond their dues are listed here too,
because the deleted record doesn't count as a member.

Four more columns are hidden at first: **County**, **DART**, **Refunded**, and **Active**,
which says **Active** or **Deactivated**. Turn them on from **Columns** when a mailing list
or an audit needs them.

On a narrower screen, the columns that matter least drop out one at a time, so **Given** and
**Net** stay in sight. The place columns go first, then **Email**, **Phone**, and the dates.
A column you added from **Columns** always stays. On a phone, the table scrolls sideways
inside the page, a note above it says so, and the **Name** stays pinned at the left.

What you can do
===============

Filter the list
~~~~~~~~~~~~~~~

* **From** and **To**, the range of gift dates counted.
* **Search**, a name or an email address.
* **County**, one county or several: click the box, check each county you want, and press
  **Clear** to uncheck them all.
* **DART**, the donors whose record names that DART.
* **At least** and **At most**, limits on what a donor gave over the whole range, in
  whole dollars.

Each filter applies as soon as you set it, and **Reset filters** clears them all. The
filters are kept in the page's address. When no donor matches, **Reset filters** appears
under the empty list too. Click a heading with a faint two-way arrow to sort by it, and
click it again to reverse the order. Every heading except **Active** sorts.

Choose the columns and download
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Columns**, **Load columns**, and **Save columns** sit at the right above the table, beside
the export buttons. They work exactly as they do on the payment list (see
:doc:`payment-list`). The columns you choose are used in the table and in the downloads
alike. **Export CSV** gives a file for a mailing list, and **Export PDF** a copy for the
board, each with the columns you chose.

The **Emailed reports** screen can send this list on a schedule. There, **Period** sets the
dates each emailed copy covers: **This month**, **Last month**, **This year**, or **Last
year**.

Open a donor's record and delete a donor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are an account administrator as well as the treasurer, or a system administrator,
each donor's name is a link to their :doc:`../admin/member-record`. The record tells you
who the donor is: the name, address, and phone on **Profile**, and every gift on
**Payments**. That is where you delete a donor, such as somebody who asks to be removed, or a
record made by a test gift. On **Delete or deactivate**, type the donor's email address and
press **Delete member**. **Back to donors** brings you back here without deleting anybody.
The delete brings you back here too. An account administrator who isn't the treasurer
reaches the same record from **Member record** on one of the donor's payments. The member
record page lists every way in.

The gifts are the organization's financial record, so the delete keeps them. This list
then shows **Deleted member** and the deleted account's number, such as **Deleted member
41**, in the donor's place. The gifts and the amounts are the same, and the year's totals
don't change. The payment list names the same **Deleted member** on each gift. A **Deleted
member** row is never a link, because that record keeps the payments in the books and can't
be changed or deleted.

**Grant a term** isn't on a donor's record. A donor doesn't hold a membership, and becomes a
member only by joining on the site with the same address.

If you are the treasurer but not an account administrator, the names aren't links, because
the member record is an account administrator's screen.

Other things about donors
~~~~~~~~~~~~~~~~~~~~~~~~~

A donor's gifts count toward the year-end contribution statement, which CalDART emails to
every active account that gave (see :doc:`contributions`). An account administrator
corrects a mistyped email address on the donor's member record.

If something looks wrong
========================

If the list says *No donors match*, widen the dates or press **Reset filters**. If somebody
you know gave isn't listed, they may have given while signed in as a member or a friend.
Their gifts are then on their own record, on the payment list and the **Contributions** tab.
If the line beside the export buttons says *The columns could not be loaded; the list shows
the default ones.*, reload the page.
