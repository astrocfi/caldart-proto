:roles: account_admin, dart_leader

=======
Members
=======

**Members** lists every member and every friend of CalDART, one row each, with their
membership, their DART, their pilot certificate and medical, and how to reach them. A friend
supports CalDART without paying dues. Use the list to find people, to see who is about to
lapse, and to download a report or a roster.

An account administrator and a DART leader find it under **Administration** in the menu. A
system administrator can open it too. A donor who has only given through the public site is
never on this list; the treasurer's screens cover donors.


What you see
============

The caption over the table counts the people your filters match, such as *42 members match
these filters*. The table shows 25 people at a time. When there are more, the foot of the
list reads, for example, *Showing 1–25 of 212*, between **Previous** and **Next**; a page
button with nowhere to go has a dashed frame. Moving to another page brings the top of the
table back into view.

The table shows the same columns as the membership report you download, and **Columns**
changes both (see `Choosing the columns`_). At first it shows the report's eleven:

**Name**
   The person's name. A deactivated account has *account deactivated* beside it.

**Email**
   Their address. Click it to write to them.

**Phone**
   Their phone number.

**DART**
   Their team, or **Unaffiliated**. A DART (Disaster Airlift Response Team) is one of the
   local teams that fly for CalDART.

**Status**
   A colored dot and the membership's state: **Current** (green), **Expiring soon** in its
   last 30 days (amber), **Expired** (red), **Never expires** for a life member (green), or
   **Friend** (gray).

**Kind**
   Member or Friend.

**Expires**
   The date the membership runs out. A life member's reads **Never**, and a friend's reads
   **Friend**. The date is the end of the person's unbroken cover: somebody who renews in
   March for a term that starts in July already shows next July's date, so you never add
   terms up yourself.

**Certificate** and **Medical**
   The pilot certificate and the medical on the person's profile. An airline transport
   pilot certificate reads **ATP**.

**Medical expires**
   The medical's date, after a mark that answers the question the list is most often
   opened for, who can fly today: a green check when the person holds a pilot certificate
   and their medical is current, a red cross when the medical has lapsed, and a dash for
   somebody who is not a pilot.

**Aircraft**
   The N-numbers of the aircraft on their profile.

On a narrower screen the table leaves default columns out, one at a time, until the rest
fit: **Email**, then **DART**, then **Phone**, **Kind**, and **Aircraft**, so a laptop keeps
the pilot columns; then **Medical**, **Certificate**, and **Medical expires**. **Name**,
**Status**, and **Expires** always stay, and so does any column you check beyond the
defaults. A line over the table names any column it hid; the downloads still carry it.
On a phone the table can still be wider than the screen: the line over it then reads
*Scroll sideways for more.* before the columns it hid, a shadow marks the edge with more
beyond it, and the names stay pinned at the left while you scroll. With a keyboard, Tab to the table and use
the arrow keys.

For an account administrator a name opens the :doc:`member-record`. For a DART leader it
opens the :doc:`member-check` card for that person, and a deactivated account's name opens
nothing, since the member check never shows one. Only an account administrator sees the
**New member** button (see :doc:`new-member`).


Sorting
=======

The list opens sorted by name, and the arrow beside **Name** says so. **Name**, **Email**,
**DART**, **Expires**, **Joined**, and **Profile updated** sort: their headings carry an
arrow, faint until you use it. Click one to sort by it, and click again to reverse the
order. The whole list is sorted, every page of it. People who tie fall into name order, so
a sorted list reads the same every time. The other headings have no arrow and do not sort.


Filtering
=========

The filter bar sits above the table. A list or a checkbox applies the moment you change it,
and a box you type in applies after a short pause. There is no Apply button. **Reset
filters**, at the end of the bar, empties it and leaves the sort alone. The filters and the sort are part of
the page's address, so a filtered list is a link you can bookmark or send to a colleague.

**Kind**
   **Any kind**, the first choice, lists members and friends together. **Members only** and
   **Friends only** list one kind. A member who has asked to become a friend at the end of
   their term is a member until that day comes. Somebody who joined as a member and has
   never paid is a friend: nobody is a member until a paid or granted term has started.

**Search**
   A name, an email address, either phone number, or a pilot certificate number, though the
   box's hint names only the first three. A full name
   works: *Ana Bracco* finds her.

**Membership**
   **Any**, the blank choice, takes in everybody. **Current** (a term covers today),
   **Expired** (a paid term has run out), and **Friend** (a friend of CalDART, including
   somebody who joined as a member and has never paid) between them cover every person
   exactly once, and the report's **Status** column prints the same three words.

**Certificate** and **Medical**
   The pilot certificate and the medical on the person's profile. **Certificate** also
   offers **Any licensed**: every certificate a pilot may act on alone, sport through
   airline transport pilot. **Medical** also offers **Has any medical**. The blank choice,
   **Any**, takes in everyone, including the people who answered "none".

**DART**
   The team the person belongs to.

**County**
   The California counties on people's profiles. Click the box to open the list of
   counties and check as many as you like; the list shows the people of any county you
   checked. Uncheck a county to take it back, or press **Clear** to take them all back at
   once. With no county checked the filter narrows nothing.

**Role**
   People who hold one role, such as DART leader or Treasurer. A system administrator is
   listed only under System administrator, even though they can do everything.

**Expiring within (days)**
   A number of days; the box takes digits only. A member who has already renewed drops out
   at once, and a life member never appears.

**Include deactivated**
   Off at first. Check it to list deactivated accounts too. The downloads never carry one,
   checked or not.

Filters combine. "Current members of one DART who expire within 30 days" is two lists and a
number.


Downloading the report
======================

**Export CSV** and **Export PDF** download the membership report for exactly what the list is
showing: the same filters and the same order, every matching person and every page. The CSV
opens in a spreadsheet, for mail merges and anything you want to sort or total. The PDF is a
landscape letter table ready to print, with your filters printed under the title and the
date and page numbers at the bottom, so it says on its face what it is a list of.

Both files carry eleven columns unless you choose others: **Name**, **Email**, **Phone**,
**DART**, **Status**, **Kind**, **Expires**, **Certificate**, **Medical**, **Medical
expires**, and **Aircraft**. **Kind** reads Member or Friend. A life member and a friend have
an empty **Expires** cell.


Choosing the columns
~~~~~~~~~~~~~~~~~~~~

**Columns**, at the right of the bar beside the export buttons, opens a list of every column
the report offers, with a box to check for each. Twelve more are on offer: **Plan**,
**Certificate number**, **Instrument** (Yes or No for a pilot, by whether **Instrument** is
among the ratings; blank for a non-pilot), **Home airport**, **Secondary airport**, **City**,
**State**, **County**, **Callsign** (the amateur radio callsign), **Joined** (the day the
first term on file began), **Member since** (the day the member says they joined), and
**Profile updated** (the day their profile was last changed). **Reset to the default
columns**, under the boxes, checks the eleven again.

Your choice changes the table on screen and both downloads together, as the panel's title,
*Columns in the table and the download*, says. You cannot uncheck the last column. Add many
columns and the PDF starts to wrap its cells, which is the point at which the CSV is the
better file. The panel closes when you click outside it, press Escape, or Tab past its
last control.

.. _saved-column-sets:

Saved column sets
~~~~~~~~~~~~~~~~~

Beside **Columns**, **Load columns** lists the sets of columns you have saved for this
report. Pick a name and its columns are checked for you, in the table and the downloads
alike. The trashcan beside a name asks
first: press it and it turns into **Delete** and **Cancel**; press **Delete** and that set
is gone, or **Cancel**, Escape, or a click elsewhere to leave it as it is. **Save columns**
keeps the boxes as they stand: type a name of up to 60 characters
and press **Save**, or press Enter. Saving under a name you already use replaces that set,
and loading a set puts its name in the box, so a set you load and change saves again under
the same name. Each of the three buttons opens its own panel under itself, and a click
outside it or Escape puts it away. Your saved sets are yours alone, and each report keeps
its own. The other screens with downloads work the same way.


If something looks wrong
========================

If a download carries more people than the screen shows, a box you had just typed in had not
applied yet; wait for the table to narrow, then download. If somebody you expect is missing,
press **Reset filters** (an empty list offers one too) and search for them by name: a filter may be hiding them, their
account may be deactivated (check **Include deactivated**), or they may be a donor, who is
never listed here. If the line beside the export buttons says *The columns didn't load; the list
shows the default ones.*, the table shows the name, email, DART, status, and expiry, and the
downloads carry the report's own default columns; reload the page to get the column chooser
back. If a
member reads **Expired** and says they renewed, an account administrator can check the
**Memberships** and **Payments** tabs of their :doc:`member-record`.
