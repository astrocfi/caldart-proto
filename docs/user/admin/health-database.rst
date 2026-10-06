:roles: system_admin

===================
Health and database
===================

**Health and database** shows how the server is doing, whether other mail systems will trust
the email it sends, the database backups it holds, and the FAA aircraft data it loads. Only a system administrator sees it, under
**System** in the menu, beside :doc:`sent-emails` and :doc:`scheduled`. Opening **System**
on its own lands here.

A system administrator can do everything any other role can do. Keep the role to the one or
two people who run the site, and give everyone else the narrower role that fits their job on
the :doc:`user-record`. Anything that has to happen on the server itself, such as installing
an upgrade, restoring a backup, or changing the settings, is a job for the person who
installed the site.

The page has four panels, top to bottom: **Health**, **Mail delivery**, **Backups**, and
**FAA aircraft data**.


Health
======

Six checks, each with a value and its status, **Good**, **Warning**, or **Problem**. A check
that needs attention says, under its value, what is wrong and who to ask. **Refresh** runs
them again.

- **Database**: *Connected* when the site can reach its database. *Not reachable* means the
  site is down or about to be. Tell the person who installed the site at once.
- **Database upgrade**: *Complete*, or how many changes that arrived with an upgrade have
  not been applied, such as *3 steps not applied*. Anything but *Complete* means an upgrade
  was left half finished; tell the person who installed the site.
- **Disk free**: the space left on the disk that holds the backups, such as *50.0 GB*. It
  warns below 2 GB and asks for attention below 512 MB. Old backups are the usual reason;
  download the ones worth keeping and ask for the rest to be deleted from the server.
- **Last backup**: when the newest backup was taken, or *No backup yet*. It warns after a
  week, and asks for attention after a month or when there has never been one. Take one
  from the next panel.
- **Version**: which release is running. Quote it when you report a problem.
- **Debug mode**: must read *Off*. If a live site reads *On*, ask the person who installed
  the site to turn it off at once, because it shows internal details to anyone who causes
  an error.


Mail delivery
=============

**Mail delivery** tells you whether other mail systems, such as Gmail, Outlook, and the
providers your members use, will trust the email CalDART sends. If they do not, a bulk
email can land in people's spam folders or never arrive, and nothing on the compose screen
would tell CalDART management. Read it once the site is installed, before the first large
bulk email, and after anyone changes the domain name's records or the server's mail
settings. Fixing what it finds is a job for whoever manages the CalDART domain name and the
server.

The panel opens with one sentence that sums everything up: either every check is good, or
it says how many found a problem and what that costs. Under it is one block for each of
four checks. Each block has:

- a colored dot and a word, **Good**, **Warning**, or **Problem**, beside the check's name,
  or on a line of its own under the name on a phone;
- a line that says what the check is for, in plain words, and what it found;
- when the check is not good, **What to do**, a sentence you can pass on as it stands to
  the person who looks after the domain name or the server.

**Warning** means mail will probably still arrive, but the setup is weaker than it should
be, or the panel could not judge it. **Problem** means some mail is likely to be marked as
spam or refused until it is fixed.

Under the blocks, **Checked** gives the date and time of the last look and the domain it was
made for, for example *Checked 10/03/2026 at 8:00 AM for caldart.example.org.* Without
**Check again**, the panel shows what it found in the last five minutes; press it after
somebody says they have fixed something, and it looks the records up again, which takes a
few seconds.

The four checks:

- **Approved senders (SPF)**: a public list, kept with the domain name (or, when bounces
  return to a different address, the domain of that address, which the block names), of the
  servers allowed to send email that claims to come from CalDART. It is good when the list
  exists, names the server the website sends through, and tells receivers to be suspicious
  of anything else. It is a problem when there is no list, the list is malformed, or the
  website's server is not on it. It is a warning when the list is too lenient, or when the
  website hands its mail to a server on the same machine, so the panel cannot tell which
  public address the mail leaves from.
- **Message signature (DKIM)**: a digital signature the mail server puts on every message,
  checked against a public key published with the domain name. It is a problem when the key
  is not published. *No DKIM selector is configured* is a warning: the website has not been
  told the key's name, so the signature may be working but the panel cannot check it.
- **Handling of forged mail (DMARC)**: a short public instruction that tells receiving
  systems what to do with a message that claims to come from CalDART but fails the other
  checks, and where to send reports about it. It is a problem when none is published, or
  when more than one is, because receiving systems then follow none of them. It is a warning
  while it only says to watch (``p=none``), and good when it says to send forgeries to spam
  (``quarantine``) or refuse them (``reject``). When it names addresses for reports, the
  block lists them. When CalDART sends from a part of a larger domain, such as
  ``caldart.example.org``, and that part has no instruction of its own, receiving systems
  follow the one for ``example.org``, and so does the check: the block says where it found
  the instruction, and judges its setting for subdomains (``sp=``) when there is one.
- **Bounce address**: where a receiving server sends back a message it cannot deliver,
  which CalDART reads to find the addresses that are no good. Some systems trust a message
  more when it is on the same domain as the From address, so it is a warning when it is on
  an unrelated domain.

Changes to a domain name can take a few hours to reach everyone, so **Check again** may show
the old answer for a while. A lookup that *did not get an answer in time*, or a check that
*took too long*, says nothing about the records: press **Check again** in a minute or two.
*No name server could answer* means the domain's own name servers are not working.


Backups
=======

The table lists every backup on the server, newest first, with its **File** name, when it
was **Taken**, its **Size**, and last a **Download** link. On a narrow screen **Taken** is
left out, and the **File** name stays pinned at the left while the table scrolls sideways.

**Create backup** takes one now. It leaves out the FAA aircraft registry, which the nightly
import brings back. The button reads *Taking a backup…*, beside *Taking a backup. A large
database takes a minute or two.*, while it works, so leave the page open. *Backup taken.*
confirms it, and the backup heads the table.

**Download** saves a backup to your own computer. Keep at least one copy somewhere other than
the server: a backup on the same disk as the database is lost with it. Take a backup before
every upgrade, before any bulk change, and before anyone experiments with the data.

The panel says so: *There is no restore button. To restore a backup, ask the person who
installed the site.* Restoring replaces everything in the database and is done on the
server with the site stopped.


FAA aircraft data
=================

Every night at 4:30 AM CalDART loads the FAA's aircraft registry: the list of aircraft types
members pick from, and the registrations the N-number box lists on the aircraft forms. The
line under the panel's text reads *Imported 312 types and 204 registrations on 09/20/2026*,
adding, for example, *folded 2 hand-added types* when types an account administrator added
by hand have since been registered by the FAA and were merged into its entries. A failed
load reads *Failed:* and the reason; before the first one, *No import has run yet.* There is
no practice run, because the load changes nothing but the copy. **Run now** starts one at
once;
it reads *Running since* and the time, and the button waits, until the load ends a few
minutes later. A press while one runs says *An import is already running.*


Routine
=======

Once a week, open **Health and database**: six **Good** health checks and a recent backup are
the whole check. Before any upgrade, take a backup and download it. Once a month, keep a copy somewhere
off the server. When someone reports a problem, read **Health** first and note the
**Version**.


If something looks wrong
========================

If **Create backup** fails, the message under it comes from the server; pass it to whoever
runs the server, since nothing half written is left behind. If the N-number box offers
nothing for an aircraft you know is registered, read the line under **FAA aircraft data**: a
*Failed:* line, or a date more than a few days old, means the nightly load has stopped, and
the person who runs the server can check it. Meanwhile **Run now** loads it by hand.
