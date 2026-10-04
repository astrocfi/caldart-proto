:roles: system_admin

===================
Health and database
===================

**Health and database** shows how the server is doing, the database backups it holds, and the
aircraft database it loads from the FAA. Only a system administrator sees it, under
**System** in the menu, beside :doc:`sent-emails` and :doc:`scheduled`. Opening **System**
on its own lands here.

A system administrator can do everything any other role can do. Keep the role to the one or
two people who run the site, and give everyone else the narrower role that fits their job on
the :doc:`user-record`. Anything that has to happen on the server itself, such as installing
an upgrade, restoring a backup, or changing the settings, is a job for the person who
installed the site.

The page has three panels, top to bottom: **Health**, **Backups**, and **Aircraft
database**.


Health
======

Six checks, each with a value and its status, **OK**, **Warning**, or **Attention**. **Refresh**
runs them again.

- **Database**: whether the site can reach its database. Anything but *ok* means the site is
  down or about to be. Tell whoever runs the server at once.
- **Pending migrations**: changes to the database that arrived with an upgrade and have not
  been applied. It should read 0. Anything else means an upgrade was left half finished.
- **Disk free**: the space left where backups are kept. It warns below 2,048 MB and asks for
  attention below 512 MB. Old backups are the usual reason; download the ones worth keeping
  and ask for the rest to be deleted from the server.
- **Last backup**: when the newest backup was taken. It warns after a week, and asks for
  attention after a month or when there has never been one. Take one from the next panel.
- **Version**: which release is running. Quote it when you report a problem.
- **Debug mode**: must read *off*. If a live site reads *on*, have it fixed at once, because
  it shows internal details to anyone who causes an error.


Backups
=======

The table lists every backup on the server, newest first, with its **File** name, when it
was **Taken**, its **Size**, and last a **Download** link. On a narrow screen **Taken** is
left out, and the **File** name stays pinned at the left while the table scrolls sideways.

**Create backup** takes one now. It leaves out the FAA aircraft registry, which the nightly
import brings back. The button reads *Taking a backup…* while it works, a minute or two on a
large database, so leave the page open. A message names the file when done.

**Download** saves a backup to your own computer. Keep at least one copy somewhere other than
the server: a backup on the same disk as the database is lost with it. Take a backup before
every upgrade, before any bulk change, and before anyone experiments with the data.

There is no restore button. Restoring replaces everything in the database and is done on the
server with the site stopped, by the person who installed it.


Aircraft database
=================

Every night at 4:30 AM CalDART loads the FAA's aircraft registry: the list of aircraft types
members pick from, and the registrations the N-number box lists on the aircraft forms. The
line under the panel's text reads *Imported 312 types and 204 registrations on 09/20/2026*,
adding, for example, *folded 2 hand-added types* when types an account administrator added
by hand have since been registered by the FAA and were merged into its entries. A failed
load reads *Failed:* and the reason; before the first one, *No import has run yet.* There is
no dry run, because the load changes nothing but the copy. **Run now** starts one at once;
it reads *Running since* and the time, and the button waits, until the load ends a few
minutes later. A press while one runs says *An import is already running.*


Routine
=======

Once a week, open **Health and database**: six **OK** checks and a recent backup are the whole
check. Before any upgrade, take a backup and download it. Once a month, keep a copy somewhere
off the server. When someone reports a problem, read **Health** first and note the
**Version**.


If something looks wrong
========================

If **Create backup** fails, the message under it comes from the server; pass it to whoever
runs the server, since nothing half written is left behind. If the N-number box offers
nothing for an aircraft you know is registered, read the line under **Aircraft database**: a
*Failed:* line, or a date more than a few days old, means the nightly load has stopped, and
the person who runs the server can check it. Meanwhile **Run now** loads it by hand.
