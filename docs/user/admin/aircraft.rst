:roles: account_admin

========
Aircraft
========

The **Aircraft** screen is CalDART's one list of the airplanes its members fly, with the
insurance a DART leader checks before a mission. Members add the airplanes they fly from
**My aircraft**. Your job is to keep the register tidy, keep the insurance details current,
and have the downloads ready for an insurance review.

Only an account administrator finds it in the menu, as **Aircraft** under
**Administration**. A system administrator can open it too, and also keeps the
:ref:`coverage-policy` there.


N-numbers
=========

CalDART stores every registration the same way: in capitals, with a leading N and no
punctuation. Type it however you like in any box. N-12345, n12345, and 12345 are the same
airplane, so an airplane can be in the register only once.


What you see
============

The header, beside **New aircraft**, says how fresh CalDART's copy of the FAA aircraft
registry is, such as *FAA data as of 09/20/2026*. That is the day of the last successful
import, which runs every night. Until the first import, it says *FAA data not loaded yet*.
The airplanes listed under the N-number box on the aircraft forms, and the list of aircraft
types, both come from that copy.

The caption over the table counts the airplanes that match your filters, such as *57
aircraft*. The table shows 25 at a time. When there are more, the foot of the table says,
for example, *Showing 1–25 of 57*, between **Previous** and **Next**.

The table shows the same columns as the register you download, and **Columns** changes both
(see `Downloading the register`_). To begin with, it shows the report's nine:

**N-number**
   The registration, which opens the :doc:`aircraft-record`. An airplane that is out of
   service shows **Out of service**, and the register still lists it.

**Make** and **Model**
   The record's aircraft type, spelled as on the list of aircraft types.

**Owner**
   The owner's name.

**Carrier**, **Liability / occurrence**, and **Hull**
   The insurance carrier, and the policy's limits in dollars, right-aligned. If an airplane
   doesn't have a policy on file, meaning a carrier or an expiry date, all three are blank.

**Expires**
   A colored dot and the state of the insurance, with its date: *Insured to 04/29/2027*
   (green), *Expiring 10/31/2026* in its last 30 days (amber), *Expired 03/02/2026* once it
   has lapsed (red), or *No insurance on file* (gray).

**Covered**
   Whether CalDART's insurance policy covers an airplane of this category and airworthiness
   at all, as set in the :ref:`coverage-policy`. It shows **Yes**, or **No** for a kind the
   policy excludes, such as a helicopter, however current the airplane's own insurance is.
   An airplane without a recorded category shows **Yes**. The **Expires** dot tells you
   whether the airplane's own insurance is in force.

Each row stays on one line, and anything too long for its column ends in an ellipsis. On a
narrower screen, the table drops columns until the rest fit: the insurance figures first,
then **Covered**, **Owner**, **Model**, and **Make**. The N-number, **Expires**, and any
column you added to the defaults always stay. If the table is still wider than the screen,
a line above it says so, and the N-numbers stay pinned at the left while you scroll.

You can sort by **N-number**, **Make**, **Model**, **Owner**, and **Expires**. Their
headings carry an arrow, and the register opens sorted by N-number. Click a heading to sort
the whole register by it, and click again to reverse the order. Under **Expires**, an
airplane without insurance on file always goes to the bottom, whichever way you sort, so it
doesn't crowd out the ones about to lapse. The other headings don't have an arrow and don't
sort.

When no airplane matches, the table says *No aircraft match these filters* and offers
**Reset filters**.


.. _coverage-policy:

Coverage policy
===============

The **Coverage policy** card, above the table, says which airplanes CalDART's insurance
doesn't cover, so a DART leader isn't surprised on the ramp. Only a system administrator
sees the card and changes the policy. An account administrator sees the register without
it. The card has three lines:

**Excluded categories**
   The aircraft categories the policy leaves out, such as **Helicopter**, or *None*.

**Excluded airworthiness**
   The airworthiness categories it leaves out, such as **Experimental**, or *None*.

**Note to members**
   A short statement of the limitation in your own words, or *None*. Every member sees it
   above the list on **My aircraft**.

To change it, press **Edit policy**. In the two drop-downs, check the categories and the
airworthiness categories to leave out (**Clear** in either one unchecks them all). Write
the note, and press **Save changes**. *Coverage policy saved.* appears. **Cancel** puts the
card back as it was. The note can be up to 1,000 characters.

The policy takes effect at once. The aircraft check shows an airplane the policy leaves out
as **NOT COVERED**, a no-go, with the reason, such as *helicopters are excluded by CalDART's
policy*, whatever its insurance. The member check marks the airplane **Not covered** on the
pilot's card, and **My aircraft** marks it for its pilot. If an airplane doesn't have a
recorded **Category**, the policy never leaves it out by category, whatever its
airworthiness says. Instead, the aircraft check says *Category not recorded*, so record the
category on the :doc:`aircraft-record`.


Filtering
=========

A list filter applies as soon as you change it, and a box you type in applies after a short
pause. **Reset filters** clears them all. The filters, the sort, and the page are kept in
the page's address. You can bookmark a filtered register or send it to a colleague, and the
browser's back button steps back through your changes.

**Search**
   An N-number, a make, a model, or an owner. A registration is tidied first, so 172sp finds
   N172SP.

**Make**
   Any part of the make.

**Category**
   One aircraft category, such as **Airplane**, **Helicopter**, or **Glider**.

**Airworthiness**
   One airworthiness category, such as **Standard**, **Experimental**, or **Light sport**.

**Owner type**
   **Individual**, **FBO**, or **Flying club**.

**Insurance**
   **Insured** (a policy on file that hasn't expired yet), **Insurance expired**, or **No
   insurance on file**, the same words each row's insurance dot shows.

**Expiring within**
   **Expiring in 30 days**, **Expiring in 60 days**, or **Expiring in 90 days**: insurance
   that is still valid and about to lapse. A policy that has already expired is left out.


Adding an airplane
==================

**New aircraft**, at the top right, opens **Add an aircraft** above the table and puts you
in its first box. While the form is open, the button says **Close**. **Close**, **Cancel**,
or Escape closes the form. It is the whole record, the same as on the
:doc:`aircraft-record`, so you can fill in everything at once. Only the N-number and the
aircraft type are required. Type the start of the N-number, such as N17, and the box lists
the FAA registry's airplanes whose N-number starts that way. Pick one to fill in the type,
year, seats, category, airworthiness, and owner from the registry, then check them. Press
**Add aircraft**. The toast gives the N-number and *added to the register*, and the
airplane's record opens.


Adding an aircraft type
=======================

The aircraft types are the FAA's list of every type ever registered in the United States,
including foreign-built ones such as the Aeropro Eurofox, so almost any airplane's type is
already there. When a search in **Aircraft type** doesn't find anything, the box says *No
aircraft type matches that.* Unlike a member, you also see **New aircraft type**. First try
the make alone, or a designator such as c172. **New aircraft type** is for a type the FAA
has never registered:

#. Press **New aircraft type**. A small form opens under the box.
#. Fill in **Make** and **Model** (both required), and **Seats** and **Engines** if you know
   them.
#. Press **Add aircraft type**, or Enter. The type is added to the list and picked at once.
   **Cancel** closes the small form.

CalDART tidies the names the same way it tidies the FAA's, so *CESSNA* becomes *Cessna*. If
the type is already listed, *That aircraft type is already listed.* appears under
**Model**; search for it instead. If the FAA later registers the same make and model, the
nightly import merges your entry into the FAA's, and every airplane of that type follows.


Downloading the register
========================

**Export CSV** and **Export PDF** download exactly the airplanes your filters have picked,
in the table's order. Set the filters first, then download. Both have nine columns unless
you choose others: **N-number**, **Make**, **Model**, **Owner**, **Carrier**, **Liability /
occurrence**, **Hull**, **Expires**, and **Covered**. The CSV gives money as plain dollars
for a spreadsheet. The PDF is a table on landscape letter paper, with the filters printed
under the title. It prints a check mark (✓) after each expiry date still in force and an X
(✗) after each one that has lapsed, so a printed copy makes sense without color. The CSV
gives the date alone.

**Columns**, at the right of the bar beside the export buttons, picks the columns for the
table on screen and for the downloads together. Five more are available: **Category**,
**Airworthiness**, **Owner type**, **Liability / person**, and **Pilots**, the members who
list the airplane on their profile. They stay off until you check them. **Pilots** is
filled in only in the downloads. Who flies an airplane is for the member check to show, so
on screen that column shows a dash. **Reset to the default columns** checks the nine again.
**Load columns** and **Save columns** keep a set of columns under a name, as
:ref:`saved-column-sets` describes.

A useful monthly routine: choose **Expiring in 30 days**, download the PDF, and work down it.


If something looks wrong
========================

*An aircraft with this N-number is already on file.* means the airplane is already in the
register, under whatever spelling somebody used first. Search for it and correct that
record. If a member can't find an airplane when they add it to their profile, it has
probably been taken out of service. Their search leaves it out until they type the whole
registration. If the line beside the export buttons says *The columns didn't load; the list
shows the default ones.*, reload the page. If a download has more rows than you expected, a
box you typed in hadn't applied yet. Wait for the table to narrow, then download again.
