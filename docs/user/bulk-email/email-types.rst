:roles: system_admin

===========
Email types
===========

**Email types** lists the types of bulk email CalDART sends, such as Operational,
Fundraising, and Mission. For each type it says what the email is for, who may send it, and
whether members and friends may turn it off. Only a system administrator sees it, under
**Bulk email** in the menu.

The types matter to the people who receive the email. Every member and friend can turn off
any type that allows it, on their own :doc:`../member/email-preferences` screen or from the
unsubscribe link at the foot of an email of that type, and an account administrator can do
it for them on the :doc:`../admin/member-record`. Turning off one type leaves every other
type arriving as before.


What you see
============

A table with one row per type, in the order every screen lists them. The description and
the senders wrap, so they read in full:

- **Name**, what every screen and every email calls it.
- **What it is for**, one sentence that members read beside the switch that turns it off.
  It never narrows below a readable width, and it breaks only between words.
- **Who may send it**: **DART leader**, **CalDART management**, or both. A type with
  neither reads **System administrators only**, because a system administrator can send
  every type.
- **Can be turned off**: **Yes** or **No**, with a colored dot.
- **Edit** and a trashcan, last.

On a screen too narrow for every column, **Can be turned off**, then **Who may send it**
are left out, and **Edit** and the trashcan sit one above the other; on a phone the table
scrolls sideways, says so above it, and keeps **Name** pinned at the left. With no types the
table reads *No email types yet*, with an **Add an email type** button.

Every site starts with three types: **Operational** and **Mission**, sent by CalDART
management and DART leaders, and **Fundraising**, sent by CalDART management alone. All
three can be turned off. They are ordinary types: edit them, delete them, or add more.


Adding or changing a type
=========================

Press **Add an email type**, or **Edit** on a row. The form opens above the table and takes you
to its first box, scrolling it into view. Fill it in:

**Name**
   At most 60 characters, and different from every other type's name. Capitals and
   punctuation do not make a name different: with **Mission** on the list, *mission* and
   *Mission!* are both refused with *Another email type already has this name.*
**What it is for**
   One sentence in plain words. Members read it on their **Email preferences** screen when
   deciding whether to keep the email.
**Who may send it**
   Tick **DART leader**, **CalDART management**, or both. Leave both clear to keep the type
   for system administrators.
**Recipients may turn it off**
   Ticked, each email of this type carries an unsubscribe link, and the type appears on
   everyone's **Email preferences**. Clear it only for email every member and friend must
   receive: such an email says at its foot that it cannot be turned off. Clearing the box
   keeps everyone's earlier choice, and ticking it again brings those choices back.

Press **Add type** or **Save type**. The message *Operational added.* or *Operational saved.*
confirms it, with the type's own name. **Cancel**, or Escape, closes the form and changes
nothing, and you are back on the button that opened it.


Deleting a type
===============

Press the trashcan on the row. It turns into **Delete** and **Cancel**; press **Delete** to
go ahead. *Operational deleted.* confirms it, and every member's choice about that type goes
with it.

A type that a bulk email has already used cannot be deleted, because the record of that
email names it. Its trashcan is grayed out, and a line under the table says why; holding the
pointer over the trashcan gives the reason in full: *Operational has been used for a bulk
email, so it cannot be deleted. To keep DART leaders and CalDART management from sending it,
take their roles off it instead.* Edit the type, clear both boxes under **Who may send it**,
and save.
After that only a system administrator can send it.


If something looks wrong
========================

If a member says they still receive email they turned off, open their
:doc:`../admin/member-record` (as an account administrator) and look at their **Email
preferences**. A type whose **Can be turned off** reads **No** reaches everyone whatever
they chose earlier. Email about a person's own account, such as receipts, renewal
reminders, and password links, is not bulk email and always arrives.
