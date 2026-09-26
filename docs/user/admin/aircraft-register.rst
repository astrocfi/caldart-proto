=================
Aircraft register
=================

The **Aircraft register** is CalDART's one list of the airplanes its members fly, with the
insurance a DART leader checks before a mission. Members add the airplanes they fly from
**My aircraft**; you keep the register tidy, the insurance details current, and the
downloads ready for an insurance review.

Only an account administrator finds it, as **Aircraft** under **Administration** in the
menu. A system administrator can open it too.


N-numbers
=========

A registration is kept in one form: capitals, no punctuation, and a leading N. Type it
however you like in any box. N-12345, n12345, and 12345 are the same airplane, so an
airplane can be in the register only once.


What you see
============

The caption over the table counts the airplanes your filters match, such as *57 aircraft*.
The table shows 25 at a time, with **← Previous** and **Next →** and a count such as
*1–25 of 57* under it when there are more.

**N-number**
   The registration, which opens the :doc:`aircraft-record`. An airplane taken out of
   service carries an **Out of service** chip; the register lists it all the same.

**Make** and **Model**
   As the record has them.

**Owner**
   The owner's name, then Individual, FBO, or Flying club.

**Insurance**
   A colored dot beside the expiry date: green while the cover runs, amber in its last 30
   days, red once it has lapsed, and gray with no policy on file.

Each row stays on one line, and anything too long for its column ends in an ellipsis. Click
a column heading to sort the whole register by it; click again to reverse. An airplane with
no insurance on file always sorts to the bottom of the insurance column, whichever way you
sort, so it never crowds out the ones about to lapse.

When no airplane matches, the table says *No aircraft match these filters* and suggests
clearing a filter or adding the aircraft to the register.


Filtering
=========

A list applies the moment you change it, and a box you type in applies after a short pause.
**Reset to Defaults** empties them all. The filters, the sort, and the page are kept in the
page's address, so a filtered register can be bookmarked or sent to a colleague, and the
browser's back button steps back through them.

**Search**
   An N-number, a make, a model, or an owner. A registration is tidied first, so 172sp finds
   N172SP.

**Make**
   Any part of the make.

**Owner type**
   **Individual**, **FBO**, or **Flying club**.

**Insurance**
   **Current** (a policy on file and not yet expired), **Expired**, or **Not on file**.

**Expiring within**
   **Expiring in 30 days**, **Expiring in 60 days**, or **Expiring in 90 days**: cover that
   is still valid and about to lapse. A policy that has already expired is left out.


Adding an airplane
==================

**New aircraft**, at the top right, opens **Add an aircraft** above the table, and the
button reads **Close** while the form is open. The form is the one on the
:doc:`aircraft-record`. Only the N-number, make, and model are required. Press **Add
aircraft**. The message reads that the airplane was *added to the register*, and its record
opens.


Downloading the register
========================

**Export CSV** and **Export PDF** download exactly the airplanes the filters have chosen, in
the table's order. Set the filters first, then download. Both carry nine columns unless you
choose others: **N-number**, **Make**, **Model**, **Owner**, **Carrier**, **Liability /
occurrence**, **Hull**, **Expires**, and **Current**. The CSV gives money as plain dollars
for a spreadsheet. The PDF is a landscape letter table with the filters printed under the
title.

**Columns** chooses what the downloads carry. Three more are on offer: **Owner type**,
**Liability / person**, and **Pilots**, the members who list the airplane on their profile.
They are off until you tick them. **Reset to the default columns** ticks the nine again.
Your choice changes the downloads only; the register on screen keeps its five columns.
**Load columns** and **Save columns** keep a set of columns under a name, as
:ref:`saved-column-sets` describes.

A useful monthly routine: choose **Expiring in 30 days**, download the PDF, and work down it.


If something looks wrong
========================

*An aircraft with this N-number is already on file.* means the register already has the
airplane, under whatever spelling somebody first used; search for it and correct that
record. An airplane a member cannot find when they add it to their profile has probably been
taken out of service, which leaves it out of their search until they type the whole
registration. If the line under the filters says *The columns could not be loaded; the
downloads carry the default columns.*, reload the page. If a download carries more rows than
you expected, a box you had typed in had not applied yet; wait for the table to narrow, then
download again.
