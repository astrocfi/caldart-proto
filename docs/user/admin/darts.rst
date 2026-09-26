=====
DARTs
=====

**DARTs** is the list of teams a member can join. A DART (Disaster Airlift Response Team) is
one of the local teams that fly for CalDART. Everything on this screen shows up in the
**DART** list on the join form, on a member's profile, and in the DART filter on
:doc:`members`, so adding a team here is all it takes to start putting people on it.

Only an account administrator finds it, under **Administration** in the menu. A system
administrator can open it too.


What you see
============

One row per DART, in name order until you click a column heading to sort:

- **Name**, the name members see.
- **Airport**, the fields the team flies from.
- **Website**, a **Visit** link to the team's own site, if it has one.
- **People**, how many people run the team.
- **Roster**, how many of them receive the team's monthly roster by email. Only people with
  an email address count, since a roster cannot reach anyone else.
- **Members**, how many members and friends are on the team. Click the number to open the
  member list filtered to that team.
- **Status**, **Active** or **Inactive**.
- **Edit**, which opens the team's form.

With no teams yet the table says *No DARTs yet*.


Adding a DART
=============

**Add a DART** opens a short form above the table:

**Name**
   What members will see in the list, such as "Palo Alto". Required.

**Airports**
   The fields the team flies from, as three-character identifiers separated by commas: PAO,
   or CCR, C83 for a team with two fields. Paste KCRQ and the leading K comes off. At least
   one is required and twelve at most. A DART is known by its fields, so there is no town to
   fill in.

**Website**
   The team's own site, if it has one.

Press **Add DART**, or **Cancel**. The new team appears on the join form straight away, so its
pilots can choose it the same day.


The people who run it
=====================

**DART management** holds as many people as the team needs, each with a **Name** and a
**Title**, and optionally a **Phone** and an **Email**.

- **Add a person** adds a row. It is grayed out while the last row has no name, so give the
  person above a name first.
- Tick **Roster** on the row of each person who should receive the team's roster by email.
- The arrows at the head of a row move that person up or down. The order is the order the
  team's page on the public website lists them in, so put the leader first. A row with no
  name cannot be moved, and neither can its neighbors past it.
- The trashcan at the end of a row takes that person off the list.

The people are saved with the rest of the form.


Changing a DART
===============

**Edit** opens the same form on an existing team, headed with its name. Press **Save DART**.
Renaming a team is safe: the members on it stay on it.

**Making one inactive.** Untick **Active** (*Active — untick to make the DART inactive
without losing its history*) and save. The team disappears from the join form and from the
list on a member's profile, and everybody already on it stays on it, so the history and the
reports still read correctly. Tick the box again to bring the team back.


Deleting a DART
===============

**Delete this DART**, at the foot of the edit form, asks before it acts. When the team has
members or a page on the public website, the question says what the delete leaves behind,
for example *Deleting Napa makes its 12 members unaffiliated and unlinks 1 website page.
This cannot be undone.* The members come off the team and stay members, with nothing else on
their record touched. A website page for the team keeps its own words and loses only its
link to the team. Press **Delete for good**, or **Keep**.

Deleting is permanent, so a team that has stopped flying is better made inactive.


What happens next
=================

Early each month every active team's roster goes by email to each person ticked **Roster**.
The subject is the team's name, the word *roster*, and the date. The :doc:`reports` screen
lists the rosters, shows when each was last sent, and can send them all at once.

A team's own page on the public website is kept by a website administrator. The **DART**
field on that page is what ties the two together.


If something looks wrong
========================

*Give the DART a name.* and *Give the DART at least one airport.* mean a required box is
empty. *Use three-character identifiers, separated by commas, like CCR, C83.* means an
airport is written some other way, and *That list names the same airport twice.* means what
it says. A **Roster** count lower than the people you ticked means some of them have no
email address. After a team is deleted, an unpublished draft of its website page still names
it, and publishing that draft fails: ask the website administrator to open the page, clear
its **DART** field, and publish again.
