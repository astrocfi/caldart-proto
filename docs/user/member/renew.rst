=====
Renew
=====

On the **Renew your membership** screen you pay for your next term. If you are
current, it says *A renewal starts the day after your current term ends, so you
don't lose any days by renewing early.* If your membership has lapsed, it says *Your
new year starts today.* Open it from **Renew** in the menu, from the **Renew** button on your
:doc:`dashboard`, or from the link in any renewal reminder email.


What you see
============

The **Your membership** card comes first, across the full width of the page. It
shows your membership status, then either *Expires* with the date and the days
left, or *Expired* with the date it ran out. Then it shows your plan, such as
*Annual membership*.

Renewing is for members. A friend of CalDART doesn't have anything to renew, and
neither does somebody who joined as a member and hasn't paid yet. Opening **Renew**
takes them to :doc:`become-a-member` instead.

Below it is the checkout, in its own card. It works like the payment step of the
join wizard (see :doc:`join`). Choose the plan (the first one on the list is chosen
for you), add a contribution if you like, and check **Renew automatically each
year** if you want CalDART to renew you from then on. Then pay from one of the tabs.
If the site doesn't have a membership plan set up, it shows *No membership plan is
set up yet. Ask an administrator.* instead of the plans, and you can't pay.

If your automatic renewal is already on, a card headed **Automatic renewal is on**
appears instead of the checkout: *We will charge $145.00 on 04/27/2027. You do not
need to do anything.*, with your own amount and date. You don't need to do
anything, and the card keeps you from paying twice by mistake. If you want to pay
for another term now anyway, press **Renew now anyway**. It opens the checkout under
the card, with **Renew automatically each year** already checked. If the last charge
was declined, the card says *The last charge was declined. CalDART will try again
on*, followed by the day and the amount. **Renew now anyway** is still there.

If automatic renewal has stopped, the card is headed **Automatic renewal is
paused**, with the reason. The reason is *A charge was refused, so CalDART will not
renew you by itself.* If your membership lapsed more than 30 days ago and a charge
wasn't refused, it is *Your membership lapsed, so CalDART will not renew it by
itself.* The checkout is open below the card, with **Renew automatically each year**
checked. So you can renew here and turn automatic renewal on again with the method
you pay with.


What happens next
=================

When the payment clears, *Thank you — your membership is renewed.* appears, and you
go back to your dashboard, which shows the new date straight away. The receipt
arrives by email, subject *CalDART: your receipt for $45.00* with your own amount
(see :doc:`payments`).

* If you renew while you are still current, the new term starts the day after the
  current one ends. Renew on 03/01/2027 with an expiry of 06/30/2027, and your new
  expiry is 06/29/2028.
* If your membership has already lapsed, the new term starts today. You don't pay
  for the gap, and you don't get it back.

An Annual term runs 365 days, counting the day it starts, so a term that starts on
03/01/2026 ends on 02/28/2027.


Life members
============

A life member doesn't have anything to renew, so their menu doesn't have a **Renew**
entry. They give through **Donate** like everyone else (see :doc:`donate`). If a
life member follows a renewal link, such as one in an earlier email, it opens
**Donate** instead.


Renewal reminders
=================

CalDART sends you five emails as your term runs out. Each one covers a stretch of
days, so you get every one, whatever day you joined. For example, if you buy a
membership three weeks before it expires, you still get the last four. On the
default schedule they arrive as the table shows.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - When
     - Subject
   * - 31 to 60 days before your term ends
     - *CalDART: your membership expires in 45 days*, with the actual count
   * - 8 to 30 days before
     - *CalDART: your membership expires in 21 days*
   * - 1 to 7 days before
     - *CalDART: your membership expires in 3 days*
   * - The day it ends, or up to 6 days after
     - *CalDART: your membership expires today*, or *CalDART: your membership
       expired 2 days ago*
   * - 30 to 60 days after
     - *CalDART: your membership lapsed 30 days ago*

A system administrator can change the number of days for the first, second, and
final reminders, and for the last one. Whatever the numbers, each reminder arrives
within these stretches:

- The first: from its number of days before your end date, until the day before the
  second one's stretch begins. On the default schedule, 60 to 31 days before.
- The second: from its number of days before, until the day before the final one's
  stretch begins. On the default schedule, 30 to 8 days before.
- The final one: from its number of days before until 1 day before. On the default
  schedule, 7 to 1 days before.
- The one at expiry: from your end date through 6 days after it. This one never
  moves.
- The last one: from its number of days after your end date, for 30 days. On the
  default schedule, 30 to 60 days after.

Every subject gives the actual number of days.

Every reminder links straight to this screen. You are still current on your end
date itself. The membership shows as expired the next morning.

CalDART sends each reminder once per term, and renewing stops the rest. You don't
get these reminders while automatic renewal covers your term. Life members,
friends, members who are due to become friends, and deactivated accounts don't get
them either. Automatic renewal sends its own emails, described on :doc:`payments`.
If it stops, the usual reminders start again.

Reminders go to the address you sign in with. An account administrator can see
every reminder CalDART sent on the **Reminders** screen, so the office can always
tell whether you were reminded.


If something looks wrong
========================

If you renewed and your dashboard still shows the earlier date, reload the page. If
it still does, look at **Recent payments** on your dashboard. A payment marked
**Failed** means CalDART didn't take any money or add a term, so try again. *Your
payment is still being processed.* means the payment hasn't finished yet. Your
membership starts by itself when it clears. If you were charged and still show as
expired, contact the office with the date and the amount.
