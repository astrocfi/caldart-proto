=================
DART leader guide
=================

Before a mission you need three answers about the person in front of you:
is their CalDART membership current, is their medical current, and is the
aircraft they are about to fly insured?  The **member check** answers all
three on one screen, and it is designed to be read on a phone while you are
standing on the ramp.

You need the ``dart_leader`` or ``account_admin`` role; both get the
**Member check** and **Aircraft check** entries under *Operations* in the
portal menu, and **Members** under *Administration* for the member list
described below.  System administrators may open the same screens
(``/portal/leader``, ``/portal/leader/aircraft`` and ``/portal/admin/members``).


The check, in ten seconds
=========================

#. Sign in and open **Member check** in the portal menu (``/portal/leader``).
#. Type a surname, an email address, or the N-number of the aircraft.
#. Read **GO** or **NO-GO** on the person's line in the results.
#. Tap them for the detail: the medical, the certificate, and the insurance on
   the airplanes they fly.

The verdict says **GO** or **NO-GO** in words, not only in color, so it is
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

Registrations are normalized for you: the leading ``N`` is optional and
punctuation, spaces, and case are ignored.  A search term with no digits in it
is never treated as a registration, so looking for "Nate" finds Nate rather
than every N-numbered airplane on file.

The search returns at most twenty people, and every line already answers the
question: the name, with **GO** or **NO-GO** against it, and nothing else.  For
a single name that is the whole check; open the card when you want the
membership, the medical, the certificate, the ratings, or the insurance on the
airplanes.  If nobody comes back for an N-number, the page offers to check the
aircraft itself instead.


Reading the status card
=======================

**The band.**  A member is a **GO** when their membership *and* their medical
are current — the same rule the results list applies.  When either is not, the
band reads **NO-GO** and names the reasons — "Membership expired", "No medical
on file" — so you know what to ask them to fix.

.. note::

   The band is about the *person*.  Aircraft insurance is listed separately
   below it, because a member with a lapsed policy on one airplane may be
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

**Aircraft** lists every airplane on the member's profile with its own
insurance chip, or says "No aircraft on this member's profile." when there are
none:

======================  =========================================================
Chip                    Meaning
======================  =========================================================
Insured                 A policy is on file and has not expired
Expiring soon           Insured, but the policy runs out within 30 days
Insurance expired       The policy's expiry date has passed
No insurance on file    Nobody has recorded a policy for this airplane
======================  =========================================================

The member's phone number and email address are links: tap to call or mail
them without leaving the card.


Checking an aircraft on its own
===============================

**Aircraft check** (``/portal/leader/aircraft``) works the way the member check
does: one box, **Search by N-number**, that searches the aircraft register as
you type, with the results listed underneath it.  Each result is one line: the
N-number, the make and model, and **GO** or **NO-GO** at the far end for its
insurance — **GO** while a policy is current, including one about to expire.
There is no button to press; tap a result to open its card, and **Back to
search** returns to the list.

The card shows **INSURED** or **NOT INSURED**, the carrier, the liability
limits per occurrence and per person, the hull value, the expiry date, the
owner, when the record was last written and by whom, and every member who lists
that airplane on their profile with their own membership and medical currency.
The policy number is on the record but not on this card; an account
administrator can read it out of the register.  The address of the card ends in
``?aircraft=`` and the N-number, so it survives a reload and can be sent to
another leader.

**Last updated** is the date of the last write to the register record, with the
name of whoever made it — "2026/09/01 by Dana Fiske".  A record nobody has
touched since the demo data was loaded shows the date alone.  It tells you how
old the insurance on the card is: a policy that expires next month and a record
last written two years ago is worth a phone call.

Use it when the airplane in front of you is not the one on the member's
profile — a club airplane, or one they have just started flying.  As on the
member search, you can type the registration however you like, and a make, a
model, or an owner's name finds the airplane too, so a half-remembered tail
number is enough.

If nothing in the register matches, the list says so.  Ask the pilot to add
the airplane from **My aircraft** in their portal, or ask an account
administrator to add it to the register.  The same advice appears when a link
names a registration the register has never seen.


The member list
===============

**Members**, under *Administration* in the portal menu
(``/portal/admin/members``), lists every member of CalDART, not only your own
DART's, with whether they can fly today, their DART, when their membership
runs out, and their email address.  Use it to find people before a mission
rather than to check one person on the ramp.

* **Filter** with the bar above the table: by name or email, membership,
  certificate, medical, DART, county, role, how soon the membership expires,
  and active accounts only.  Each filter applies as soon as you change it; the
  text boxes follow a short pause in your typing.  **Clear** empties them all.
  The filters are part of the page's address, so a filtered list is a link you
  can bookmark or send to another leader.
* **Sort** by clicking a column heading; click again to reverse it.
* **Open** a name to see that member in the member check, with the GO / NO-GO
  card for them.
* **Download** the report with **Export CSV** or **Export PDF**.  Either file
  carries every member the filters match, not just the page on screen, and
  **Columns** chooses what goes in it — phone, certificate, medical, aircraft,
  county, and more.  The list on screen keeps its five columns whatever you
  choose.  **Save columns**, under the boxes, keeps the columns you ticked under
  a name, and **Load columns** ticks them again next time, as
  :ref:`member-report-columns` describes.

Adding a member, and the full member record behind each name, belong to the
account administrators; see :doc:`account-administrator-guide`.


When something looks wrong
==========================

**"Membership expired" but the member says they paid.**  Ask them to open the
portal dashboard; a renewal is active from the moment it is paid.  If it still
reads expired, an account administrator can look at their payment history.

**"No medical on file" for a pilot who has one.**  The member enters their own
medical in **My profile**.  Nobody else can enter it for them except an
account administrator.

**An aircraft is missing from the card.**  Members attach the airplanes they
commonly fly themselves, in **My aircraft**.  Use the aircraft check for
anything not on their list.

**The insurance dates look stale.**  Insurance is maintained by account
administrators in the aircraft register, and by the member who first added the
airplane.  Point them at :doc:`aircraft`.
