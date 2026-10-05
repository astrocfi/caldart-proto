:roles: account_admin

===============
Aircraft record
===============

The **aircraft record** holds everything the register knows about one airplane: its
details, its owner, its insurance, every change made to it, and the members who fly it.
Only an account administrator can open it, by clicking an N-number on the
:doc:`aircraft-register`, on a member record, or in a list of pilots. A system
administrator can open it too.


What you see
============

The N-number heads the page, with the make and model under it and the insurance status
(**Insured**, **Expiring soon**, **Insurance expired**, or **No insurance on file**, and
**Not verified**, amber, for a current policy nobody has checked yet, as the
:doc:`aircraft-check` reads it) and **Out of service** (when the airplane is out of
service) at the right.

A **Verification** card heads the page below that, the same as on a :doc:`member-record`.
It lists **Insurance**, with what the record holds (such as *Avemco · AV-00012345 ·
$1,000,000 / $100,000 · expires 03/01/2027*, or *Not on file* with nothing recorded) and its
mark: **Verified** with who verified it and on which day, or **Not verified** in amber. A
policy whose date has passed reads **Expired** before its mark, and insurance with no expiry
date on file has nothing to verify and no mark. **Verify**
opens the same verification panel as the :doc:`aircraft-check`: correct the policy against
its documents, check **Insurance verified**, and press **Save verification**. *Verification saved*
confirms it, the card returns with you on its **Verify**, and the form below starts again
from the saved record. **Cancel**, or Escape, closes the panel and changes nothing.

**Details** is the form, headed by a line such as *Last updated 09/01/2026 by Dana Fiske*:
the date of the last change and the account behind it. A record whose **History** records no
change has no such line. The form has four parts.

**Aircraft**
   **N-number**, **Year**, **Aircraft type**, **Seats**, **Category**, and
   **Airworthiness**. The N-number is a US
   registration: the box writes the N, then takes digits first and at most two letters,
   never I or O. As you type, up to eight airplanes from the FAA data whose N-number
   starts with what you typed are listed under the box, each with its N-number, aircraft
   type, year, and registrant; click one, or reach it with the arrow keys and press Enter,
   and Escape closes the list. Picking one writes its N-number into the box and fills the
   type, year, seats, category, and airworthiness; it fills **Owner name** from the registration and guesses **Owner
   type** from the kind of registrant it is (a person or co-owners become Individual, a
   partnership becomes Flying club, a company becomes FBO; a government registrant, or one
   that fits none of those, leaves Owner type as it was). The line under the box then reads
   *From FAA data as of* the day of CalDART's copy, until the N-number changes. An
   airplane the registry lacks is simply not listed; type its whole N-number. The aircraft type is picked from a list: type the make, the
   model, or a designator (cessna 172, c172, skyhawk) in **Aircraft type** and pick the
   entry, which shows its seats. The make and model come from the type, and picking one
   with **Seats** empty fills in its seats and, when the registry knows it, the
   **Category**. A type the list lacks can be added with **New aircraft type**, as the
   :doc:`aircraft-register` describes. **Category** (Airplane, Helicopter, Gyroplane,
   Glider, Balloon, Airship, Powered lift, Weight-shift control, Powered parachute, or
   Other) and **Airworthiness** (Standard, Limited, Restricted, Experimental, Provisional,
   Multiple, Primary, Special flight permit, or Light sport) may stay **Not recorded**;
   the :ref:`coverage-policy` is judged against them.

**Owner**
   **Owner type** (Individual, FBO, or Flying club), **Owner name**, and **Owner contact**,
   an email address or a phone number. A name filled from the FAA registry arrives in
   title case, *SKYWAYS AVIATION LLC* as **Skyways Aviation LLC**; correct it if the
   business spells itself otherwise. A business name you type is kept exactly as typed.

**Insurance**
   **Carrier**, **Policy number**, **Liability per occurrence**, **Liability per person**,
   **Hull**, and **Insurance expires**. Amounts are in US dollars, and the commas write
   themselves when you leave the box, so 1000000 becomes 1,000,000. Nothing may be
   negative.

**Administration**
   **Notes**, and **In service**. Clearing **In service** marks the airplane **Out of
   service** in the register, on this record, and on a DART leader's aircraft check, and
   stops offering it to members searching for an airplane to add to their profile. A member
   who types its whole registration still finds it, marked, so nobody adds a second record
   for the same airplane.

Press **Save changes**. The message reads that the airplane was *saved*. Saving a change to
any insurance field clears the insurance's verification.


History
=======

**History** lists every change to the record, newest first, one line each: the date and
time, the account that made it, and what it did, such as *09/01/2026 at 12:00 PM · Dana
Fiske · updated carrier, insurance expiry*, or *created* for the change that added the airplane. A
change with no account behind it, such as the demo data, reads *the seed*. The words match
the form, so *insurance expiry* is the **Insurance expires** box.

A record with no recorded change says *No change is recorded for this record.* The next save
starts the list. If the history cannot be fetched, the card says *That record's history
didn't load. Try again in a moment.*


Pilots who fly it
=================

This card lists every member who has attached the airplane to their profile, one a line
with each part in a column of its own: their name, their email address, **Member current**, **Member expired**, or **Friend**, and **GO** or
**NO-GO**, the :doc:`member-check`'s own verdict for that person, so the record and the
checks never disagree. A name opens that person's
:doc:`member-record`. With nobody attached it reads *No member lists this aircraft on their
profile.*


Deleting the record
===================

**Delete this aircraft**, at the bottom of the page, asks once: *Delete* the N-number
*permanently? It will disappear from every member's profile.*, above a red **Delete** and
**Cancel**. Press **Delete** to go ahead, or **Cancel**, Escape, or a click elsewhere to keep
the record. The record is removed from the register and from every profile that had it.

If the airplane may come back, clear **In service** instead. The history stays, and a leader
checking the tail number can still see what was on file.


Who else can change a record
============================

Any signed-in member can add an airplane from **My aircraft**, and the member who added one
can correct it there. Only an account administrator can delete an airplane, because other
members may fly it. Every insurance date a DART leader reads comes from this record.


If something looks wrong
========================

*An aircraft with this N-number is already on file.* means another record already holds that
registration; open it from the register and delete whichever record is the duplicate. *Pick
the aircraft type from the list.* means the **Aircraft type** box holds typing that was never
picked from the list. *Enter an amount of $0 or more.* means a money box holds a negative
number or something that is not a number; type dollars, and a leading $ and commas are fine.
*Use a US registration like N172SP: N, then digits, then at most two letters.* means the
N-number does not follow the US pattern. **No insurance on file** means the record has no
expiry date, which is different from an expired policy; enter the carrier, the limits, and
the expiry before a DART leader relies on the airplane. *No such aircraft* means the record
has been deleted; use **Back to the register**.
