==================
Backup and restore
==================

Four commands look after the data: ``db_backup`` writes a dump, ``db_restore``
puts one back, ``db_reset`` rebuilds a development database from nothing, and
``health`` says whether any of that has been happening.  They live in
``backend/apps/sysadmin/``; the portal's System page reaches the same code
through the endpoints listed under :ref:`api-reminders-system`.


How a dump is taken
===================

``manage.py db_backup`` runs ``pg_dump`` with ``--no-owner --no-privileges``
and gzips its output as it arrives (:ref:`backup-streaming`) into
``BACKUP_DIR`` as
``caldart-<YYYYMMDD-HHMMSS>.sql.gz``.  ``--name`` overrides that file name, for
a dump you want to find again by hand::

  uv run backend/manage.py db_backup --name before-the-schema-change.sql.gz
  caldart_manage db_backup --name before-the-schema-change.sql.gz    # production

Keep the ``.sql.gz`` ending whatever you call it.  The download endpoint only
serves names matching ``^[A-Za-z0-9][A-Za-z0-9._-]*\.sql\.gz$``, and
``db_restore`` expects gzip.

It finds ``pg_dump`` in one of two places:

* the local binary, when ``postgresql-client`` is installed and
  ``DB_BACKUP_VIA_DOCKER`` is false;
* ``docker compose exec -T -e PGPASSWORD db pg_dump``, when it is not, or when
  ``DB_BACKUP_VIA_DOCKER=true`` forces it.

The second is the default because a development machine usually has Docker but
not the client tools.  On a server, install ``postgresql-client`` and set
``DB_BACKUP_VIA_DOCKER=false``: it is faster and it works even if the compose
project name changes.

.. _backup-credentials:

How the credentials reach the tool
----------------------------------

``pg_dump`` and ``psql`` are given a connection URL through ``--dbname``, and
that URL carries no password: an argument list is readable by every other user
on the machine through ``ps``, and it lands in shell history.  The password
travels in the ``PGPASSWORD`` environment variable of the child process
instead, and the compose form names the variable without a value so Docker
copies it across from the same environment rather than spelling it out in an
argument.  An empty password is left unset, so a ``.pgpass`` file or a trust
connection still works.

The user name and the database name are percent-encoded into the URL, so an
awkward account such as ``ann marie@caldart`` still produces a URL libpq can
parse.

.. _backup-streaming:

How the bytes move
------------------

A dump is never held in memory.  ``pg_dump`` writes to a pipe, and the backup
reads that pipe a megabyte at a time and compresses each block straight into
the ``.sql.gz`` file while the tool is still running; a restore reads the file
the same way and writes into ``psql``'s standard input.  Peak memory is
therefore a single block, whatever the size of the database, and the file on
disk grows throughout the dump rather than appearing at the end.

Each tool's standard error goes to a temporary file rather than to a second
pipe, so a tool that prints more than a pipe will hold cannot stall waiting for
someone to read it.  A non-zero exit raises ``BackupError`` carrying that
output, and a backup that fails part way through deletes the partial file it
had started.  A ``psql`` that exits before it has read the whole dump -- a
connection or authentication failure, say -- is reported the same way: the
broken pipe its early exit leaves behind is swallowed so that the message the
tool printed is what reaches the operator.  If the copy itself fails instead --
a dump that cannot be read, a disk that fills -- the tool is killed and waited
for before the error propagates, so no ``pg_dump`` or ``psql`` is left blocked
on a pipe nobody is moving.

A restore reads the dump through once, a block at a time, before it drops
anything.  A corrupt, truncated, or non-gzip file therefore fails with
``BackupError`` naming the file and leaves the database that is already there
untouched, and the extra pass costs no memory.

``BACKUP_DIR`` defaults to ``backups/`` at the repository root, which is
gitignored.  A relative value is resolved against the repository root; an
absolute one is used as given.  In production, put it somewhere the systemd
unit can write: ``caldart-web.service`` mounts the filesystem read-only except
for ``media/``, ``staticfiles/``, and ``backups/``, so a ``BACKUP_DIR``
elsewhere needs a matching ``ReadWritePaths`` line.


Taking a backup
===============

Development::

  make backup

Production, through the ``caldart_manage`` function defined in
:ref:`deploy-manage-commands`::

  caldart_manage db_backup

Or from a browser: ``/portal/system`` → **Backups** → **Create backup**.  Three
endpoints back that panel, all ``system_admin`` only:

.. code-block:: text

   GET  /api/v1/system/backups                  → [{name, size_bytes, created_at}]
   POST /api/v1/system/backups                  → 201 {name, size_bytes, created_at}
   GET  /api/v1/system/backups/{name}/download  → application/gzip

``GET`` lists ``BACKUP_DIR`` — a dump written anywhere else is invisible here
and cannot be downloaded.  ``POST`` runs the same code path as the command,
synchronously, so on a large database the request takes as long as ``pg_dump``
does; a ``BackupError`` comes back as a **400** with the message in ``detail``.
There is deliberately no restore endpoint.

Scheduling
----------

There is no backup timer in ``deploy/`` — retention policy is a site decision.
The simplest version is a oneshot service and a timer of your own, modeled on
``caldart-reminders.service`` and ``caldart-reminders.timer``.

``/etc/systemd/system/caldart-backup.service``:

.. code-block:: ini

   [Unit]
   Description=CalDART database backup
   Documentation=file:///srv/caldart/docs/developer/backup-restore.rst
   After=network.target docker.service

   [Service]
   Type=oneshot

   User=caldart
   Group=caldart
   UMask=0027

   WorkingDirectory=/srv/caldart/backend
   EnvironmentFile=/etc/caldart/caldart.env
   Environment=DJANGO_SETTINGS_MODULE=caldart.settings.prod

   ExecStart=/srv/caldart/.venv/bin/python /srv/caldart/backend/manage.py db_backup

   # Nothing rotates dumps, so the same run drops the ones over 30 days old.
   # systemd expands ${BACKUP_DIR} from the environment file, so the prune reads
   # the directory the dump just wrote to.
   ExecStart=/usr/bin/find ${BACKUP_DIR} -name caldart-*.sql.gz -mtime +30 -delete

   # pg_dump on a large database is not quick.
   TimeoutStartSec=3600

   NoNewPrivileges=true
   PrivateTmp=true
   ProtectHome=true
   ProtectSystem=strict
   ProtectKernelTunables=true
   ProtectKernelModules=true
   ProtectControlGroups=true
   RestrictSUIDSGID=true
   RestrictRealtime=true
   LockPersonality=true
   SystemCallArchitectures=native
   SystemCallFilter=@system-service
   RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
   CapabilityBoundingSet=

   ReadWritePaths=/srv/caldart/backups

It has no ``[Install]`` section: the timer is what pulls it in, and
``systemctl start caldart-backup.service`` is what runs one by hand.

``/etc/systemd/system/caldart-backup.timer``:

.. code-block:: ini

   [Unit]
   Description=Take a CalDART database backup daily at 03:30
   Documentation=file:///srv/caldart/docs/developer/backup-restore.rst

   [Timer]
   Unit=caldart-backup.service
   OnCalendar=*-*-* 03:30:00
   Persistent=true
   AccuracySec=1min
   RandomizedDelaySec=5min

   [Install]
   WantedBy=timers.target

``Persistent=true`` takes the missed backup when the machine comes back rather
than skipping the night.  Install both, then enable the timer::

  sudo systemctl daemon-reload
  sudo systemctl enable --now caldart-backup.timer
  systemctl list-timers caldart-backup.timer
  sudo systemctl start caldart-backup.service    # take one right away
  journalctl -u caldart-backup -n 20

Five details to keep in step with the rest of the deployment.  ``BACKUP_DIR``
has to be an absolute path in ``/etc/caldart/caldart.env`` — the production
template sets ``/srv/caldart/backups`` — because the prune hands the value
straight to ``find``, which resolves a relative path against
``WorkingDirectory`` while Django resolves it against the repository root.
``ReadWritePaths`` expands no variables, so it is the one line that spells the
directory out by hand: it has to name whatever ``BACKUP_DIR`` points at, or
``ProtectSystem=strict`` fails the dump with a permission error.  A
``Type=oneshot`` unit runs its ``ExecStart`` lines in order and fails if either
exits non-zero, so a prune that cannot find its directory reports a failed
backup even when the dump itself worked.  The prune matches only the generated
``caldart-<timestamp>.sql.gz`` names, so a dump you gave your own ``--name`` is
left alone.  And the unit expects a local ``pg_dump`` with
``DB_BACKUP_VIA_DOCKER=false``; going through ``docker compose`` instead needs
the ``caldart`` user in the ``docker`` group.

A dump on the same disk as the database is not a backup.  Copy them somewhere
else — another host, object storage, an external disk — as a second step,
together with the media files (:ref:`backup-media`).  The
health panel warns when the newest dump is more than seven days old and turns
red past thirty.

A dump carries everything in the database, and in production that includes the
``caldart_cache`` table, so a dump taken while a PayPal access token is cached
holds a token that stays valid for up to the nine hours PayPal grants it (see
:ref:`paypal-token-cache`).  Treat a backup file as being as sensitive as the
credentials inside it: restrict who can read it wherever you copy it to, and
prefer an encrypted destination.


.. _backup-media:

Backing up the media files
==========================

A database dump carries every row and none of the uploaded files.  Those live
under ``backend/media/`` (``/srv/caldart/backend/media`` in production), in
three directories Wagtail writes:

``original_images/``
   every image an editor uploaded, as uploaded;
``images/``
   the resized copies (renditions) Wagtail makes of them for pages.  The
   database lists each one, so a restored database expects these files too;
``documents/``
   every uploaded document, including the members-only ones.

Back up the whole directory, alongside each dump.  ``rsync`` keeps a mirror
on another machine up to date and copies only what changed::

  sudo rsync -a --delete /srv/caldart/backend/media/ backup-host:/backups/caldart/media/

A ``tar`` archive is a point-in-time copy to keep beside the dump of the same
moment.  Write it outside ``BACKUP_DIR``: the backup list and the health panel
read every ``*.sql.gz`` there, and nothing else belongs in it::

  sudo tar -czf /root/caldart-media-$(date +%Y%m%d-%H%M%S).tar.gz \
      -C /srv/caldart/backend media

The files are as sensitive as the dump: the members-only documents are in
them.  To put an archive back, unpack it over the checkout and give the files
back to the service user::

  sudo tar -xzf /root/caldart-media-20260601-033000.tar.gz -C /srv/caldart/backend
  sudo chown -R caldart:caldart /srv/caldart/backend/media


Downloading a backup
====================

``GET /system/backups/<name>/download`` streams the gzipped file with
``Content-Type: application/gzip``.  It is ``system_admin`` only.

The name is validated before anything is opened: it must match
``^[A-Za-z0-9][A-Za-z0-9._-]*\.sql\.gz$``, and the resolved path must be a
direct child of ``BACKUP_DIR``.  That rejects ``..`` segments, absolute paths
and symlinks pointing out of the directory, all of which return 404 rather than
saying which.  ``backend/tests/test_sysadmin_api.py`` has a case for each.


Restoring
=========

Restoring is **destructive**: ``pg_dump`` writes ``CREATE TABLE`` without
``DROP``, so the ``public`` schema is dropped and recreated before the dump is
replayed.  Everything currently in the database goes.

::

  make restore FILE=backups/caldart-20260601-070000.sql.gz

The command prompts for confirmation.  ``YES=1``, or ``--yes`` on the command
directly, skips the prompt for scripted use::

  uv run backend/manage.py db_restore caldart-20260601-070000.sql.gz --yes

``YES=0``, ``YES=no``, ``YES=false`` and an unset ``YES`` all keep the prompt,
and any other value stops ``make`` without touching the database; the full rule
is in :ref:`make-switches`.

The argument may be a path or a bare file name inside ``BACKUP_DIR``.

In production, stop the web unit and the scheduled jobs' timers first, so
nothing writes during the restore and no job runs against the restored
bookkeeping before you have checked it (:ref:`backup-after-restore`)::

  sudo systemctl stop caldart-web caldart-renewals.timer caldart-reminders.timer \
      caldart-reports.timer caldart-statements.timer
  sudo systemctl stop caldart-backup.timer    # if you installed it
  caldart_manage db_restore /srv/caldart/backups/caldart-....sql.gz --yes
  caldart_manage migrate

Leave the web unit and the timers stopped: :ref:`backup-after-restore` starts
them again once its checks pass.  The ``migrate`` is deliberate: a dump taken
from an older release restores an older schema, and ``manage.py health`` will
report the pending migrations if you forget.

**Restoring onto a fresh machine** is the same, into an empty database:
follow :doc:`deployment` up to its database step, restore, migrate,
``collectstatic``, and put the media files back from the copy taken beside the
dump (:ref:`backup-media`).  Either way, go through :ref:`backup-after-restore`
before the site takes traffic.

There is no restore button in the portal, and there will not be one.  Wiping
the database is not a thing to do from a browser tab.


.. _backup-rehearsal:

Rehearsing a restore
====================

A backup nobody has restored is a hope.  Restore one into a scratch database
now and then, check that it holds what the live database holds, and throw the
scratch copy away.  None of it touches the live database.

**Check the file.**  ``gzip -t`` reads the whole archive and says nothing when
it is sound.  The dump inside is plain SQL, so ``pg_restore --list``, which
reads only pg_dump's archive formats, refuses it with *input file appears to
be a text format dump*; list the tables and data blocks with ``zcat``
instead::

  gzip -t backups/caldart-20260601-033000.sql.gz
  zcat backups/caldart-20260601-033000.sql.gz | grep -c '^CREATE TABLE'
  zcat backups/caldart-20260601-033000.sql.gz | grep '^COPY public\.' | cut -d' ' -f2

**Restore it into a scratch database.**  In development, create the database
and point ``db_restore`` at it for one command; a variable set on the command
line wins over ``.env``::

  docker compose exec -T db createdb -U caldart caldart_rehearsal
  DATABASE_URL=postgres://caldart:caldart@localhost:5432/caldart_rehearsal \
      uv run backend/manage.py db_restore backups/caldart-20260601-033000.sql.gz --yes

On a server, the environment file wins over anything ``caldart_manage`` could
set, so replay the dump with ``psql`` inside the container instead.  Run it
from ``/srv/caldart``::

  sudo docker compose exec -T db createdb -U caldart caldart_rehearsal
  sudo zcat /srv/caldart/backups/caldart-20260601-033000.sql.gz \
      | sudo docker compose exec -T db psql -U caldart -d caldart_rehearsal \
            -v ON_ERROR_STOP=1 -q

``ON_ERROR_STOP`` makes the first failing statement stop the replay with an
error, instead of scrolling past it.

**Count the rows.**  Save the query below as ``counts.sql`` and run it against
both databases.  The two lists should match, table for table, when the dump is
fresh; against an older dump the live numbers are the larger ones.

.. code-block:: sql

   SELECT 'accounts_user', count(*) FROM accounts_user
   UNION ALL SELECT 'members_membership', count(*) FROM members_membership
   UNION ALL SELECT 'payments_payment', count(*) FROM payments_payment
   UNION ALL SELECT 'aircraft_aircraft', count(*) FROM aircraft_aircraft
   UNION ALL SELECT 'mail_emaillog', count(*) FROM mail_emaillog
   UNION ALL SELECT 'wagtailcore_page', count(*) FROM wagtailcore_page
   UNION ALL SELECT 'django_migrations', count(*) FROM django_migrations;

::

  docker compose exec -T db psql -U caldart -d caldart -At < counts.sql
  docker compose exec -T db psql -U caldart -d caldart_rehearsal -At < counts.sql

(``sudo`` in front of each on a server, and the live database's name in
place of ``caldart`` if ``DATABASE_URL`` names another.)

**Throw it away.**

::

  docker compose exec -T db dropdb -U caldart caldart_rehearsal


.. _backup-after-restore:

After a restore
===============

Before the site takes traffic again, check that it is the site you meant to
bring back:

1. ``caldart_manage health`` says ``db`` is ``ok`` and ``pending_migrations``
   is ``0``.  A number above zero means the ``migrate`` step was skipped.
2. The row counts above match what you expected of a dump from that moment.
3. ``systemctl start caldart-web``, then ``journalctl -u caldart-web -n 50``
   shows the workers booting with no traceback.
4. Signed in as an administrator: the member list shows the members you
   expect, a member record opens with its memberships and payments, the
   payment list shows the latest payments you expect, and ``/admin/`` opens.
5. Signed out: the public home page renders with its images, and a public
   document downloads.  A broken image or a 404 on a document means the media
   files did not come back with the dump (:ref:`backup-media`).

A restore from an older dump rolls the scheduled jobs' bookkeeping back with
everything else.  A renewal charged after the dump was taken looks due again,
and the next automatic renewal run would charge the card a second time.  That
is why the restore above stops the timers.  Check what the jobs would do before
starting them again::

  caldart_manage run_auto_renewals --dry-run
  caldart_manage send_renewal_reminders --dry-run

Compare every charge the dry run lists with the provider's dashboard.  For a
member the provider already charged after the dump was taken, record that
payment by hand against the member's plan (``POST /admin/payments/record``,
:doc:`api-finance`), with the provider's charge id as the reference.  Recording
it extends the member's term and moves their automatic renewal's charge date
past the new expiry, exactly as a card checkout would, so their standing
authority stays in place and ``run_auto_renewals --dry-run`` no longer lists
them.  Run it again to confirm, then start the timers::

  sudo systemctl start caldart-renewals.timer caldart-reminders.timer \
      caldart-reports.timer caldart-statements.timer
  sudo systemctl start caldart-backup.timer   # if you installed it

A payment recorded by hand carries no link to the provider's charge, so a
refund issued from the portal against it sends nothing to Stripe or PayPal.  To
give that money back, refund the charge in the provider's dashboard, then
record the refund in the portal against the recorded payment.


Resetting a development database
================================

``db_reset`` drops the schema through the Django connection, re-migrates, and
re-seeds::

  make reset                     # db_reset --seed --noinput
  uv run backend/manage.py db_reset            # asks first
  uv run backend/manage.py db_reset --seed     # + seed_demo and seed_content

Without ``--seed`` it stops after ``migrate`` and ``seed_roles``, leaving an
empty but usable database.  With it, ``seed_demo`` creates the demo accounts
(password ``caldart-demo``) and ``seed_content`` the example pages.

It names the database it is about to destroy in the prompt.  On a parallel
branch that database is ``caldart_<branch-slug>`` from ``DATABASE_URL``; check
the name in the prompt before typing yes, and never point it at a database that
is not yours.  It is not for production, ever: use ``db_restore`` there.


Checking on all of this
=======================

``manage.py health``, ``GET /system/health`` and the health panel of
``/portal/system`` all return the same six facts:

========================  ==================================================
Field                     Meaning
========================  ==================================================
``db``                    ``ok``, or the connection error
``pending_migrations``    how many migrations on disk are not applied
``disk_free_mb``          free space on the filesystem holding ``BACKUP_DIR``
``last_backup``           timestamp of the newest dump, or ``null``
``version``               ``[project] version`` from ``pyproject.toml``
``debug``                 whether ``DEBUG`` is on — false in production
========================  ==================================================

``manage.py health --json`` prints it as JSON, which is what to point a
monitoring check at.

The panel grades each one: free space warns below 2 GB and fails below 512 MB,
the last backup warns after a week and fails after a month, any pending
migration warns, and ``DEBUG`` being on in production fails.

Related
=======

:doc:`api-system` documents the health and backup endpoints in detail.
