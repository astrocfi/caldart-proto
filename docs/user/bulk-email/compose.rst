:roles: management

=======
Compose
=======

**Compose** is where you write one email to many members and friends of CalDART at once: a
newsletter, a seminar notice, or a call for volunteers. Each person gets a copy of their own.
CalDART management opens it as **Compose** under **Bulk Email** in the menu. A system
administrator can open it too.

Pressing **Compose** opens a fresh email, or the empty one you started earlier. The screen
reads top to bottom as three numbered cards. There is no Save button: everything you do is
kept as you go, so you can leave and come back from :doc:`drafts`.


1. Who gets it
==============

You build the list of people, called the *batch*, a group at a time. The filters at the top
are the ones the member list uses:

- **Kind**: members or friends. A friend is somebody who supports CalDART without a paid
  membership.
- **Search**: a name, an email address, a phone number, or a certificate number.
- **Membership**, **Certificate**, **Medical**, **DART** (a Disaster Airlift Response Team,
  one of CalDART's local groups), **County**, and **Role**.
- **Expiring within (days)**: members whose membership ends within that many days.

Choose the filters, then press **Add to batch**. Everybody they choose joins the batch, and a
line says what happened, such as *Added 12 people; 3 were already in the batch.* Change the
filters and press **Add to batch** again as often as you like: nobody is added twice. With no
filters at all, **Add to batch** adds every member and friend. Donors are never added.

Above the batch a line counts it, such as *38 people will receive this email; 4 are skipped.*
The table lists everybody in the batch with their **Name**, **Email**, **Kind**, **DART**,
**Added by** (the filters of the add that brought them in, such as *County: Marin*), and
**Will receive?**, which reads *Yes* or the reason they are skipped:

- *Account deactivated*: the account has been deactivated.
- *Account deleted*: the account no longer exists.
- *No email address* or *Invalid email address*: there is nowhere to send it.
- *Address bounced*: an earlier email to this address came back undelivered. Once the
  address is corrected, or a user administrator presses **Clear bounce** on the account, the
  person receives copies again.
- *Duplicate address*: somebody earlier in the batch has the same address, so it gets one
  copy.

Whether each person receives the email is worked out again whenever you open the screen, and
once more when the email starts sending. Type in **Find in the batch** to find one person.
The trashcan on a row takes that person out after you press **Remove**. **Clear batch** takes
everybody out after you confirm it. **Download list** saves the batch as a spreadsheet file
(CSV) with each person's membership status, the add that brought them in, and whether they
will receive it.


2. What it says
===============

Write the **Subject**, one line, and the **Message**. The message is plain text: leave a
blank line between paragraphs and each becomes a paragraph of the email. A quiet note under
the message reads *Saved* once your words are kept, or *Saving…* while you type.

Each copy comes from the site's own address. Under the message it carries a short footer
with your organization's name, the contact address when one is set, and the line *You receive
this email as a member or a friend of* your organization.


3. Check and send
=================

Until the email can go, the card lists what is missing, such as *Write a subject.* or *Add
people to the batch.* Then it offers two buttons:

- **Send to 38 people** (with the number who will receive it) sends it now.
- **Schedule for later** asks for a **Date** and a **Time**, in Pacific time, then
  **Continue**. The time must be in the future and within a year.

Either one asks first: *This sends* the subject *to 38 people.*, followed by when it goes.
When the email goes to more than 50 people, the confirmation also asks you to **Type 38 to
confirm**, and the button that sends stays off until the number matches. Press **Send now**
or **Schedule it** to go ahead, or **Go back**. If the batch changed while you were typing,
the send is refused with the new number, such as *The batch has changed: it now holds 39
people. Type the new count.*

After **Send now** you have two minutes to change your mind. The card shows *Sending in 1:58*
with a bar counting down, and a **Cancel** button; the same countdown sits in a banner at the
top of the screen. **Cancel** turns the email back into a draft with nothing lost.

A scheduled email shows *Scheduled for* its date and time, with **Cancel the schedule** and
**Change the time**. Until it starts you can still change its batch and its message.

Once sending starts, the screen holds still and reads, for example, *Sending… 12 of 38 sent,
about 1 minute left.* CalDART sends a few copies a minute so the mail provider never turns
them away, so a large email takes a while. **Stop sending** stops it after the copy going out
now, once you confirm it: copies already sent cannot be called back. When it finishes, a line
such as *Sent to 37 people. 1 failed and 4 were skipped.* sits beside **See who received
it**, which opens the email's page under :doc:`sent`.


If something looks wrong
========================

If the batch holds fewer people than you expected, look at the skips first, then at the
filters of each add in the **Added by** column: a forgotten **County** or **Kind** narrows an
add quietly. If the email still says *Starting to send* a few minutes after the countdown
ended, the server's sender may have stopped; a system administrator can start it by hand from
the Scheduled page. If somebody says the email never arrived, find their row under
:doc:`sent`.
