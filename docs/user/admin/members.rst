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

The caption over the table counts the people who match your filters, such as *42 people
match*. The table shows 25 people at a time. When there are more, the foot of the list
says, for example, *Showing 1–25 of 212*, between **Previous** and **Next**. When there
isn't a page to go to, that button has a dashed frame. Moving to another page scrolls back
to the top of the table.

The table shows the same columns as the membership report you download, and **Columns**
changes both (see `Choosing the columns`_). To begin with, it shows the report's eleven:

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
   A colored dot and the state of the membership: **Current** (green), **Expiring soon** in
   its last 30 days (amber), **Expired** (red), **Never expires** for a life member
   (green), **Not yet paid** (gray) for a member who hasn't paid their first dues, or
   **Friend** (gray).

**Kind**
   Member or Friend. A member who hasn't paid yet shows Member.

**Expires**
   The date the membership runs out. For a life member it says **Never**, for a friend
   **Friend**, and for a member who hasn't paid yet **None yet**. The date is the end of the
   person's unbroken membership. Somebody who renews in March for a term that starts in
   July already shows next July's date, so you never have to add up terms yourself.

**Certificate** and **Medical**
   The pilot certificate and the medical on the person's profile. An airline transport
   pilot certificate shows as **ATP**.

**Medical expires**
   The medical's date, after a mark that answers the question people most often open the
   list for: who can fly today? A green check means the person holds a pilot certificate
   and their medical is current. A red cross means the medical has lapsed, and a dash means
   the person isn't a pilot.

**Aircraft**
   The N-numbers of the aircraft on their profile.

On a narrower screen, the table drops default columns, one at a time, until the rest fit:
**Email**, then **DART**, then **Phone**, **Kind**, and **Aircraft**, so a laptop keeps the
pilot columns. After those go **Medical**, **Certificate**, and **Medical expires**.
**Name**, **Status**, and **Expires** always stay, and so does any column you add to the
defaults. A line above the table names any column it hid, and the downloads still include
it. On a phone, the table can still be wider than the screen. Then the line above it says
*Scroll sideways for more.* before the hidden columns, a shadow marks the edge where there
is more, and the names stay pinned at the left while you scroll. With a keyboard, Tab to
the table and use the arrow keys.

For an account administrator, a name opens the :doc:`member-record`. For a DART leader, it
opens that person's :doc:`member-check` card. The name of a deactivated account doesn't open
anything for a DART leader, since the member check never shows one. Only an account
administrator sees the **New member** button (see :doc:`new-member`). If a DART leader's
profile names a DART, they see **Show my DART** there instead. It sets the **DART** filter
to their own team, which gives them their roster.


Sorting
=======

The list opens sorted by name, and the arrow beside **Name** shows it. You can sort by
**Name**, **Email**, **DART**, **Expires**, **Joined**, and **Profile updated**. Their
headings carry an arrow, faint until you use it. Click a heading to sort by it, and click
again to reverse the order. The whole list is sorted, every page of it. People who tie are
put in name order, so a sorted list comes out the same every time. The other headings
don't have an arrow and don't sort.


Filtering
=========

The filter bar sits above the table. A list or a checkbox applies as soon as you change it,
and a box you type in applies after a short pause. You don't press an Apply button.
**Reset filters**, at the end of the bar, clears the filters but keeps the sort. The
filters and the sort are part of the page's address, so you can bookmark a filtered list
or send it to a colleague.

**Kind**
   **Any kind**, the first choice, lists members and friends together. **Members only** and
   **Friends only** list one kind. A member who has asked to become a friend at the end of
   their term stays a member until that day. Somebody who joined as a member and has never
   paid is listed with the members.

**Search**
   A name, an email address, either phone number, or a pilot certificate number, although
   the hint in the box mentions only the first three. A full name works too: *Ana Bracco*
   finds her.

**Membership**
   **Any**, the blank choice, includes everybody. The other four choices cover every person
   exactly once: **Current** (a term covers today), **Expired** (a paid term has run out),
   **Not yet paid** (somebody who joined as a member and has never paid), and **Friend** (a
   friend of CalDART). The report's **Status** column uses the same words.

**Certificate** and **Medical**
   The pilot certificate and the medical on the person's profile. **Certificate** also
   offers **Any licensed**: every certificate a pilot may act on alone, from sport through
   airline transport pilot. **Medical** also offers **Has any medical**. The blank choice,
   **Any**, includes everyone, even the people who answered "none".

**DART**
   The team the person belongs to.

**County**
   The California counties on people's profiles. Click the box to open the list of
   counties, and check as many as you like. The list then shows the people in any county
   you checked. Uncheck a county to remove it, or press **Clear** to remove them all at
   once. While no county is checked, the filter doesn't narrow the list.

**Role**
   People who hold one role, such as DART leader or Treasurer. A system administrator is
   listed only under System administrator, even though they can do everything.

**Expiring within (days)**
   A number of days; the box takes digits only. A member who has already renewed drops out
   at once, and a life member never appears.

**Include deactivated**
   Off to begin with. Check it to list deactivated accounts too. The downloads never
   include them, checked or not.

Filters combine. "Current members of one DART who expire within 30 days" takes two lists
and a number.


Downloading the report
======================

**Export CSV** and **Export PDF** download the membership report for exactly what the list
shows: the same filters and the same order, with every matching person on every page. The
CSV opens in a spreadsheet, for mail merges and anything you want to sort or total. The PDF
is a table on landscape letter paper, ready to print. It prints your filters under the
title, and the date and page numbers at the bottom, so anyone holding it can see what it
lists.

Both files have eleven columns unless you choose others: **Name**, **Email**, **Phone**,
**DART**, **Status**, **Kind**, **Expires**, **Certificate**, **Medical**, **Medical
expires**, and **Aircraft**. **Kind** says Member or Friend. A life member, a friend, and a
member who hasn't paid yet have an empty **Expires** cell.


Choosing the columns
~~~~~~~~~~~~~~~~~~~~

**Columns**, at the right of the bar beside the export buttons, opens a list of every column
the report offers, with a box to check for each. Twelve more are available: **Plan**,
**Certificate number**, **Instrument** (Yes or No for a pilot, depending on whether
**Instrument** is among the ratings; blank for a non-pilot), **Home airport**, **Secondary
airport**, **City**, **State**, **County**, **Callsign** (the amateur radio callsign),
**Joined** (the day the first term on file began), **Member since** (the day the member
says they joined), and **Profile updated** (the day their profile last changed). **Reset to
the default columns**, under the boxes, checks the eleven again.

Your choice changes the table on screen and both downloads together, as the panel's title,
*Columns in the table and the download*, says. You can't uncheck the last column. If you
add many columns, the PDF starts to wrap its cells, and at that point the CSV is the better
file. The panel closes when you click outside it, press Escape, or Tab past its last
control.

.. _saved-column-sets:

Saved column sets
~~~~~~~~~~~~~~~~~

Beside **Columns**, **Load columns** lists the sets of columns you have saved for this
report. Pick a name, and its columns are checked for you, in the table and the downloads
alike. The trashcan beside a name asks first: press it, and it turns into **Delete** and
**Cancel**. Press **Delete** to remove that set, or **Cancel**, Escape, or a click elsewhere
to keep it. **Save columns** keeps the boxes as they are: type a name of up to 60
characters and press **Save**, or press Enter. If you save under a name you already use,
the new set replaces the old one. Loading a set puts its name in the box, so if you load a
set and change it, it saves again under the same name. Each of the three buttons opens its
own panel below it, and a click outside the panel or Escape closes it. Your saved sets are
yours alone, and each report keeps its own. The other screens with downloads work the same
way.


If something looks wrong
========================

If a download has more people than the screen shows, a box you had just typed in hadn't
applied yet. Wait for the table to narrow, then download. If somebody you expect is
missing, press **Reset filters** (an empty list offers one too) and search for them by
name. A filter may be hiding them, their account may be deactivated (check **Include
deactivated**), or they may be a donor, who is never listed here. If the line beside the
export buttons says *The columns didn't load; the list shows the default ones.*, the table
shows the name, email, DART, status, and expiry. The downloads use the report's own default
columns. Reload the page to get the column chooser back. If a member shows **Expired** but
says they renewed, an account administrator can check the **Memberships** and **Payments**
tabs of their :doc:`member-record`.
