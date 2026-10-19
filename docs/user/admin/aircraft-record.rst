:roles: account_admin

===============
Aircraft record
===============

The **aircraft record** holds everything the register knows about one airplane: its
details, its owner, its insurance, every change made to it, and the members who fly it.
Only an account administrator can open it, by clicking an N-number on the
:doc:`aircraft`, on a member record, or in a list of pilots. A system
administrator can open it too.


What you see
============

The N-number heads the page, with the make and model under it. At the right are the
insurance status and, if the airplane is out of service, **Out of service**. The insurance
status is **Insured**, **Expiring soon**, **Insurance expired**, or **No insurance on
file**. A current policy that hasn't been verified shows **Not verified** in amber, as on
the :doc:`aircraft-check`.

Below that is a **Verification** card, the same as on a :doc:`member-record`. It lists
**Insurance**, with what the record holds, such as *Avemco · AV-00012345 · Liability
$1,000,000 per occurrence, $100,000 per person · expires 03/01/2027*, or *No insurance on
file*. Beside it is its mark: **Verified**, with who verified it and on which day, or **Not
verified** in amber. A policy past its date shows **Expired** before its mark. If the
insurance doesn't have an expiry date on file, there isn't anything to verify, so it
doesn't show a mark. **Verify** opens the same verification panel as the
:doc:`aircraft-check`: correct the policy against its documents, check **Insurance
verified**, and press **Save verification**. *Verification saved* confirms it. The card
comes back with you on its **Verify** button, and the form below reloads from the saved
record. **Cancel**, or Escape, closes the panel without changing anything.

**Details** is the form. A line at its head, such as *Last updated 09/01/2026 by Dana
Fiske*, gives the date of the last change and the account that made it. If the **History**
is empty, the line doesn't appear. The form has four parts.

**Aircraft**
   **N-number**, **Year**, **Aircraft type**, **Seats**, **Category**, and
   **Airworthiness**. The N-number is a US registration. The box writes the N for you, then
   takes digits first and at most two letters, never I or O. As you type, the box lists up
   to eight airplanes from the FAA data whose N-number starts with what you typed. Each
   shows its N-number, aircraft type, year, and registrant. Click one, or reach it with the
   arrow keys and press Enter. Escape closes the list. Picking one writes its N-number into
   the box and fills in the type, year, seats, category, and airworthiness. It also fills in
   **Owner name** from the registration and guesses **Owner type** from the kind of
   registrant: a person or co-owners become Individual, a partnership becomes Flying club,
   and a company becomes FBO. For a government registrant, or any other kind, Owner type
   stays as it was. The line under the box then says *From FAA data as of* and the date of
   CalDART's copy, until you change the N-number. If the registry doesn't have the airplane,
   it isn't listed; type its whole N-number.

   You pick the aircraft type from a list. Type the make, the model, or a designator
   (cessna 172, c172, skyhawk) in **Aircraft type** and pick the entry, which shows its
   seats. The make and model come from the type. If **Seats** is empty, picking a type fills
   in its seats and, when the registry knows it, the **Category**. To add a type that isn't
   on the list, use **New aircraft type**, as the :doc:`aircraft` describes. You can leave
   **Category** (Airplane, Helicopter, Gyroplane, Glider, Balloon, Airship, Powered lift,
   Weight-shift control, Powered parachute, or Other) and **Airworthiness** (Standard,
   Limited, Restricted, Experimental, Provisional, Multiple, Primary, Special flight permit,
   or Light sport) at **Not recorded**. The :ref:`coverage-policy` judges the airplane by
   these two.

**Owner**
   **Owner type** (Individual, FBO, or Flying club), **Owner name**, and **Owner contact**,
   an email address or a phone number. A name filled in from the FAA registry comes in
   title case, so *SKYWAYS AVIATION LLC* becomes **Skyways Aviation LLC**. Correct it if the
   business spells its name differently. A business name you type is kept exactly as you
   typed it.

**Insurance**
   **Carrier**, **Policy number**, **Liability per occurrence**, **Liability per person**,
   **Hull**, and **Insurance expires**. Amounts are in US dollars, and the commas appear
   when you leave the box, so 1000000 becomes 1,000,000. None of the amounts can be
   negative.

**Administration**
   **Notes**, and **In service**. Clearing **In service** marks the airplane **Out of
   service** in the register, on this record, and on a DART leader's aircraft check. It
   also stops offering the airplane to members who search for one to add to their profile.
   A member who types its whole registration still finds it, marked, so nobody adds a second
   record for the same airplane.

Press **Save changes**. The toast gives the N-number and *saved*. Saving a change to any
insurance field clears the insurance's verification.


History
=======

**History** lists every change to the record, newest first, one line each: the date and
time, the account that made it, and what it did. For example, *09/01/2026 at 12:00 PM ·
Dana Fiske · updated carrier, insurance expiry*, or *created* for the change that added the
airplane. A change without an account behind it, such as the demo data, shows *the seed*.
The words match the form, so *insurance expiry* is the **Insurance expires** box.

If the record doesn't have any recorded changes, the card says *No changes recorded
yet.* The next save starts the list. If the history can't be fetched, the card says
*That record's history didn't load. Try again in a moment.*


Pilots who fly it
=================

This card lists every member who has added the airplane to their profile, one to a line,
with each part in its own column: their name, their email address, **Member current**,
**Member expired**, or **Friend**, and **GO** or **NO-GO**. The verdict is the
:doc:`member-check`'s own verdict for that person, so the record and the checks always
agree. A name opens that person's :doc:`member-record`. When nobody has added the airplane,
the card says *No member lists this aircraft on their profile.*


Deleting the record
===================

**Delete this aircraft**, at the bottom of the page, asks once: *Delete* the N-number
*permanently? It will disappear from every member's profile.*, above a red **Delete** and
**Cancel**. Press **Delete** to go ahead, or **Cancel**, Escape, or a click elsewhere to keep
the record. The record is removed from the register and from every profile that had it.

If the airplane may come back, clear **In service** instead. The history stays, and a leader
who checks the tail number can still see what was on file.


Who else can change a record
============================

Any signed-in member can add an airplane from **My aircraft**, and the member who added one
can correct it there. Only an account administrator can delete an airplane, because other
members may fly it. Every insurance date a DART leader sees comes from this record.


If something looks wrong
========================

*An aircraft with this N-number is already on file.* means another record already has that
registration. Open it from the register and delete whichever record is the duplicate. *Pick
the aircraft type from the list.* means you typed in the **Aircraft type** box but didn't
pick an entry from the list. *Enter an amount of $0 or more.* means a money box holds a
negative number or something that isn't a number. Type dollars; a leading $ and commas are
fine. *Use a US registration like N172SP: N, then digits, then at most two letters.* means
the N-number doesn't follow the US pattern. **No insurance on file** means the record
doesn't have an expiry date, which isn't the same as an expired policy. Enter the carrier,
the limits, and the expiry before a DART leader relies on the airplane. *No such aircraft*
means the record has been deleted; use **Back to the register**.
