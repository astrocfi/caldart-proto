:roles: dart_leader, account_admin, user_admin, verifier

==============
Aircraft check
==============

The **Aircraft check** tells you whether CalDART's insurance covers an airplane at all,
whether its insurance is current and verified, who flies it, and how old the record is. Use it when the airplane in front of you
is missing from the pilot's profile: a club airplane, or one they have just started flying.
It is also where an airplane's insurance is verified against the policy documents.

A verifier, a DART leader, a user administrator, and an account administrator find it under
**Operations** in the menu, below **Member check**. A system administrator can open it too.


Searching
=========

Type into **N-number, make, model, or owner**. The register is searched as you type, and a
registration, a make, a model, or an owner's name all match, so a half-remembered tail
number is enough.
The leading N is optional, and spaces, dashes, and capitals are ignored.

Each result is one line: the N-number, the make and model, and **GO** or **NO-GO** at the
far end. **GO** means an airplane the coverage policy covers, with a current, verified
policy, including one about to expire. A screen reader reads the mark as *Insured*, *Not
verified*, *Not insured*, or *Not covered*.
You see at most eight results. There is no button to press. Tap a result to open its card.

An airplane taken out of service is left out of the results until you type its whole
registration. Then it appears, and its card is marked **Out of service**.

A search that finds nothing says *No aircraft matches that* and suggests trying the
registration, the make or model, or the owner's name.


Reading the card
================

Opening a card takes you to its top. **Back to search** returns you to the list and the
search box. The card's address ends with the N-number, so it
survives a reload and you can send it to another leader.

The band across the top gives one of four verdicts:

- **NOT COVERED**, with the reason, such as *helicopters are excluded by CalDART's
  policy*: the coverage policy a system administrator keeps on the
  :doc:`aircraft` leaves out the airplane's category or its airworthiness
  category. This is a no-go whatever its insurance.

- **INSURED**, with *Coverage is current* or *Coverage expires soon*: a current policy
  that somebody has verified. This is a go.
- **NOT VERIFIED**, with *Coverage is current but not verified*, on amber: the policy is
  current, and nobody has checked it against the documents yet.
- **NOT INSURED**, with *Coverage has expired* or *No policy on file*.

Under the band are the N-number, **Out of service** when an administrator has taken
the airplane out of service, and the make, model, year, and seats. Then come five rows:

**Category**
   The aircraft category and the airworthiness category, such as *Helicopter · Standard*,
   and **Not covered**, beside a red dot, when the coverage policy leaves the airplane out. With no
   category recorded it reads *Category not recorded*, followed by the airworthiness category
   when there is one, such as *Category not recorded · Standard*: the policy cannot tell
   whether the airplane's category is covered, so ask the pilot, and have the category recorded on **My aircraft**
   or the :doc:`aircraft-record`.

**Insurance**
   Where the insurance stands, the carrier, the expiry date, and, once somebody has
   checked the policy, **Verified** with who verified it and on which day. The insurance
   reads **Not verified** in amber for a current policy nobody has checked, as the
   :doc:`member-check` reads it, and otherwise **Insured**, **Expiring soon**, **Insurance
   expired**, or **No insurance on file**. With no insurance on file there is nothing to
   verify, and no mark.

**Liability**
   The limits per occurrence and per person, and the hull value.

**Owner**
   The owner's name, whether they are an individual, an FBO, or a flying club, and how to
   reach them. An email address or a phone number is a link: tap it to write or to call,
   as on the :doc:`member-check` card. Each pilot's name under **Pilots who fly it** opens
   their member check.

**Last updated**
   The date of the last change to the record and who made it, such as *09/01/2026 by Dana
   Fiske*. A record nobody has changed since it was loaded shows the date alone. It tells
   you how old the insurance details are: a policy that runs out next month on a record
   last changed two years ago is worth a phone call.

**Pilots who fly it** lists every member and friend of CalDART who has the airplane on
their profile. Each line gives:

- the person's name, a link to their card on the :doc:`member-check`;
- **GO** or **NO-GO**, the same verdict the :doc:`member-check` gives that person: a
  current membership, a current medical, and a verified pilot certificate, medical, and
  photo ID. Open their card to read their membership and why a pilot is a NO-GO.

With nobody listed the card says *No member lists this aircraft on their profile.*

The policy number is kept on the record and left off this card. An account administrator
can read it on the **Aircraft** screen.


Verifying the insurance
=======================

A verifier, a DART leader, a user administrator, an account administrator, and a system
administrator see **Verify** under the N-number. Press it to open the **Verification**
panel, with the policy's **Carrier**, **Policy number**, **Liability per occurrence**,
**Liability per person**, **Hull**, and **Insurance expires**, the amounts in US dollars.
Correct any that differ from the policy documents, check **Insurance verified**, and press
**Save verification**. The toast reads *Verification saved* and the card shows the new
verdict. Changing a field unchecks the box, so you check it again once you have checked the
new value; unchecking it clears the verification. With no expiry date entered there is no
policy to verify, so the box is replaced by *Nothing to verify yet*. **Cancel**, or Escape,
closes the panel and changes nothing. Either way you are back on **Verify**.

Any later change to the insurance, by the pilot on **My aircraft** or by an account
administrator, clears the verification. Each save that verifies or clears it emails the
people subscribed to *Verification recorded* on the :doc:`notifications` screen.


When the airplane is missing
============================

A link that names a registration the register has never seen shows a card saying the
airplane *is not in the register*, with *Ask the pilot to add it on My aircraft, or ask an
account administrator.* **Back to search** above it goes back. A pilot adds an airplane
from **My aircraft** on their own portal, and an account administrator can add it from the
**Aircraft** screen.


If something looks wrong
========================

If the card reads **NOT VERIFIED** for insurance you verified, somebody has changed the
policy since; check it again and press **Verify**. If the insurance on the card looks out
of date, the record has not been changed since the
date under **Last updated**; ask the pilot to correct it from **My aircraft**, or ask an
account administrator to correct it on the :doc:`aircraft-record`. If a search finds nothing
for an airplane you know is on file, type the registration in full: it may be out of
service, or it may be past the first eight results. If the card says *That check could not
be run*, the server could not answer; go **Back to search** and try once more, and tell a
system administrator if it keeps happening.
