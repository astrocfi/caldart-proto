:roles: account_admin

=================
Aircraft register
=================

The **Aircraft register** is CalDART's one list of the airplanes its members fly, with the
insurance a DART leader checks before a mission. Members add the airplanes they fly from
**My aircraft**; you keep the register tidy, the insurance details current, and the
downloads ready for an insurance review.

Only an account administrator finds it, as **Aircraft register** under **Administration**
in the menu. A system administrator can open it too, and also keeps the :ref:`coverage-policy`
there.


N-numbers
=========

A registration is kept in one form: capitals, no punctuation, and a leading N. Type it
however you like in any box. N-12345, n12345, and 12345 are the same airplane, so an
airplane can be in the register only once.


What you see
============

The header, beside **New aircraft**, says how fresh CalDART's copy of the FAA aircraft
registry is, such as *Registry as of 09/20/2026*: the day of the last successful import,
which runs every night. Until the first import it reads *Registry not imported yet*.
The airplanes the N-number box lists on the aircraft forms and the list of aircraft types
both come from that copy.

The caption over the table counts the airplanes your filters match, such as *57 aircraft*.
The table shows 25 at a time; when there are more, the foot of the table reads, for example,
*Showing 1–25 of 57*, between **Previous** and **Next**.

The table shows the same columns as the register you download, and **Columns** changes both
(see `Downloading the register`_). At first it shows the report's nine:

**N-number**
   The registration, which opens the :doc:`aircraft-record`. An airplane taken out of
   service reads **Out of service**; the register lists it all the same.

**Make** and **Model**
   The record's aircraft type, as the list of aircraft types spells it.

**Owner**
   The owner's name.

**Carrier**, **Liability / occurrence**, and **Hull**
   The insurance carrier, and the policy's limits in dollars, right-aligned.

**Expires**
   A colored dot and the cover's state with its date: *Insured to 04/29/2027* (green),
   *Expiring 10/31/2026* in its last 30 days (amber), *Expired 03/02/2026* once it has
   lapsed (red), or *No insurance on file* (gray).

**Current**
   Yes while the insurance runs, No once it has lapsed or with none on file.

Each row stays on one line, and anything too long for its column ends in an ellipsis. On a
narrower screen the table leaves columns out until the rest fit, the insurance figures
first, then **Owner**, **Model**, and **Make**; the N-number, **Expires**, and any column
you ticked beyond the defaults always stay. When the table is still wider than the screen, a line over it says
so, and the N-numbers stay pinned at the left while you scroll.

**N-number**, **Make**, **Model**, **Owner**, and **Expires** sort: their headings carry an
arrow, and the register opens sorted by N-number. Click one to sort the whole register by
it; click again to reverse. An airplane with no insurance on file always sorts to the bottom
of **Expires**, whichever way you sort, so it never crowds out the ones about to lapse. The
other headings have no arrow and do not sort.

When no airplane matches, the table says *No aircraft match these filters* and offers
**Reset filters**.


.. _coverage-policy:

Coverage policy
===============

The **Coverage policy** card, above the table, says which airplanes CalDART's insurance
does not cover, so a DART leader is not surprised on the ramp. Only a system
administrator sees the card and changes the policy; an account administrator sees the
register without it. It reads three lines:

**Excluded categories**
   The aircraft categories the policy leaves out, such as **Helicopter**, or *None*.

**Excluded airworthiness**
   The airworthiness categories it leaves out, such as **Experimental**, or *None*.

**Note to members**
   A short statement of the limitation in your own words, or *None*. Every member reads it
   above the list on **My aircraft**.

To change it, press **Edit policy**. Tick the categories and the airworthiness categories
to leave out in the two drop-downs (**Clear** in either unticks them all), write the note,
and press **Save policy**; *Coverage policy saved.* appears. **Cancel** puts the card back
as it was. The note takes at most 1,000 characters.

The policy takes effect at once. The aircraft check shows an airplane it leaves out as
**NOT COVERED**, a no-go, with the reason, such as *helicopters are excluded by CalDART's
policy*, whatever its insurance; the member check marks the airplane **Not covered** on the
pilot's card; and **My aircraft** marks it for its pilot. An airplane with no **Category**
recorded is never left out by its category, whatever its airworthiness says: the aircraft
check says *Category not recorded* instead, so record the category on the
:doc:`aircraft-record`.


Filtering
=========

A list applies the moment you change it, and a box you type in applies after a short pause.
**Reset filters** empties them all. The filters, the sort, and the page are kept in the
page's address, so a filtered register can be bookmarked or sent to a colleague, and the
browser's back button steps back through them.

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
   **Current** (a policy on file and not yet expired), **Expired**, or **Not on file**.

**Expiring within**
   **Expiring in 30 days**, **Expiring in 60 days**, or **Expiring in 90 days**: cover that
   is still valid and about to lapse. A policy that has already expired is left out.


Adding an airplane
==================

**New aircraft**, at the top right, opens **Add an aircraft** above the table and takes you
to its first box, and the button reads **Close** while the form is open. **Close**,
**Cancel**, or Escape closes it again. The form is the whole record, the one on the
:doc:`aircraft-record`, so everything can be filled in at once. Only the N-number and the
aircraft type are required. Type the start of the N-number, such as N17, and the FAA
registry's airplanes whose N-number starts with it are listed under the box; pick one to
fill the type, year, seats, category, airworthiness, and owner from the registry, then
check them. Press **Add
aircraft**. The message reads that the airplane was
*added to the register*, and its record opens.


Adding an aircraft type
=======================

The aircraft types are the FAA's list of every type ever registered in the United States,
foreign-built ones such as the Aeropro Eurofox included, so the type of almost any airplane
is already there. When a search in **Aircraft type** finds nothing, the box says *No
aircraft type matches that.*, and you, unlike a member, also see **Add a type**. Try the
make alone, or a designator such as c172, first. **Add a type** is for a type the FAA has
never registered:

#. Press **Add a type**. A small form opens under the box.
#. Fill in **Make** and **Model** (both required), and **Seats** and **Engines** if you know
   them.
#. Press **Add type**, or Enter. The type is added to the list and picked at once.
   **Cancel** closes the small form.

CalDART tidies the names the way it tidies the FAA's, so *CESSNA* becomes *Cessna*. If the
type is listed already, *That aircraft type is already listed.* appears under **Model**:
search for it instead. When the FAA later registers the same make and model, the nightly
import folds your entry into the FAA's, and every airplane of that type follows.


Downloading the register
========================

**Export CSV** and **Export PDF** download exactly the airplanes the filters have chosen, in
the table's order. Set the filters first, then download. Both carry nine columns unless you
choose others: **N-number**, **Make**, **Model**, **Owner**, **Carrier**, **Liability /
occurrence**, **Hull**, **Expires**, and **Current**. The CSV gives money as plain dollars
for a spreadsheet. The PDF is a landscape letter table with the filters printed under the
title.

**Columns**, at the right of the bar beside the export buttons, chooses the columns of the
table on screen and of the downloads together. Five more are on offer: **Category**,
**Airworthiness**, **Owner type**, **Liability / person**, and **Pilots**, the members who
list the airplane on their profile. They are off until you tick them. **Pilots** is filled
in the downloads alone: who flies an airplane is the member check's to show, so its column
on screen reads a dash. **Reset to the default columns** ticks the nine again. **Load
columns** and **Save columns** keep a set of columns under a name, as
:ref:`saved-column-sets` describes.

A useful monthly routine: choose **Expiring in 30 days**, download the PDF, and work down it.


If something looks wrong
========================

*An aircraft with this N-number is already on file.* means the register already has the
airplane, under whatever spelling somebody first used; search for it and correct that
record. An airplane a member cannot find when they add it to their profile has probably been
taken out of service, which leaves it out of their search until they type the whole
registration. If the line beside the export buttons says *The columns could not be loaded;
the list shows the default ones.*, reload the page. If a download carries more rows than
you expected, a box you had typed in had not applied yet; wait for the table to narrow, then
download again.
