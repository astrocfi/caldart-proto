==============
Aircraft check
==============

The **Aircraft check** tells you whether the insurance on an airplane is current, who flies
it, and how old the record is. Use it when the airplane in front of you is missing from the
pilot's profile: a club airplane, or one they have just started flying.

A DART leader and an account administrator find it under **Operations** in the menu, below
**Member check**. A system administrator can open it too.


Searching
=========

Type into **Search by N-number**. The register is searched as you type, and a registration,
a make, a model, or an owner's name all match, so a half-remembered tail number is enough.
The leading N is optional, and spaces, dashes, and capitals are ignored.

Each result is one line: the N-number, the make and model, and **GO** or **NO-GO** at the
far end for its insurance. **GO** means a current policy, including one about to expire.
You see at most eight results. There is no button to press. Tap a result to open its card.

An airplane taken out of service is left out of the results until you type its whole
registration. Then it appears, and its card is marked **Out of service**.

A search that finds nothing says *No aircraft matches that* and suggests trying the
registration, the make or model, or the owner's name.


Reading the card
================

**Back to search** returns you to the list. The card's address ends with the N-number, so it
survives a reload and you can send it to another leader.

The band across the top reads **INSURED** with *Coverage is current* or *Coverage expires
soon*, or **NOT INSURED** with *Coverage has expired* or *No policy on file*.

Under the band are the N-number, an **Out of service** chip when an administrator has taken
the airplane out of service, and the make, model, year, and seats. Then come four rows:

**Insurance**
   The insurance chip (**Insured**, **Expiring soon**, **Insurance expired**, or **No
   insurance on file**), the carrier, and the expiry date.

**Liability**
   The limits per occurrence and per person, and the hull value.

**Owner**
   The owner's name, whether they are an individual, an FBO, or a flying club, and how to
   reach them.

**Last updated**
   The date of the last change to the record and who made it, such as *2026/09/01 by Dana
   Fiske*. A record nobody has changed since it was loaded shows the date alone. It tells
   you how old the insurance details are: a policy that runs out next month on a record
   last changed two years ago is worth a phone call.

**Members who fly it** lists every member who has the airplane on their profile, each with
**Member current** or **Member expired** and **Medical current** or **Medical not
current**. With nobody listed the card says *No member lists this aircraft on their
profile.*

The policy number is kept on the record and left off this card. An account administrator
can read it in the aircraft register.


When the airplane is missing
============================

A link that names a registration the register has never seen shows a card saying the
airplane *is not in the register*, with *Nobody has added this aircraft yet. Ask the pilot
to add it to their profile, or add it from the aircraft register.* Press **Search again**
to go back. A pilot adds an airplane from **My aircraft** on their own portal, and an
account administrator can add it from the :doc:`aircraft-register`.


If something looks wrong
========================

If the insurance on the card looks out of date, the record has not been changed since the
date under **Last updated**; ask the pilot to correct it from **My aircraft**, or ask an
account administrator to correct it on the :doc:`aircraft-record`. If a search finds nothing
for an airplane you know is on file, type the registration in full: it may be out of
service, or it may be past the first eight results. If the card says *That check could not
be run*, the server could not answer; press **Search again** and try once more, and tell a
system administrator if it keeps happening.
