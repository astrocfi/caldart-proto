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
:doc:`compose`, or kept as a group on :doc:`groups`.


The list
========

One line per template, by name:

- **Name**: what the template is called when you choose it.
- **Subject**: the subject it starts an email with.
- **Type**: the kind of email it starts as, such as *Operational*, or a dash for none.
- **Last edited**: the day it last changed.
- **Edit** opens the template in the form below the heading, and the trashcan deletes it
  after you press **Delete**. Emails already started from it keep their words.

Before the first template is saved the table reads *No templates yet*. On a narrow screen the
table scrolls sideways.


Making and changing a template
==============================

**New template** opens an empty form; **Edit** opens it on one template, which is also how
you rename it. The form is the compose screen's **What it says** card with a name:

- **Name**: required, such as *Monthly newsletter*. No two templates may share a name, in
  any mix of capital and small letters.
- **Type of email**: the kind of email a draft started from it takes, or **No type** to
  choose one in each draft.
- **Subject**, **Reply-To address** (where replies go; leave it blank for the usual
  address), and **Message**, with the same buttons as on :doc:`compose`, **Insert field**
  among them. A field such as *{first_name}* stays as written in the template and is filled
  in for each person when an email goes.

**Save template** keeps it, and a line such as *Monthly newsletter saved.* says so; **Cancel**
closes the form without saving. A refused field says why under it, as on the compose screen.

A quicker way to make a template is **Save as a template** on the compose screen, which keeps
the message you are writing under the name you give it.


Using a template
================

On :doc:`compose`, **Start from a template** at the top of **What it says** lists the
templates. Choose one and press **Use this template**: the email takes the template's subject,
message, and type. The people in the batch stay. When you have already written something, it
asks first, saying the template replaces the subject and the message you have written, and
goes ahead only once you press **Replace my words**.

The email is a copy. Changing it afterward leaves the template as it was, and changing the
template later leaves the emails already started from it as they are.
