:roles: management

=========
Templates
=========

**Templates** keeps the messages you send again and again, such as the monthly newsletter, a
meeting notice, or a call for volunteers, so a new email starts from one instead of from a
blank page. Every member of CalDART management shares the same templates. CalDART management
opens it as **Templates** under **Bulk Email** in the menu. A system administrator can open it
too.

A template holds a message and nobody to send it to: who gets an email is chosen on
:doc:`compose`, or kept as a recipient group on :doc:`groups`.


The list
========

One line per template, by name:

- **Name**: what the template is called when you choose it. Press it to open the template
  in the form below the heading.
- **Subject**: the subject it starts an email with.
- **Type**: the type of email it starts as, such as *Operational*, or a dash for none.
- **Last edited**: the day it last changed.
- **Actions**, last: the trashcan, which deletes the template after you press **Delete**.
  Emails already started from it keep their words.

On a screen too narrow for every column, **Type**, then **Last edited**, then **Subject** are
left out; on a phone the table scrolls sideways, says so above it, and keeps **Name** pinned
at the left. Before the first template is saved the table reads *No templates yet*, with its
own **New template** button.


Making and changing a template
==============================

**New template** opens an empty form; a template's name opens it on that template, which is
also how you rename it. The cursor starts in the form's first box; the Escape key closes the
form, as **Cancel** does, and puts you back on the button or name that opened it. The form is
the compose screen's **What it says** card with a name:

- **Name**: required, such as *Monthly newsletter*. No two templates may share a name, in
  any mix of capital and small letters.
- **Type of email**: one button for each type, with the sentence saying what it is for, as
  on the compose screen; a draft started from the template takes that type. **No type**
  leaves the choice to each draft.
- **Subject**, **Reply-To** (where replies go; the hint under it names the address used
  when you leave it empty, as on the compose screen), and **Message**, with the same
  buttons as on :doc:`compose`, **Insert field** among them. A field such as **First name**
  shows in the message as a chip, as it does there, stays a field in the template, and is
  filled in for each person when an email goes.

**Save template** keeps it, and a line such as *Monthly newsletter saved.* says so; **Cancel**
closes the form without saving. A refused field says why under it, as on the compose screen.

A quicker way to make a template is **Save as a template** at the top of **What it says** on
the compose screen. It asks for a **Template name** and keeps the subject, message, type, and
Reply-To address you have there; a line such as *Saved as the template Monthly newsletter.
Find it under Templates.* says so, with **Templates** a link to this screen.


Using a template
================

On :doc:`compose`, **Start from a template** at the top of **What it says** lists the
templates. Choose one and press **Use this template**: the email takes the template's subject,
message, type, and Reply-To address (the usual address when the template leaves it blank).
The people in the batch stay. On a scheduled email, a different type takes it back to your
drafts, as :doc:`drafts` explains. When you have already written something, it
asks first, saying the template replaces the subject, the message, and the Reply-To address
you have, and the type too when the template has one, and goes ahead only once you press
**Replace my words**.

The email is a copy. Changing it afterward leaves the template as it was, and changing the
template later leaves the emails already started from it as they are.
