=================
Local development
=================

The day-to-day work on a checkout that :doc:`setup` has already brought up:
which pieces run where, how to stop in a debugger on either side, what the
development logs say, where the email goes, how the test database relates to
yours, and how to put the demo data back.

Every command runs from the repository root, as every Make target does.


The pieces
==========

Four processes make up a running development site.  Two are containers that
``make up`` starts and leaves running; two are foreground processes you start
in terminals of your own.

.. list-table::
   :header-rows: 1
   :widths: 18 22 60

   * - Piece
     - Started by
     - What it does
   * - Postgres 16
     - ``make up``
     - the ``db`` container, on ``127.0.0.1:5432``, user and password
       ``caldart``.  Holds one database per worktree (``DATABASE_URL``) and
       each one's ``test_`` twin.
   * - Mailpit
     - ``make up``
     - the ``mailpit`` container: an SMTP server on ``127.0.0.1:1025`` that
       delivers nothing, and a web inbox on http://localhost:8025/ showing
       every message it caught.
   * - Django
     - ``make run``
     - ``manage.py runserver`` on port 8000 under ``caldart.settings.dev``:
       the public site, the portal shell, the API, both admins, and the user
       guide at ``/docs/``.  It reloads itself when a Python file changes.
   * - Vite
     - ``make dev-frontend``
     - the frontend dev server on port 5173, only while you work on
       ``frontend/src`` with ``DJANGO_VITE_DEV_MODE=true`` in ``.env``.
       Without it, Django serves the bundle ``make build`` wrote.

``docker compose ps`` shows the two containers, and ``make down`` stops them
for every worktree on the machine at once (:ref:`setup-per-worker`).  The data
survives in the ``caldart_pgdata`` volume.

A second Django server beside the first needs its own port and a matching
``SITE_URL``, so links in the emails it sends lead back to it::

  SITE_URL=http://localhost:8021 uv run backend/manage.py runserver 8021

A variable set on the command line wins over the same name in ``.env``.


Debugging
=========

The backend
-----------

Put ``breakpoint()`` on the line you want to stop at and make the request.
``make run`` keeps the server in the foreground, so ``pdb`` takes over that
terminal: ``n`` steps, ``s`` steps in, ``p expr`` prints, ``c`` carries on.
The request waits in the browser until you continue.  Take the line out before
you commit; ``ruff`` does not flag it.

``manage.py shell`` is the quickest way to try a query or a service call
against your own database::

  uv run backend/manage.py shell

A test stops the same way.  ``--pdb`` drops into the debugger at the first
failure or error instead of printing the traceback, and ``-x`` stops there::

  uv run pytest backend/tests/test_members_list.py -x --pdb

``breakpoint()`` inside a test or the code it calls needs ``-s`` as well, so
pytest does not capture the terminal ``pdb`` reads from.

pytest-randomly shuffles the test order on every run and prints the seed it
used at the top of the report.  When a failure depends on what ran before it,
``--randomly-seed=<that seed>`` repeats the same order, and ``-p no:randomly``
runs the tests in their written order.

The portal
----------

The portal is a React application running in the browser, so its debugger is
the browser's own developer tools.  With ``make dev-frontend`` running, Vite
serves every module with a source map: the **Sources** panel shows the
TypeScript files under ``src/`` as you wrote them, a breakpoint set there
holds, and a ``debugger;`` statement in the code stops there when the tools
are open.  The **Network** panel shows each ``/api/v1/`` call with its status
and JSON body, which is usually the fastest way to tell whether a problem is
in the portal or in the API.  React's own browser extension, React Developer
Tools, adds the component tree and each component's props and state.

The built bundle (``make build``) carries no source maps, so debug against the
Vite dev server.

A Vitest test runs in Node rather than a browser.  ``npx vitest`` in
``frontend/`` watches the files and reruns the tests a change touches, and
``screen.debug()`` inside a test prints the rendered DOM.


Logs
====

Development logs go to the terminal ``make run`` is in.  The application's
own records pass through the one ``console`` handler that
``caldart/settings/base.py`` defines, as ``LEVEL time logger message``, and
``runserver`` adds a line per request in Django's own format:

.. code-block:: text

   INFO 2026-09-26 09:14:03,512 django.utils.autoreload Watching for file changes with StatReloader
   [26/Sep/2026 09:14:07] "GET /portal/ HTTP/1.1" 200 1432

The root logger is at ``INFO``.  ``django.db.backends`` is held at
``WARNING``, so SQL is not echoed, and ``caldart.audit`` writes every
privileged action at ``INFO`` whatever the root level is
(:ref:`deploy-audit-log`).

``LOG_LEVEL`` is a production variable: ``prod.py`` reads it and the
development settings do not.  To see what a piece of code logs below
``INFO``, or the SQL it runs, raise that one logger from the shell and call
the code there::

  uv run backend/manage.py shell
  >>> import logging
  >>> logging.getLogger("django.db.backends").setLevel(logging.DEBUG)
  >>> from apps.members.models import MembershipPlan
  >>> list(MembershipPlan.objects.all())

Under pytest the root logger is at ``ERROR``, so a passing run is quiet.
pytest still captures every record, and a failing test prints them in its
report under *Captured log call*.


Email
=====

``.env.example`` sets ``EMAIL_URL=smtp://localhost:1025``, so every message
development sends reaches Mailpit and stops there.  Open
http://localhost:8025/ to read it as the recipient would, HTML and plain text
alike, with its attachments.  Mailpit keeps the newest 5000 messages and is
shared by every worktree on the machine.

Everything the application sends also leaves a row in the email log: the
address, the purpose, the subject, when, whether the mail server took it, and
the names of any attachments.  Three ways to read it:

* the portal: sign in as ``sysadmin@example.org`` and open **System**, whose
  **Email log** panel filters by date, purpose, recipient, status, and
  attachments, and exports what it shows as CSV or PDF;
* the Django admin, read-only, at http://localhost:8000/django-admin/mail/emaillog/;
* the API, ``GET /api/v1/system/emails`` (:doc:`api-system`).

A message Mailpit shows with no email log row did not come from the
application's own sending path.  Django's ``sendtestemail`` command is the
usual source, and :doc:`email` explains both.


The test database
=================

``pytest`` never touches your development database.  pytest-django creates a
second one named ``test_`` plus the name in ``DATABASE_URL``, so a worktree on
``caldart_dev_operations`` tests against ``test_caldart_dev_operations``, and
two worktrees can run their suites at the same time.  The test database is
built from the migrations at the start of each run and dropped at the end.

``--reuse-db`` keeps it between runs, which saves the migration step on a
quick loop, and ``--create-db`` forces a fresh one after a migration changes::

  uv run pytest backend/tests/test_members_list.py --reuse-db

The test settings read ``.env`` for ``DATABASE_URL`` and nothing else that
matters: throttles are off, email goes to memory, and the mock payment
provider is on (:doc:`testing`).


Reseeding
=========

``make seed`` is idempotent: it creates what is missing and leaves what is
there.  It does not undo changes you made to the demo data, so it is the right
command after pulling a branch that adds seed data and the wrong one for
starting over.

To start over, ``make reset`` drops the schema of the database in
``DATABASE_URL``, migrates, and seeds again.  It asks no question, so check
the database name in ``.env`` first.  It is also the only safe step after a
migration is regenerated.

The pieces can be run one at a time::

  uv run backend/manage.py seed_roles              # the role groups
  uv run backend/manage.py seed_demo               # accounts, members, payments
  uv run backend/manage.py seed_demo --seed 7      # the same shape, other names
  uv run backend/manage.py seed_content            # the example Wagtail site

``seed_demo``'s ``--seed`` is the random seed behind the generated names,
dates, and amounts; the default, ``20260904``, gives the data set the
end-to-end specs expect.  Seeding runs against today's date, so a database
seeded last week has reminders and renewals that are no longer due today.
``make reset`` brings them back.

``uv run backend/manage.py db_reset`` without ``--noinput`` names the database
and asks before it drops anything; :doc:`backup-restore` covers it with the
other data commands.
