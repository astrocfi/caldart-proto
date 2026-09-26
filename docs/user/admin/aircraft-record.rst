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

The N-number heads the page, with the make and model under it and the insurance chip
(**Insured**, **Expiring soon**, **Insurance expired**, or **No insurance on file**) at the
right, beside **Out of service** when the airplane is out of service.

**Details** is the form, headed by a line such as *Last updated 2026/09/01 by Dana Fiske*:
the date of the last change and the account behind it. A record nobody has changed since it
was loaded gives the date alone. The form has four parts.

**Aircraft**
   **N-number**, **Year**, **Make**, **Model**, and **Seats**. The N-number is a US
   registration: the box writes the N, then takes digits first and at most two letters,
   never I or O. The model box suggests types as you type (*Start typing: Mal, 172, RV-7*),
   and picking one fills in the make.

**Owner**
   **Owner type** (Individual, FBO, or Flying club), **Owner name**, and **Owner contact**,
   an email address or a phone number.

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

Press **Save changes**. The message reads that the airplane was *saved*.


History
=======

**History** lists every change to the record, newest first, one line each: the date and
time, the account that made it, and what it did, such as *2026/09/01 12:00 · Dana Fiske ·
updated carrier, insurance expiry*, or *created* for the change that added the airplane. A
change with no account behind it, such as the demo data, reads *the seed*. The words match
the form, so *insurance expiry* is the **Insurance expires** box.

A record with no recorded change says *No change is recorded for this record.* The next save
starts the list. If the history cannot be fetched, the card says *That record's history
could not be loaded.*


Pilots who fly this aircraft
============================

This card lists every member who has attached the airplane to their profile, with their
email address, **Member current** or **Member expired**, and **Medical current** or
**Medical not current**: the same facts a DART leader sees. A name opens that person's
:doc:`member-record`. With nobody attached it reads *No member lists this aircraft on their
profile.*


Deleting the record
===================

**Delete this aircraft**, at the foot of the page, asks once: *Delete* the N-number
*permanently? It will disappear from every member's profile.* Press **Yes, delete it** to go
ahead, or **Keep it**. The record is removed from the register and from every profile that
had it.

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
registration; open it from the register and delete whichever record is the duplicate.
*Enter an amount of $0 or more.* means a money box holds a negative number or something that
is not a number; type dollars, and a leading $ and commas are fine. *Use a US registration
like N172SP: N, then digits, then at most two letters.* means the N-number does not follow
the US pattern. **No insurance on file** means the record has no expiry date, which is
different from an expired policy; enter the carrier, the limits, and the expiry before a
DART leader relies on the airplane. *No such aircraft* means the record has been deleted;
use **Back to the register**.
