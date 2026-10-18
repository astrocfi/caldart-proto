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
`Downloading the log`_). Unless you choose others, these are the columns, with **To** first:

- **To**: the address it went to, as a link that opens the email (see `Opening an email`_).
- **Sent**: the date and time. The arrow on the heading shows the order, newest first.
  Click the heading to reverse it. The other headings don't have an arrow, because the log
  sorts only by **Sent**.
- **Purpose**: what the email was for. For a copy of a bulk email, *Bulk email* is a link
  to that email's page on :doc:`../bulk-email/sent`, where its delivery report shows every
  copy.
- **Name**: the recipient's name, if CalDART knows it. A DART contact on a roster has a
  name but doesn't have an account.
- **Subject**: the email's subject line.
- **Status**: *Sent* beside a green dot, or *Failed:* and the reason, such as *The mail
  server refused the address.*, beside a red one. *Bounced*, beside a red dot, means the
  mail server took the email, but the recipient's mail server later refused it for good.

Check **Error**, **Attachments**, **Bounced**, or **Bounce detail** to add those columns.
They give the reason a send failed, in the same words, the names of any attached files, the
date a bounce came back, and the reason the recipient's mail server gave, such as *5.1.1
550 User unknown*.

On a narrow screen, the table drops the default columns that matter least, **Purpose**,
**Name**, and **Subject**, in that order. It keeps **To**, **Sent**, **Status**, and any
column you added to the defaults. That way, a phone can still tell two emails to the same
address apart by when each one went. A line above the table names the columns it dropped.
If the table is still too wide, it scrolls sideways inside its card, says so in that line,
and keeps **To** pinned at the left.

When there are more than 25 emails, the foot says, for example, *Showing 1–25 of 412*, with
**Previous** and **Next**. Moving to another page scrolls back to the top of the table.


Opening an email
================

Press the address in **To** to open that email on a page of its own, with its subject as
the heading. The page shows, one line each:

- **To**: the recipient's name, if CalDART knows it, and the address.
- **For**: what the email was for, the same as **Purpose** in the table.
- **Sent**: the date and time.
- **Status**: *Sent*, *Failed*, or *Bounced*, beside its dot.
- **Error**, for a failed send: the reason in words, such as *The mail server refused the
  address.* Under it is what the server recorded, such as *Recorded as
  SMTPRecipientsRefused*, to pass on to whoever runs the server.
- **Bounced on** and **Bounce report**, for a bounced email: when the bounce came back and
  what the recipient's mail server said.
- **Attachments**: the names of any attached files.

The log keeps who an email went to and what it was for. It doesn't keep a copy of the text,
so it never holds a password reset link or a verification link. A copy of a bulk email
offers **Open the bulk email**, which opens that email's page on :doc:`../bulk-email/sent`,
where you can read its message. **Back to sent emails** takes you back to the list, with
the filters, order, and page you had when you opened the email.


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
   *Invitation*, *Password reset*, *Email verification*, *Email change link*, *Email change
   notice*, *Password changed*, *Account already exists*, *Two-factor sign-in turned on*,
   *Two-factor sign-in turned off*, *Two-factor sign-in reset*, *Backup code used*, *New
   backup codes*, *Wrong two-factor code*, *Sign-in paused*, *Bulk email*, *Bulk email test*,
   *Scheduled report*, *DART roster*, or one of the notifications: *Notification: Sign-up*,
   *Notification: Member added by an administrator*, *Notification: Member became a friend*,
   *Notification: Friend became a member*, *Notification: Membership paid*, *Notification:
   Membership granted by an administrator*, *Notification: Membership expired*,
   *Notification: Automatic renewal or recurring donation turned on*, *Notification:
   Automatic renewal or recurring donation turned off*, *Notification: Automatic renewal or
   recurring donation charge failed*, *Notification: Automatic charge needs checking*,
   *Notification: Donation received*,
   *Notification: Payment recorded by hand*, *Notification: Payment refunded*,
   *Notification: Account deactivated*, *Notification: Account reactivated*, *Notification:
   Roles changed*, *Notification: Email address changed*, *Notification: Profile changed*,
   *Notification: Verification recorded*, *Notification: Aircraft added*, *Notification:
   Aircraft changed*, or *Notification: Aircraft removed*. The renewal reminders are named
   here by the days of the default schedule. Once a system administrator changes the
   **Reminder schedule** on :doc:`scheduled`, they show its days instead, such as *Renewal
   reminder (45 days)*, in the list, in the table, and in the downloads.
**Status**
   **Sent**, **Failed**, or **Bounced**.
**From** and **To**
   A range of days, including both ends.
**Search**
   A name or an address, including somebody without an account.

**Reset filters** clears the filters. When nothing matches them, the empty table offers its
own **Reset filters** button. The filters, the order, and the page are kept in the page's
address, so you can bookmark a filtered view or send it to another system administrator.


Downloading the log
===================

**Export CSV** and **Export PDF** download every email that matches the filters, in the
table's order, with the same columns as the table. **Columns** changes the table and both
downloads together. **Load columns** and **Save columns** keep a set of columns under a
name, as :ref:`saved-column-sets` describes.


If something looks wrong
========================

The log doesn't prove that an email was delivered. A mail server may accept an email and
bounce it an hour later. The row then says *Sent* until the hourly bounce check reads the
bounce. At that point the row changes to *Bounced*, and the address is flagged on the
person's records (:doc:`scheduled`). If the server doesn't have a bounce mailbox set up,
CalDART never reads the bounces, and every such row stays *Sent*. If the log shows many
*Failed:* rows, the site can't reach its mail server. Tell whoever runs the server. Once it
is fixed, a password reset to your own address is a quick test. When somebody asks for a
password reset or a fresh verification link, the site tells them the same thing whether or
not the email went. That way a reset never gives away whether an address has an account, so
a *Failed:* row here is how you learn that their email never left. If an email you expected
is missing altogether, the job that sends it may not have run. You can run each job by hand
on :doc:`scheduled`.
