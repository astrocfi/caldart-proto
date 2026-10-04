:roles: management, dart_leader

=======
Compose
=======

**Compose** is where you write one email to many members and friends of CalDART at once: a
newsletter, a seminar notice, or a call for volunteers. Each person gets a copy of their own.
CalDART management opens it as **Compose** under **Bulk Email** in the menu, and so does a
DART leader, who writes to their own DART (:doc:`dart-leaders`). A system administrator can
open it too.

Pressing **Compose** opens a fresh email, or the empty one you started earlier. The screen
reads top to bottom as three numbered cards. There is no Save button: everything you do is
kept as you go, so you can leave and come back from :doc:`drafts`. A draft made with
**Duplicate** (:doc:`sent`) says at the top *This is a copy of* and the email's subject.


1. Who gets it
==============

The people you add make up the batch: the list this email goes to. You build it a group at a
time, with the filters the member list uses:

- **Kind**: **Members only** or **Friends only**. A friend is somebody who supports CalDART
  without a paid membership.
- **Search**: a name or an email address.
- **Membership**, **Certificate**, **Medical**, **DART** (a Disaster Airlift Response Team,
  one of CalDART's local groups), **County**, and **Role**.
- **Expiring within (days)**: members whose membership ends within that many days.

Choose the filters, then press **Add to batch**. Everybody they choose joins the batch, and a
line, which takes the keyboard focus, says what happened, such as *Added 12 people; 3 were
already in the batch.* or *Nobody matches these filters.* Add again as often as you like:
nobody is added twice. With no filters chosen, it adds every member and friend. Donors are
never added.

**Add a saved group**, beside **Add to batch**, adds everybody in a group kept on
:doc:`groups` the same way: nobody is added twice.

Once somebody is in the batch, a line counts it, such as *38 people will receive this email;
4 are skipped.*, or *39 people will receive this email.* when nobody is skipped. Under it, in
one row, **Download list** saves the batch as a spreadsheet file (CSV) with
each person's membership status, the filters that chose them, whether they will receive
the email, and its type. **Save as a group** keeps the batch as a group to add to another
email later (:doc:`groups` explains the two kinds). **Clear batch** takes everybody out after
you press **Clear the batch**.

The table lists the batch in surname order, ten at a time until you press **Show all**. Each
row has the person's **Name**, **Email**, and **Will receive?**, which reads *Yes* or the
reason they are skipped; then **Kind**, **DART**, and **Chosen by** (the filters that brought
them in, *Group: Board* for a saved group, or *Copied from* and a subject); and the trashcan.
A narrow screen leaves out **DART** and **Chosen by**. The reasons are:

- *Account deactivated*: the account has been deactivated.
- *Account deleted*: the account no longer exists.
- *Not in your DART*: on a DART leader's email, the person's profile names another DART, or
  none (:doc:`dart-leaders`).
- *No email address* or *Invalid email address*: there is nowhere to send it.
- *Address bounced*: an earlier email to this address came back undelivered. Once the
  address is corrected, or a user administrator presses **Clear bounce** on the account, the
  person receives copies again.
- *Opted out of Mission* (with the email's type): the person has turned that kind of email
  off on their :doc:`../member/email-preferences` or with an unsubscribe link. Nobody is
  skipped for this until you choose the type.
- *Duplicate address*: somebody earlier in the batch has the same address, so it gets one
  copy.

Whether each person receives the email is worked out again whenever you open the screen, and
once more when the email starts sending. In a batch of more than ten people, type in **Find in
the batch** to find one person. The trashcan on a row takes that person out after you press
**Remove**.


2. What it says
===============

CalDART management can start from a message kept on :doc:`templates` with **Start from a
template**, which asks before it replaces words already written, and keep this message as one
with **Save as a template**; that page explains both.

To ask who can fly for a mission, switch on **This is a mission callout** and set **Answers
close**; :doc:`callouts` explains the answer buttons and where the answers collect.

First choose the **Type of email**: one button for each kind you may send, such as
**Operational** or **Mission**, with a sentence saying what it is for. Until you choose,
the card reads *Choose what kind of email this is.* The choice saves at once. Everybody who
has turned that kind off is then skipped in the batch above. The kinds, and who may send
each, are kept on :doc:`email-types`.

Then write the **Subject**, one line, and the **Message**. Once you start typing, a quiet note
under the message reads *Saving…* and then *Saved*.

**Reply-To** is where a reader's reply goes. Every copy comes from the site's own address,
which nobody reads, so without it a reply would reach nobody. It starts filled in with the
address your organization chose for replies, or with your own address. Change it to any
address that should get the replies, such as a DART leader's or a shared operations
mailbox; empty it to go back to the starting address, which the hint under it names. The
address saves when you leave the field or press Enter, and *Reply-To saved.* says so. An
address that is not one, such as *ops@*, reads *Enter a valid email address.* and the
address saved before stays until you fix it; the subject and the message keep saving
meanwhile.

The buttons over the message format it: **Bold** and **Italic** for the words you have
selected, **Heading** for a line that heads a section, and **Bulleted list** and **Numbered
list**. A button stays pressed while the words at the cursor have its style; press it again
to take the style off.

- **Link** asks for the **Web or email address** the selected words go to, such as
  *caldart.org/events* or an email address, then **Add link**. With nothing selected, the
  address itself is put in as the link. On a link, the button offers **Save link** and
  **Remove link**.
- **Image** opens your computer's file picker. Choose a PNG, JPEG, GIF, or WebP picture of
  at most 5 MB. While it uploads the box reads *Uploading* and the file's name; then
  **Describe the image** in a few words, such as *Volunteers loading a Cessna*, and press
  **Put image in**. The description is required: many mail programs hide pictures until the
  reader allows them, and the description is what they see instead. A large picture is made
  smaller to suit an email, and any location the camera recorded in it is removed.
- **Insert field** lists details each person's copy fills in for them: **First name**,
  **Last name**, **Full name**, **Email address**, **DART**, **Membership plan**,
  **Membership status**, **Expiration date**, and **Home airport**. Choose one and it goes in
  where the cursor was last, in the subject or the message, written in braces, such as
  *{first_name}*. Somebody with no value for a field gets nothing there; to put in a word
  instead, add it after a bar, as in *{first_name|friend}*, which reads *friend* for a person
  with no first name.

A field can only be one of those in the list. Anything else written in braces, such as
*{nickname}*, is refused with *{nickname} is not one of the fields. Pick a field from Insert
field, or take out the braces.*, and the words are not saved until it is fixed. A link's web
address that needs braces of its own writes them as *%7B* and *%7D*, as the message says
when the braces are in one. A field with bold or another style on only part of it
is refused too: delete it and put it in again with **Insert field**.

Each copy comes from the site's own address, with replies going to the **Reply-To**
address. Under the message it carries a short footer
with your organization's name and the contact address when one is set. For a kind people may
turn off, the footer says *You receive Mission email from CalDART because you have not turned
it off. To stop it, unsubscribe here:* with a link for that person, and their mail program
can offer its own **Unsubscribe** button. For a kind nobody may turn off, it says why they
receive it instead.

**Send me a test**, at the bottom of the card, sends the email to you alone, so you can see it
in your own mail program as the people in the batch will: the same layout, pictures, links,
footer, and Reply-To, with your own details in its fields. Its subject starts *[Test]*. What
you have typed is saved first. Each press sends one more test and says where it went, such as
*A test went to pat@example.org.*, which takes the keyboard focus. A test is not counted and
is listed in the log of sent emails as *Bulk email test*. An email with a problem marked
**Must fix** (see below) is not sent as a test; the problems are listed instead.


3. Check and send
=================

At the top of the card are the **Checks**: mistakes the site looks for in the saved email,
each on a line of its own with a dot. They run when the card opens, again when you press
**Check again**, and again when you press **Send** or **Schedule for later**. While they run
the card reads *Checking the email for mistakes, such as links that do not work…*, which can
take a few seconds. *No problems found.* means there is nothing to say, or *Nothing else to
fix.* while a step such as the subject is still missing.

Words that could not be saved come first, marked **Must fix**, such as *Your subject has a
mistake:* and the reason, with **Fix it under 2. What it says.**, which puts the cursor there.
**Send** and **Schedule for later** stay off until the words are saved.

A red dot and **Must fix:** mark a problem the email cannot go with, such as a **Reply-To**
that is not an email address, or a field that cannot be filled in. **Send** stays off until it
is fixed and you press **Check again**. An amber dot and **Worth a look:** mark something
that may be a mistake, and *You can still send.* says you may go ahead anyway:

- *{dart_name} is empty for 41 of 120 people who receive this email, so their copies show
  nothing there.* Most people have no value for that field: add words to show instead, as
  in *{dart_name|your DART}*, or take it out.
- *The email still says "TODO".* Placeholder text, such as *TODO*, *XXX*, *lorem ipsum*, or
  *[insert*, is still in the subject or the message.
- *1 picture has no description for people who cannot see pictures.* Delete it and put it
  in again with **Image**, which asks for one.
- *1 picture is wider than 1200 pixels, too wide for many mail programs.*
- *This link does not load*, sometimes with the kind of error the site answered, or *This
  link timed out*: the page may be gone or the address mistyped. Open it yourself to be
  sure.
- *This link does not use https, so it is not secure.*
- *Links into a private network are not checked.* The link points inside a private
  network or at the site's own server, which it does not try, for safety.
- *Links to a port other than 80 or 443 are not checked.* The address names an unusual
  port, such as *:8080*; open it yourself to be sure.
- *This link was not checked in time.* The checks stop after about half a minute.

Links to this site's own pages, links holding a field, and email address links are not
tried. If the checks cannot run at all, or take more than a few seconds when you press
**Send**, the card says *The checks could not run. You can still send.* and lets you go
on: an email with a problem marked **Must fix** is still refused when you send it.

Below the checks is a preview: the email as the first person in the batch will
receive it, their own details filled in, once the message is written. *Previewing as Ann
Able (1 of 38)* says whose copy it is; **Next person** and **Previous person** step through
everybody who receives it. The preview shows what has been saved, and says so while your
latest words cannot be saved. While
nobody in the batch receives the email, the preview is your own copy. The footer reads as
it will in the email, but its unsubscribe link in the preview leads nowhere, so nobody is
unsubscribed by a click there. When a field in the message cannot be filled in, the
preview says why instead.

Until the email can go, the card lists what is missing, such as *Choose a type.*, *Write a
subject.*, or *Add people to the batch.* Then it offers two buttons:

- **Send to 38 people** (with the number who will receive it) sends it now.
- **Schedule for later** asks for a **Date** and a **Time**, in Pacific time, such as *8:00
  AM*, then **Continue**. The time must be in the future and within a year.

Either one asks first: *This sends* the subject *to 38 people.*, followed by when it goes,
such as *Sending starts in 2 minutes, and until then you can cancel it.* or *It goes out on
10/04/2026 at 8:00 AM Pacific time.* When the email goes to more than 50 people, the
confirmation also asks you to **Type 38 to confirm**, and the button that sends stays off
until the number matches. A different number reads *That number does not match. Type 38, the
number of people who will receive it.* The focus starts on **Go back**, so Enter pressed
twice never sends. Press **Send now** or **Schedule it**, or **Go back** (or Escape). A batch
that changed meanwhile is refused with its new number, such as *The batch has changed: it
now holds 39 people. Type the new count.*


Once it is sent
===============

Where the email stands then shows in a banner at the top of the screen.

After **Send now** you have two minutes to change your mind. The banner reads *Sending in 1
min 58 s* with a bar counting down and **Cancel**, in place of **Check and send**; then
*Starting to send. Nothing has been sent yet.* **Cancel** turns the email back into a draft
with nothing lost until the first copy goes out.

A scheduled email shows *Scheduled for* its date and time with **Cancel the schedule**. Until
it starts you can still change its message, and **Check and send** offers **Change the
time** and **Send in 2 minutes instead**, which starts the two-minute countdown. A change to
its batch takes it back to your drafts, since the count you confirmed changed: *The
recipients changed, so this email is back in your drafts.*

Once sending starts, the screen holds still and the banner reads, for example, *Sending… 12
of 38 sent, about 1 minute left.* with a bar. CalDART sends a few copies a minute so the mail
provider never turns them away, so a large email takes a while. **Stop sending** stops it
after the copy going out now, once you press **Stop now**: copies already sent cannot be
called back. When it finishes, the banner says how it went, such as *Sent to 51 people.
Everyone was sent a copy.*, beside **See who received it** (:doc:`sent`). A partly sent email
can never be changed again.


If something looks wrong
========================

If the batch holds fewer people than you expected, look at the skips first, then at the
**Chosen by** column: a forgotten **County** or **Kind** narrows an add quietly. If the email
still says *Starting to send* a few minutes after the countdown ended, the server's sender may
have stopped; a system administrator can start it by hand from the Scheduled page. If somebody
says the email never arrived, find their row under :doc:`sent`.
