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

The people you add make up the batch: the list this email goes to. You build it a group at a
time, with the filters the member list uses:

- **Kind**: **Members only** or **Friends only**. A friend is somebody who supports CalDART
  without a paid membership.
- **Search**: a name or an email address.
- **Membership**, **Certificate**, **Medical**, **DART** (a Disaster Airlift Response Team,
  one of CalDART's local groups), **County**, and **Role**.
- **Expiring within (days)**: members whose membership ends within that many days.

Choose the filters, then press **Add to batch**. Everybody they choose joins the batch, and a
line says what happened, such as *Added 12 people; 3 were already in the batch.* Change the
filters and press **Add to batch** again as often as you like: nobody is added twice. With no
filters chosen, **Add to batch** adds every member and friend. Donors are never added.

Once somebody is in the batch, a line counts it, such as *38 people will receive this email;
4 are skipped.* Under it, **Download list** saves the batch as a spreadsheet file (CSV) with
each person's membership status, the filters that chose them, whether they will receive
the email, and its type. **Clear batch** takes everybody out after you press **Clear the batch**.

The table lists the batch in surname order, ten at a time until you press **Show all**. Each
row has the person's **Name**, **Email**, and **Will receive?**, which reads *Yes* or the
reason they are skipped; then **Kind**, **DART**, and **Chosen by** (the filters that brought
them in, such as *Kind: Members only*). On a narrow screen the table scrolls sideways. The
reasons are:

- *Account deactivated*: the account has been deactivated.
- *Account deleted*: the account no longer exists.
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

First choose the **Type of email**: one button for each kind you may send, such as
**Operational** or **Mission**, with a sentence saying what it is for. Until you choose,
the card reads *Choose what kind of email this is.* The choice saves at once. Everybody who
has turned that kind off is then skipped in the batch above. The kinds, and who may send
each, are kept on :doc:`email-types`.

Then write the **Subject**, one line, and the **Message**. Once you start typing, a quiet note
under the message reads *Saving…* and then *Saved*.

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
*{nickname}*, is refused with *{nickname} is not a recipient field.*, and the message is
not saved until it is fixed. A web address that needs braces of its own writes them as
*%7B* and *%7D*, as the message says. A field with bold or another style on only part of it
is refused too: delete it and put it in again with **Insert field**.

Each copy comes from the site's own address. Under the message it carries a short footer
with your organization's name and the contact address when one is set. For a kind people may
turn off, the footer says *You receive Mission email from CalDART because you have not turned
it off. To stop it, unsubscribe here:* with a link for that person, and their mail program
can offer its own **Unsubscribe** button. For a kind nobody may turn off, it says why they
receive it instead.


3. Check and send
=================

At the top of the card is a preview: the email as the first person in the batch will
receive it, their own details filled in. *Previewing as Ann Able (1 of 38)* says whose copy
it is; **Next person** and **Previous person** step through everybody who receives it. The
preview shows what has been saved, so it catches up a moment after you stop typing. While
nobody in the batch receives the email, the preview is your own copy. When a field in the
message cannot be filled in, the preview says why instead.

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
number of people who will receive it.* Press **Send now** or **Schedule it** to go ahead, or
**Go back**; the Escape key goes back too. If the batch changed meanwhile, the send is refused
with the new number, such as *The batch has changed: it now holds 39 people. Type the new
count.*


Once it is sent
===============

Where the email stands then shows in a banner at the top of the screen.

After **Send now** you have two minutes to change your mind. The banner reads *Sending in 1
min 58 s* with a bar counting down, and a **Cancel** button. Once the countdown ends it reads
*Starting to send. Nothing has been sent yet. You can still cancel until the first copy goes
out.* **Cancel** turns the email back into a draft with nothing lost.

A scheduled email shows *Scheduled for* its date and time with **Cancel the schedule**. Until
it starts you can still change its message, and the **Check and send** card offers **Change
the time**, which opens at the time already chosen, and **Send now instead**. A change to the
batch of a scheduled email takes it back to your drafts, because the number of people you
confirmed has changed, and the screen says *The recipients changed, so this email is back in
your drafts. Press Send or Schedule again when it is ready.*

Once sending starts, the screen holds still and the banner reads, for example, *Sending… 12
of 38 sent, about 1 minute left.* with a bar. CalDART sends a few copies a minute so the mail
provider never turns them away, so a large email takes a while. **Stop sending** stops it
after the copy going out now, once you press **Stop now**: copies already sent cannot be
called back. When it finishes, the banner says how it went, such as *Sent to 51 people.
Everyone was sent a copy.*, beside **See who received it**, which opens the email's page under
:doc:`sent`. An email that was partly sent can never be changed again, even after **Send the
rest**.


If something looks wrong
========================

If the batch holds fewer people than you expected, look at the skips first, then at the
**Chosen by** column: a forgotten **County** or **Kind** narrows an add quietly. If the email
still says *Starting to send* a few minutes after the countdown ended, the server's sender may
have stopped; a system administrator can start it by hand from the Scheduled page. If somebody
says the email never arrived, find their row under :doc:`sent`.
