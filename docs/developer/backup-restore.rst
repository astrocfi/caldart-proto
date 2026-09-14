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

``manage.py db_backup`` runs ``pg_dump`` with ``--no-owner --no-privileges``,
gzips the output, and writes it to ``BACKUP_DIR`` as
``caldart-<YYYYMMDD-HHMMSS>.sql.gz``.  ``--name`` overrides that file name, for
a dump you want to find again by hand::

  manage.py db_backup --name before-the-schema-change.sql.gz

Keep the ``.sql.gz`` ending whatever you call it.  The download endpoint only
serves names matching ``^[A-Za-z0-9][A-Za-z0-9._-]*\.sql\.gz$``, and
``db_restore`` expects gzip.

It finds ``pg_dump`` in one of two places:

* the local binary, when ``postgresql-client`` is installed and
  ``DB_BACKUP_VIA_DOCKER`` is false;
* ``docker compose exec -T db pg_dump``, when it is not, or when
  ``DB_BACKUP_VIA_DOCKER=true`` forces it.

The second is the default because a development machine usually has Docker but
not the client tools.  On a server, install ``postgresql-client`` and set
``DB_BACKUP_VIA_DOCKER=false``: it is faster and it works even if the compose
project name changes.

``BACKUP_DIR`` defaults to ``backups/`` at the repository root, which is
gitignored.  A relative value is resolved against the repository root; an
absolute one is used as given.  In production, put it somewhere the systemd
unit can write: ``caldart-web.service`` mounts the filesystem read-only except
for ``media/``, ``staticfiles/`` and ``backups/``, so a ``BACKUP_DIR``
elsewhere needs a matching ``ReadWritePaths`` line.


Taking a backup
===============

Development::

  make backup

Production::

  cd /srv/caldart/backend
  sudo -u caldart env $(grep -v '^#' /etc/caldart/caldart.env | xargs) \
      DJANGO_SETTINGS_MODULE=caldart.settings.prod \
      /srv/caldart/.venv/bin/python manage.py db_backup

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
The simplest version is a systemd timer modelled on
``caldart-reminders.timer``, or a root crontab entry::

  # /etc/cron.d/caldart-backup
  30 3 * * *  caldart  cd /srv/caldart/backend && \
      DJANGO_SETTINGS_MODULE=caldart.settings.prod \
      /srv/caldart/.venv/bin/python manage.py db_backup >/dev/null

Pair it with a prune, since nothing rotates dumps automatically::

  # keep 30 days
  find /srv/caldart/backups -name 'caldart-*.sql.gz' -mtime +30 -delete

A dump on the same disk as the database is not a backup.  Copy them somewhere
else — another host, object storage, an external disk — as a second step.  The
health panel warns when the newest dump is more than seven days old and turns
red past thirty.


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

The argument may be a path or a bare file name inside ``BACKUP_DIR``.

In production, stop the web unit first so nothing writes during the restore::

  sudo systemctl stop caldart-web
  cd /srv/caldart/backend
  sudo -u caldart ... manage.py db_restore /srv/caldart/backups/caldart-....sql.gz --yes
  sudo -u caldart ... manage.py migrate
  sudo systemctl start caldart-web

The ``migrate`` afterwards is deliberate: a dump taken from an older release
restores an older schema, and ``manage.py health`` will report the pending
migrations if you forget.

**Restoring onto a fresh machine** is the same, into an empty database:
create the database, restore, migrate, ``collectstatic``.  There is no separate
media backup — ``backend/media/`` holds Wagtail's uploads and has to be copied
alongside the dump, with ``rsync`` or a tar.

There is no restore button in the portal, and there will not be one.  Wiping
the database is not a thing to do from a browser tab.


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
