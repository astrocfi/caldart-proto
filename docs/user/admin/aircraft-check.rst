:roles: dart_leader, account_admin, user_admin, verifier

==============
Aircraft check
==============

The **Aircraft check** tells you four things about an airplane: whether CalDART's insurance
covers it at all, whether its insurance is current and verified, who flies it, and how old
the record is. Use it when the airplane in front of you isn't on the pilot's profile, such
as a club airplane or one they have just started flying. You also verify an airplane's
insurance here, against the policy documents.

A verifier, a DART leader, a user administrator, and an account administrator find it under
**Operations** in the menu, below **Member check**. A system administrator can open it too.


Searching
=========

Type into **N-number, make, model, or owner**. CalDART searches the register as you type.
A registration, a make, a model, or an owner's name all match, so a half-remembered tail
number is enough. You can leave off the leading N, and spaces, dashes, and capitals don't
matter.

Each result is one line: the N-number, the make and model, and **GO** or **NO-GO** at the
far end. **GO** means the coverage policy covers the airplane and its insurance is current
and verified, even if it is about to expire. A screen reader says *Insured*, *Not
verified*, *Not insured*, or *Not covered* for the mark.
You see up to eight results. You don't press a button: tap a result to open its card.

The results leave out an airplane that is out of service until you type its whole
registration. Then it appears, and its card is marked **Out of service**.

When the search doesn't find anything, it says *No aircraft matches that* and suggests
trying the registration, the make or model, or the owner's name.


Reading the card
================

A card opens at its top. **Back to search** takes you back to the list and the search box.
The card's address ends with the N-number, so you can reload it or send it to another
leader.

The band across the top gives one of four verdicts:

- **NOT COVERED**, with the reason, such as *helicopters are excluded by CalDART's
  policy*. The coverage policy, which a system administrator keeps on the
  :doc:`aircraft`, leaves out the airplane's category or its airworthiness
  category. This is a no-go, whatever its insurance.

- **INSURED**, with *Coverage is current* or *Coverage expires soon*. The policy is current
  and somebody has verified it. This is a go.
- **NOT VERIFIED**, with *Coverage is current but not verified*, on amber. The policy is
  current, but nobody has checked it against the documents yet.
- **NOT INSURED**, with *Coverage has expired* or *No policy on file*.

Under the band you see the N-number, **Out of service** if an administrator has taken the
airplane out of service, and the make, model, year, and seats. Then come five rows:

**Category**
   The aircraft category and the airworthiness category, such as *Helicopter · Standard*.
   When the coverage policy leaves the airplane out, **Not covered** follows, beside a red
   dot. When the category isn't recorded, the row says *Category not recorded*, followed by
   the airworthiness category if there is one, such as *Category not recorded · Standard*.
   The policy can't tell whether that airplane is covered, so ask the pilot, and have the
   category recorded on **My aircraft** or the :doc:`aircraft-record`.

**Insurance**
   The state of the insurance, the carrier, and the expiry date. Once somebody has checked
   the policy, it also shows **Verified**, with who verified it and on which day. A current
   but unverified policy shows **Not verified** in amber, just as on the
   :doc:`member-check`. Otherwise the row shows **Insured**, **Expiring soon**, **Insurance
   expired**, or **No insurance on file**. If no insurance is on file, there isn't anything
   to verify, so the row doesn't show a mark.

**Liability**
   The limits per occurrence and per person, and the hull value.

**Owner**
   The owner's name, whether they are an individual, an FBO, or a flying club, and how to
   reach them. An email address or a phone number is a link: tap it to write or to call,
   as on the :doc:`member-check` card. Each pilot's name under **Pilots who fly it** opens
   their member check.

**Last updated**
   The date of the last change to the record and who made it, such as *09/01/2026 by Dana
   Fiske*. If nobody has changed the record since it was loaded, you see the date alone.
   This tells you how old the insurance details are. A policy that runs out next month, on
   a record last changed two years ago, is worth a phone call.

**Pilots who fly it** lists every member and friend of CalDART who has the airplane on
their profile. Each line gives:

- the person's name, a link to their card on the :doc:`member-check`;
- **GO** or **NO-GO**, the same verdict the :doc:`member-check` gives that person. A GO
  needs a current membership, a current medical, and a verified pilot certificate, medical,
  and photo ID. Open their card to see their membership and why they are a NO-GO.

When nobody has the airplane on their profile, the card says *No member lists this aircraft
on their profile.*

The record keeps the policy number, but this card leaves it off. An account administrator
can see it on the **Aircraft** screen.


Verifying the insurance
=======================

A verifier, a DART leader, a user administrator, an account administrator, and a system
administrator see **Verify** under the N-number. Press it to open the **Verification**
panel. It shows the policy's **Carrier**, **Policy number**, **Liability per occurrence**,
**Liability per person**, **Hull**, and **Insurance expires**, with the amounts in US
dollars. Correct anything that differs from the policy documents, check **Insurance
verified**, and press **Save verification**. The toast says *Verification saved*, and the
card shows the new verdict.

Changing a field unchecks the box, so check it again once you have checked the new value.
Unchecking the box clears the verification. If the expiry date is blank, there isn't a
policy to verify, so you see *Nothing to verify yet* where the box would be. **Cancel**, or
Escape, closes the panel without changing anything. Either way, you land back on
**Verify**.

Any later change to the insurance clears the verification, whether the pilot makes it on
**My aircraft** or an account administrator makes it. Each save that verifies or clears it
emails the people subscribed to *Verification recorded* on the :doc:`notifications` screen.


When the airplane is missing
============================

If a link names a registration the register has never seen, the card says the airplane *is
not in the register*, with *Ask the pilot to add it on "My aircraft", or ask an account
administrator.* **Back to search** above it takes you back. A pilot adds an airplane from
**My aircraft** on their own portal, and an account administrator can add it from the
**Aircraft** screen.


If something looks wrong
========================

If the card says **NOT VERIFIED** for insurance you verified, somebody has changed the
policy since then. Check it again and press **Verify**. If the insurance on the card looks
out of date, nobody has changed the record since the date under **Last updated**. Ask the
pilot to correct it from **My aircraft**, or ask an account administrator to correct it on
the :doc:`aircraft-record`. If a search doesn't find an airplane you know is on file, type
the whole registration: the airplane may be out of service, or it may be past the first
eight results. If the card says *That check couldn't be run*, the server couldn't answer. It
says what to do next: *Try again, and if it fails again, tell a system administrator.*
