:roles: management, dart_leader

========
Callouts
========

When CalDART activates for a mission, a mission callout asks who can fly. **Callouts**
collects the answers: who is available, who is available with limits, who isn't, and who
hasn't answered yet. Open it from **Callouts** under **Bulk email** in the menu. CalDART
management sees every callout. A DART leader sees the callouts they sent, and the ones sent
to their own DART, the one on their profile. A DART is a Disaster Airlift Response Team, one
of CalDART's local groups.


Sending a callout
=================

A callout is a bulk email. Write it on :doc:`compose` like any other, and switch on **This is
a mission callout** under **What it says**. The type becomes **Mission**, the only type a
callout can go as, so somebody who may not send Mission email can't send a callout. **Answers
close** shows the date and the time the buttons stop working, two days ahead. Change either
if you need to. The callout can't be sent if its answers would close before it goes out.

Every copy asks *Can you participate? Choose your answer.* and has three buttons above its
footer: **Available**, **Available with limits**, and **Not available**. Each person's buttons
are their own, so nobody can answer for anybody else. A test copy and the preview show the
buttons, but they don't record anything. :doc:`../member/callouts` shows how the email looks
to the people it goes to.


The list
========

There is one line per callout, with the most recently sent first, as the arrow on **Sent**
shows:

- **Subject**: what it said, as you wrote it. A field such as **First name** shows as a chip,
  as on :doc:`compose`. The subject opens the callout's own page, below.
- **Sent**: the day it went out.
- **Answers**: a dot and *Taking answers until* the date and time they close, or *Closed*
  and when.
- **From** and **DART**: who sent it, and the DART a DART leader's callout went to, or a
  dash for one that went to anybody.
- **Yes**, **Limits**, **No**, and **No answer**: how many people answered *Available*,
  *Available with limits*, and *Not available*, and how many haven't answered.

On a narrow screen, **DART** and then **From** drop out, and then **Subject** narrows, so the
counts stay whole and in sight. On a phone, the table scrolls sideways, a note above it says
so, and **Subject** stays pinned at the left. Until the first callout, the table says *No
callout has been sent*, with a **New email** button. It opens Compose, where **This is a
mission callout** makes the email a callout. If a DART leader's profile doesn't name a DART, a
box above the table tells them to set their DART on My profile (:doc:`dart-leaders`). The
empty table under it then says only *No callout has been sent*, without a **New email**
button.


One callout's page
==================

The page's first line says who sent the callout and when, and when the answers close, or
closed. Under it come the counts of each answer, then the actions, then one line for every
person the callout reached:

- **Name** and **Answer**: a dot and *Available*, *Available with limits*, *Not available*,
  or *No answer yet*. For a DART leader or an account administrator, the name opens the
  person's record on :doc:`../admin/member-record`.
- **Go/no-go**: *GO* or *NO-GO*, as the member check shows them today. GO needs a current
  membership, a current medical, and a verified certificate, medical, and photo ID. For a DART
  leader, an account administrator, a user administrator, or a verifier, it opens the person's
  card on :doc:`../admin/member-check`, where each item is verified.
- **Note**: what the person added, such as *can fly Saturday only*, in full.
- **Answered**: when they last answered, such as *10/03/2026 at 5:34 PM*.
- **DART**, **Home airport**, and **Aircraft**: from their profile as it is today. A narrow
  screen leaves these three out.

The **Answer** menu narrows the table to one answer, or to *No answer yet*, or **Any answer**
for everybody. **Find a person** narrows it to a name or an address. The caption then says
how many people it shows out of everybody, such as *Showing 2 of 39*. **Reset filters** clears
both. When nobody matches them, the empty table offers its own **Reset filters** button.
**Download answers** saves every line as a spreadsheet file. **See the email and who it went
to** opens the email on :doc:`sent`, with what happened to every copy. While answers are
coming in, the page updates itself every half minute.

**Remind non-responders**, then **Send reminders**, sends the callout again, with the same
message, to everybody on the page who hasn't answered. Nobody who has answered is sent it.
It starts within a minute: *The reminders will be sent within a minute.* Each person's details
in the reminder are filled in as they are at that time. Each reminder is a round of copies,
listed under **Reminders** with its time and how many people it went to. The counts on
:doc:`sent` include every round, and its table lists each person's first copy. If you stop a
round of reminders and then send it with **Send the rest**, or retry it with **Retry failed**,
anybody who has answered in the meantime is skipped, *Answered the callout*. The button stays
off, with the reason under it, while the callout is still sending, once it has closed, and
once everybody has answered.

**Close now**, then **Close the callout**, stops the answers at once. After that, nobody can
answer or change an answer, and the answers already given stay. Reminders that haven't gone
out yet aren't sent. This can't be undone. Once a callout has closed, nobody is sent a copy of
it, even if sending ran late, and the page says how many people weren't sent it.

A DART leader can open a callout another leader sent to their DART. They can remind, close,
and stop its reminders, and read its email on :doc:`sent`, where its other actions are left
out.

You can also have each new or changed answer emailed to you as it arrives. An account
administrator subscribes your address to the *Callout answer* notification on
:doc:`../admin/notifications`. Its subject says *CalDART: Ann Able answered Available with
limits to a mission callout*, with the organization's name first.


If something looks wrong
========================

A person who never received the callout, because they were skipped or their copy failed,
isn't listed and isn't reminded. :doc:`sent` shows why. The same goes for a person whose
account has since been deactivated, and their link stops working. If a person says the
buttons didn't do anything, they may have tried after the callout closed, and the page they
reached says so. A reminder skips the same people a send would, such as somebody who has
turned Mission email off. **Retry failed** on :doc:`sent` sends a fresh copy to anybody whose
reminder the mail server refused.
