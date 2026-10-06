:roles: account_admin, treasurer

===============
Emailed reports
===============

**Emailed reports** is where you tell CalDART to email a report on a schedule, and where each DART's
monthly roster is sent from. A roster is the list of a DART's members and friends with the
details a team needs to reach them.

An account administrator and the treasurer find it as **Emailed reports** under
**Administration** in the menu. A
system administrator can open it too. The treasurer sees the subscriptions for the money
reports; the DART rosters belong to account administrators alone.


Reports on a schedule
=====================

CalDART emails each report to one address on the schedule you choose, with the filters and
columns chosen for it. The **Reports on a schedule** card lists every one for a report you
may read:

- **Report**: the report's name, as its own screen's tab or menu entry names it, such as
  *Members*, *Payments*, *Reconciliation*, *Contributions*, or *Donors*.
- **Recipient**: the account's name, or the bare address for somebody outside CalDART.
- **Schedule**: *Weekly on Monday* (or another day), *Monthly*, *Quarterly*, or *Yearly*.
- **Formats**: *CSV*, *PDF*, or *Both*.
- **Last sent** and **Next**: when it last went and when it is due.
- **Active**: *Active* beside a green dot while it is being sent, and *Paused* beside a gray
  one while it is paused.

Each row carries four controls, last on the line under an **Actions** heading a screen
reader announces. A message in the corner of the screen says what the last three did. On a
screen too narrow for every column, **Last sent**, then **Next**, then **Formats**, then
**Schedule**, then **Recipient** are left out, and the controls wrap onto two lines; on a phone the table
scrolls sideways, says so above it, and keeps **Report** pinned at the left.

**Edit**
   Opens the subscription's form above the table, where **Add a scheduled report** opens it, to
   change its filters, columns, formats, and schedule, as **Changing one** below describes.

**Send now**
   Sends the report at once, whatever the date, and leaves its next date alone. The message
   reads *Sent to* the recipient, or says why nothing went: the report could not be built or
   the mail server refused it, or the recipient no longer holds a role that may read the
   report, in which case its emails are paused.

**Pause** and **Resume**
   A paused subscription keeps everything it was set up with and sends nothing until you
   resume it. Resuming one whose recipient may no longer read the report is refused, and the
   message says why.

**The trashcan**
   Asks first: press it and it turns into **Delete** and **Cancel**. Press **Delete** and
   the emailed report is gone; **Cancel**, Escape, or a click elsewhere leaves it as it is.

With none set up the table reads *No reports are sent by email yet*.


Setting one up
~~~~~~~~~~~~~~

**Add a scheduled report** opens the form above the table and takes you to its first box. Until
you choose a report, **Add emailed report** waits, and *Choose a report first.* sits beside
it.

#. **Report** offers the reports you may read, each by the name its own screen uses: the
   membership report, the roles report, the verification report, the aircraft,
   the payments, the renewals, the reconciliation, and the contributions for an account
   administrator; the payments, the renewals, the reconciliation, the contributions, and
   the donors for the treasurer; and every one of them plus the sent emails for a system
   administrator. The roles report lists the people who hold each role other than member,
   in a section per role that says *Nobody holds this role.* when it is empty; it filters
   by name or email, by role, and by kind, and it can go to a user administrator as well
   as an account administrator. The verification report lists what a verifier checks, in
   two sections, *People* and *Aircraft insurance*, each saying *Nothing to show.* when it
   is empty. A person has one row: their DART, then **Photo ID**, **Certificate**, and
   **Medical**, each *Not verified*, *Verified*, or blank for an item they do not hold;
   then what is on file, the medical's expiry date in **Expires**, and the day it last
   changed. An aircraft's row names its N-number, its owner (under the one heading **DART
   or owner**), the carrier, the policy's expiry date, and the day it last changed.
   **Verified** (*Yes* when everything on the row is verified), **Verified by**, and
   **Verified on** (the most recent verification on the row) are there to add from
   **Columns**. Its **Status** filter lists the rows with anything not yet verified when
   left blank, or the fully **Verified** ones, or **All** of them, and its **DART** filter
   keeps one DART's people and the aircraft they fly. It can go to a verifier, a DART leader, a user
   administrator, or an account administrator. Choosing a report draws the same filters its own screen
   has, with no **Reset filters** button among them. The payments and donors reports add
   **Period**: **This month**, **Last month**, **This year**, or **Last year**, worked out
   on the day each email goes, so a monthly subscription for **Last month** always carries
   the month before the one it is sent in. The reconciliation report offers **Period** in
   place of its screen's fixed **From** and **To** dates, and the contributions report has
   one **Year** control: **This year** or **Last year**, also worked out on the day each
   email goes.
#. **Columns** chooses what the report carries, as on the report's own screen; left alone,
   it carries the default columns. The reconciliation and contributions reports have fixed
   columns and offer no chooser.
#. **Formats** attaches a CSV, a PDF, or both.
#. **Schedule** is **Weekly**, **Monthly**, **Quarterly**, or **Yearly**. A weekly one asks
   for the **Day** it goes. A monthly subscription goes on the first of the month, a
   quarterly one on the first of January, April, July, and October, and a yearly one on the
   first of January.
#. **Recipient email** is where it goes.

Press **Add emailed report**, or **Cancel** or Escape. *Report added.* confirms a save. An address that belongs to a CalDART account is refused when
that account holds no role that may read the report, with *does not hold a role that may read
this report* under the address: the treasurer cannot be sent the membership report, whose
medical and certificate details are not theirs to read. An address no account holds is
refused until you check **This address is outside CalDART and may receive this report**, which
appears once CalDART asks for it. A filter the report cannot use is named, with the reason,
under the filters.


Changing one
~~~~~~~~~~~~

**Edit** on a row opens the same form above the table, headed **Edit emailed report** and filled
with everything the subscription was set up with: its filters, its columns, its formats, and
its schedule and day. A subscription on the report's default columns opens with the defaults
checked. The **Report** and the **Recipient** are shown as plain text, since neither can
change: to send a different report, or to send it to somebody else, delete the subscription
and set up another.

Change what you need and press **Save changes**; the form closes, *Report saved.* confirms it,
and the row shows the change. A changed schedule moves **Next** to the schedule's next day
after today. **Cancel**, or Escape, closes the form and changes nothing, and you are back on
the row's **Edit**. A filter the report cannot use is named, with the reason, under the
filters, as when setting one up.

One form is open at a time. **Add a scheduled report** closes an open edit, **Edit** on another row
opens that row's subscription in its place, and **Edit** on the row being edited closes it.


What happens next
~~~~~~~~~~~~~~~~~

The emails go out every morning at 6:00 AM. The subject reads *CalDART report:* with the
report's title and the date, such as *(09/27/2026)*, and the files are attached. A
subscription that could not be sent is tried again the next morning. One whose recipient
has lost the role is paused.


DART rosters
============

Early each month every active DART's roster goes as a PDF to each of the DART's people checked
**Roster** on the :doc:`darts` screen who has an email address. The subject is the DART's
name, the word *roster*, and the date. A roster lists the DART's members and friends by name,
with each person's phone, email, certificate, medical, aircraft, expiry, and a **Kind** column
saying which each one is. It never lists a deactivated account or a donor.

The **DART rosters** card lists each active DART, its **Recipients** (the checked people with
an address), and when its roster was **Last sent**. A DART with nobody set to receive it is sent nothing.

Under the table sit the box **Practice run: show what would happen, send nothing**, checked
to begin with, the button beside it, and under them what the last run did, so the button
never moves when a long result appears. While the box is checked the button reads
**Preview rosters**: press it, and under it the card reads **What this run would do**, where
the cursor moves, and a line such as *Would send 7 emails, skipped 1.* When something was skipped, a further
line gives the reasons: *nobody to send to* for a DART with nobody set to receive it, and
*no address on file* for a checked person with no email address. A table names each email
with **Who** and **What**, and **Report or DART** when an email names one. Clear the box,
and the button reads **Send rosters now**: it sends every DART's roster at once, whatever
the date, and the heading then reads **What this run did**.


If something looks wrong
========================

If a subscription stops arriving, look at its **Active** column: *Paused* means it was paused,
often because the recipient lost the role that reads the report, and **Resume** tells you
whether that is still so. If a roster never reaches a DART's people, check on :doc:`darts`
that somebody is checked **Roster** and has an email address, then press **Preview
rosters**, with **Practice run: show what would happen, send nothing** checked, to see who
it would reach. If a line reads *Not sent*
and blames the mail server, try **Send now** again later, and tell a system administrator if
it keeps failing; they can see every email CalDART tried to send on the :doc:`sent-emails` page.
