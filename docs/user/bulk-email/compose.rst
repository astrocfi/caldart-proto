:roles: management, dart_leader

=======
Compose
=======

**Compose** is where you write one email to many members and friends of CalDART at once: a
newsletter, a seminar notice, or a call for volunteers. Each person gets a copy of their own.
CalDART management finds it under **Bulk email** in the menu. So does a DART leader, who
writes to their own DART (:doc:`dart-leaders`). A system administrator can open it too.

Pressing **Compose** opens a fresh email, or the empty one you started earlier. The screen
has three numbered cards, from top to bottom. There isn't a Save button. Everything you do is
saved as you go, so you can leave and come back from :doc:`drafts`. A draft made with
**Duplicate** (:doc:`sent`) shows *This is a copy of* and the email's subject at the top.


1. Who gets it
==============

The people you add make up the recipient list: everyone this email goes to. You build it one
search at a time, with the same filters the member list uses:

- **Kind**: **Members only** or **Friends only**. A friend supports CalDART without paying
  dues. A member who hasn't paid yet counts as a member, as on :doc:`../admin/members`.
- **Search**: a name or an email address.
- **Membership**, **Certificate**, **Medical**, **DART**, **County**, and **Role**. A DART is
  a Disaster Airlift Response Team, one of CalDART's local groups. Under **DART** and
  **County**, check as many as you like.
- **Expiring within (days)**: members whose membership ends within that many days.

The people the filters match show under them, ten at a time, with a count such as *12 people
match these filters.* If you don't choose a filter, every member and friend matches. Donors
never match. Each row has **Name**, **Email**, **Will receive?** (*Yes*, or why not, as
below), **Kind**, and **DART**.

Press **Add these people** to put everybody the search matches on the recipient list. A line
says what happened, such as *Added 12 people; 3 were already on the recipient list.*, and the
keyboard focus moves to it. Search and add as often as you like: nobody is added twice.
**Save as a group** saves the search as a group (:doc:`groups`). **Add a saved group** opens a
**Group** drop-down that shows each group's size. Choose one and press **Add this group**.

Once somebody is on the recipient list, a line gives the count, such as *38 people will
receive this email; 4 are skipped.* **Download list** saves the list as a spreadsheet file
(CSV) with each person's membership status, the filters that chose them, whether they will
receive the email, and the email's type. **Remove everyone** empties the list once you confirm.

The table lists the people in surname order, ten at a time until you press **Show all**. Each
row has the person's **Name**, **Email**, **Will receive?** (*Yes* or the reason they are
skipped), **Kind**, **DART**, **Chosen by** (the filters that brought them in, *Group: Board*
for a saved group, or *Copied from* and a subject), and a trashcan at the end. A narrow screen
hides **Chosen by** first, then **DART**, **Kind**, and **Email**. The reasons are:

- *Account deactivated*: the account has been deactivated.
- *Account deleted*: the account has been deleted.
- *Not in your DART*: on a DART leader's email, the person's profile names another DART, or
  doesn't name one (:doc:`dart-leaders`).
- *No email address* or *Invalid email address*: there is nowhere to send it.
- *Address bounced*: an earlier email to this address came back undelivered. Once the
  address is corrected, or a user administrator presses **Clear bounce** on the account, the
  person receives copies again.
- *Opted out of Mission* (with the email's type): the person turned that type of email off on
  their :doc:`../member/email-preferences` or with an unsubscribe link. Nobody is skipped for
  this until you choose the type.
- *Duplicate address*: somebody earlier on the list has the same address, so only one copy goes.

CalDART works out again who will receive the email each time you open the screen, and once
more when the email starts sending. On a recipient list of more than ten people, type in
**Find on the list** to find one person. The trashcan on a row takes that person off the list
after you press **Remove**.


2. What it says
===============

CalDART management can start from a saved message with **Start from a template**, which asks
before it replaces anything you have written. **Save as a template** keeps this message as a
template. :doc:`templates` explains both.

To ask who can fly for a mission, switch on **This is a mission callout** and set **Answers
close**. :doc:`callouts` explains the answer buttons and where the answers collect.

First choose the **Type of email**. There is one button for each type you may send, such as
**Operational** or **Mission**, with a sentence saying what it is for. A mission callout offers
only **Mission**, and switching on a callout chooses it. Until you choose, the card says
*Choose what type of email this is.* The choice saves at once. Everybody who has turned that
type off is then skipped on the recipient list above. :doc:`email-types` lists the types and
who may send each one.

Then write the **Subject**, one line, and the **Message**. Your work saves as you type. A small
note under the message says *Saving…* and then *Saved*.

**Replies go to** is where a reader's reply goes. Every copy comes from the site's own address.
Nobody reads that mailbox, so without a reply-to address a reply wouldn't reach anybody. If you
leave the box empty, replies go to the address your organization chose for replies, or to your
own address. The hint under the box says which. To send replies somewhere else, type that
address, such as a DART leader's or a shared operations mailbox. Empty the box to go back to
the hint's address. The address saves when you leave the box or press Enter, and you see
*Address for replies saved.* If you type something like *ops@*, you see *Enter a valid email
address.*, and the address saved before stays until you fix it.

The buttons over the message format it: **Bold**, **Italic**, **Heading**, **Bulleted list**,
and **Numbered list**. A button stays pressed while the words at the cursor have its style.
Press it again to take the style off.

- **Link** asks for the **Web or email address** the selected words go to, such as
  *caldart.org/events* or an email address, then **Add link**. If you haven't selected any
  words, the address itself goes in as the link. With the cursor on a link, the button offers
  **Save link** and **Remove link**.
- **Image** opens your computer's file picker. Choose a PNG, JPEG, GIF, or WebP picture of
  at most 5 MB. While it uploads, the box shows *Uploading* and the file's name. Then
  **Describe the image** in a few words, such as *Volunteers loading a Cessna*, and press
  **Put image in**. The description is required: many mail programs hide pictures until the
  reader allows them, and the description is what they see instead. A large picture is made
  smaller to suit an email, and any location the camera recorded in it is removed.
- **Insert field**, here and beside the subject, lists the details filled in for each person
  in their own copy: **First name**, **Last name**, **Full name**, **Email address**,
  **DART**, **Membership plan**, **Membership status**, **Expiration date**, and **Home
  airport**. Choose one and it goes in at the cursor. In the subject it appears in braces, as
  *{first_name}*. In the message it appears as a chip, which Backspace or Delete removes whole.
  Braces you type in the message turn into a chip once the cursor moves on. To show a word
  when the detail is missing, click the chip (or press Enter or Space on it), fill in **If we
  don't have their first name, show**, and press **Apply**. The chip then says *First name, or
  friend*. In the subject, write *{first_name|friend}*.

A field that isn't on the list, such as *{nickname}*, is refused, and your words aren't saved
until you fix it: *{nickname} is not one of the fields. Delete it, or pick a field from Insert
field.* In the message it is a chip marked *not a field*. Click it for **Choose a field**,
**Turn into words**, or **Remove**. In the subject, pick a field or take out the braces. If a
link's web address needs braces, write them as *%7B* and *%7D*, as the message says. A field
with only part of it styled is refused too. Put it in again with **Insert field**.

Under the message, each copy has a short footer with your organization's name and, if one is
set, the contact address. For a type people may turn off, the footer says *You receive Mission
email from CalDART because you have not turned it off. To stop it, unsubscribe here:* with a
link for that person, and their mail program can offer its own **Unsubscribe** button. For a
type people can't turn off, the footer says why they receive it.

**Send me a test**, at the bottom of the card, sends the email to you alone. You see it in your
own mail program as the people on the recipient list will: the same layout, pictures, links,
footer, and address for replies, with your own details in its fields. Its subject starts
*[Test]*. What you have typed is saved first. Each press sends another test and says where it
went, such as *A test went to pat@example.org.*, and the keyboard focus moves to that line. A
test isn't counted with the copies, and the log of sent emails lists it as *Bulk email test*.
A problem marked **Must fix** (see below) stops the test, and the problems are listed.


3. Check and send
=================

The card opens with the **Checks**. The site looks for mistakes in the saved email and lists
each one on its own line, with a dot. The checks run when the card opens, again when you press
**Check again**, and again when you press **Send** or **Schedule for later**. While they run,
the card says *Checking the email for mistakes, such as links that do not work…*. This can take
a few seconds. When all is well, the card says *No problems found.*, or *Nothing
else to fix.* while a step such as the subject is still missing.

Words that couldn't be saved come first, marked **Must fix**. For example, you may see *Your
subject has a mistake:* and the reason, with **Fix it under 2. What it says.**, which puts the
cursor there. **Send** and **Schedule for later** stay off until the words are saved.

A red dot and **Must fix:** mark a problem that stops the email from going, such as a
**Replies go to** address that isn't an email address, or a field that can't be filled in.
**Send** stays off until you fix it and press **Check again**. An amber dot and **Worth a
look:** mark something that may be a mistake. *You can still send.* tells you that you may go
ahead anyway:

- *{dart_name} is empty for 41 of 120 people who receive this email, so their copies don't
  show anything there.* Add words to show instead, as in *{dart_name|your DART}*, or take it out.
- *The email still says "TODO".* Placeholder text, such as *TODO*, *XXX*, *lorem ipsum*, or
  *[insert*, is still in the subject or the message.
- *1 picture doesn't have a description for people who cannot see pictures.* Delete it and
  put it in again with **Image**, which asks for one.
- *1 picture is wider than 1200 pixels, too wide for many mail programs.*
- *This link does not load*, sometimes with the kind of error the site answered, or *This
  link timed out*: the page may be gone or the address mistyped. Open it yourself to be sure.
- *This link does not use https, so it is not secure.*
- *Links into a private network are not checked.* The link points inside a private network or
  at the site's own server. For safety, the site doesn't try those.
- *Links to a port other than 80 or 443 are not checked.* The address names an unusual
  port, such as *:8080*. Open it yourself to be sure.
- *This link was not checked in time.* The checks stop after about half a minute.

The site doesn't try links to its own pages, links that hold a field, or email address links.
If the checks can't run at all, or take more than a few seconds when you press **Send**, the
card says *The checks could not run. You can still send.* and lets you go on. An email with a
problem marked **Must fix** is still refused when you send it.

Once the message is written, a preview appears below the checks. It shows the email as the
first person on the recipient list will receive it, with their own details filled in.
*Previewing as Ann Able (1 of 38)* says whose copy it is. **Next person** and **Previous
person** step through everybody who receives it. The preview shows the saved email, and it
says so if your latest words can't be saved. If nobody on the recipient list will receive the
email, the preview shows your own copy. The footer looks as it will in the email, but its
unsubscribe link doesn't unsubscribe anybody. Every link in the preview opens in a new tab, so
you can try them without leaving the email. If a field can't be filled in, the preview says why.

Until the email can go, the card lists what is missing, such as *Choose a type.*, *Write a
subject.*, or *Add people to the recipient list.* Then it offers two buttons:

- **Send to 38 people** (with the number who will receive it) sends it now.
- **Schedule for later** asks for a **Date** and a **Time**, in Pacific time, such as *8:00
  AM*, then **Continue**. The time must be in the future and within a year.

Either one asks you first. The question says *This sends*, the subject, and *to 38 people.*,
then when it goes, such as *Sending starts in 2 minutes, and until then you can cancel it.* or
*It goes out on 10/04/2026 at 8:00 AM Pacific time.* When the email goes to more than 50
people, it also asks you to **Type 38 to confirm**, and the button that sends stays off until
the number matches. If you type a different number, you see *That number does not match. Type
38, the number of people who will receive it.* The cursor starts in that box, or on
**Cancel**, so pressing Enter twice never sends the email. Press **Send** or **Schedule it**,
or **Cancel**. If the recipient list changed in the meantime, the send is refused with the new
count, such as *The recipient list has changed: it now holds 39 people. Type the new count.*


Once it is sent
===============

Once you press **Send**, the cards disappear, and only the banner at the top stays.

You then have two minutes to change your mind. The banner says *Sending in 1 min 58 s*, with a
bar counting down and **Cancel**. Then it says *Starting to send. Nothing has been sent yet.*
Until the first copy goes out, **Cancel** turns the email back into a draft without losing
anything, and the three cards come back.

A scheduled email keeps its cards until it starts. Its banner shows *Scheduled for* its date
and time, with **Cancel the schedule**. You can still change its message, and **Check and
send** offers **Change the time** and **Send in 2 minutes instead**, which starts the
two-minute countdown. If you change its recipient list, the email goes back to your drafts,
since the count you confirmed has changed: *The recipients changed, so this email is back in
your drafts.*

Once sending starts, the banner shows its progress with a bar, such as *Sending… 12 of 38
sent, about 1 minute left.* CalDART sends a few copies a minute, which keeps the mail service
from turning them away, so a large email takes a while. **Stop sending**, then **Stop now**,
stops it after the copy going out at that moment. Copies already sent can't be called back.
When it finishes, the banner says how it went, such as *Sent to 51 people. Everyone was sent a
copy.*, beside **See who received it** (:doc:`sent`). A partly sent email can't be changed.


If something looks wrong
========================

If the recipient list has fewer people than you expected, look at the skipped people first,
then at the **Chosen by** column. A **County** or **Kind** you forgot to clear quietly narrows
what you add. If the email still says *Starting to send* a few minutes after the countdown
ended, the sender on the server may have stopped. A system administrator can start it by hand
from the Scheduled tasks page. If somebody says the email never arrived, find their row under
:doc:`sent`.
