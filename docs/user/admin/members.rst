=======
Members
=======

**Members** lists every member and every friend of CalDART, one row each, with whether they
can fly today, their DART, when their membership runs out, and their email address. A friend
supports CalDART without paying dues. Use the list to find people, to see who is about to
lapse, and to download a report or a roster.

An account administrator and a DART leader find it under **Administration** in the menu. A
system administrator can open it too. A donor who has only given through the public site is
never on this list; the treasurer's screens cover donors.


What you see
============

The caption over the table counts the people your filters match, such as *42 members match
these filters*. The table shows 25 people at a time. When there are more, the foot of the
list reads, for example, *Showing 1–25 of 212*, with **Previous** and **Next**.

**Pilot**
   A green tick when the person holds a pilot certificate and their medical is in date, a
   red cross when the medical has lapsed, and a dash for somebody who is not a pilot. It
   answers the question the list is most often opened for: who can fly today.

**Name**
   The person's name. A deactivated account has *account deactivated* beside it.

**DART**
   Their team, or **Unaffiliated**. A DART (Disaster Airlift Response Team) is one of the
   local teams that fly for CalDART.

**Membership Exp.**
   A colored dot and the date the membership runs out. The dot is green while the membership
   is current, amber in its last 30 days, red once it has run out, blue for somebody who has
   joined and not paid, and gray for somebody who has never been a member and for a friend.
   A life member's date reads **Never**, and a friend's reads **Friend**.

**Email**
   Their address. Click it to write to them.

The date is the end of the person's unbroken cover. Somebody who renews in March for a term
that starts in July already shows next July's date, so you never add terms up yourself.

For an account administrator a name opens the :doc:`member-record`. For a DART leader it
opens the :doc:`member-check` card for that person, and a deactivated account's name opens
nothing, since the member check never shows one. Only an account administrator sees the
**New member** button (see :doc:`new-member`).


Sorting
=======

Click a column heading to sort by it, and click again to reverse the order. The whole list
is sorted, every page of it. **Pilot** sorts the way its marks read: a current medical first,
then a lapsed one, then everybody who is not a pilot. People who tie fall into name order, so
a sorted list reads the same every time.


Filtering
=========

The filter bar sits above the table. A list or a checkbox applies the moment you change it,
and a box you type in applies after a short pause. There is no Apply button. **Reset to
Defaults** empties the bar and leaves the sort alone. The filters and the sort are part of
the page's address, so a filtered list is a link you can bookmark or send to a colleague.

**Kind**
   **All**, the first choice, lists members and friends together. **Members only** and
   **Friends only** list one kind. A member who has asked to become a friend at the end of
   their term is a member until that day comes.

**Search**
   A name, an email address, either phone number, or a pilot certificate number. A full name
   works: *Ana Bracco* finds her.

**Membership**
   **Current** (a term covers today), **Unpaid** (their only term was never paid for),
   **Expired** (a paid term has run out), **No membership** (nobody has ever granted or sold
   them a term), or **Friend**. Between them the five words cover every person exactly once,
   and the report's **Status** column prints the same five.

**Certificate** and **Medical**
   The pilot certificate and the medical on the person's profile. **Certificate** also
   offers **Any licensed**: every certificate a pilot may act on alone, sport through
   airline transport pilot. **Medical** also offers **Has any medical**. The blank choice,
   **Any**, takes in everyone, including the people who answered "none".

**DART**
   The team the person belongs to.

**County**
   The California counties on people's profiles. The box shows six at a time. Hold Ctrl
   (Command on a Mac) and click to choose more than one, and the list shows the people of
   any county you chose. Click a chosen county with Ctrl held to take it back. With no
   county chosen the filter narrows nothing.

**Role**
   People who hold one role, such as DART leader or Treasurer. A system administrator is
   listed only under System administrator, even though they can do everything.

**Expiring within (days)**
   A number of days; the box takes digits only. A member who has already renewed drops out
   at once, and a life member never appears.

**Include deactivated**
   Off at first. Tick it to list deactivated accounts too. The downloads never carry one,
   ticked or not.

Filters combine. "Current members of one DART who expire within 30 days" is two lists and a
number.


Downloading the report
======================

**Export CSV** and **Export PDF** download the membership report for exactly what the list is
showing: the same filters and the same order, every matching person and every page. The CSV
opens in a spreadsheet, for mail merges and anything you want to sort or total. The PDF is a
landscape letter table ready to print, with your filters printed under the title and the
date and page numbers at the foot, so it says on its face what it is a list of.

Both files carry eleven columns unless you choose others: **Name**, **Email**, **Phone**,
**DART**, **Status**, **Kind**, **Expires**, **Certificate**, **Medical**, **Medical
expires**, and **Aircraft**. **Kind** reads Member or Friend. A life member and a friend have
an empty **Expires** cell.


Choosing the columns
~~~~~~~~~~~~~~~~~~~~

**Columns**, beside the filters, opens a list of every column the report offers, with a box
to tick for each. Nine more are on offer: **Plan**, **Certificate number**, **IFR**,
**City**, **State**, **County**, **Joined** (the day the first term on file began), **Member
since** (the day the member says they joined), and **Profile updated** (the day their profile
was last changed). **Reset to the default columns**, under the boxes, ticks the eleven again.

Your choice changes the downloads only. The list on screen keeps its five columns. You cannot
untick the last column. Add many columns and the PDF starts to wrap its cells, which is the
point at which the CSV is the better file.

.. _saved-column-sets:

Saved column sets
~~~~~~~~~~~~~~~~~

Beside **Columns**, **Load columns** lists the sets of columns you have saved for this
report. Pick a name and its columns are ticked for you. The trashcan beside a name deletes
that set. **Save columns** keeps the boxes as they stand: type a name of up to 60 characters
and press **Save**, or press Enter. Saving under a name you already use replaces that set,
and loading a set puts its name in the box, so a set you load and change saves again under
the same name. Each of the three buttons opens its own panel under itself, and a click
outside it or Escape puts it away. Your saved sets are yours alone, and each report keeps
its own. The other screens with downloads work the same way.


If something looks wrong
========================

If a download carries more people than the screen shows, a box you had just typed in had not
applied yet; wait for the table to narrow, then download. If somebody you expect is missing,
press **Reset to Defaults** and search for them by name: a filter may be hiding them, their
account may be deactivated (tick **Include deactivated**), or they may be a donor, who is
never listed here. If the line under the filters says *The columns could not be loaded; the
downloads carry the default columns.*, reload the page to get the column chooser back. If a
member reads **Expired** and says they renewed, an account administrator can check the
**Memberships** and **Payments** tabs of their :doc:`member-record`.
