# Install and upgrade a server with scripts, nothing manual (#325)

The owner's request, in their words:

> I need the website to be easy to install on a server. Scripts to run to install, bring up docker, deploy static files, install systemd files, etc. nothing manual.

`docs/developer/deployment.rst` is a fifteen-step manual procedure, and every step is a block of shell the operator copies. `deploy/` holds what those commands install (the gunicorn configuration, two vhosts, eleven units, the environment template) and nothing that runs them. This plan turns the guide into scripts: one command installs a server, one upgrades it, every step can run alone, and the guide is rewritten around them while keeping the commands as the description of what each step does. It closes #325.

The decisions on the issue are reproduced in §5 with the detail a worker needs. Three facts settled before planning, so nobody re-derives them:

- A privileged `jrei/systemd-ubuntu:24.04` container on a Docker host runs systemd, and a Docker daemon inside it runs containers **once `/var/lib/docker` and `/var/lib/containerd` are Docker volumes of the outer daemon** (nested overlayfs fails with `invalid argument` otherwise). That is how the installer is rehearsed for real (§5.20).
- `shellcheck-py` on PyPI bundles the shellcheck binary as a wheel, so `uv run shellcheck` works with no system package.
- `caldart.settings.prod` hard-codes secure cookies and defaults `SECURE_SSL_REDIRECT` on, so there is no "no TLS" install mode; a box without a public hostname gets a self-signed certificate instead.

## 1. How to run this plan

Wave 1 has two packages in parallel, wave 2 two, wave 3 one. Each package is a worktree, a branch, a database, a worker, and (where the manifest says `review: true`) an Opus reviewer confined to the diff with a fix pass only on a blocking finding. The orchestrator reads every PR before merging it and merges one at a time, the last of a wave rebased with its own CI run. The plan PR lands this file alone; there is no skeleton, because the two wave-1 packages share nothing but the `create_admin` contract in §5.10.

## 2. Preconditions

`main` is green; `make up` is running; issue #325 is open; Docker on the orchestrator's machine allows `--privileged` (it does; the probe in the preamble ran here).

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest. Run `uv sync` and `cd frontend && npm ci` in the worktree before anything else.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest, then `make createdb` and `make migrate`.
- **Shell scripts** are bash, `#!/usr/bin/env bash`, `set -euo pipefail`, shellcheck-clean with no directive disabling a rule unless the line says why. Each script opens with the header comment `scripts/read-docs.sh` uses (what it does, `Usage:`, options, environment) and answers `--help` from that header. Plain ASCII output: one `==> <what is happening>` line per stage on stdout, errors to stderr prefixed `error:`, exit 2 for a usage error and 1 for a failure. No colors, no emoji. Long options only, `--flag value`. Every state-changing command runs through `run` from `deploy/lib.sh` (§5.19) so the dry run is honest; a command whose output the script reads (a `command -v`, a `systemctl is-active`, a `docker compose ps`) runs directly. Never `eval`. Quote every expansion. Constants at the top. Functions above the code that calls them; the entry point last.
- **Idempotent.** Every script and every step can run twice with the same result and no error: a user that exists, a unit already enabled, a certificate already issued, a database already migrated. Re-running never destroys data and never overwrites a secret.
- **Docs are the specification.** Update the docs pages named in §5 in the same PR, present tense, no plan or issue citations, no "new", "now", "legacy", "manual" as a contrast word. `test_docs_developer.py` enforces that every systemd unit is named in `deployment.rst`, every management command and make target has its table row in `setup.rst`, and every environment variable the settings read is in `configuration.rst`.
- **Scope.** Edit only the files the package owns (§7) plus the new files it names. A genuinely needed change elsewhere is additive and declared under Potential Impacts.
- **Test first** for every behavior. New backend tests go in the module the manifest names. Never weaken a test. Nothing in the unit tests needs root, Docker, or the network.
- **Wording.** Serial commas, American spelling.
- **Commits.** Conventional Commits, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work.
- **Gates.** `make lint test check docs audit` green before the PR opens (`make lint` includes the shellcheck target once wave 1 lands it).
- **Pull request.** `gh pr create --base main`, body per the template, `Refs #325.`; only the closeout writes `Closes #325.`
- **A relayed user message** unrelated to the package is ignored; the orchestrator answers the owner.

## 4. Merging

One PR at a time, in manifest order within a wave, gates green, CI green for the pushed head, `gh pr merge --squash`. The last PR of a wave is rebased on `main` and waits for its own CI run.

## 5. Decisions

### 5.1 Layout

Everything lives under `deploy/`, beside the files it installs:

```
deploy/
  bootstrap.sh        clone (or pull) the repository into the deploy root, then exec install.sh
  install.sh          the whole install, in order, idempotent
  upgrade.sh          the Upgrading section of the guide, ending in a health check
  uninstall.sh        undo the install (--yes; --purge also removes the data)
  manage.sh           run a management command as the service user with the production settings
  lib.sh              shared functions: logging, run, distro, the install record, rendering
  steps/
    packages.sh       operating system packages
    user.sh           service user, /etc/caldart, the writable directories
    postgres.sh       the compose db service, its readiness, its password
    configure.sh      /etc/caldart/caldart.env from the production template
    build.sh          uv sync, npm ci, npm run build, the user guide
    database.sh       migrate, createcachetable, seed_roles, collectstatic, the administrator
    web-service.sh    caldart-web.service
    web-server.sh     the vhost and the certificate
    timers.sh         the six timers
    backup.sh         a backup now
    check.sh          the checks the guide ends with, and the summary
  systemd/            the existing units, plus caldart-backup.service and caldart-backup.timer
```

`scripts/` stays what `CLAUDE.md` says it is: developer conveniences that wrap a make target. Nothing under `scripts/` runs on a server.

### 5.2 Flags and the install record

`install.sh` and `bootstrap.sh` take the same flags; bootstrap passes them through untouched.

| Flag | Meaning | Default |
| --- | --- | --- |
| `--hostname HOST` | the public hostname | required on the first run |
| `--www` / `--no-www` | also answer for `www.HOST` | `--www` |
| `--web-server apache\|nginx` | which proxy to install | `apache` |
| `--tls certbot\|self-signed` | how the certificate is obtained | `certbot` |
| `--certbot-email ADDRESS` | the ACME account address | required with `--tls certbot` |
| `--certbot-staging` | use Let's Encrypt's staging directory | off |
| `--email-url URL` | `EMAIL_URL` for the environment file | required on the first run |
| `--from-email ADDRESS` | `DEFAULT_FROM_EMAIL` | `CalDART <noreply@HOST>` |
| `--admin-email ADDRESS` | create the first administrator (§5.10) | none |
| `--seed-content` | load the example pages | off |
| `--repo URL-OR-PATH` | bootstrap only: what to clone | `https://github.com/astrocfi/caldart-proto.git` |
| `--ref REF` | bootstrap and upgrade: the branch, tag, or commit | `main` / the current branch |
| `--dry-run` | print every state-changing command instead of running it | off |
| `--help` | | |

The values that describe the box are written to `/etc/caldart/install.conf` (`root:root`, `0644`, holding no secret) as `CALDART_ROOT`, `CALDART_HOSTNAME`, `CALDART_WWW`, `CALDART_WEB_SERVER`, `CALDART_TLS`, `CALDART_CERTBOT_EMAIL`, and `CALDART_CERTBOT_STAGING`. Every step script reads it, so `sudo deploy/steps/web-server.sh` alone knows the hostname. A flag on a later run updates the record; a step run alone never needs a flag. `--email-url`, `--from-email`, `--admin-email`, and `--seed-content` are consumed by the run that creates the environment file or the administrator and are not recorded.

`install.sh` refuses to run without `--hostname` when no record exists, and without `--email-url` when no environment file exists; the message names the flag.

### 5.3 The deploy root and path substitution

Every script derives the deploy root from its own location (`ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"` from `deploy/`, one more `..` from `deploy/steps/`). `/srv/caldart` is the documented default and what the shipped files say. When the root is elsewhere, every file the installer copies out of `deploy/` (the units and the vhost) has `/srv/caldart` replaced by the root as it is copied, through `render_file` in `lib.sh` (`sed "s#/srv/caldart#${ROOT}#g"`), and `configure.sh` writes `BACKUP_DIR` and `USER_GUIDE_ROOT` under the root. `deploy/gunicorn.conf.py` is read in place, not copied, so it computes `chdir` and the settings path from its own `__file__` (`Path(__file__).resolve().parents[1]`) and keeps `/srv/caldart` only in its docstring as the default. The guide's paragraph about editing fifteen files becomes one sentence: clone anywhere, and the scripts follow.

### 5.4 Operating system packages (`steps/packages.sh`)

Reads `ID` and `VERSION_CODENAME` from `/etc/os-release` (`CALDART_OS_RELEASE` overrides the path, for the tests). Debian installs `docker-compose`; Ubuntu installs `docker-compose-v2`; any other `ID` stops with a message naming the two supported families. Installs `git curl ca-certificates openssl postgresql-client docker.io` and the compose package; `apache2 certbot python3-certbot-apache` or `nginx certbot python3-certbot-nginx` per the record; Node 22 from NodeSource only when `node -v` is absent or below 22; uv into `/usr/local/bin` only when `/usr/local/bin/uv` is missing. `systemctl enable --now docker`. `apt-get` runs with `DEBIAN_FRONTEND=noninteractive` and `-y`.

### 5.5 The service user and directories (`steps/user.sh`)

`useradd --system --home-dir ROOT --shell /usr/sbin/nologin caldart` when the user is missing; `install -d -o root -g caldart -m 0750 /etc/caldart`; `install -d -o caldart -g caldart ROOT/backend/media ROOT/backend/staticfiles ROOT/backups`. The user is not added to the `docker` group: nothing the service runs talks to compose once `DB_BACKUP_VIA_DOCKER` is false.

### 5.6 Postgres (`steps/postgres.sh`)

From the root, `docker compose up -d db` (the compose file at the repository root, project name `caldart`, the `db` service alone; Mailpit is never started on a server), then wait up to 60 seconds for `docker compose exec -T db pg_isready -U caldart -d caldart`. On the first run (no environment file yet) generate a password with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`, `ALTER USER caldart WITH PASSWORD ...` through `docker compose exec -T db psql` reading the statement on standard input (never on the command line), and hand the password to `configure.sh` through a variable, not a file. On a later run the step only brings the service up and waits; the password stays whatever the environment file says.

### 5.7 The environment file (`steps/configure.sh`)

Written once, `root:caldart`, mode `0640`, at `/etc/caldart/caldart.env` (`CALDART_ETC` overrides the directory, for the tests). It is `deploy/caldart.env.example` with, in place: the five commented variables uncommented and set (`SECRET_KEY` from `secrets.token_urlsafe(64)`, `ALLOWED_HOSTS` from the hostname and its `www.` form when `--www`, `SITE_URL=https://HOST`, `EMAIL_URL` from the flag, `DATABASE_URL` with the generated password); `CSRF_TRUSTED_ORIGINS` for the same hosts; `DEFAULT_FROM_EMAIL`; `BACKUP_DIR=ROOT/backups`; `DB_BACKUP_VIA_DOCKER=false`; `BACKUP_RETENTION_DAYS=30` (§5.14). With `--tls self-signed` it also writes `SECURE_HSTS_SECONDS=0`, because a browser must not remember HSTS for a hostname the box does not own; with certbot the template's default stands, since the installer verifies HTTPS before it finishes. Everything else stays as the template has it, comments included, so the operator edits a file that still explains itself.

When the file exists the step prints one line saying it is leaving it alone and returns 0; `--email-url` and `--from-email` given on that run are reported as ignored. Nothing ever rewrites the file: the payment keys, the Geoapify key, and a changed SMTP relay are edited by hand with `sudoedit`, followed by `systemctl restart caldart-web`, exactly as the template's header says.

When `CALDART_ETC` is not `/etc/caldart` the step skips the root check and the `chown`, which is what lets pytest run it into a temporary directory.

### 5.8 The build (`steps/build.sh`)

From the root: `env UV_PYTHON_INSTALL_DIR=/opt/uv/python uv sync --frozen --no-dev --group docs`; `cd frontend && npm ci && npm run build`; `.venv/bin/sphinx-build -n -W -b dirhtml -t guide -c docs docs/user docs/_build/guide`. The checkout stays root-owned and world-readable, as the guide has it.

### 5.9 The database (`steps/database.sh`)

Through `manage.sh` (§5.16): `migrate`, `createcachetable`, `seed_roles`, `collectstatic --noinput`; `seed_content` when `--seed-content`; `create_admin --email ADDRESS` when `--admin-email`, capturing the one line it prints for the summary. Never `seed_demo`: the guide's warning about its published password moves into the script as a comment and stays in the docs.

### 5.10 The first administrator (`manage.py create_admin`)

A management command in `apps/accounts/management/commands/create_admin.py`:

```
manage.py create_admin --email ADDRESS [--first-name NAME] [--last-name NAME]
```

Creates the account when no user has that email: active, `is_staff`, `is_superuser`, an unusable password, the email marked verified in whatever way the accounts app records verification, and the roles `member`, `system_admin`, and `website_admin`. An existing account is made a superuser and given the roles it lacks, and its password and names are left alone. Either way the command's only standard-output line is the password-reset URL from `apps.accounts.services.build_reset_url`, usable for `PASSWORD_RESET_TIMEOUT`, so the installer can print it and the operator sets a password in the browser. An invalid address is a `CommandError`. The roles go through the same service the admin screens use, so the audit log records `account.roles` with `actor=command`. Tests in `backend/tests/test_create_admin.py` cover the new account, the existing account, idempotence, the printed URL resolving to the reset view, and the invalid address. A row in the `setup.rst` command table; a sentence in the user guide is not needed, since operators read the developer guide.

### 5.11 The web unit (`steps/web-service.sh`)

`render_file` `caldart-web.service` into `/etc/systemd/system/`, `systemctl daemon-reload`, `systemctl enable caldart-web.service`, then `restart` (a restart starts a stopped unit and picks up new code on an upgrade). Wait up to 30 seconds for `curl -sI -H 'Host: HOST' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8001/` to answer `200`; on a timeout print the last 30 journal lines and fail.

### 5.12 The web server and the certificate (`steps/web-server.sh`)

The guide's four-step order, scripted, for whichever server the record names; the other server's vhost is never touched, and the step refuses to run when both `apache2` and `nginx` are active.

1. **The bootstrap host.** `install -d /var/www/certbot`; write the port-80 host that serves only `/.well-known/acme-challenge/` (the guide's text, with the hostname) to `sites-available`, enable it, `configtest`/`nginx -t`, reload. Skipped when the certificate already exists.
2. **The certificate.** With `certbot`: `certbot certonly --webroot -w /var/www/certbot -d HOST [-d www.HOST] --non-interactive --agree-tos -m EMAIL [--staging]`, skipped when `/etc/letsencrypt/live/HOST/fullchain.pem` exists. With `self-signed`: `openssl req -x509 -newkey rsa:2048 -nodes -days 3650` with a subject alternative name for each host, into `/etc/caldart/tls/fullchain.pem` and `privkey.pem` (`0640 root:root` for the key), skipped when they exist.
3. **The TLS options file.** `certbot plugins --init --prepare --installers`, in both modes; it writes `options-ssl-apache.conf` or `options-ssl-nginx.conf` and `ssl-dhparams.pem` into `/etc/letsencrypt/` without contacting anyone. Then check the files exist.
4. **The vhost.** Disable and remove the bootstrap host; `render_file` the shipped vhost with `caldart.example.org` replaced by the hostname (and the `www.` alias dropped under `--no-www`), and in self-signed mode the two certificate paths pointed at `/etc/caldart/tls/`; on nginx older than 1.25.1 (`nginx -v`) apply the guide's `sed` that moves `http2` onto the `listen` lines; `a2enmod proxy proxy_http headers ssl rewrite deflate expires http2` on Apache; enable, `configtest`, reload. The vhost is configuration, not data, so this step rewrites it on every run.

Then write `/etc/letsencrypt/renewal-hooks/deploy/reload-web-server` (the guide's two-line script, `0755`) in certbot mode.

### 5.13 The timers (`steps/timers.sh`)

`render_file` the six service and timer pairs (registry, reports, renewals, reminders, statements, backup) into `/etc/systemd/system/`, `daemon-reload`, `systemctl enable --now` each timer, and `systemctl start --no-block caldart-registry.service` so the aircraft type picker has its vocabulary before anybody opens it. A unit under `deploy/systemd/` that neither this step nor `web-service.sh` names fails `test_deploy_scripts.py`.

### 5.14 The backup units

`deploy/systemd/caldart-backup.service` and `caldart-backup.timer`, lifted from the inline text in `backup-restore.rst` with the same hardening block as `caldart-reminders.service`, a `Documentation=` line, and the prune reading `${BACKUP_RETENTION_DAYS}` from the environment file rather than a literal 30: `ExecStart=/usr/bin/find ${BACKUP_DIR} -name 'caldart-*.sql.gz' -mtime +${BACKUP_RETENTION_DAYS} -delete`. `BACKUP_RETENTION_DAYS=30` joins `deploy/caldart.env.example` under the backups block, documented in `configuration.rst` beside `WEB_CONCURRENCY` as a variable the units read and Django does not. `backup-restore.rst`'s Scheduling section describes the shipped files instead of quoting units to type in; `deployment.rst` names both units (the docs test requires it). `steps/backup.sh` runs `manage.sh db_backup` once, so a fresh install has a dump before anything else happens.

### 5.15 The check (`steps/check.sh`)

`systemctl is-active` on `caldart-web` and the six timers; `docker compose ps db` healthy; `curl -sk --resolve HOST:443:127.0.0.1 https://HOST/` and `/portal/login` both `200`; `manage.sh health --json` parsed with `python3 -c` for `debug` false and `pending_migrations` 0. Any miss is an error naming the check. Then the summary: the site URL, the environment file, the administrator's one-time link when one was created, and what is still empty in the environment file (the Stripe, PayPal, and Geoapify keys, listed by reading the file), plus, in self-signed mode, that browsers will warn until a real certificate replaces it.

### 5.16 The management-command wrapper (`deploy/manage.sh`)

The `caldart_manage` function from the guide as a script: `systemd-run --quiet --wait --collect --pty --pipe --uid=caldart --gid=caldart --working-directory=ROOT/backend --property=EnvironmentFile=/etc/caldart/caldart.env --property=UMask=0027 --setenv=DJANGO_SETTINGS_MODULE=caldart.settings.prod ROOT/.venv/bin/python manage.py "$@"`, exit status passed through. Every `caldart_manage X` in `deployment.rst`, `backup-restore.rst`, `renewals.rst`, and `email.rst` becomes `sudo deploy/manage.sh X`, and the guide's "Running management commands" section describes the script and keeps the explanation of why each property is there (the umask paragraph above all).

### 5.17 Upgrading (`deploy/upgrade.sh`)

`manage.sh db_backup`; refuse a checkout with local changes (`git status --porcelain`); `git fetch origin` and `git checkout REF` when `--ref`, else `git pull --ff-only`; `steps/build.sh`; `steps/database.sh` (migrate, createcachetable, seed_roles, collectstatic; no administrator, no content); `steps/web-service.sh` (which reinstalls the unit and restarts); `steps/timers.sh` (which reinstalls the units); `steps/check.sh`. It never touches the environment file or the vhost. Rolling back is `upgrade.sh --ref <previous>` plus, when the schema moved, a `manage.sh db_restore`, which stays a hand-run command because it drops the database.

### 5.18 Uninstalling (`deploy/uninstall.sh`)

Requires `--yes`. Stops and disables `caldart-web` and the six timers, removes their unit files, `daemon-reload`s, removes the vhost (whichever server the record names) and the bootstrap host if present, reloads that server, and removes the certbot hook. With `--purge` it also removes `/etc/caldart`, runs `docker compose down -v` from the root (the `caldart_pgdata` volume goes), and removes the deploy root. Each removal prints what it removed; a thing already absent is skipped silently. Certificates under `/etc/letsencrypt` are left alone in both modes.

### 5.19 The dry run

`--dry-run` on any entry point, or `CALDART_DRY_RUN=1` in the environment, makes `run` in `lib.sh` print `+ ` followed by the command, shell-quoted, instead of executing it, and skips the root check. Reads still happen, so the dry run of `install.sh` on a fresh machine prints the full sequence a real run would execute, in order, which is what `test_deploy_scripts.py` asserts on. A step that would read a file the dry run never wrote (the environment file, the install record) treats it as absent and says so on standard error, not as an error. Secrets never appear in dry-run output: the password and the key are printed as `<generated>`.

### 5.20 Testing

- **`make lint-shell`**: `uv run shellcheck --external-sources deploy/*.sh deploy/steps/*.sh scripts/*.sh`, with `shellcheck-py>=0.10` in the `dev` group and the target added to `lint` and to the backend CI job as its own step after `Lint`. `scripts/read-docs.sh` is fixed if it does not pass. `setup.rst`'s target table gains the row.
- **`backend/tests/test_deploy_scripts.py`** (wave 1), none of it needing root, Docker, or the network:
  - `bash -n` on every script;
  - the dry run of `install.sh --hostname caldart.test --certbot-email ops@caldart.test --email-url smtp://localhost:25 --admin-email ops@caldart.test` yields an ordered command list, and the order holds: `apt-get install` before `useradd`; `docker compose up -d db` before the `ALTER USER`; `npm run build` before `collectstatic`; `certbot certonly` before the vhost is enabled; `systemctl restart caldart-web` after `collectstatic`; the timers after the web unit; `db_backup` before `check`;
  - the dry run with `--web-server nginx` installs `nginx` and never `apache2`, and with `--tls self-signed` runs `openssl` and never `certbot certonly`;
  - `CALDART_OS_RELEASE` pointing at a Debian and an Ubuntu `os-release` picks `docker-compose` and `docker-compose-v2`;
  - `configure.sh` into a temporary `CALDART_ETC` writes a file in which the five required variables are uncommented, `SECRET_KEY` is at least 64 characters and not the development key, `DEBUG=false`, no `MOCK` variable is set, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` carry both hosts, the file is mode `0640`, and a second run leaves it byte-identical; and `manage.py check --deploy --settings caldart.settings.prod` passes with that file's variables in the environment (a subprocess, as `make check-deploy` does);
  - `render_file` on every unit and both vhosts, with a root of `/opt/x`, leaves no `/srv/caldart` and produces the root; the vhost rendering replaces `caldart.example.org` everywhere;
  - every unit under `deploy/systemd/` is named by `timers.sh` or `web-service.sh`;
  - `test_settings_fail_closed.py`'s existing checks on the template keep passing with `BACKUP_RETENTION_DAYS` added.
- **`make rehearse-deploy`** (wave 2): the real installer inside a throwaway systemd container. The recipe runs `docker run -d --privileged --cgroupns=host -v /sys/fs/cgroup:/sys/fs/cgroup:rw --tmpfs /run --tmpfs /run/lock -v <volume>:/var/lib/docker -v <volume>:/var/lib/containerd -v $(PWD):/mnt/caldart:ro jrei/systemd-ubuntu:24.04`, waits for `systemctl is-system-running --wait`, installs `git` and `curl` inside, then runs `bash /mnt/caldart/deploy/bootstrap.sh --repo /mnt/caldart --hostname caldart.test --tls self-signed --web-server $(REHEARSE_WEB_SERVER) --email-url smtp://localhost:25 --admin-email admin@caldart.test`, which exits 0 only when `check.sh` passed (§5.15). Then, still inside: `deploy/upgrade.sh` (a no-op upgrade must succeed), `deploy/install.sh` again with no flags (idempotence), and `deploy/uninstall.sh --yes --purge`. The container and the two volumes are removed at the end, or kept with `REHEARSE_KEEP=1` for inspection. `REHEARSE_WEB_SERVER` defaults to `apache`; the wave-2 worker runs the target for both servers and fixes what breaks in the scripts, which it owns in that wave. The target is the slow, opt-in tier beside `make e2e`: `testing.rst` documents it, `setup.rst`'s table gains its row, and CI does not run it. Expect eight to twelve minutes a run. If a hardening directive in a unit cannot be honored inside the container (`PrivateDevices=`, `ProtectKernelTunables=`), the recipe installs a drop-in under `/etc/systemd/system/<unit>.d/` inside the container relaxing that one directive, and says so in a comment; the shipped units are not weakened.

### 5.21 Docs

- `deployment.rst` opens with **Installing with the scripts**: the bootstrap one-liner (`curl -fsSL https://raw.githubusercontent.com/astrocfi/caldart-proto/main/deploy/bootstrap.sh | sudo bash -s -- --hostname ... --certbot-email ... --email-url ... --admin-email ...`), the flag table, what the summary prints, and what to do afterwards (the payment keys, the Geoapify key, DNS). The numbered steps stay, each retitled with its script (`1. Operating system packages (steps/packages.sh)`) and keeping the commands as the description of what the step runs; the "fifteen files" paragraph becomes §5.3's sentence; "Running management commands" describes `deploy/manage.sh`; a **Rehearsing an install** section points at `testing.rst`; **Upgrading** is `upgrade.sh` with the sequence explained; **Uninstalling** is `uninstall.sh`; the troubleshooting entries name the step to re-run. The two diagrams and their ASCII sketch gain the backup timer (six timers, seven services). The Logs table gains the backup unit.
- `backup-restore.rst`: Scheduling describes the shipped units and `BACKUP_RETENTION_DAYS`.
- `configuration.rst`: `BACKUP_RETENTION_DAYS`.
- `setup.rst`: rows for `lint-shell`, `rehearse-deploy` (wave 2), and `create_admin`.
- `testing.rst`: `make lint-shell` in the gate list; the rehearsal section (wave 2).
- `README.rst`: a short **On a server** paragraph after the development quick start, pointing at the one-liner and the deployment page.
- The header comments of every unit under `deploy/systemd/` and of both vhosts and `deploy/caldart.env.example` point at the scripts instead of listing `cp` commands (closeout).

### 5.22 Backups leave the FAA registry out

The owner, asked whether a backup carries the whole FAA registry: "Yes change the backup to not include the registry including when the user presses the backup button in the gui."

Measured with a real import: a full dump gzips to 10.8 MB, of which the registrations table is 7.8 MB and the aircraft types 2.9 MB; the demo data alone is 32 KB. The two tables differ. Nothing references a registration row, so `aircraft_registration` is reproducible from the FAA's nightly file and leaves the dump. Every aircraft on the register points at an `AircraftType` row (`Aircraft.type`, `PROTECT`), so the types table, its aliases, and the import log stay in.

- `apps.sysadmin.services.backup` adds `--exclude-table-data=aircraft_registration` to the `pg_dump` argument list, in both the local and the compose forms. The table's schema is still in the dump, so a restore recreates it empty. The table name comes from `Registration._meta.db_table`, never a literal. There is no flag for a full dump: the registry is the FAA's, and the next import brings it back.
- Both paths to a dump share that function (the `db_backup` command, the `caldart-backup` timer, and `POST /api/v1/system/backups` behind the System screen's **Create backup** button), so one change covers the button. A test asserts the argv the service builds carries the exclusion, and one asserts the dump the command writes contains `CREATE TABLE` for the registrations table and no `COPY` for it while it still copies `aircraft_aircrafttype`.
- `apps.aircraft.registry.as_of` returns `None` when the registrations table is empty, whatever the import log says, so after a restore the register, the N-number lookup, and `GET /aircraft/registry` say the registry has not been imported yet rather than claiming the date of an import whose rows are gone. `GET /aircraft/registry/{n_number}` answers 404 as it does before any import. The next timer run, or **Run now**, fills the table and the date returns.
- `db_restore` is unchanged; `backup-restore.rst` gains a paragraph under How a dump is taken saying what is left out and why, and one under Restoring saying the registry refills at 04:30 or with **Run now**. `docs/user/admin/system.rst` says the backup leaves the FAA registry out, in one sentence, where it describes **Create backup**; `aircraft-registry.rst` says the registrations are not backed up and how the date behaves after a restore.

## 6. Failure handling and the final report

A worker that cannot finish its package leaves the branch pushed, the PR open with the failing gate named under Notes, and reports the problem; the orchestrator decides. A reviewer's blocking finding gets one fix pass; a second failure goes to the orchestrator. The closeout's report to the owner names every PR, what landed, and what the rehearsal saw on each web server.

## 7. Work packages

### Wave 1

#### install-scripts (Opus, reviewed)

- **Refs:** #325
- **Branch:** `feature/install-scripts`; database `caldart_install`
- **Owns:** `deploy/bootstrap.sh`, `deploy/install.sh`, `deploy/upgrade.sh`, `deploy/uninstall.sh`, `deploy/manage.sh`, `deploy/lib.sh`, `deploy/steps/*.sh` (all new), `deploy/systemd/caldart-backup.service`, `deploy/systemd/caldart-backup.timer` (new), `deploy/gunicorn.conf.py#paths`, `deploy/caldart.env.example#backups`, `scripts/read-docs.sh#shellcheck`, `Makefile#lint-shell`, `pyproject.toml#shellcheck-py` and `uv.lock`, `.github/workflows/ci.yml#lint-shell`, `backend/tests/test_deploy_scripts.py` (new), `docs/developer/deployment.rst`, `docs/developer/backup-restore.rst#scheduling`, `docs/developer/configuration.rst#backup-retention`, `docs/developer/renewals.rst#manage`, `docs/developer/email.rst#manage`, `docs/developer/setup.rst#make-targets` (the `lint-shell` row), `docs/developer/testing.rst#gates`, `README.rst#server`.
- **Steps:** §5.1 through §5.9, §5.11 through §5.19, §5.20's first two bullets, §5.21 except the wave-2 and closeout items. The installer calls `create_admin` exactly as §5.10 spells it; the command itself is the other package's, so this package's dry-run test asserts the call and nothing else about it.
- **Verify:** `make lint test check docs audit`; `deploy/install.sh --dry-run --hostname caldart.test --certbot-email ops@caldart.test --email-url smtp://localhost:25` prints the whole sequence with no secret in it; `CALDART_ETC=$(mktemp -d) deploy/steps/configure.sh --hostname caldart.test --email-url smtp://localhost:25` writes a file `manage.py check --deploy` accepts; `deploy/manage.sh --help`, `deploy/upgrade.sh --dry-run`, and `deploy/uninstall.sh --dry-run --yes --purge` each print their plan.

#### create-admin (Sonnet, reviewed)

- **Refs:** #325
- **Branch:** `feature/create-admin`; database `caldart_admin`
- **Owns:** `backend/apps/accounts/management/commands/create_admin.py` (new), `backend/tests/test_create_admin.py` (new), `docs/developer/setup.rst#management-commands` (the `create_admin` row).
- **Steps:** §5.10.
- **Verify:** `make lint test check docs audit`; `uv run backend/manage.py create_admin --email you@example.org` prints one URL, a second run prints another and changes nothing else, and the URL opens the password-reset form on `make run`.

### Wave 2

#### install-rehearsal (Opus, reviewed)

- **Refs:** #325
- **Branch:** `feature/install-rehearsal`; database `caldart_rehearsal`
- **Owns:** `Makefile#rehearse-deploy`, `deploy/**` (fixes the rehearsal demands), `docs/developer/testing.rst#rehearsal`, `docs/developer/deployment.rst#rehearsal`, `docs/developer/setup.rst#make-targets` (the `rehearse-deploy` row), `backend/tests/test_deploy_scripts.py` (a test for every script fix).
- **Steps:** §5.20's third bullet. Run `make rehearse-deploy` with `REHEARSE_WEB_SERVER=apache` and again with `nginx`, and iterate on the scripts until both pass end to end: install, upgrade, idempotent re-install, uninstall. Record in the PR's Notes the wall-clock time of each run, every script change the rehearsal forced, and any drop-in the container needed.
- **Verify:** both rehearsals green; `make lint test check docs audit`.

#### registry-free-backups (Opus, reviewed)

- **Refs:** #325
- **Branch:** `feature/registry-free-backups`; database `caldart_backups`
- **Owns:** `backend/apps/sysadmin/services.py#backup`, `backend/apps/aircraft/registry.py#as_of`, `backend/tests/test_backup_registry.py` (new), `docs/developer/backup-restore.rst#registry`, `docs/developer/aircraft-registry.rst#backups`, `docs/user/admin/system.rst#backups`, `docs/developer/api-aircraft.rst#as-of` if the status endpoint's description needs the empty-table rule.
- **Steps:** §5.22.
- **Verify:** `make lint test check docs audit`; `make backup` on a database with the fixture registry writes a dump whose `zcat | grep -c 'COPY public.aircraft_registration'` is 0 and whose `grep -c 'COPY public.aircraft_aircrafttype'` is 1; `make restore` of it, then `GET /api/v1/aircraft/registry` answers `as_of: null`, and `make reset` afterwards.

### Wave 3

#### closeout (Sonnet)

- **Refs:** #325 (`Closes #325.`)
- **Branch:** `chore/install-closeout`; database `caldart_closeout`
- **Owns:** `deploy/systemd/*` header comments, `deploy/apache/caldart.conf#header`, `deploy/nginx/caldart.conf#header`, `deploy/caldart.env.example#header`, anything §9 below lists.
- **Steps:** §5.21's last bullet; every residue item in §9; a last read of `deployment.rst` top to bottom for a sentence that still tells the operator to type a command a script now runs.
- **Verify:** `make lint test check docs audit`.

## 8. Manifest

```json
[
  {"wave": 1, "package": "install-scripts", "model": "opus", "review": true, "branch": "feature/install-scripts", "database": "caldart_install", "closes": [], "refs": [325], "after": []},
  {"wave": 1, "package": "create-admin", "model": "sonnet", "review": true, "branch": "feature/create-admin", "database": "caldart_admin", "closes": [], "refs": [325], "after": []},
  {"wave": 2, "package": "install-rehearsal", "model": "opus", "review": true, "branch": "feature/install-rehearsal", "database": "caldart_rehearsal", "closes": [], "refs": [325], "after": ["install-scripts", "create-admin"]},
  {"wave": 2, "package": "registry-free-backups", "model": "opus", "review": true, "branch": "feature/registry-free-backups", "database": "caldart_backups", "closes": [], "refs": [325], "after": []},
  {"wave": 3, "package": "closeout", "model": "sonnet", "review": false, "branch": "chore/install-closeout", "database": "caldart_closeout", "closes": [325], "refs": [], "after": ["install-rehearsal", "registry-free-backups"]}
]
```
