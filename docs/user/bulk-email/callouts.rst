:roles: management, dart_leader

========
Callouts
========

When CalDART activates for a mission, a mission callout asks who can fly. **Callouts**
collects the answers: who is available, who is available with limits, who is not, and who
has not answered yet. Open it from **Callouts** under **Bulk email** in the menu. CalDART
management sees every callout. A DART leader sees the callouts they sent and the ones sent
to the DART (a Disaster Airlift Response Team, one of CalDART's local groups) on their own
profile.


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

One line per callout, the most recently sent first, which the arrow on **Sent** shows:

- **Subject**: what it said. It opens the callout's own page, below.
- **Sent**: the day it went out.
- **Answers**: a dot and *Taking answers until* the date and time they close, or *Closed*
  and when.
- **From** and **DART**: who sent it, and the DART a DART leader's callout went to, or a
  dash for one that went to anybody.
- **Available**, **With limits**, **Not available**, and **No answer**: how many people gave
  each answer, and how many have not answered.

On a screen too narrow for every column, **DART**, then **From**, are left out; on a phone
the table scrolls sideways, says so above it, and keeps **Subject** pinned at the left. Before
the first callout the table reads *No callout has been sent*, with a **New email**
button that opens Compose, where **This is a mission callout** makes the email a callout.


One callout's page
==================

The page's first line says who sent it and when, and when the answers close, or when they
closed. Under it the answers are counted by kind, then come the actions, then one line for
every person the callout reached:

- **Name** and **Answer**: a dot and *Available*, *Available with limits*, *Not available*,
  or *No answer yet*.
- **Go/no-go**: *GO* or *NO-GO*, as the member check reads them now: a current membership,
  a current medical, and a verified certificate, medical, and photo ID.
- **Note**: what the person added, such as *can fly Saturday only*, in full.
- **Answered**: when they last answered, such as *10/03/2026 at 5:34 PM*.
- **DART**, **Home airport**, and **Aircraft**: from their profile as it is now. On a screen
  too narrow for every column these three are left out.

The **Answer** menu narrows the table to one answer, or to *No answer yet*, with **Any
answer** for everybody, and **Find a person** to a name or an address; the caption then says
how many of everybody it shows, such as *Showing 2 of 39*. **Reset filters** puts both back;
when nobody matches them, the empty table offers its own **Reset filters** button. **Download answers** saves every line as a spreadsheet
file. **See the email and who it went to** opens the email on :doc:`sent`, with what became
of every copy. The page keeps itself up to date every half minute while answers are coming
in.

**Remind non-responders** sends the callout again, with the same message, to everybody on
the page who has not answered, once you press **Send reminders**. Nobody who has answered
is sent it, and it starts within a minute: *The reminders will be sent within a minute.*
Each person's details in the reminder are filled in as they are then. Each time you remind
is a round of copies, listed under **Reminders** with its time and how many people it went
to. The counts on :doc:`sent` include every round, and its table lists each person's first
copy. When a round of reminders is stopped and then sent with **Send the rest**, or
retried with **Retry failed**, anybody who has answered meanwhile is skipped, *Answered
the callout*. The button stays off, with the reason under it, while the callout is still
sending, once it has closed, and once everybody has answered.

**Close now** stops the answers at once, after you press **Close the callout**. Nobody can
answer or change an answer after that, and the answers already given stay. Reminders not
sent yet are not sent. This cannot be undone. Once a callout has closed, nobody is sent a
copy of it, even when sending ran late, and the page says how many people were not sent
it.

A DART leader can open a callout another leader sent to their DART, remind, close, and
stop its reminders, and read its email on :doc:`sent`, where its other actions are left
out.

Each new or changed answer can also be emailed to you as it arrives: an account
administrator subscribes your address to the *Callout answer* notification on
:doc:`../admin/notifications`. Its subject reads *CalDART: Ann Able answered Available with
limits to a mission callout*, with the organization's name first.


If something looks wrong
========================

A person who never received the callout, because they were skipped or their copy failed,
is not listed and is not reminded; :doc:`sent` shows why. Nor is a person whose account has
since been deactivated: their link no longer works. A person who says the buttons did nothing
may have tried after the callout closed: the page they reach says so. A reminder skips the same
people a send would, such as somebody who has turned Mission email off. **Retry failed** on
:doc:`sent` sends a fresh copy to anybody whose reminder the mail server refused.
