:roles: account_admin

=========
Reminders
=========

**Reminders** is the record of the renewal emails CalDART has sent, newest first. Use it to
answer "were they told?" when somebody says their membership lapsed without warning.

An account administrator finds it under **Administration** in the menu. A system
administrator can open it too, and also reads the same record on the :doc:`scheduled` page,
where the reminders can be sent by hand.


How the reminders work
======================

Every morning at 7:00 AM CalDART looks for memberships near their end and emails each member
at five stages. Each stage covers a stretch of the calendar, so every member passes through
it even if a morning is missed. On the default schedule the stages are:

- **60 days before**: anyone whose membership ends in 31 to 60 days. The subject reads
  *CalDART: your membership expires in* and the number of days.
- **30 days before**: anyone whose membership ends in 8 to 30 days, with the same subject.
- **7 days before**: anyone whose membership ends within the week, with the same subject.
- **Expired**: anyone whose membership ran out in the last seven days. The subject reads
  *CalDART: your membership expires today*, or *expired* and the number of days *ago*.
- **30 days after**: anyone whose membership ran out 30 to 60 days ago. The subject reads
  *CalDART: your membership lapsed* and the number of days *ago*.

A system administrator can change the number of days for the first three stages and the last
one on the :doc:`scheduled` page, and the stages then read with the new numbers everywhere on
this screen. The first stage runs from its number of days before the end date until one day
more than the second's number, the second until one day more than the final one's, and the
final one until 1 day before. The last stage runs from its number of days after the end date
for 30 days. The expired stage never moves: it runs from the end date through 6 days after.

Each subject begins with your organization's name in place of CalDART. Each member gets one
email per membership at each stage. Nobody is sent a reminder whose membership renews itself
automatically, who holds a life membership, who has already renewed, whose account is
deactivated, or who has no email address. Nobody has to start the scan, and there is no
button for it on this screen.


What you see
============

Two cards. The first, **Renewal reminders**, has a line explaining the schedule, then a table
of the twenty most recent reminders. The caption counts every reminder ever sent, such as *418
reminders sent*.

- **Sent**: the date and time it went out.
- **Reminder**: which stage it was.
- **Member**: who it went to.
- **To**: the address it was sent to.

The **Reminder** list above the table narrows it to one stage: **60 days before**, **30 days
before**, **7 days before**, **Expired**, or **30 days after** on the default schedule. **Any
kind**, or **Reset filters** beside it, puts them back. The rows open newest first, with the
arrow on **Sent**; click a column heading to sort the rows shown. On a narrow screen the
table leaves out **To**, then **Reminder**, and keeps **Member** in sight.

An empty table reads *No reminders sent yet*: no membership has reached a stage, which is
normal on a new site or when every member renewed early. With one stage chosen it reads *No
reminders of this kind*, with a **Reset filters** button.

The second card, **Reminder schedule**, lists the four numbers the stages are dated by:
**First reminder**, **Second reminder**, and **Final reminder** in days before expiry, and
**Lapsed reminder** in days after it. A line under them says who last saved the schedule and
when, or reads *The default schedule: nobody has changed it.* You can read the schedule here
but not change it.


If something looks wrong
========================

If a member says they were never told, choose the stage they should have reached and look
for their name. A row here means CalDART handed the email to the mail server; it does not
prove the email arrived, so ask them to check their spam folder, and check the address in
**To** against their record on :doc:`members`. No row at all usually means one of the
reasons above applied, most often that they had already renewed or had automatic renewal
turned on. If the table stops gaining rows for days on end, the morning scan may have
stopped; tell a system administrator, who can check it on the :doc:`scheduled` page.
