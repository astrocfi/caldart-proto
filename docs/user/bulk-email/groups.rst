:roles: management

================
Recipient groups
================

**Recipient groups** keeps the people you email again and again, such as the members of your
DART, the board, or every friend whose membership has lapsed. You can then add them to a
recipient list in one step. Every member of CalDART management shares the same groups.
CalDART management finds the screen under **Bulk email** in the menu. A system administrator
can open it too.

A group is one of two kinds:

- **Fixed**: the same people every time, until you add or remove someone. Use it for a list
  of names, such as the board.
- **Live**: filters, such as *Kind: Friends only, County: Marin*. Each time you use the group,
  it finds whoever matches the filters at that moment. So it keeps up as people join, move,
  and leave.


The list
========

There is one line per group, in order of name:

- **Name** opens the group's own page, below, where you change it.
- **Type**: *Fixed* or *Live*.
- **People**: how many people the group has today. For a live group, CalDART runs the filters
  again to count them. It says *Unknown* if the group's filters need fixing (below).
- **Last edited**: the day the group, its people, or its filters last changed.
- **Actions**, last: the trashcan deletes the group after you press **Delete**. Emails the
  group was added to keep their people, and their recipient lists still name the group that
  brought each person in. **Download list** saves the group's people as a spreadsheet file
  (CSV) named after the group, such as *caldart-group-board.csv*. It has each person's name,
  email address, kind, and DART. An empty group doesn't offer one.

On a narrow screen, **Type** and then **Last edited** drop out. On a phone, the table scrolls
sideways, a note above it says so, and **Name** stays pinned at the left. Until the first
group is saved, the table says *No recipient groups yet* and has its own **New group**
button.

**New group** asks for a **Name** and the **Type of group**. Then **Add group** opens the
group's page, empty, for you to fill in. The cursor starts in **Name**. The Escape key closes
the form, as **Cancel** does, and puts you back on **New group**. Two groups can't share a
name, even if the capital letters differ. The usual way to make a group is **Save as a
group** on the compose screen, below.


A group's page
==============

**Name** shows the group's name. To change it, type the new name and press **Save changes**.
Emails the group was added to earlier keep the name it had then.

A fixed group's **People** card lists everybody in it, with **Name**, **Email**, **Kind**,
**DART**, and a trashcan at the end. A narrow screen leaves out **DART**, then **Kind**, and
then **Email**. A deactivated account shows *(deactivated)* after the name, and a send skips
it. To add somebody, type part of their name or email address in **Add a person** and choose
them from the list that appears. A line such as *Ann Able added.* confirms it. If the person
is in the group already, you see *Ann Able is in this group already.* The trashcan on a row
takes that person out of the group after you press **Remove**.

A live group's **Filters** card lists its filters in words, each with a trashcan that takes
it out after you press **Remove**. To add more, choose them in the filter bar and press **Add
these filters**. These are the same filters :doc:`compose` uses. If you haven't chosen any,
this adds every member and friend. A line such as *Added the filters County: Napa.* confirms
it, and the bar empties for the next ones. If the group has those filters already, you see
*This group has these filters already.* The group has everybody any of its filters find. A
live group without any filters is empty. The **Who it finds now** card lists the people the
filters find today.

A filter can stop working after it was saved, for example when its DART is deleted. The
group's line on the list then says *This group's filters need fixing* and links to its page.
There, each filter the member list doesn't accept any more says so. Until you take those
filters out, the group's people can't be listed or downloaded, and **Add a saved group**
refuses the group with the same sentence. Every other group works as usual.

**Download list**, under the people, saves them as a spreadsheet file named after the group.
An empty group, such as a live group whose filters don't find anybody, doesn't offer one.


Using a group
=============

On :doc:`compose`, **Add a saved group** beside **Add these people** opens a **Group**
drop-down. It shows each group with its kind and how many people it has. Choose one and press
**Add this group** to add everybody in it at that moment. A line such as *Added 12 people; 3
were already on the recipient list.* confirms it. As with any add, nobody is added twice. On
the recipient list, the **Chosen by** column says *Group: Board* for the people the group
brought in. It keeps that name if the group is renamed or deleted later.

Beside **Add these people**, **Save as a group** saves the search your filters make as a group
to use again, whoever is on the recipient list. Give it a **Group name** and choose the **Type
of group** by pressing the button or its name:

- **Fixed** saves everybody the search matches at that moment, including people who would be
  skipped for this email.
- **Live** saves the filters, so the group finds whoever matches them each time you use it.

The popup stays open while you fill it in. **Cancel**, Escape, or a click outside it closes
it. **Add group** saves the group, and a line such as *Saved as the group Board.* links to
its page.
