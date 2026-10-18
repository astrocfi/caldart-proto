:roles: system_admin

===========
Email types
===========

**Email types** lists the types of bulk email CalDART sends, such as Operational,
Fundraising, and Mission. For each type it says what the email is for, who may send it, and
whether members and friends may turn it off. Only a system administrator sees it, under
**Bulk email** in the menu.

The types matter to the people who receive the email. Every member and friend can turn off
any type that allows it. They do it on their own :doc:`../member/email-preferences` screen,
or with the unsubscribe link at the bottom of an email of that type. An account
administrator can do it for them on the :doc:`../admin/member-record`. Turning off one type
doesn't stop any other type.


What you see
============

You see a table with one row per type, in the order every screen lists them. The description
and the senders wrap, so you can read them in full:

- **Name**: what every screen and every email calls the type.
- **What it is for**: one sentence that members read beside the switch that turns it off.
  The column never gets too narrow to read, and it breaks only between words.
- **Who may send it**: **DART leader**, **CalDART management**, or both. A type with
  neither says **System administrators only**, because a system administrator can send
  every type.
- **Can be turned off**: **Yes** or **No**, with a colored dot.
- **Edit** and a trashcan, last.

On a narrow screen, **Can be turned off** and then **Who may send it** drop out, and **Edit**
and the trashcan sit one above the other. On a phone, the table scrolls sideways, a note
above it says so, and **Name** stays pinned at the left. If there aren't any types, the table
says *No email types yet* and has a **New email type** button.

Every site starts with three types. **Operational** and **Mission** are sent by CalDART
management and DART leaders, and **Fundraising** by CalDART management alone. All three can
be turned off. They are ordinary types: you can edit them, delete them, or add more.


Adding or changing a type
=========================

Press **New email type**, or **Edit** on a row. The form opens above the table and scrolls
to its first box, with the cursor in it. Fill it in:

**Name**
   At most 60 characters, and different from every other type's name. Capitals and
   punctuation don't make a name different. With **Mission** on the list, *mission* and
   *Mission!* are both refused with *Another email type already has this name.*
**What it is for**
   One sentence in plain words. Members read it on their **Email preferences** screen when
   they decide whether to keep the email.
**Who may send it**
   Check **DART leader**, **CalDART management**, or both. Leave both clear to keep the type
   for system administrators.
**Recipients may turn it off**
   When this is checked, each email of this type has an unsubscribe link, and the type
   appears on everyone's **Email preferences**. Clear it only for email every member and
   friend must receive. Such an email says at its foot that it can't be turned off. Clearing
   the box keeps everyone's earlier choice, and checking it again brings those choices back.

Press **Add email type** or **Save changes**. The message *Operational added.* or
*Operational saved.*, with the type's own name, confirms it. **Cancel**, or Escape, closes
the form without changing anything, and you are back on the button that opened it.


Deleting a type
===============

Press the trashcan on the row. It turns into **Delete** and **Cancel**. Press **Delete** to
go ahead. *Operational deleted.* confirms it, and every member's choice about that type is
deleted with it.

You can't delete a type that a bulk email has already used, because the record of that
email names it. Its trashcan is grayed out, and a line under the table says why. Hold the
pointer over the trashcan to see the reason in full: *Operational has been used for a bulk
email, so it cannot be deleted. To keep DART leaders and CalDART management from sending it,
take their roles off it instead.* So edit the type, clear both boxes under **Who may send
it**, and save. After that, only a system administrator can send it.

Every mission callout goes as the **Mission** type, so you can't delete it or rename it. You
can still change its description, its senders, and whether members may turn it off.


If something looks wrong
========================

If a member says they still receive email they turned off, open their
:doc:`../admin/member-record` (as an account administrator) and look at their **Email
preferences**. A type whose **Can be turned off** says **No** reaches everyone, whatever
they chose earlier. Email about a person's own account, such as receipts, renewal
reminders, and password links, isn't bulk email, and it always arrives.
