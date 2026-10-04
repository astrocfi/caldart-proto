:roles: treasurer, account_admin

========
Renewals
========

The **Renewals** tab lists everyone who has asked the site to charge them on a schedule:
members whose membership renews itself each year, and members and friends (people with
an account who support CalDART without being members) who give a recurring donation.
Below them it lists the charges the site has scheduled and tried. It is where you
answer "why was I not renewed?" and where you turn a standing charge off on somebody's
behalf.

What you see
============

Automatic renewals and recurring donations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first table has one row per standing authority, newest first, fifty to a page. A
person holds at most one automatic renewal and one recurring donation. With the columns
you start with, each row shows:

* **Member**, the person's name, and **Email**, their address.
* **Kind**: **Automatic renewal**, **Automatic renewal and contribution**, or **Recurring
  donation** followed by how often it charges, such as *Recurring donation · Monthly*.
* **Plan**, the membership plan it renews, or a dash for a recurring donation.
* **Next charge**, the amount the next charge comes to, and **Due**, the day it falls due.
* **Method**, the saved card or PayPal account it will be taken from.
* **Status**: **On**, **Awaiting a method**, **Paused**, or **Off**. A paused row shows,
  beneath its status, the reason its last charge was declined. That is the wording the
  member was emailed.
* **Actions**, the **Turn off** button, or *Off* once it is off.

Three more columns start off: **Cadence**, how often it charges; **Failed charges**, how
many charges in a row have been declined; and **Started**, the day the person gave the
authority.

On a narrower screen the table leaves out the **Email** and the **Method** first, then the
other columns, so the amount, the **Status**, and the **Actions** stay in sight. On a phone
the table scrolls sideways inside the page, a line above it says so, and the **Member**
stays pinned at the left.

A recurring donation charges monthly, quarterly, or yearly, whatever the giver's
membership, and only a yearly one sends a warning email before it charges. An automatic
renewal is always yearly. The daily run skips a renewal held by somebody who has since
become a friend, since a friend pays no dues.

Recent charges
~~~~~~~~~~~~~~

The second table, **Recent charges**, has one row per scheduled charge, fifty to a page:
the day it was **Scheduled**, the **Member**, the **Outcome** (**Scheduled**,
**Charged**, **Refused**, or **Skipped**), when it was **Tried**, and the **Reason** a
provider gave for refusing it.

What you can do
===============

Filter the tables
~~~~~~~~~~~~~~~~~

Above the first table, **Status** narrows it to one status, **Kind** to one kind, and
**Search** matches a name, an email address, or the saved card or account. **Reset
filters** clears all three, and appears under an empty table too. The filters and the
pages of both tables are kept in the page's address, so you can bookmark a view. Above the
second table, **Outcome** narrows the charges to one outcome, which is the quickest way to
read the refusals from a run on their own.

Under each table, *Showing 1–50 of 180* says which rows the page holds, and **Previous**
and **Next** step through the pages. Click a column heading to sort the page on screen by
it, and click it again to reverse the order.

Choose the columns and download
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Columns**, **Load columns**, and **Save columns**, at the right above the first table,
choose the columns of the table and of its downloads together, exactly as on the payment
list (see :doc:`payment-list`). **Export CSV** and **Export PDF** download the standing
authorities the filters describe, with the columns you chose, newest first. The
**Emailed reports** screen can also send this list on a schedule.

Turn a standing charge off
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Turn off** ends a person's automatic renewal or recurring donation for them. Because
the person is emailed when it happens, the button asks first, under it: *Turn off
automatic renewal for Marta Reyes? They are emailed that it is off.*, with a red **Turn it
off** and **Cancel**. Press **Turn it off** to go ahead, or **Cancel** or Escape to leave it
alone. A message then confirms what was turned off and for whom, such as
*Automatic renewal is off for Marta Reyes.*

What happens next:

* Every charge still scheduled against it is dropped.
* The membership itself runs to the end of its term.
* The row stays in the table, marked **Off**.
* The person is emailed. The subject is *CalDART: automatic renewal is off* for a
  renewal, or *CalDART: your recurring donation is off* for a recurring donation.
* They can turn it on again themselves from their own **Payments** screen, or, for a
  recurring donation, from the **Donate** screen.

If something looks wrong
========================

If a member says they were not renewed, find their row and read the reason under
**Paused**; it is the provider's own explanation, usually an expired or declined card,
and the member can put a new card on file from their own **Payments** screen. If
**Recent charges** says *No renewal charges yet*, nothing has fallen due: the site
schedules a charge about two weeks before it takes it. If a charge you expected is
missing, check the member's **Due** date in the first table.
