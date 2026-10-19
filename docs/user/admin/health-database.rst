:roles: system_admin

===================
Health and database
===================

**Health and database** shows how the server is doing, whether other mail systems will trust
the email it sends, the database backups it holds, and the FAA aircraft data it loads. Only a
system administrator sees it, under **System** in the menu, beside :doc:`sent-emails` and
:doc:`scheduled`. Opening **System** by itself brings you here.

A system administrator can do everything any other role can do. Keep the role to the one or
two people who run the site. On the :doc:`user-record`, give everyone else the narrower role
that fits their job. Anything that has to happen on the server itself, such as installing
an upgrade, restoring a backup, or changing the settings, is a job for the person who
installed the site.

The page has four panels, top to bottom: **Health**, **Mail delivery**, **Backups**, and
**FAA aircraft data**.


Health
======

There are seven checks, each with a value and a status: **Good**, **Warning**, or
**Problem**. When a check needs attention, it says under its value what is wrong and who to
ask. **Refresh** runs them again.

- **Database**: *Connected* when the site can reach its database. *Not reachable* means the
  site is down or about to be. Tell the person who installed the site at once.
- **Database upgrade**: *Complete*, or how many changes from an upgrade haven't been applied
  yet, such as *3 steps not applied*. Anything but *Complete* means somebody left an upgrade
  half finished. Tell the person who installed the site.
- **Disk free**: the space left on the disk that holds the backups, such as *50.0 GB*. It
  shows a warning below 2 GB and a problem below 512 MB. Old backups are the usual reason.
  Download the ones worth keeping, and ask for the rest to be deleted from the server.
- **Last backup**: when the newest backup was taken, or *No backup yet*. It shows a warning
  after a week, and a problem after a month or if there has never been a backup. Take one
  from the next panel.
- **Scheduled jobs**: *On schedule* when the last run of every scheduled job succeeded and
  none of them is late. If a job's last run failed, or stopped before it finished, that is a
  problem, and the value counts them, such as *1 failed*. A job that should have run by now
  and hasn't is a warning (*1 late*). So is a job that has never run, once the site has been
  up long enough for it to. Under the value, one line names each job and what happened, such
  as *Automatic renewal charges failed at 6:30 AM: 2 renewal charges need checking*. Beside
  it, **View log** opens the job's runs (:doc:`job-log`). A job shows as good again once a
  later run succeeds, either the next scheduled run or a real **Run now**. For example,
  settling the renewal charges a treasurer has to check doesn't clear *Automatic renewal
  charges* by itself; the next run does. A late job usually means the server has stopped
  starting it, so tell the person who installed the site. *Unknown* means the site couldn't
  read its record of the runs.
- **Version**: which release is running. Quote it when you report a problem.
- **Debug mode**: should say *Off*. If a live site says *On*, ask the person who installed
  the site to turn it off at once. Debug mode shows internal details to anyone who causes
  an error.


Mail delivery
=============

**Mail delivery** tells you whether other mail systems, such as Gmail, Outlook, and the
providers your members use, will trust the email CalDART sends. If they don't, a bulk email
can land in people's spam folders or never arrive, and CalDART management wouldn't see any
sign of it on the compose screen. Look at this panel once the site is installed, before the
first large bulk email, and whenever anyone changes the domain name's records or the
server's mail settings. Fixing what it finds is a job for whoever manages the CalDART domain
name and the server.

The panel opens with a one-sentence summary. Either every check is good, or it says how
many found a problem and what that means for your mail. Under it is a block for each of the
four checks. Each block has:

- a colored dot and a word, **Good**, **Warning**, or **Problem**, beside the check's name,
  or on a line of its own under the name on a phone;
- when the check isn't good, a line that says in plain words what the check is for and what
  it found, then **What to do**. That is a sentence you can pass on as it is to the person
  who looks after the domain name or the server. A good check shows only its name and the
  word.

**Warning** means mail will probably still arrive, but the setup is weaker than it should
be, or the panel couldn't tell. **Problem** means some mail is likely to be marked as spam
or refused until somebody fixes it.

Under the blocks, **Checked** gives the date and time of the last check and the domain it
checked, for example *Checked 10/03/2026 at 8:00 AM for caldart.example.org.* The panel
reuses what it found in the last five minutes. When somebody says they have fixed
something, press **Check again**. The panel looks the records up again, which takes a few
seconds.

The four checks:

- **Approved senders (SPF)**: a public list of the servers allowed to send email that
  claims to come from CalDART. The list is kept with the domain name. If bounces go back to
  a different address, it is kept with that address's domain, and the block names it. The
  check is good when the list exists, names the server the website sends through, and tells
  receivers to be suspicious of anything else. It is a problem when the list is missing or
  malformed, or when the website's server isn't on it. It is a warning when the list is too
  lenient. It is also a warning when the website hands its mail to a server on the same
  machine, because then the panel can't tell which public address the mail leaves from.
- **Message signature (DKIM)**: a digital signature the mail server puts on every message,
  checked against a public key published with the domain name. It is a problem when the key
  isn't published. *No DKIM selector is configured* is a warning. It means the website
  hasn't been told the key's name, so the signature may be working, but the panel can't
  check it.
- **Handling of forged mail (DMARC)**: a short public instruction that tells receiving
  systems what to do with a message that claims to come from CalDART but fails the other
  checks, and where to send reports about it. It is a problem when there isn't one, or when
  there is more than one, because receiving systems then ignore all of them. It is a
  warning while it only says to watch (``p=none``). It is good when it says to send
  forgeries to spam (``quarantine``) or to refuse them (``reject``). If it names addresses
  for reports, the block lists them. Suppose CalDART sends from part of a larger domain,
  such as ``caldart.example.org``, and that part doesn't have its own instruction.
  Receiving systems then follow the one for ``example.org``, and so does the check. The
  block says where it found the instruction, and judges its setting for subdomains
  (``sp=``) if there is one.
- **Bounce address**: where a receiving server sends back a message it can't deliver.
  CalDART reads these to find the addresses that don't work. Some systems trust a message
  more when this address is on the same domain as the From address, so the check shows a
  warning when it is on an unrelated domain.

Changes to a domain name can take a few hours to reach everyone, so **Check again** may
show the old answer for a while. If a lookup *did not get an answer in time*, or a check
*took too long*, that doesn't tell you anything about the records. Press **Check again** in
a minute or two. *No name server could answer* means the domain's own name servers aren't
working.


Backups
=======

The table lists every backup on the server, newest first, with its **File** name, when it
was **Taken**, its **Size**, and a **Download** link at the end. On a narrow screen,
**Taken** is dropped, and the **File** name stays pinned at the left while the table
scrolls sideways.

**Create backup** takes one right away. The backup leaves out the FAA aircraft registry,
which the nightly import brings back. While it works, the button says *Taking a backup…*,
next to *Taking a backup. A large database takes a minute or two.*, so leave the page open.
*Backup taken.* confirms it, and the backup appears at the top of the table.

**Download** saves a backup to your own computer. Keep at least one copy somewhere other
than the server, because a backup on the same disk as the database is lost along with it.
Take a backup before every upgrade, before any bulk change, and before anyone experiments
with the data.

The panel itself says so: *The portal doesn't have a restore button. To restore a backup,
ask the person who installed the site.* A restore replaces everything in the database, and
it is done on the server with the site stopped.

Under that note, *Last nightly backup* gives the date and time of the server's own last
backup and how that run ended, with **View log** beside it (:doc:`job-log`). The nightly
run also deletes the server's older backups, once they are older than the number of days
the person who installed the site chose.


FAA aircraft data
=================

Every night at 4:30 AM, CalDART loads the FAA's aircraft registry. It holds the list of
aircraft types members pick from, and the registrations listed under the N-number box on
the aircraft forms. The line under the panel's text says, for example, *Imported 312 types
and 204 registrations on 09/20/2026*. It may add something like *merged 2 hand-added
types*. That means the FAA has registered types an account administrator added by hand,
and the load merged them into the FAA's entries. A failed load shows *Failed:* and the
reason. Before the first load, the line says *No import has run yet.* There isn't a
practice run, because the load only changes CalDART's copy of the registry.
**Run now** starts a load at once. The line says *Running since* and the time, and the
button waits until the load ends a few minutes later. If you press it while a load is
running, it says *An import is already running.* Under that, *Last load* gives the time and
the outcome of the last load, with **View log** (:doc:`job-log`).


Routine
=======

Once a week, open **Health and database**. Seven **Good** health checks and a recent backup
are all you need to see. Before any upgrade, take a backup and download it. Once a month,
keep a copy somewhere off the server. When someone reports a problem, look at **Health**
first and note the **Version**.


If something looks wrong
========================

If **Create backup** fails, the message under it comes from the server. Pass it on to
whoever runs the server. A failed backup doesn't leave a half-written file behind. If the
N-number box doesn't list an aircraft you know is registered, look at the line under **FAA
aircraft data**. A *Failed:* line, or a date more than a few days old, means the nightly
load has stopped, and the person who runs the server can look into it. In the meantime,
**Run now** loads the data by hand.
