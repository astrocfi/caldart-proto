:roles: system_admin

===========
Sent emails
===========

**Sent emails** lists every email CalDART has tried to send, 25 at a time and newest first.
It answers "what did we send this person?" and "is our mail going out at all?" Only a system
administrator sees it, under **System** in the menu, because it lists every address the site
has written to.

The page is the log itself: the filters, then the table of emails. Each email opens on a
page of its own.


What you see
============

Each row is one email. The table shows the columns checked under **Columns** (see
`Downloading the log`_), which are these unless you choose others:

- **Sent**: the date and time. The arrow on the heading shows the order, newest first; click
  the heading to turn it round. The other headings carry no arrow: the log sorts by **Sent**
  alone.
- **Purpose**: what the email was for. For a copy of a bulk email, *Bulk email* is a link
  to that email's page on :doc:`../bulk-email/sent`, where its delivery report shows every
  copy.
- **To**: the address it went to, a link that opens the email (see `Opening an email`_).
- **Name**: the recipient's name, when CalDART knows it. A DART contact on a roster has a
  name and no account.
- **Subject**: the email's subject line.
- **Status**: *Sent* beside a green dot; *Failed:* and the reason the mail server gave, beside a
  red one; or *Bounced*, beside a red one, for an email the mail server took that the
  recipient's mail server later refused for good.

Check **Error**, **Attachments**, **Bounced**, or **Bounce detail** to add them: the reason a
send failed, the names of any files attached, the date a bounce came back, and the reason
the recipient's mail server gave, such as *5.1.1 550 User unknown*.

On a narrow screen the table leaves out the default columns that matter least, **Purpose**,
**Name**, **Subject**, and on a phone **Sent**, in turn, and keeps **To**, **Status**, and
any column you checked beyond the defaults; a line above the table names what it left out.
If it is still too wide it scrolls sideways inside its card, says so in that line, and
keeps **To** pinned at the left.

When there are more than 25 emails, the foot reads, for example, *Showing 1–25 of 412*, with
**Previous** and **Next**; moving to another page brings the top of the table back into
view.


Opening an email
================

Press the address in **To** to open that email on a page of its own, headed by its subject.
It reads, one line each:

- **To**: the recipient's name, when CalDART knows it, and the address.
- **For**: what the email was for, as **Purpose** reads in the table.
- **Sent**: the date and time.
- **Status**: *Sent*, *Failed*, or *Bounced*, beside its dot.
- **Error**, for a failed send: the reason the mail server gave.
- **Bounced on** and **Bounce report**, for a bounced email: when the bounce came back and
  what the recipient's mail server said.
- **Attachments**: the names of any files attached.

The log keeps who an email went to and what it was for. It keeps no copy of the text, so a
password reset link or a verification link is never kept in it. A copy of a bulk email
offers **Open the bulk email**, which opens that email's page on
:doc:`../bulk-email/sent`, where its message is. **Back to sent emails** returns to the
list.


Filtering the log
=================

The filters narrow the whole log, every page of it:

**Purpose**
   One kind of email: *First reminder (60 days before)*, *Second reminder (30 days before)*,
   *Final reminder (7 days before)*, *Expired reminder (up to 6 days after)*, *Lapsed reminder (30
   days after)*,
   *Automatic renewal or recurring donation turned on*, *Renewal notice*, *Card expiring*,
   *Renewal charged*, *Automatic renewal or recurring donation charge failed*, *Automatic
   renewal or recurring donation turned off*, *Receipt*, *Refund*, *Contribution statement*,
   *Invitation*, *Password reset*, *Email verification*, *Bulk email*, *Bulk email test*,
   *Scheduled report*, *DART roster*, or one of the notifications: *Notification: Sign-up*,
   *Notification: Member added by an administrator*, *Notification: Member became a friend*,
   *Notification: Friend became a member*, *Notification: Membership paid*, *Notification:
   Membership granted by an administrator*, *Notification: Membership expired*,
   *Notification: Automatic renewal or recurring donation turned on*, *Notification:
   Automatic renewal or recurring donation turned off*, *Notification: Automatic renewal or
   recurring donation charge failed*, *Notification: Donation received*,
   *Notification: Payment recorded by hand*, *Notification: Payment refunded*,
   *Notification: Account deactivated*, *Notification: Account reactivated*, *Notification:
   Roles changed*, *Notification: Email address changed*, *Notification: Profile changed*,
   *Notification: Verification recorded*, *Notification: Aircraft added*, *Notification:
   Aircraft changed*, or *Notification: Aircraft removed*. The renewal reminders are named
   here as the default schedule dates them. Once a system administrator changes the
   **Reminder schedule** on :doc:`scheduled`, they carry its days instead, such as *Renewal
   reminder (45 days)*, in the list, in the table, and in the downloads.
**Status**
   **Sent**, **Failed**, or **Bounced**.
**From** and **To**
   A range of days, both included.
**Search**
   A name or an address, including somebody with no account.

**Reset filters** clears the filters; when nothing matches them, the empty table offers its
own **Reset filters** button. The filters, the order, and the page are kept in
the page's address, so a filtered view can be bookmarked or sent to another system
administrator.


Downloading the log
===================

**Export CSV** and **Export PDF** download every email the filters match, in the table's
order, with the same columns as the table: **Columns** changes the table and both downloads
together. **Load columns** and **Save columns** keep a set of columns under a name, as
:ref:`saved-column-sets` describes.


If something looks wrong
========================

The log does not prove delivery: a mail server that accepts an email and bounces it an hour
later leaves a row marked *Sent* until the hourly bounce check reads the bounce, when the row
turns *Bounced* and the address is flagged on the person's records (:doc:`scheduled`). On a
server with no bounce mailbox set up, bounces are never read and every such row stays
*Sent*. If the log shows many *Failed:* rows, the site cannot reach
its mail server; tell whoever runs the server, and once it is fixed, a password reset to your
own address is a quick test. Somebody who asks for a password reset or a fresh verification
link is told the same thing whether or not it went, so a reset never gives away whether an
address has an account: a *Failed:* row here is how you learn their email never left. If an email you expected is missing altogether, the job that
sends it may not have run; :doc:`scheduled` runs each one by hand.
