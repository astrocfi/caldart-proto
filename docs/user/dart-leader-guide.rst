=================
DART leader guide
=================

Before a mission you need three answers about the person in front of you:
is their CalDART membership current, is their medical current, and is the
aircraft they are about to fly insured?  The **member check** answers all
three on one screen, and it is designed to be read on a phone while you are
standing on the ramp.

You need the ``dart_leader`` role.  Account administrators and system
administrators can use the same screens.

.. contents:: On this page
   :local:
   :depth: 1


The check, in ten seconds
=========================

#. Sign in and open **Member check** in the portal menu (``/portal/leader``).
#. Type a surname, an email address, or the N-number of the aircraft.
#. Tap the person in the results.
#. Read the band at the top of the card.

The band says **GO** or **NO-GO** in words, not only in colour, so it is
readable in bright sun and to anyone who does not see red and green apart.


Searching
=========

One box takes all three kinds of search:

============================  ==================================================
You type                      What you get
============================  ==================================================
``Reyes``                     Everyone whose first or last name contains "Reyes"
``Marta Reyes``               That person, whichever way round you type the name
``marta@``                    Everyone whose email address contains "marta@"
``N172SP``, ``n172sp``,       Every member who lists that aircraft on their
``n-172-sp``, ``172sp``       profile
============================  ==================================================

Registrations are normalised for you: the leading ``N`` is optional and
punctuation, spaces and case are ignored.  A search term with no digits in it
is never treated as a registration, so looking for "Nate" finds Nate rather
than every N-numbered aeroplane on file.

The search returns at most twenty people, each with their membership state, so
you can often tell who you want before opening the card.  If nobody comes back
for an N-number, the page offers to check the aircraft itself instead.


Reading the status card
=======================

**The band.**  A member is a **GO** when their membership *and* their medical
are current.  When either is not, the band reads **NO-GO** and names the
reasons — "Membership expired", "No medical on file" — so you know what to ask
them to fix.

.. note::

   The band is about the *person*.  Aircraft insurance is listed separately
   below it, because a member with a lapsed policy on one aeroplane may be
   perfectly current in another.  Read both before you launch.

**Membership** shows the state, the plan, and the expiry date.  A lifetime
member shows "Life · lifetime" and never expires.  A membership counts as
current up to and including its last day.

**Medical** shows BasicMed or the class of medical, its expiry, and whether it
is current today.  A medical expiring today still counts as current.  "No
medical on file" means the member has not entered one — it is not the same as
an expired medical, and the card says which it is.

**Certificate** is informational: the certificate type, its number, whether
the member is IFR rated, and any ratings they have listed.  It does not feed
the go/no-go verdict.

**Aircraft** lists every aeroplane on the member's profile with its own
insurance chip:

======================  =========================================================
Chip                    Meaning
======================  =========================================================
Insured                 A policy is on file and has not expired
Expiring soon           Insured, but the policy runs out within 30 days
Insurance expired       The policy's expiry date has passed
No insurance on file    Nobody has recorded a policy for this aeroplane
======================  =========================================================

The member's phone number and email address are links: tap to call or mail
them without leaving the card.


Checking an aircraft on its own
===============================

**Aircraft check** (``/portal/leader/aircraft``) takes a tail number and shows
one card: **INSURED** or **NOT INSURED**, the carrier and policy number, the
liability limits per occurrence and per person, the hull value, the expiry
date, the owner, and every member who lists that aeroplane on their profile
with their own membership and medical currency.

Use it when the aeroplane in front of you is not the one on the member's
profile — a club aeroplane, or one they have just started flying.  As on the
member search, you can type the registration however you like.

If the registration is not in the register at all, the card says so.  Ask the
pilot to add the aeroplane from **My aircraft** in their portal, or ask an
account administrator to add it to the register.


When something looks wrong
==========================

**"Membership expired" but the member says they paid.**  Ask them to open the
portal dashboard; a renewal is active from the moment it is paid.  If it still
reads expired, an account administrator can look at their payment history.

**"No medical on file" for a pilot who has one.**  The member enters their own
medical in **My profile**.  Nobody else can enter it for them except an
account administrator.

**An aircraft is missing from the card.**  Members attach the aeroplanes they
commonly fly themselves, in **My aircraft**.  Use the aircraft check for
anything not on their list.

**The insurance dates look stale.**  Insurance is maintained by account
administrators in the aircraft register, and by the member who first added the
aeroplane.  Point them at :doc:`aircraft`.
