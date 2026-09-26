=======
Reports
=======

**Reports** is where you tell CalDART to email a report on a schedule, and where each DART's
monthly roster is sent from. A roster is the list of a DART's members and friends with the
details a team needs to reach them.

An account administrator and the treasurer find it under **Administration** in the menu. A
system administrator can open it too. The treasurer sees the subscriptions for the money
reports; the DART rosters belong to account administrators alone.


Subscriptions
=============

A subscription emails one report, with the filters and columns chosen when it was set up, to
one address on its schedule. The **Subscriptions** card lists every subscription for a report
you may read:

- **Report**: the report's title, such as *CalDART membership report*.
- **Recipient**: the account's name, or the bare address for somebody outside CalDART.
- **Schedule**: *Weekly on Monday* (or another day), *Monthly*, *Quarterly*, or *Yearly*.
- **Formats**: *CSV*, *PDF*, or *Both*.
- **Last sent** and **Next**: when it last went and when it is due.
- **Active**: a green dot while it is being sent, and a gray one while it is paused.

Each row carries three controls. The line above the table says what each one did.

**Send now**
   Sends the report at once, whatever the date, and leaves its next date alone. The line
   reads *Sent to* the recipient, or says why nothing went: the report could not be built or
   the mail server refused it, or the recipient no longer holds a role that may read the
   report, in which case the subscription is paused.

**Pause** and **Resume**
   A paused subscription keeps everything it was set up with and sends nothing until you
   resume it. Resuming one whose recipient may no longer read the report is refused, and the
   line says why.

**The trashcan**
   Deletes the subscription.

With none set up the table reads *No reports are sent by email yet*.


Setting one up
--------------

**New subscription** opens the form:

#. **Report** offers the reports you may read: the membership report, the aircraft register,
   the payments, the reconciliation, and the contributions for an account administrator;
   the payments, the reconciliation, the contributions, and the donors for the treasurer;
   and every one of them plus the email log for a system administrator. Choosing one draws
   the same filters its own screen has. The payments, contributions, and donors reports add
   **Period**: **This month**, **Last month**, **This year**, or **Last year**, worked out on
   the day each email goes, so a monthly subscription for **Last month** always carries the
   month before the one it is sent in.
#. **Columns** chooses what the report carries, as on the report's own screen; left alone,
   it carries the default columns. The reconciliation and contributions reports have fixed
   columns and offer no chooser.
#. **Formats** attaches a CSV, a PDF, or both.
#. **Schedule** is **Weekly**, **Monthly**, **Quarterly**, or **Yearly**. A weekly one asks
   for the **Day** it goes. A monthly subscription goes on the first of the month, a
   quarterly one on the first of January, April, July, and October, and a yearly one on the
   first of January.
#. **Recipient email** is where it goes.

Press **Save**, or **Cancel**. An address that belongs to a CalDART account is refused when
that account holds no role that may read the report, with *does not hold a role that may read
this report* under the address: the treasurer cannot be sent the membership report, whose
medical and certificate details are not theirs to read. An address no account holds is
refused until you tick **This address is outside CalDART and may receive this report**, which
appears once CalDART asks for it. A filter the report cannot use is named, with the reason,
under the filters.


What happens next
-----------------

The emails go out every morning at 06:00. The subject reads *CalDART report:* with the
report's title and the date, and the files are attached. A subscription that could not be
sent is tried again the next morning. One whose recipient has lost the role is paused.


DART rosters
============

Early each month every active DART's roster goes as a PDF to each of the DART's people ticked
**Roster** on the :doc:`darts` screen who has an email address. The subject is the DART's
name, the word *roster*, and the date. A roster lists the DART's members and friends by name,
with each person's phone, email, certificate, medical, aircraft, expiry, and a **Kind** column
saying which each one is. It never lists a deactivated account or a donor.

The **DART rosters** card lists each active DART, its **Recipients** (the ticked people with
an address), and when its roster was **Last sent**. A DART with nobody ticked is sent nothing.

**Send rosters now** sends every DART's roster at once, whatever the date. Leave **Dry run
(send nothing)** ticked the first time. The card then reads **What this run would do** and a
line such as *Would send 7 emails, skipped 1.* When something was skipped, a further line
gives the reasons: *nobody ticked* for a DART with nobody to send to, and *no address on
file* for a ticked person with no email address. A table names each email with **What**,
**Who**, and **Report or DART**. Clear the box and press the button again to send them for
real; the heading then reads **What this run did**.


If something looks wrong
========================

If a subscription stops arriving, look at its **Active** dot: a gray one means it was paused,
often because the recipient lost the role that reads the report, and **Resume** tells you
whether that is still so. If a roster never reaches a DART's people, check on :doc:`darts`
that somebody is ticked **Roster** and has an email address, then run **Send rosters now**
with **Dry run (send nothing)** ticked to see who it would reach. If a line reads *Not sent*
and blames the mail server, try **Send now** again later, and tell a system administrator if
it keeps failing; they can see every email CalDART tried to send on the :doc:`system` page.
