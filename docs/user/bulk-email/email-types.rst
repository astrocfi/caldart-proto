:roles: system_admin

===========
Email types
===========

**Email types** lists the kinds of bulk email CalDART sends, such as Operational,
Fundraising, and Mission. For each kind it says what the email is for, who may send it, and
whether members and friends may turn it off. Only a system administrator sees it, under
**Bulk Email** in the menu.

The kinds matter to the people who receive the email. Every member and friend can turn off
any kind that allows it, on their own :doc:`../member/email-preferences` screen or from the
unsubscribe link at the foot of an email of that kind, and an account administrator can do
it for them on the :doc:`../admin/member-record`. Turning off one kind leaves every other
kind arriving as before.


What you see
============

A table with one row per kind, in the order every screen lists them. The description and
the senders wrap, so they read in full:

- **Name**, what every screen and every email calls it.
- **What it is for**, one sentence that members read beside the switch that turns it off.
- **Who may send it**: **DART leader**, **CalDART management**, or both. A kind with
  neither reads **System administrators only**, because a system administrator can send
  every kind.
- **Can be turned off**: **Yes** or **No**, with a colored dot.
- **Edit** and a trashcan.

Every site starts with three kinds: **Operational** and **Mission**, sent by CalDART
management and DART leaders, and **Fundraising**, sent by CalDART management alone. All
three can be turned off. They are ordinary kinds: edit them, delete them, or add more.


Adding or changing a kind
=========================

Press **Add an email type**, or **Edit** on a row, and fill in the form:

**Name**
   At most 60 characters, and different from every other kind's name. Capitals and
   punctuation do not make a name different: with **Mission** on the list, *mission* and
   *Mission!* are both refused with *Another email type already has this name.*
**What it is for**
   One sentence in plain words. Members read it on their **Email preferences** screen when
   deciding whether to keep the email.
**Who may send it**
   Tick **DART leader**, **CalDART management**, or both. Leave both clear to keep the kind
   for system administrators.
**Recipients may turn it off**
   Ticked, each email of this kind carries an unsubscribe link, and the kind appears on
   everyone's **Email preferences**. Clear it only for email every member and friend must
   receive: such an email says at its foot that it cannot be turned off. Clearing the box
   keeps everyone's earlier choice, and ticking it again brings those choices back.

Press **Add type** or **Save type**. The message *Operational added.* or *Operational saved.*
confirms it, with the kind's own name. **Cancel** closes the form and changes nothing.


Deleting a kind
===============

Press the trashcan on the row. It turns into **Delete** and **Keep**; press **Delete** to
go ahead. *Operational deleted.* confirms it, and every member's choice about that kind goes
with it.

A kind that a bulk email has already used cannot be deleted, because the record of that
email names it. Its trashcan is greyed out, and a line under the table says why; holding the
pointer over the trashcan gives the reason in full: *Operational has been used for a bulk
email, so it cannot be deleted. To keep DART leaders and CalDART management from sending it,
take their roles off it instead.* Edit the kind, clear both boxes under **Who may send it**,
and save.
After that only a system administrator can send it.


If something looks wrong
========================

If a member says they still receive email they turned off, open their
:doc:`../admin/member-record` (as an account administrator) and look at their **Email
preferences**. A kind whose **Can be turned off** reads **No** reaches everyone whatever
they chose earlier. Email about a person's own account, such as receipts, renewal
reminders, and password links, is not bulk email and always arrives.
