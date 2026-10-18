:roles: account_admin

=====
DARTs
=====

**DARTs** is the list of teams a member can join. A DART (Disaster Airlift Response Team) is
one of the local teams that fly for CalDART. Every team on this screen appears in the
**DART** list on the join form, on a member's profile, and in the DART filter on
:doc:`members`. Adding a team here is all it takes to start putting people on it.

Only an account administrator finds it, under **Administration** in the menu. A system
administrator can open it too.


What you see
============

There is one row per DART, in name order until you click a column heading to sort. The
arrow beside a heading shows the order. **Website** and **Actions** don't sort.

- **Name**, the name members see.
- **Airport**, the fields the team flies from.
- **Website**, a **Visit** link to the team's own site, if it has one.
- **People**, how many people run the team.
- **Roster**, how many of them get the team's monthly roster by email. Only people with an
  email address count, since a roster can't reach anyone else.
- **Members**, how many members and friends are on the team. Click the number to open the
  member list filtered to that team.
- **Status**, **Active** or **Inactive**.
- **Actions**, where **Edit** opens the team's form.

On a narrower screen, the table drops **Website**, then **People**, **Airport**,
**Roster**, and **Members**, so the name, the status, and **Edit** stay in sight on a phone.

Until you add a team, the table holds a single line: *No DARTs yet*.


Adding a DART
=============

**New DART** opens a short form above the table and puts you in its first box:

**Name**
   What members will see in the list, such as "Palo Alto". Required.

**Airports**
   The fields the team flies from, as three-character identifiers separated by commas: PAO,
   or CCR, C83 for a team with two fields. Leave off the leading K, so CRQ for KCRQ; if you
   paste KCRQ, the K is dropped. Enter at least one and at most twelve. A DART is known by
   its fields, so there isn't a town to fill in.

**Website**
   The team's own site, if it has one.

Press **Add DART**, or **Cancel**. The new team appears on the join form straight away, so
its pilots can choose it the same day.


The people who run it
=====================

**DART management** holds as many people as the team needs, each with a **Name** and a
**Title**, and optionally a **Phone** and an **Email**. A name typed all in capitals or all
in lower case is saved in title case, so *SMITH* becomes **Smith**. A name typed in mixed
case is kept as typed.

- **Add a person** adds a row. It is grayed out while the last row is missing a name, so
  give the person above a name first.
- Check **Roster** on the row of each person who should get the team's roster by email.
- The arrows at the head of a row move that person up or down. The team's page on the
  public website lists the people in this order, so put the leader first. You can't move a
  row without a name, or move its neighbors past it.
- The trashcan at the end of a row asks first: press it and it turns into **Remove** and
  **Cancel**. Press **Remove** to take that person off the list. **Cancel**, Escape, or a
  click elsewhere leaves them on it.

The people are saved with the rest of the form.


Changing a DART
===============

**Edit** opens the same form for an existing team, above the table, with the team's name at
its head, and puts you in its first box. Press **Save changes**. Escape closes the form, as
**Cancel** does, and you land back on the row's **Edit**.
You can safely rename a team: its members stay on it.

**Making one inactive.** Uncheck **Active** and save. The line under the box says *Uncheck
to make the DART inactive without losing its history.* The team disappears from the join
form and from the list on a member's profile. Everybody already on the team stays on it, so
the history and the reports stay correct. Check the box again to bring the team back.


Deleting a DART
===============

**Delete this DART**, at the bottom of the edit form, asks before it acts: it turns into a
red **Delete** and **Cancel**. If the team has members or a page on the public website, a
line above the buttons says what deleting it will do, for example *Deleting Napa makes its
12 members unaffiliated and unlinks 1 website page. This cannot be undone.* The members come
off the team but stay members, and the rest of their record stays as it was. A website page
for the team keeps its own words and loses only its link to the team. Press **Delete**, or
press **Cancel**, Escape, or click elsewhere to keep the team.

Deleting is permanent, so it is better to make a team that has stopped flying inactive.


What happens next
=================

Early each month, every active team's roster goes by email to each person with **Roster**
checked. The subject is the team's name, the word *roster*, and the date. The
:doc:`subscriptions` screen lists the rosters, shows when each was last sent, and can send
them all at once.

Each person with **Roster** checked also hears about every sign-up that chooses the team.
The email names the new member or friend and links to their record. The
:doc:`notifications` page describes it under *Notification: Sign-up*.

A website administrator looks after each team's own page on the public website. The
**DART** field on that page ties the page to the team.


If something looks wrong
========================

*Give the DART a name.* and *Give the DART at least one airport.* mean a required box is
empty. *Use three-character identifiers, separated by commas, like CCR, C83.* means an
airport is written some other way. *That list names the same airport twice.* means just
what it says. If the **Roster** count is lower than the number of people you checked, some
of them don't have an email address. After you delete a team, an unpublished draft of its
website page still names it, and publishing that draft fails. Ask the website administrator
to open the page, clear its **DART** field, and publish again.
