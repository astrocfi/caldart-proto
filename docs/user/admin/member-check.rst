:roles: dart_leader, account_admin, user_admin, verifier

============
Member check
============

The **Member check** answers four questions about a pilot before a mission. Is their
CalDART membership current? Is their medical current? Has somebody checked their pilot
certificate, medical, and photo ID against the documents? Is the airplane they fly insured?
It is built for a phone, so you can use it standing on the ramp. You also verify those
documents here.

A verifier, a DART leader, a user administrator, and an account administrator find it
under **Operations** in the menu. A DART (Disaster Airlift Response Team) is one of the
local teams that fly for CalDART. A system administrator can open it too.


The check in ten seconds
========================

#. Open **Member check**.
#. Type a surname, part of an email address, a phone number, or an N-number into
   **Name, email, phone, or N-number**.
#. Look for **GO** or **NO-GO** at the end of the person's line.
#. Tap the line for the detail: the medical, the certificate, the photo ID, and the
   insurance on the airplanes they fly.

The verdict is spelled out in words as well as shown in color, so you can read it in
bright sun, and so can anyone who can't tell red from green.


Searching
=========

The box searches as you type, and it takes four kinds of search:

- **A name.** Part of a first or last name finds everyone who matches. A full name finds
  that person whichever way round you type it, so *Marta Reyes* and *Reyes, Marta* both
  work.
- **An email address.** Part of an address is enough.
- **A phone number.** Type at least seven digits. The punctuation doesn't matter, so
  (415) 555-0100, 415-555-0100, and 4155550100 all find the same person, whether it is
  their phone or their alternate phone.
- **An N-number.** This finds every member who lists that airplane on their profile. You
  can leave off the leading N, and spaces, dashes, and capitals don't matter. A search
  without any digits is never taken for a registration, so looking for "Nate" finds Nate.

The search finds members and friends of CalDART. A friend supports CalDART without paying
dues. It never finds two kinds of account: a deactivated account, and a donor, who gave
through the public site and can't sign in.

You see up to twenty people, each on one line. The line gives the name, their DART in its
own column, such as *Monterey DART* (or *No DART*), and **GO** or **NO-GO** at the end. The
DART tells apart two people with the same name. On a phone, it sits under the name. For a
quick check of one person, that line is all you need.


Reading the status card
=======================

Tap a line to open the person's card, which opens at its top. **Back to search** takes you
back to the list and the search box. The card's address names the person, so you can
reload it or send the link to another leader.

**The band** across the top says **GO** when the membership and the medical are both
current and the pilot certificate, the medical, and the photo ID are all verified. Beside
it is *Membership and medical are current and verified*. Otherwise the band says **NO-GO**
and names each reason:

- *Membership expired*. Or *Not yet paid*, for somebody who joined as a member and has
  never paid. Or, for a friend, *Friend of CalDART, not a member*. A friend doesn't pay
  dues, so a friend is always a NO-GO on membership.
- *Not a pilot*, for somebody without a pilot certificate. Apart from the membership, it is
  their only reason. The card doesn't list the medical and photo ID of a person who can't
  fly.
- *Medical expired*, *No medical on file*, or *No medical expiry on file*. The last one
  means the member chose a class of medical but never entered its date.
- *Medical not verified*, *Certificate not verified*, or *Photo ID not verified*, when
  nobody has checked that document yet.
- *No photo ID on file*, when the photo ID says *Not provided*.

Each document gives at most one reason. A medical that has expired, or isn't on file, gives
only that reason, verified or not, because verifying it wouldn't clear the pilot. When the
member or an administrator changes a verified item, the verification is cleared, and the
item needs checking again.

The band is about the person. The card lists insurance separately, below it, because a
member with a lapsed policy on one airplane may fly another. Look at both before you
launch.

Under the band are the person's name and a single line: their DART, such as *Monterey
DART* (or *No DART*), *DART leader* and *Verifier* if they hold those roles, their phone
number, and their email address. Tap the number to call them, or the address to write to
them.

**Membership** shows the status (**Current**, **Expiring soon**, **Expired**, **Not
yet paid**, **Friend**, or **Never expires** for a life member), then the plan and the
expiry date. A membership counts as current up to and including its last day.

**Medical** shows **Current**, **Expired** once its date has passed, or **Not current**
if nobody entered a date. Then come the kind of medical (BasicMed or the class), its expiry
date, and its mark. A medical that expires today still counts as current. A medical of
*None* shows only the word *None*.

**Certificate** shows the certificate, its number, any ratings (including **Instrument**
if the pilot holds an instrument rating), and its mark.

**Photo ID** shows the kind of photo ID the member showed (a driver's license, a
passport, a state ID card, a military ID, another kind, or *Not provided*) and its mark.
CalDART doesn't record anything else about the document.

Each mark says **Verified**, followed by who verified it and on which day, such as
*Verified by Dana Leader on 05/01/2026*. Or it says **Not verified** in amber, the color of
a check still to be made. If the person doesn't hold an item (*Not a pilot*, a medical of
*None*, or a photo ID of *Not provided*), there isn't anything to verify, so it doesn't
show a mark.

**Aircraft** lists every airplane on the member's profile, each with its insurance status
and expiry date. The status gives the same answer as the :doc:`aircraft-check`:

- **Insured**: a current policy that somebody has verified.
- **Expiring soon**: insured, and the policy runs out within 30 days.
- **Not verified**, in amber: the policy is current, but nobody has checked it against the
  documents yet. You verify it on the :doc:`aircraft-check`.
- **Insurance expired**: the policy's expiry date has passed.
- **No insurance on file**: nobody has recorded a policy for this airplane.

If CalDART's coverage policy leaves out an airplane, such as a helicopter while helicopters
are excluded, the card shows **Not covered**, beside a red dot, where the insurance status
would be. The reason follows its expiry date, such as *Not covered: helicopters are
excluded by CalDART's policy*. For an airplane without a recorded category, the card shows
*Category not recorded* there instead.

If the profile doesn't list any airplanes, the card says *No aircraft on this member's
profile.*


Verifying the documents
=======================

A verifier, a DART leader, a user administrator, an account administrator, and a system
administrator see **Verify** under the person's name. Press it to open the
**Verification** panel:

#. Check the fields against the documents in front of you: **Pilot certificate**,
   **Certificate number**, **Medical**, **Medical expires**, and **Photo ID**. Correct
   any that are wrong. **Certificate number** takes seven digits only. You can leave it and
   **Medical expires** blank.
#. Check **Pilot certificate verified**, **Medical verified**, and **Photo ID verified**
   for each document you have seen. The boxes start out checked for items already verified.
   Changing a field unchecks its box, so check it again only after you have checked the
   new value. Uncheck a box to clear that verification. If the person doesn't hold an item
   (*Not a pilot*, a medical of *None*, or a photo ID of *Not provided*), it doesn't have a
   box, since there isn't anything to verify. Choose what they showed you, and its box
   appears. If the person doesn't hold any of the three, the panel says *Nothing to verify
   yet*.
#. Press **Save verification** at the foot of the panel. The toast says *Verification
   saved*, and the card shows the new marks and verdict. **Cancel**, or Escape, closes the
   panel without changing anything.
   Either way, you land back on **Verify**.

If the record refuses a field, such as a certificate without a number, the message appears
under the field, and nothing is saved. You may verify your own documents. Each save that
verifies or clears an item emails the people subscribed to *Verification recorded* on the
:doc:`notifications` screen, once for the whole save.


Making someone a verifier
=========================

A DART leader, a user administrator, and a system administrator also see **Make a
verifier** under the person's name. If the person is already a verifier, the button is
**Remove as verifier**. It appears on everybody's card except your own, because nobody
changes their own roles. It asks first and explains what the change means. **Cancel** is
already chosen, so a stray Enter doesn't change anything. Press **Yes, make a verifier**
(or **Yes, remove as verifier**) to change the role, and a toast confirms it. **Cancel**,
or Escape, leaves the role as it was.
A verifier sees **Member check** and **Aircraft check** in their menu the next time the
page loads. See :doc:`../roles`.


The verification report
=======================

Above the search box, *Everything requiring verification:* sits beside **Export CSV** and
**Export PDF**. These download the CalDART verification report, which lists everything not
yet verified, in two sections:

- **People**, one row per person with something to verify, sorted by name. The columns are
  **Name**, **DART**, **Photo ID**, **Certificate**, **Medical**, **Details**,
  **Expires**, and **Updated**. Each of the three checks says *Not verified*, *Verified*,
  or *Not provided*. **Details** is what is on file, such as *Passport · Private · 1234567
  · Third class*. **Expires** is the medical's expiry date, and **Updated** is the day the
  person's profile last changed.
- **Aircraft insurance**, one row per airplane, with its own columns: **N-number**,
  **Owner**, **Carrier**, **Expires** (the policy's expiry date), and **Updated** (the day
  the record last changed). Airplanes don't have check columns.

The line under the PDF's title says *Showing: Not yet verified*. The report only checks
what somebody holds. A non-pilot's **Certificate** says *Not provided*, and so does the
**Medical** of a person without a medical, and the **Photo ID** of a person without a photo
ID on file. The report leaves out a person who doesn't hold any of the three, and an
airplane without a policy on file. A section heading always starts on the same page as its
first rows.

The CSV is one table under one header row, so a spreadsheet can read it whole. Its first
column, **Section**, names each row's section, which the PDF shows with headings instead.
The CSV uses the People columns for both sections. An airplane's N-number goes under
**Name**, its owner under **DART or owner**, and its carrier under **Details**, and its
three check cells stay blank. You can also have the report emailed on a schedule from the
:doc:`subscriptions` screen, where you can add the **Verified**, **Verified by**, and
**Verified on** columns.


When nobody matches
===================

When the search doesn't find anyone, it says *Nobody matches that*. If you typed an
N-number, the card says *No member lists that aircraft. You can still check the aircraft
itself.* It offers a **Check** button that opens the :doc:`aircraft-check` for that
airplane.

To browse everyone before a mission, use the members list, under **Administration**. See
:doc:`members`.


If something looks wrong
========================

If a member says they paid but the card says *Membership expired*, ask them to open their
dashboard. A renewal counts from the moment it is paid, and an account administrator can
see their payment history on the :doc:`member-record`. If an item that was verified shows
a *not verified* reason, somebody has changed it since. Open **Verify**, check the new
value, and check its box again. If a pilot has a medical but the card says *No medical on
file*, they haven't entered it on their profile. Only they or an account administrator can
add it. If an airplane is missing from the card, the member hasn't added it to their
profile, so use the :doc:`aircraft-check` for it. Insurance dates that look old come from
the aircraft register, where an account administrator or the member who added the airplane
keeps them up to date; see :doc:`aircraft-record`. If a card says *We could not find that
person*, their account may have been deleted. **Back to search** above it takes you back.
