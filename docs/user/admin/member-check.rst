============
Member check
============

The **Member check** answers three questions about a pilot before a mission: is their
CalDART membership current, is their medical current, and is the airplane they fly
insured? It is built to be read on a phone while you stand on the ramp.

A DART leader and an account administrator find it under **Operations** in the menu. A
DART (Disaster Airlift Response Team) is one of the local teams that fly for CalDART. A
system administrator can open it too.


The check in ten seconds
========================

#. Open **Member check**.
#. Type a surname, part of an email address, a phone number, or an N-number into
   **Name, email, phone, or N-number**.
#. Read **GO** or **NO-GO** at the end of the person's line.
#. Tap the line for the detail: the medical, the certificate, and the insurance on the
   airplanes they fly.

The verdict is written in words as well as color, so it reads in bright sun and to anyone
who cannot tell red from green.


Searching
=========

The box searches as you type, and one box takes four kinds of search:

- **A name.** Part of a first or last name finds everyone who matches. A full name finds
  that person whichever way round you type it, so *Marta Reyes* and *Reyes, Marta* both
  work.
- **An email address.** Part of an address is enough.
- **A phone number.** Type at least seven digits. The punctuation does not matter, so
  (415) 555-0100, 415-555-0100, and 4155550100 all find the same person, whether it is
  their phone or their alternate phone.
- **An N-number.** Every member who lists that airplane on their profile. The leading N is
  optional, and spaces, dashes, and capitals are ignored. A search with no digits in it is
  never read as a registration, so looking for "Nate" finds Nate.

The search finds members and friends of CalDART. A friend supports CalDART without paying
dues. Two kinds of account are never found: an account that has been deactivated, and a
donor, who gave through the public site and cannot sign in.

You see at most twenty people, each on one line with a name and **GO** or **NO-GO**. For a
single name that line is the whole check.


Reading the status card
=======================

Tap a line to open the person's card. **Back to search** returns you to the list. The
address of the card names the person, so a reload keeps it open and you can send the link
to another leader.

**The band** across the top reads **GO** when the membership and the medical are both
current, with *Membership and medical are current* beside it. Otherwise it reads **NO-GO**
and names each reason:

- *Membership expired* or *No CalDART membership*. For a friend the reason says they are a
  friend of CalDART and hold no membership: a friend pays no dues, so a friend is always a
  NO-GO on membership.
- *Medical expired*, *No medical on file*, or *No medical expiry on file* when the member
  chose a class of medical and never entered its date.

The band is about the person. Insurance is listed separately below it, because a member
with a lapsed policy on one airplane may fly another. Read both before you launch.

Under the band is the person's name, their DART (or *No DART*), their phone number, and
their email address. Tap the number to call them, or the address to write to them.

**Membership** shows a chip (**Current**, **Expiring soon**, **Unpaid**, **Expired**, **No
membership**, **Friend**, or **Never expires** for a life member), then the plan and the
expiry date. A membership counts as current up to and including its last day.

**Medical** shows **Current** or **Not current**, the kind of medical (BasicMed or the
class), and its expiry date. A medical expiring today still counts as current.

**Certificate** shows the certificate, its number, whether the pilot is IFR rated (**IFR**,
**VFR only**, or **Not stated**), and any ratings. It is for your information and does not
change the verdict.

**Aircraft** lists every airplane on the member's profile, each with its insurance chip
and expiry date:

- **Insured**: a policy is on file and has not expired.
- **Expiring soon**: insured, and the policy runs out within 30 days.
- **Insurance expired**: the policy's expiry date has passed.
- **No insurance on file**: nobody has recorded a policy for this airplane.

With no airplanes on the profile the card says *No aircraft on this member's profile.*


When nobody matches
===================

A search that finds nobody says *Nobody matches that*. If you typed an N-number, the card
says *No member lists that aircraft. You can still check the aircraft itself.* and offers a
**Check** button that opens the :doc:`aircraft-check` for that airplane.

The members list, under **Administration**, is the place to browse everyone before a
mission. See :doc:`members`.


If something looks wrong
========================

If a member says they paid and the card reads *Membership expired*, ask them to open their
dashboard; a renewal counts from the moment it is paid, and an account administrator can
read their payment history on the :doc:`member-record`. *No medical on file* for a pilot
who has one means they have not entered it on their profile, and only they or an account
administrator can add it. An airplane missing from the card is one the member has not
attached to their profile, so use the :doc:`aircraft-check` for it. Insurance dates that
look old come from the aircraft register, where an account administrator or the member who
added the airplane keeps them; see :doc:`aircraft-record`. If a card says *That member
could not be loaded*, press **Search again**: the account may have been deleted.
