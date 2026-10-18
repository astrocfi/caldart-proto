:roles: account_admin, treasurer

===============
Emailed reports
===============

**Emailed reports** is where you tell CalDART to email a report on a schedule. It is also
where each DART's monthly roster is sent from. A roster is the list of a DART's members and
friends, with the details a team needs to reach them.

An account administrator and the treasurer find it as **Emailed reports** under
**Administration** in the menu. A system administrator can open it too. The treasurer sees
the subscriptions for the money reports. Only account administrators see the DART rosters.


Reports on a schedule
=====================

CalDART emails each report to one address on the schedule you choose, with the filters and
columns chosen for it. The **Reports on a schedule** card lists every subscription for a
report you may see:

- **Report**: the report's name, the same as its own screen's tab or menu entry, such as
  *Members*, *Payments*, *Reconciliation*, *Contributions*, or *Donors*.
- **Recipient**: the account's name, or just the address for somebody outside CalDART.
- **Schedule**: *Weekly on Monday* (or another day), *Monthly*, *Quarterly*, or *Yearly*.
- **Formats**: *CSV*, *PDF*, or *Both*.
- **Last sent** and **Next**: when it last went and when it is due.
- **Active**: *Active* beside a green dot while it is being sent, and *Paused* beside a gray
  one while it is paused.

Each row has four controls at the end of the line, under an **Actions** heading that a
screen reader announces. A message in the corner of the screen says what the last three
did. If the screen is too narrow for every column, the table drops **Last sent**, then
**Next**, then **Formats**, then **Schedule**, then **Recipient**, and the controls wrap
onto two lines. On a phone, the table scrolls sideways, says so above it, and keeps
**Report** pinned at the left.

**Edit**
   Opens the subscription's form above the table, in the same place as **Add a scheduled
   report**. There you can change its filters, columns, formats, and schedule, as
   **Changing one** below describes.

**Send now**
   Sends the report at once, whatever the date, and leaves its next date as it was. The
   message says *Sent to* and the recipient, or says why the report didn't go. Either the
   report couldn't be built, or the mail server refused it, or the recipient has lost the
   role the report needs. In that last case, its emails are paused.

**Pause** and **Resume**
   A paused subscription keeps everything it was set up with, but it doesn't send anything
   until you resume it. If the recipient has since lost the right to see the report,
   CalDART refuses to resume it, and the message says why.

**The trashcan**
   Asks first: press it, and it turns into **Delete** and **Cancel**. Press **Delete** to
   remove the emailed report. **Cancel**, Escape, or a click elsewhere leaves it as it is.

Until you set one up, the table says *No reports are sent by email yet*.


Setting one up
~~~~~~~~~~~~~~

**Add a scheduled report** opens the form above the table and puts you in its first box.
Until you choose a report, **Add emailed report** is grayed out, with *Choose a report
first.* beside it.

#. **Report** offers the reports you may see, each with the name its own screen uses. An
   account administrator gets the membership report, the roles report, the verification
   report, the aircraft, the payments, the renewals, the reconciliation, and the
   contributions. The treasurer gets the payments, the renewals, the reconciliation, the
   contributions, and the donors. A system administrator gets every one of them, plus the
   sent emails.

   The roles report lists the people who hold each role other than member, in a section per
   role. An empty section says *Nobody holds this role.* The report filters by name or
   email, by role, and by kind. It can go to a user administrator as well as an account
   administrator.

   The verification report lists what a verifier checks, in two sections, *People* and
   *Aircraft insurance*. An empty section says *Nothing to show.* Each person has one row:
   their DART, then **Photo ID**, **Certificate**, and **Medical**. Each of these says *Not
   verified* or *Verified*, or *Not provided* for an item the person doesn't hold. Then come
   what is on file, the medical's expiry date in **Expires**, and the day it last changed.
   An aircraft's row gives its N-number, its owner, the carrier, the policy's expiry date,
   and the day it last changed. In the PDF, each section has its own header row, and the
   aircraft section doesn't have the check columns. In the CSV, one header row covers both
   sections, the owner goes under **DART or owner**, and an aircraft's check cells are
   blank. You can add **Verified** (*Yes* when everything on the row is verified),
   **Verified by**, and **Verified on** (the most recent verification on the row) from
   **Columns**. Left blank, its **Status** filter lists the rows with anything not yet
   verified. It can also list only the fully **Verified** rows, or **All** of them. Its
   **DART** filter keeps one DART's people and the aircraft they fly. The report can go to
   a verifier, a DART leader, a user administrator, or an account administrator.

   When you choose a report, the form shows the same filters as the report's own screen,
   without the **Reset filters** button. The payments and donors reports add **Period**:
   **This month**, **Last month**, **This year**, or **Last year**. CalDART works out the
   period on the day each email goes, so a monthly subscription for **Last month** always
   covers the month before the one it is sent in. The reconciliation report offers
   **Period** instead of its screen's fixed **From** and **To** dates. The contributions
   report has a single **Year** control, **This year** or **Last year**, also worked out on
   the day each email goes.
#. **Columns** chooses what the report includes, as on the report's own screen. If you
   leave it alone, the report has the default columns. A column you leave out is left out
   of every section of the PDF that has it. The reconciliation and contributions reports
   have fixed columns and don't offer a chooser.
#. **Formats** attaches a CSV, a PDF, or both.
#. **Schedule** is **Weekly**, **Monthly**, **Quarterly**, or **Yearly**. For a weekly one,
   choose the **Day** it goes. A monthly subscription goes on the first of the month, a
   quarterly one on the first of January, April, July, and October, and a yearly one on the
   first of January.
#. **Recipient email** is where it goes.

Press **Add emailed report**, or **Cancel** or Escape. *Report added.* confirms a save. If
the address belongs to a CalDART account, and that account doesn't hold a role allowed to
see the report, CalDART refuses it. The message *does not hold a role that may read this
report* appears under the address. For example, you can't send the treasurer the
membership report, because its medical and certificate details aren't theirs to see. If
the address doesn't belong to an account, CalDART refuses it until you check **This
address is outside CalDART and may receive this report**. That box appears once CalDART
asks for it. If the report can't use a filter, the filter is named, with the reason, under
the filters.


Changing one
~~~~~~~~~~~~

**Edit** on a row opens the same form above the table, headed **Edit emailed report**. It
is filled in with everything the subscription was set up with: its filters, its columns,
its formats, and its schedule and day. If the subscription uses the report's default
columns, the form opens with the defaults checked. The **Report** and the **Recipient** are
shown as plain text, because you can't change them. To send a different report, or to send
it to somebody else, delete the subscription and set up another one.

Change what you need and press **Save changes**. The form closes, *Report saved.* confirms
it, and the row shows the change. If you change the schedule, **Next** moves to the
schedule's next day after today. **Cancel**, or Escape, closes the form without changing
anything, and you land back on the row's **Edit**. If the report can't use a filter, the
filter is named, with the reason, under the filters, just as when you set one up.

Only one form is open at a time. **Add a scheduled report** closes a form you are editing.
**Edit** on another row opens that row's subscription instead, and **Edit** on the row you
are editing closes it.


What happens next
~~~~~~~~~~~~~~~~~

The emails go out every morning at 6:00 AM. The subject says *CalDART report:* with the
report's title and the date, such as *(09/27/2026)*, and the files are attached. If a
subscription couldn't be sent, CalDART tries again the next morning. If its recipient has
lost the role, the subscription is paused.


DART rosters
============

Early each month, every active DART's roster goes out as a PDF. It goes to each of the
DART's people who has **Roster** checked on the :doc:`darts` screen and has an email
address. The subject is the DART's name, the word *roster*, and the date. A roster lists the
DART's members and friends by name, with each person's phone, email, certificate, medical,
aircraft, and expiry. A **Kind** column says whether each one is a member or a friend. A
roster never lists a deactivated account or a donor.

The **DART rosters** card lists each active DART, its **Recipients** (the checked people
with an address), and when its roster was **Last sent**. If nobody at a DART is set to get
the roster, it isn't sent.

Under the table are the box **Practice run: show what would happen without sending
anything**, checked to begin with, and the button beside it. What the last run did appears
under them, so the button stays in place when a long result appears. While the box is
checked, the button says **Preview rosters**. Press it, and the card shows the heading
**What this run would do**, where the cursor moves. Under it is a line such as *Would send 7
emails, skipped 1.* If anything was skipped, another line gives the reasons: *nobody to send
to* for a DART where nobody is set to get it, and *no address on file* for a checked person
without an email address. A table names each email with **Who** and **What**, and **Report
or DART** when an email names one. If you clear the box, the button says **Send rosters
now**. It sends every DART's roster at once, whatever the date, and the heading then says
**What this run did**.


If something looks wrong
========================

If a subscription stops arriving, look at its **Active** column. *Paused* means it was
paused, often because the recipient lost the role the report needs. **Resume** tells you
whether that is still true. If a roster never reaches a DART's people, check on
:doc:`darts` that somebody has **Roster** checked and has an email address. Then press
**Preview rosters**, with **Practice run: show what would happen without sending anything**
checked, to see who it would reach. If a line says *Not sent* and blames the mail server,
try **Send now** again later. If it keeps failing, tell a system administrator. They can
see every email CalDART tried to send on the :doc:`sent-emails` page.
