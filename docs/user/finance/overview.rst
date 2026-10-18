:roles: treasurer, account_admin

==================
The money overview
==================

The **Money overview** screen answers "how are we doing?" at a glance: what came in, what
the payment services kept, what reached the bank, and what went back in refunds. The
payment services are the companies that take payments online, such as Stripe. This is
the first tab of the finance area, and **Accounting** under **Finance** in the menu opens
it.

Who sees this screen
====================

The treasurer and an account administrator. A treasurer sees every payment, fee, refund,
and automatic renewal, but never the medical and certificate details on a member's
record. An account administrator sees the same money and the member records as well.

Moving around the finance area
==============================

A row of tabs sits at the top of every finance screen:

* **Money overview**, this screen.
* **Payments**, every payment, one row each (see :doc:`payment-list`).
* **Renewals**, the automatic renewals and recurring donations people have set up (see
  :doc:`renewals`).
* **Reconciliation**, the totals laid out for matching against a bank statement (see
  :doc:`reconciliation`).
* **Contributions**, everyone who gave in one calendar year (see :doc:`contributions`).
* **Donors**, everyone who has given through the public donation page (see
  :doc:`donors`). Only the treasurer has this tab.

When you open one payment, one member's money history, or the form for recording a
check, the tabs stay in place with **Payments** marked, so you can always see where you
are.

Every table in the finance area fills the width of your browser window. A table wider
than the window scrolls sideways inside its own frame.

What you see
============

The three figures across the top
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are three tiles, each covering every payment on the site:

* **This month**, the calendar month you are in.
* **Year to date**, from January 1 to today.
* **Last 12 months**, a rolling twelve-month window.

Each tile shows, in large type, the gross amount taken in, and how many payments made it up.
Beneath that are the **Fees** the payment services kept, the **Net** that reached the bank,
and what was **Refunded**. A card that was declined never brought in any money, so it is
left out. A payment that was later refunded did bring money in, so it is counted, with the
refund shown beside it.

Payments by period
~~~~~~~~~~~~~~~~~~

Below the tiles, **Payments by period** adds the same money up by month or by year. The
**Month** and **Year** buttons switch between the two. The newest period is at the top.

For each period the table shows the number of **Payments**, how much was **Dues**, how
much was **Contributions**, a column for each payment service that took money in the
range, the **Fees**, the **Net**, what was **Refunded**, and the **Total**.

To compare this year with last year, choose **Year** and read down the **Total**
column. Click a column heading to sort the table by it, and click it again to reverse the
order.

On a narrower screen, the payment service columns drop out first, then **Dues**,
**Contributions**, **Payments**, **Refunded**, **Fees**, and **Net**, so the **Total**
always stays beside the period. If the table is still too wide, it scrolls sideways inside
the page, a note above it says so, and the period stays pinned at the left.

What you can do
===============

Narrow the table
~~~~~~~~~~~~~~~~

Above the period table, **From**, **To**, **Provider**, **Status**, and **Search** narrow
what the table adds up. They work exactly as they do on the payment list (see
:doc:`payment-list`). The three tiles ignore them: **This month** is always this month.

Each filter applies as soon as you set it. A filter you type in applies once you stop
typing. **Reset filters** clears them all, and it appears under an empty table too. The
filters are kept in the page's address, so you can bookmark a filtered view or send the
link to another treasurer.

Reports by email
~~~~~~~~~~~~~~~~

The **Emailed reports** screen, under **Administration**, sends reports on a schedule you
choose, to you or to anyone else allowed to read them. It sends the payments,
reconciliation, and contributions reports, and for the treasurer, the donors report.

If something looks wrong
========================

If the tiles don't match a payment service's own dashboard, check three common reasons first.
The tiles count only money that arrived, and a payment service's dashboard may count attempts
too. The tiles show the gross, and a dashboard often shows the net. The tiles date a
payment by the day it went through, which can be a day before or after the payment service's
settlement date. The :doc:`reconciliation` screen shows the gross, the fees,
and the net side by side for exactly this comparison. If the period table says *No
payments in this range*, widen the dates or press **Reset filters**.
