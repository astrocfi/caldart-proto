:roles: management

================
Recipient groups
================

**Recipient groups** keeps the people you email again and again, such as the board, the
pilots of one DART, or every friend whose membership has lapsed, so you add them to a batch
in one step. Every member of CalDART management shares the same groups. CalDART management
opens it as **Recipient groups** under **Bulk Email** in the menu. A system administrator can
open it too.

A group is one of two kinds:

- **Fixed**: the same people every time, until you add or remove someone. Use it for a list
  of names, such as the board.
- **Live**: filters, such as *Kind: Friends only, County: Marin*. Each time the group is used
  it finds whoever matches the filters then, so it follows people joining, moving, and
  leaving.


The list
========

One line per group, by name:

- **Name** opens the group's own page, below, where it is changed.
- **Actions**: the trashcan deletes the group after you press **Delete**. Emails the group
  was added to keep their people, and their batch still names the group that brought each
  person in. **Download list** saves the group's people as a spreadsheet file (CSV) named
  after the group, such as *caldart-group-board.csv*, with each person's name, email address,
  kind, and DART; a group with nobody in it offers none.
- **Kind**: *Fixed* or *Live*.
- **People**: how many people the group holds now. A live group's filters are run again to
  count them. It reads *Unknown* for a live group whose filters need fixing, below.
- **Last edited**: the day the group, its people, or its filters last changed.

Before the first group is saved the table reads *No recipient groups yet*. On a phone the
table scrolls sideways.

**New group** asks for a **Name** and the **Kind of group**, then **Make the group** opens its
page, empty, to fill in. The cursor starts in **Name**; the Escape key closes the form, as
**Cancel** does, and puts you back on **New group**. No two groups may share a name, in any mix of capital and small
letters. The usual way to make a group is **Save as a group** on the compose screen, below.


A group's page
==============

**Name** shows the group's name; change it and press **Save name**. Emails the group was
added to before keep the name it had then.

A fixed group's **People** card lists everybody in it, with **Name**, **Email**, **Kind**,
**DART**, and the trashcan. A deactivated account reads *(deactivated)* after the name; a send
skips it. To add somebody, type part of their name or email address in **Add a person** and
choose them from the list that appears; a line such as *Ann Able added.* says so. Somebody
already in the group is refused with *Ann Able is in this group already.* The trashcan on a
row takes that person out of the group after you press **Remove**.

A live group's **Filters** card lists its filters in words, each with a trashcan that takes it
out after you press **Remove**. To add more, choose them in the filter bar, the same filters
:doc:`compose` uses, and press **Add these filters**; with nothing chosen, that adds every
member and friend. A line such as *Added the filters County: Napa.* says so, and the bar
empties for the next. Filters the group has already are refused with *This group has these
filters already.* The group holds everybody any of its filters find. A live group with no
filters holds nobody. The **Who it finds now** card lists them as of now.

A filter can stop working after it was saved, such as a DART that was later deleted. The
group's line on the list then reads *This group's filters need fixing*, linking to its page,
where the filters the member list no longer accepts say so. Until you take them out, the
group's people cannot be listed or downloaded, and **Add a saved group** refuses that group
with the same sentence. Every other group works as usual.

**Download list**, under the people, saves them as a spreadsheet file named after the group;
a group with nobody in it, such as a live group whose filters find nobody, offers none.


Using a group
=============

On :doc:`compose`, **Add a saved group** beside **Add to batch** lists the groups, each with
its kind and how many people it holds. Choosing one adds everybody in it now, and a line such
as *Added 12 people; 3 were already in the batch.* says so: as with any add, nobody is added
twice. The batch's **Chosen by** column reads *Group: Board* for the people the group brought
in, and keeps that name if the group is renamed or deleted later.

Under the batch, **Save as a group** keeps the batch as a group to use again. Give it a
**Group name** and choose the **Kind of group**:

- **Fixed** keeps everybody in the batch now, including people who will be skipped for this
  email.
- **Live** keeps the filters behind the batch, once each, so the group finds whoever matches
  them each time it is used. People you took out of the batch one at a time come back when
  the filters find them. A batch with people a fixed group brought in, or copied from
  another email with **Duplicate**, has no filters to keep for them, and is refused with
  *Save it as a fixed group instead.* A batch with people from a group since deleted is
  refused the same way, saying the group was deleted.

**Save group** keeps it, and a line such as *Saved as the group Board.* links to its page.
