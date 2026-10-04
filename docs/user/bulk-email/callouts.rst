:roles: management, dart_leader

========
Callouts
========

When CalDART activates for a mission, a callout asks who can fly. **Callouts** collects the
answers: who is available, who is available with limits, who is not, and who has not
answered yet. Open it from **Callouts** under **Bulk Email** in the menu. CalDART management
sees every callout. A DART leader sees the callouts they sent and the ones sent to the DART
on their own profile. A DART is one of CalDART's regional groups of pilots.


Sending a callout
=================

A callout is a bulk email. Write it on :doc:`compose` as any other, and switch on **This is
a mission callout** under **What it says**. The type becomes **Mission** when you may send
Mission email, and **Answers close** shows the date and the time the buttons stop working,
two days ahead. Change either if you need to. The callout cannot be sent if its answers
would close before it goes out.

Every copy carries three buttons above its footer: **Available**, **Available with
limits**, and **Not available**. Each person's buttons are their own, so nobody can answer
for anybody else. A test copy and the preview show the buttons, but they record nothing.
How the email looks to the people it goes to is on :doc:`../member/callouts`.


The list
========

One line per callout, the most recently sent first:

- **Subject**: what it said. It opens the callout's own page, below.
- **Sent**: the day it went out.
- **Answers**: a dot and *Taking answers*, or *Closed*.
- **From** and **DART**: who sent it, and the DART a DART leader's callout went to, or a
  dash for one that went to anybody.
- **Available**, **With limits**, **Not available**, and **No answer**: how many people gave
  each answer, and how many have not answered.

Before the first callout the table reads *No callout has been sent*.


One callout's page
==================

The page's first line says who sent it and when, and when the answers close, or when they
closed. Under it the answers are counted by kind, then come the actions, then one line for
every person the callout reached:

- **Name** and **Answer**: a dot and *Available*, *Available with limits*, *Not available*,
  or *No answer yet*.
- **Note**: what the person added, such as *can fly Saturday only*.
- **Answered**: when they last answered.
- **DART**, **Home airport**, and **Aircraft**: from their profile as it is now.
- **Go/no-go**: *GO* or *NO-GO*, as the member check reads them now: a current membership,
  a current medical, and a verified certificate, medical, and photo ID.

The **Answer** menu narrows the table to one answer, or to *No answer yet*, and **Find a
person** to a name or an address. **Download answers** saves every line as a spreadsheet
file. **See the email and who it went to** opens the email on :doc:`sent`, with what became
of every copy. The page keeps itself up to date every half minute while answers are coming
in.

**Remind non-responders** sends the callout again, with the same message, to everybody who
has not answered, once you press **Send reminders**. Nobody who has answered is sent it,
and it starts within a minute: *The reminders will be sent within a minute.* Each person's
details in the reminder are filled in as they are then. Each round of reminders is listed
under **Reminders** with its time and how many people it went to. The button stays off,
with the reason under it, while the callout is still sending, once it has closed, and once
everybody has answered.

**Close now** stops the answers at once, after you press **Close the callout**. Nobody can
answer or change an answer after that, and the answers already given stay. This cannot be
undone.

Each new or changed answer can also be emailed to you as it arrives: an account
administrator subscribes your address to the *Callout answer* notification on
:doc:`../admin/notifications`. Its subject reads *CalDART: Ann Able answered Available with
limits to a mission callout*, with the organization's name first.


If something looks wrong
========================

A person who never received the callout, because they were skipped or their copy failed,
is not listed; :doc:`sent` shows why. A person who says the buttons did nothing may have
tried after the callout closed: the page they reach says so. A reminder skips the same
people a send would, such as somebody who has turned Mission email off, and the delivery
report on :doc:`sent` gives each reason.
