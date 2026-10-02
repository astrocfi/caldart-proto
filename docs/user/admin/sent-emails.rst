:roles: system_admin

===========
Sent Emails
===========

**Sent Emails** lists every email CalDART has tried to send, 25 at a time and newest first.
It answers "what did we send this person?" and "is our mail going out at all?" Only a system
administrator sees it, under **System** in the menu, because it lists every address the site
has written to.

The page is the log itself: the filters, then the table of emails.


What you see
============

Each row is one email:

- **Sent**: the date and time. Click the heading to turn the order round.
- **Purpose**: what the email was for.
- **To**: the recipient's name, when CalDART knows it, and the address. A DART contact on a
  roster has a name and no account.
- **Status**: *Sent*; *Failed:* and the reason the mail server gave; or *Bounced*, for an
  email the mail server took that the recipient's mail server later refused for good.
- **Bounce**: for a bounced email, the date the bounce came back and the reason the
  recipient's mail server gave, such as *5.1.1 550 User unknown*.
- **Attachments**: the names of any files attached, such as a report or a statement.

When there are more than 25 emails, the foot reads, for example, *Showing 1–25 of 412*, with
**Previous** and **Next**.


Filtering the log
=================

The filters narrow the whole log, every page of it:

**Purpose**
   One kind of email: *Renewal reminder (60 days)*, *Renewal reminder (30 days)*, *Renewal
   reminder (7 days)*, *Renewal reminder (expired)*, *Renewal reminder (30 days after)*,
   *Renewal turned on*, *Renewal notice*, *Card expiring*, *Renewal charged*, *Renewal
   declined*, *Renewal turned off*, *Receipt*, *Refund*, *Contribution statement*,
   *Invitation*, *Password reset*, *Email verification*, *Scheduled report*, *DART
   roster*, or one of the notifications: *Notification: Sign-up*, *Notification: Member
   added by an administrator*, *Notification: Member became a friend*, *Notification:
   Friend became a member*, *Notification: Membership paid*, *Notification: Membership
   granted by an administrator*, *Notification: Membership expired*, *Notification:
   Automatic payment turned on*, *Notification: Automatic payment turned off*,
   *Notification: Automatic payment declined*, *Notification: Donation received*,
   *Notification: Payment recorded by hand*, *Notification: Payment refunded*,
   *Notification: Account deactivated*, *Notification: Account reactivated*,
   *Notification: Roles changed*, *Notification: Email address changed*,
   *Notification: Profile changed*, *Notification: Verification recorded*,
   *Notification: Aircraft added*, *Notification: Aircraft changed*, or *Notification:
   Aircraft removed*. The renewal reminders are named here as the default schedule dates
   them. Once a system administrator changes the **Reminder schedule** on
   :doc:`scheduled`, they carry its days instead, such as *Renewal reminder (45 days)*, in
   the list, in the table, and in the downloads.
**Status**
   **Sent**, **Failed**, or **Bounced**.
**From** and **To**
   A range of days, both included.
**Search**
   A name or an address, including somebody with no account.

**Reset to Defaults** clears the filters. The filters, the order, and the page are kept in
the page's address, so a filtered view can be bookmarked or sent to another system
administrator.


Downloading the log
===================

**Export CSV** and **Export PDF** download every email the filters match, in the table's
order. They carry **Sent**, **Purpose**, **To**, **Name**, **Subject**, and **Status**
unless you choose others with **Columns**; **Error**, **Attachments**, **Bounced**, and
**Bounce detail** are off until you tick them. **Load columns** and **Save columns** keep a set of columns under a name, as
:ref:`saved-column-sets` describes.


If something looks wrong
========================

The log does not prove delivery: a mail server that accepts an email and bounces it an hour
later leaves a row marked *Sent* until the hourly bounce check reads the bounce, when the row
turns *Bounced* and the address is flagged on the person's records (:doc:`scheduled`). On a
server with no bounce mailbox set up, bounces are never read and every such row stays
*Sent*. If the log shows many *Failed:* rows, the site cannot reach
its mail server; tell whoever runs the server, and once it is fixed, a password reset to your
own address is a quick test. If an email you expected is missing altogether, the job that
sends it may not have run; :doc:`scheduled` runs each one by hand.
