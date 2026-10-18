:roles: treasurer, account_admin

========
Renewals
========

The **Renewals** tab lists everyone who has asked the site to charge them on a schedule:
members whose membership renews itself each year, and members and friends (people with
an account who support CalDART without being members) who give a recurring donation.
Below them it lists the charges the site has scheduled and tried. Use it to answer "why
wasn't I renewed?", and to turn off somebody's automatic renewal or recurring donation for
them.

What you see
============

Automatic renewals and recurring donations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first table has one row for each automatic renewal or recurring donation, newest
first, fifty to a page. A person has at most one automatic renewal and one recurring
donation. With the starting columns, each row shows:

* **Member**, the person's name, which opens everything they have paid (see
  :doc:`member-ledger`), and **Email**, their address.
* **Type**: **Automatic renewal**, **Automatic renewal and contribution**, or **Recurring
  donation** followed by how often it charges, such as *Recurring donation · Monthly*.
* **Plan**, the membership plan it renews, or a dash for a recurring donation.
* **Next charge**, the amount the next charge comes to, and **Due**, the day it falls due.
* **Method**, the saved card or PayPal account it will be taken from.
* **Status**: **On**, **Waiting for the first payment**, **Paused after failed charges**, or
  **Turned off**. A paused row shows, beneath its status, why its last charge failed:

  - *Card declined*, followed by the words the member was emailed if the card company
    said more, such as *Card declined (member was told: "Your card has expired")*;
  - *PayPal refused the saved payment method*;
  - *Payment could not be verified*, with what was recorded. The provider took a charge
    the site couldn't match to the payment, such as one for a different amount;
  - *Charge refused*, with what the provider said, for anything else.
* **Actions**, the **Turn off** button, or *Turned off* once it is off.

Three more columns are hidden at first: **Cadence**, how often it charges; **Failed
charges**, how many charges in a row have been declined; and **Started**, the day the
person set it up.

On a narrower screen, **Email** and **Method** drop out first, then the other columns, so
the amount, the **Status**, and the **Actions** stay in sight. On a phone, the table scrolls
sideways inside the page, a note above it says so, and **Member** stays pinned at the left.

A recurring donation charges monthly, quarterly, or yearly, whatever the giver's
membership. Only a yearly one sends a warning email before it charges. An automatic renewal
is always yearly. The daily run skips the renewal of anybody who has since become a friend,
because a friend doesn't pay dues.

Recent charges
~~~~~~~~~~~~~~

The second table, **Recent charges**, has one row per scheduled charge, fifty to a page.
Each row shows the day it was **Scheduled**, the **Member**, the **Outcome** (**Scheduled**,
**Charged**, **Failed**, **Skipped**, or **Needs checking**), when it was **Tried**, and the
**Reason** a charge failed, worded as under a paused renewal's status. The member's name
opens their money history. The charges still to come are listed first, then the rest by when they
were tried, newest first.

**Needs checking** marks a charge PayPal may have taken without telling the site. Either
PayPal never answered, or it said the charge's invoice was already paid. The site doesn't
charge it again until you settle it, and its **Reason** says why. You can subscribe to
*Automatic charge needs checking* on the **Notification emails** screen. You are then
emailed when a charge is held this way, and again if the member's membership runs out while
it waits. You are also emailed about any charge the payment provider has held as pending
for more than three days.

What you can do
===============

Filter the tables
~~~~~~~~~~~~~~~~~

Above the first table, **Status** narrows it to one status, **Type** to one type, and
**Search** matches a name, an email address, or the saved card or account. **Reset
filters** clears all three, and appears under an empty table too. The filters and the
pages of both tables are kept in the page's address, so you can bookmark a view. Above the
second table, **Outcome** narrows the charges to one outcome. That is the quickest way to
see only the failed charges from a run.

Under each table, *Showing 1–50 of 180* says which rows are on the page, and **Previous**
and **Next** step through the pages. Click a column heading to sort the page on screen by
it, and click it again to reverse the order.

Choose the columns and download
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Columns**, **Load columns**, and **Save columns**, at the right above the first table,
choose the columns of the table and of its downloads together, exactly as on the payment
list (see :doc:`payment-list`). **Export CSV** and **Export PDF** download the renewals and
donations the filters describe, with the columns you chose, newest first. The
**Emailed reports** screen can also send this list on a schedule.

Settle a charge that needs checking
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Press **Settle** on the charge's row in **Recent charges**. The panel names what to
search PayPal's own dashboard for: the charge's invoice id, such as
``caldart-renewal-901``, its amount, and when it was sent. Then choose one:

* If PayPal took the money, enter the **Capture ID** PayPal shows for it and press
  **Record as paid**. The site checks the capture with PayPal, records the charge, renews
  the membership, and emails the member the usual *your membership has been renewed*
  message. If the capture is for another payment, amount, or currency, it is refused, and
  the charge stays as it was.
* If you don't find a payment, check *I searched the dashboard and didn't find a payment
  for this invoice* and press **No payment found**. The next morning's run charges it
  again. If PayPal did take it after all, PayPal refuses the second charge, the row goes
  back to **Needs checking**, and you are told again. That works only while PayPal's
  *Block accidental payments* setting is on.
* If neither fits, check the same box and press **Close as failed**. The member isn't
  charged again. Their automatic renewal or recurring donation is paused if it is on, and
  the ordinary renewal reminders take over. The member is emailed *CalDART: we could not
  renew your membership* (or *…take your recurring donation*). The email says their
  automatic renewal couldn't be completed and is paused, when their membership ends or
  ended, and how to renew by hand and turn it back on. A note then appears above **Recent
  charges** asking you to get in touch with them too. It gives their phone number if their
  record has one, their email address, and links to their money history (and, for an
  account administrator, their **Member record**). It stays until you press **Dismiss**. A
  standing charge that was already off is left as it is. The note says whether the charge
  is paused, and whether the member is emailed. A member without an email address isn't
  emailed, and neither is one whose standing charge was already off.

Once a charge's payment has gone through, **No payment found** and **Close as failed** are
refused. Record it as paid instead.

Turn a standing charge off
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Turn off** ends a person's automatic renewal or recurring donation for them. The person
is emailed when it happens, so the button asks first. Under it you see *Turn off automatic
renewal for Marta Reyes? They are emailed that it is off.*, with a red **Turn it off** and
**Cancel**. Press **Turn it off** to go ahead, or **Cancel** or Escape to leave it
alone. A message then confirms what was turned off and for whom, such as
*Automatic renewal is off for Marta Reyes.*

What happens next:

* Every charge still scheduled for it is dropped. The exception is a charge already sent
  to the payment provider that hasn't been answered yet. The site still records that one if
  the money was taken, and doesn't charge anything new.
* The membership itself runs to the end of its term.
* The row stays in the table, marked **Turned off**.
* The person is emailed. The subject is *CalDART: automatic renewal is off* for a
  renewal, or *CalDART: your recurring donation is off* for a recurring donation.
* They can turn it on again themselves from their own **My payments** screen, or, for a
  recurring donation, from the **Donate** screen.

If something looks wrong
========================

If a member says they weren't renewed, find their row and read the reason under **Paused
after failed charges**. It is usually a declined or expired card. The member can put a new
card on file from their own **My payments** screen. If **Recent charges** says *No renewal
charges yet*, nothing has fallen due yet. The site schedules a charge about two weeks
before it takes it. If a charge you expected is
missing, check the member's **Due** date in the first table.
