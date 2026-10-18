:roles: account_admin

=========
Reminders
=========

**Reminders** is the record of the renewal emails CalDART has sent, newest first. Use it to
answer "were they told?" when somebody says their membership lapsed without warning.

An account administrator finds it under **Finance** in the menu. A system administrator can
open it too, and can also see the same record on the :doc:`scheduled` page, where the
reminders can be sent by hand.


How the reminders work
======================

Every morning at 7:00 AM, CalDART looks for memberships near their end and emails each
member at five stages. Each stage covers a stretch of days, so every member still reaches it
even if a morning is missed. On the default schedule, the stages are:

- **First reminder (60 days before)**: anyone whose membership ends in 31 to 60 days. The
  subject says *CalDART: your membership expires in* and the number of days.
- **Second reminder (30 days before)**: anyone whose membership ends in 8 to 30 days, with
  the same subject.
- **Final reminder (7 days before)**: anyone whose membership ends within the week, with the
  same subject.
- **Expired reminder (up to 6 days after)**: anyone whose membership ran out today or in the
  6 days before. The subject says *CalDART: your membership expires today*, or *expired*
  and the number of days *ago*.
- **Lapsed reminder (30 days after)**: anyone whose membership ran out 30 to 60 days ago. The
  subject says *CalDART: your membership lapsed* and the number of days *ago*.

A system administrator can change the number of days for the first three stages and the
last one on the :doc:`scheduled` page. The stages then show the new numbers everywhere on
this screen. The first stage runs from its number of days before the end date until one day
more than the second stage's number. The second runs until one day more than the final
stage's number, and the final one runs until 1 day before. The lapsed reminder runs for 30
days, starting its number of days after the end date. The expired reminder never moves: it
runs from the end date through 6 days after.

In each subject, your organization's own name appears instead of CalDART. Each member gets
one email per membership at each stage. CalDART doesn't send a reminder to anyone whose
membership renews automatically, who holds a life membership, who has already renewed,
whose account is deactivated, or who doesn't have an email address. Nobody has to start
the morning check, and this screen doesn't have a button for it.


What you see
============

There are two cards. The first, **Renewal reminders**, opens with a line built from the
saved schedule, such as *Every morning at 7:00 AM, CalDART emails members whose membership
is ending: 60, 30, and 7 days before it ends, on the day it ends, and 30 days after.* The
line also says that nobody gets the same reminder twice for one membership. Then comes a
table of the twenty most recent reminders. The caption counts every reminder ever sent,
such as *418 reminders sent*.

- **Sent**: the date and time it went out.
- **Reminder**: which stage it was.
- **Member**: who it went to.
- **To**: the address it was sent to.

The **Reminder** list above the table narrows it to one stage, such as **First reminder (60
days before)** on the default schedule. **Any reminder**, or **Reset filters** beside it,
shows every stage again. The rows open newest first, with the arrow on **Sent**. Click a
column heading to sort the rows shown. On a narrow screen, the table drops **To**, then
**Reminder**, and keeps **Member** in sight.

If the table is empty, it says *No reminders have been sent yet*. No membership has reached
a stage yet, which is normal on a new site or when every member renewed early. With one
stage chosen, an empty table says *No reminders of this kind*, with a **Reset filters**
button.

The second card, **Reminder schedule**, lists all five stages in the order a membership
reaches them. **First reminder**, **Second reminder**, and **Final reminder** are in days
before expiry. **Expired reminder** says *On the day of expiry, or up to 6 days after*, and
**Lapsed reminder** is in days after expiry. A line under them says who last saved the
schedule and when. If nobody has changed it, the line says *The default schedule: nobody
has changed it. A system administrator can change it.* You can see the schedule here, but
you can't change it.


If something looks wrong
========================

If a member says they were never told, choose the stage they should have reached and look
for their name. A row here means CalDART handed the email to the mail server. It doesn't
prove that the email arrived, so ask them to check their spam folder, and compare the
address in **To** with their record on :doc:`members`. If there isn't a row at all, one of
the reasons above usually applies. Most often, they had already renewed or had automatic
renewal turned on. If the table stops getting new rows for days on end, the morning check
may have stopped. Tell a system administrator, who can check it on the :doc:`scheduled`
page.
