# Install under /opt, serve under a URL prefix behind an existing site, mail through local postfix, and a configurable Postgres port (#334)

The owner's request, in their words:

> Put the installation under /opt. I need to be able to make this a sub url like https://paloaltodart.org/caldart-proto and don't need ssl in that case. Email should be able to be sent through local postfix in addition to an smtp server. See how TaskBuffet does it. Also does installing this mess up other users of Postgres in a docker container on the same machine.

The install scripts under `deploy/` (the plan before this one) assume the site is the whole hostname, obtain a certificate, and run from `/srv/caldart` with Postgres on 5432. This plan makes the deploy root `/opt/caldart`, lets the site live under a URL prefix behind a web server that already serves the hostname over HTTPS, makes a local postfix a first-class mail path, and makes the Postgres host port a flag so a machine already running Postgres is left alone. The decisions on the issue are reproduced in §5 with the detail a worker needs. It closes #334.

Facts settled before planning:

- `whitenoise` 6.x strips `FORCE_SCRIPT_NAME` from `STATIC_URL` before matching a request, and Django prefixes `STATIC_URL` and `MEDIA_URL` with the script name itself when they are root-relative, so a prefixed deployment needs only `FORCE_SCRIPT_NAME` on the Django side. `django-vite` builds asset URLs from Django's static URL, not from Vite's `base`.
- The portal has one `API_BASE` constant and one router `basename`; the public site and the templates carry a few dozen root-relative links. `frontend/src` has 185 root-relative path literals in 64 files, most of them React Router `to=` paths, which are relative to the basename and need no change.
- TaskBuffet sends mail either through a relay (`SMTP_HOST`, which may be `localhost`) or directly to each recipient's MX. The relay through `localhost:25` is the postfix path and is what this plan adopts; direct MX delivery is not adopted, because mail from a host with no reputation is what receiving filters refuse.
- Another Postgres on the machine, native or in another container, collides with the compose `db` service only on host port 5432. The compose project `caldart`, its volume `caldart_caldart_pgdata`, and its network are namespaced and touch nothing else, and `apt-get install docker.io` on a machine that already has Docker installs nothing.

## 1. How to run this plan

Wave 1 has three packages in parallel, wave 2 two, wave 3 one. Each package is a worktree, a branch, a database, a worker, and (where the manifest says `review: true`) an Opus reviewer confined to the diff with a fix pass only on a blocking finding. The orchestrator reads every PR before merging it and merges one at a time, the last of a wave rebased with its own CI run. The plan PR lands this file alone: the three wave-1 packages share only the names fixed in §5 (`URL_PREFIX`, `data-url-prefix`, `--db-port`, `--email local`, `--tls existing`, `--url-prefix`, `--attach-to`).

## 2. Preconditions

`main` is green; `make up` is running; issue #334 is open; Docker on the orchestrator's machine allows `--privileged`.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those, the conventions of the previous plan hold word for word (`plans/archive/2026-09-27-server-install.md` §3: shell style, idempotence, `run` for every state-changing command, docs as the specification, scope, test first, serial commas, commit trailers, gates, `Refs #334.` in every PR body and `Closes #334.` only in the closeout's, relayed messages ignored). In addition:

- **`make lint` includes `lint-shell`**, so every changed script is shellcheck-clean.
- **A prefix never appears as a literal** in production code: `/caldart-proto` is a test value only. Code reads `settings.URL_PREFIX`, `request.META["SCRIPT_NAME"]`, `{% url %}`, `reverse()`, `static()`, or the page's `data-url-prefix`.
- **The e2e suite runs twice where the package touches the portal**: `make e2e` as before and `make e2e E2E_URL_PREFIX=/caldart-proto` (§5.9) once wave 2 lands it; a wave-1 portal package runs the plain suite and its own prefix tests.

## 4. Merging

As in the previous plan: one PR at a time, in manifest order within a wave, gates green, CI green for the pushed head, `gh pr merge --squash`, the last PR of a wave rebased on `main` and waiting for its own CI run.

## 5. Decisions

### 5.1 `/opt/caldart`

The default deploy root is `/opt/caldart`. Every shipped file that names `/srv/caldart` says `/opt/caldart` instead: `deploy/lib.sh` (`SHIPPED_ROOT`), `deploy/bootstrap.sh` (the default `CALDART_ROOT`), `deploy/gunicorn.conf.py`'s docstring, both vhosts, every unit, `deploy/caldart.env.example`, the `Makefile`'s rehearsal comments, `README.rst`, and the developer guide (`deployment.rst`, `backup-restore.rst`, `configuration.rst`, `testing.rst`). `test_deploy_scripts.py` renders with a root of `/srv/x` where it used `/opt/x`, so the substitution is still exercised against a different path. `/opt/uv/python`, where uv keeps its interpreter, is unrelated and unchanged. Path substitution (previous plan §5.3) still lets an operator clone anywhere.

### 5.2 The database port

- `docker-compose.yml` publishes `"127.0.0.1:${CALDART_DB_PORT:-5432}:5432"`. Development is unchanged: `make up` never sets the variable.
- `install.sh` takes `--db-port PORT` (default `5432`), validates it as an integer in 1024–65535, and records it as `CALDART_DB_PORT` in `install.conf`. `lib.sh` exports `CALDART_DB_PORT` from the record before any `docker compose` command, so `postgres.sh`, `check.sh`, and `uninstall.sh` all address the same container.
- `postgres.sh`, on a run that will create the container (no `caldart-db-1` container exists), checks the port with `ss -ltnH "sport = :PORT"`; if something already listens there, it stops: `error: port PORT is already in use on this machine; run install.sh --db-port PORT to put CalDART's Postgres on another port`. A later run against an existing container skips the check.
- `configure.sh` writes `DATABASE_URL=postgres://caldart:<password>@localhost:PORT/caldart`.
- `deploy/compose.sh` is the operator's way to run compose: it loads the record, exports the port, `cd`s to the root, and `exec`s `docker compose "$@"`. Every `sudo docker compose ...` in the guide becomes `sudo deploy/compose.sh ...`; the scripts call `docker compose` themselves after exporting the port.
- `deployment.rst` gains a short **Sharing the machine** section that answers the question on the issue: the compose project, volume, and network are namespaced; the only shared thing is the host port, and `--db-port` moves it; an existing Docker is left as it is.

### 5.3 Mail through local postfix

- `install.sh` takes `--email local` as the alternative to `--email-url URL`; exactly one of the two is required while no environment file exists (both is a usage error). `local` writes `EMAIL_URL=smtp://localhost:25`.
- With `--email local`, `configure.sh` checks with `ss -ltnH "sport = :25"` that something listens on port 25 and, if nothing does, prints a note (not an error) that mail will fail until postfix is installed and listening on localhost. The installer installs no mail server: a machine that serves `paloaltodart.org` has one, and a satellite postfix is the operator's choice.
- `email.rst` gains **A local postfix** beside the relay: `smtp://localhost:25`, no credentials, `DEFAULT_FROM_EMAIL` on a domain whose SPF names this host (or postfix set as a satellite relaying to a smarthost with `relayhost`), and `deploy/manage.sh sendtestemail you@example.org` (Django's own command) as the check. The template's `EMAIL_URL` comment names both forms.

### 5.4 `URL_PREFIX` on the Django side

- `URL_PREFIX` (environment, default empty) is read in `base.py`: normalized to `/segment[/segment]` with no trailing slash, or the empty string. It sets `FORCE_SCRIPT_NAME` (to the prefix, or `None` when empty). `LOGIN_URL` and `LOGIN_REDIRECT_URL` are built from it. `STATIC_URL` and `MEDIA_URL` stay `/static/` and `/media/`: Django prefixes them itself. `SESSION_COOKIE_PATH` and `CSRF_COOKIE_PATH` stay `/`: the same host may run only one CalDART, and a narrower path would break the public site's cookies. `WAGTAILADMIN_BASE_URL` is `SITE_URL`, which carries the prefix (§5.6).
- `prod.py` refuses a `SITE_URL` whose path is not the prefix (`ImproperlyConfigured`), so the two cannot disagree.
- The two HTML shells (`base.html`, `portal.html`) carry `data-url-prefix="{{ url_prefix }}"` on `<html>`, from a context processor in `apps.cms` (which already has one), and every root-relative `href`/`src`/`action` in the templates becomes `{% url %}` or `{{ url_prefix }}/...`; the user guide link is `{{ url_prefix }}/docs/`. Emails built from `SITE_URL` need no change; a test proves every email URL in the notifications catalog starts with `SITE_URL`.
- The CMS seed's rich-text links (`/portal/join` and the like in `seed_content_data.py`) are written with the prefix at seed time; a test seeds under a prefix and asserts the stored HTML.
- The user guide at `/docs/` is served by Django, so it follows the prefix; its internal links are relative (dirhtml) and need nothing.
- `backend/tests/test_url_prefix.py` covers: normalization (`caldart-proto`, `/caldart-proto/`, `//x//` all read as `/caldart-proto`... the last is refused), `FORCE_SCRIPT_NAME`, `LOGIN_URL`, `reverse()` of a portal and an API route carrying the prefix, `static()` carrying it, the shell attribute, a `Client` request with `SCRIPT_NAME` set reaching the portal view and the API, whitenoise serving a hashed asset under the prefix (`needs_frontend_build`), and `prod.py` refusing a mismatched `SITE_URL`. `configuration.rst` documents `URL_PREFIX`; both env templates gain it commented out.

### 5.5 The prefix in the frontend

- One module, `src/portal/urlPrefix.ts`, reads `document.documentElement.dataset.urlPrefix` once (empty when absent) and exports `URL_PREFIX`, `sitePath(path)` (prefix + path), and the derived `API_BASE` (`${URL_PREFIX}/api/v1`) and `PORTAL_BASENAME` (`${URL_PREFIX}/portal`). `client.ts` and `App.tsx` import from it. Every remaining root-relative literal that is a real URL (an `<a href>`, `window.location`, a `fetch`, a `/docs/`, `/admin/`, `/media/`, `/static/` reference) goes through `sitePath`; React Router `to=` paths stay as they are. The public site's `src/site/main.ts` reads the same attribute.
- Vite builds with `base: './'`, so the bundle's own dynamic imports and asset references resolve relative to the entry script wherever it is served; the manifest stays under `dist/.vite/`, and django-vite keeps building the entry URLs from Django's static URL. If the relative base breaks `modulepreload` or a CSS `url()` in the e2e run, the fallback is a build-time `VITE_BASE` that `build.sh` passes from the record; the worker says in the PR which it shipped and why.
- Tests: `urlPrefix.test.ts` with and without the attribute; the client and router tests render with `data-url-prefix` set and assert the fetch URLs and the router basename; the msw handlers match either base. `npm run typecheck` and the contract test are unaffected.

### 5.6 The installer's `existing` TLS mode and the prefix

- `install.sh` takes `--url-prefix PREFIX` (default empty; validated like §5.4, recorded as `CALDART_URL_PREFIX`) and a third TLS mode, `--tls existing`, recorded like the others. `existing` means: a web server on this machine already serves the hostname over HTTPS; the installer obtains no certificate, installs no vhost, and installs no certbot package.
- `configure.sh` writes `SITE_URL=https://HOST<PREFIX>`, `URL_PREFIX=<PREFIX>`, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` as before (origins are scheme and host only). `--www` still adds the `www.` host. `SECURE_HSTS_SECONDS` is untouched in `existing` mode: the existing site owns HSTS.
- `web-server.sh` in `existing` mode writes a **snippet** instead of a vhost: `deploy/apache/caldart-attach.conf` rendered to `/etc/apache2/conf-available/caldart.conf`, or `deploy/nginx/caldart-attach.conf` rendered to `/etc/nginx/snippets/caldart.conf`. The snippet, for the prefix `P` (possibly empty): a redirect from `P` to `P/`; `P/media/documents/` denied; `P/media/` off disk with the same headers as the vhost; `ProxyPass P/ http://127.0.0.1:8001/` with `ProxyPreserveHost On`, `X-Forwarded-Proto https`, `X-Forwarded-Port 443`, `RequestHeader unset X-Forwarded-Ssl`, and `ProxyPass P/media/ !` ahead of it (nginx: `location P/ { proxy_pass http://caldart_app/; ... }` with the same headers, the `upstream` block in the snippet guarded so a second include does not redefine it: the upstream goes in a separate `conf.d/caldart-upstream.conf`). The proxy strips the prefix, and Django's `FORCE_SCRIPT_NAME` puts it back. Both snippets are shipped files with the `caldart.example.org` and `/srv/caldart`-style placeholders the renderer replaces, plus a `__PREFIX__` placeholder for the prefix.
- `--attach-to FILE` (recorded as `CALDART_ATTACH_TO`) names the existing vhost file. `web-server.sh` inserts one line, `Include conf-available/caldart.conf` (Apache) or `include snippets/caldart.conf;` (nginx), before the closing `</VirtualHost>` or `}` of every block in the file that holds `SSLEngine on` / `listen ... ssl`, or of every block when none does; it keeps a copy at `FILE.caldart.bak` from before the first insertion, is idempotent (a file already carrying the line is left alone), then `configtest`/`nginx -t` and `reload-or-restart`. Without `--attach-to` the step writes the snippet, prints the include line and where it goes, and `check.sh` still runs: it fails if the site does not answer, which tells the operator the include is missing.
- `check.sh` curls `https://HOST<PREFIX>/` and `<PREFIX>/portal/login`, then fetches the portal bundle the login page names (the `Makefile`'s e2e recipe shows how) and fails unless it answers `200`: that is the check that static assets resolve under the prefix. In `existing` mode the `--resolve` stays, since the existing server is on this machine.
- `packages.sh` installs the web server package (still needed for `a2enmod`, `apachectl`, `nginx -t`) but no certbot in `existing` mode. `uninstall.sh` removes the snippet and the include line (restoring nothing else), and leaves the existing vhost's other content alone.
- `deployment.rst` gains **Under a URL prefix, behind an existing site** with the one-liner for the owner's case (`--hostname paloaltodart.org --url-prefix /caldart-proto --tls existing --attach-to /etc/apache2/sites-available/paloaltodart.conf --email local --admin-email ...`), what the snippet contains, the include line, and what changes for the operator (the site URL, the admin at `<PREFIX>/admin/`, the guide at `<PREFIX>/docs/`).

### 5.7 The rehearsal's prefix variant

`make rehearse-deploy REHEARSE_URL_PREFIX=/caldart-proto` first stands up, inside the container, a stand-in for the existing site: the web server package, a self-signed certificate for `caldart.test`, and a minimal HTTPS vhost serving a one-line page at `/`, written by the recipe from `frontend/e2e/rehearsal/` (one file per server). Then it runs `bootstrap.sh` with `--tls existing --url-prefix /caldart-proto --attach-to <that vhost file> --email local` (the container has no postfix, so the configure note about port 25 is expected and the recipe asserts it appears), and the install's `check.sh` proves `https://caldart.test/caldart-proto/`, `/caldart-proto/portal/login`, and the bundle answer `200` while `https://caldart.test/` still answers the stand-in page. Upgrade, second install, and uninstall follow as in the plain variant, and after the uninstall the stand-in vhost must no longer carry the include line and must still pass `configtest`. Both web servers are rehearsed with and without the prefix: four runs.

### 5.8 What "don't need ssl" means here

`existing` mode obtains no certificate because the existing site's TLS is what the browser sees; the proxied hop to gunicorn is loopback. `caldart.settings.prod` keeps secure cookies and the HTTPS redirect, so a site served over plain HTTP is still not a deployment this project supports; `deployment.rst` says so in one sentence.

### 5.9 The end-to-end suite under a prefix

- `make e2e E2E_URL_PREFIX=/caldart-proto` sets `URL_PREFIX` in `E2E_ENV`, `SITE_URL` to `http://localhost:$(E2E_PORT)/caldart-proto`, and starts `frontend/e2e/prefix_proxy.py` on `E2E_PORT` in front of `runserver` on `E2E_PORT + 2`: a standard-library `http.server` that answers `/caldart-proto` with a redirect to `/caldart-proto/`, strips the prefix, forwards everything under it to the upstream with `X-Forwarded-*` headers, streams the response back, and answers `404` for any other path. `E2E_BASE_URL` for Playwright becomes `http://localhost:$(E2E_PORT)/caldart-proto`. The specs use Playwright's `baseURL`-relative navigation and read the portal's links from the page, so they pass unchanged; a spec that hard-codes a root path is fixed to use `baseURL`.
- CI gains an `e2e-prefix` job, the copy of `e2e` with `E2E_URL_PREFIX=/caldart-proto`; `testing.rst` documents the variable and the proxy. The proxy is Python under `frontend/e2e/`, so ruff and mypy cover it (the `Makefile`'s e2e comments say why it lives there).

## 6. Failure handling and the final report

As in the previous plan. The closeout's report to the owner names every PR, the one-liner for `paloaltodart.org`, what the four rehearsals saw, and the answer to the Postgres question.

## 7. Work packages

### Wave 1

#### install-root-port-mail (Opus, reviewed)

- **Refs:** #334
- **Branch:** `feature/install-root-port-mail`; database `caldart_rootport`
- **Owns:** `docker-compose.yml`, `deploy/lib.sh`, `deploy/bootstrap.sh`, `deploy/install.sh`, `deploy/compose.sh` (new), `deploy/uninstall.sh#compose`, `deploy/steps/postgres.sh`, `deploy/steps/configure.sh#db-port-and-mail`, `deploy/steps/check.sh#compose`, `deploy/gunicorn.conf.py#docstring`, `deploy/systemd/*` (the root), `deploy/apache/caldart.conf#root`, `deploy/nginx/caldart.conf#root`, `deploy/caldart.env.example#root-and-mail`, `Makefile#rehearsal-comments`, `README.rst#root`, `backend/tests/test_deploy_scripts.py` (root, port, mail cases), `backend/tests/test_settings_fail_closed.py#root`, `docs/developer/deployment.rst` (root, port, sharing section, `compose.sh`, `--email local`), `docs/developer/backup-restore.rst#root`, `docs/developer/configuration.rst#root`, `docs/developer/testing.rst#root`, `docs/developer/email.rst#postfix`, `docs/developer/setup.rst#compose-row` if `compose.sh` needs a row.
- **Steps:** §5.1, §5.2, §5.3.
- **Verify:** `make lint test check docs audit`; `grep -rn /srv/caldart deploy docs README.rst Makefile backend/tests` finds nothing but `test_deploy_scripts.py`'s rendering fixture; `deploy/install.sh --dry-run --hostname caldart.test --certbot-email a@b.test --email local --db-port 5433` prints the compose port as 5433, the mail note about port 25, and the same certbot lines as before; `make rehearse-deploy` passes on Apache.

#### url-prefix-backend (Opus, reviewed)

- **Refs:** #334
- **Branch:** `feature/url-prefix-backend`; database `caldart_prefixbe`
- **Owns:** `backend/caldart/settings/base.py#url-prefix`, `backend/caldart/settings/prod.py#site-url-check`, `backend/apps/cms/context_processors.py`, `backend/templates/base.html`, `backend/templates/portal.html`, `backend/templates/cms/*.html#links`, `backend/templates/404.html`, `backend/apps/cms/seed.py#links`, `backend/apps/cms/seed_content_data.py#links`, `backend/apps/cms/models.py#links`, `backend/tests/test_url_prefix.py` (new), `.env.example#url-prefix`, `deploy/caldart.env.example#url-prefix` (one commented line under core; the other package owns the rest of the file), `docs/developer/configuration.rst#url-prefix`, `docs/developer/cms.rst#links` if the seed's links are described there.
- **Steps:** §5.4.
- **Verify:** `make lint test check docs audit`; `URL_PREFIX=/caldart-proto make run` and `curl -s -H 'SCRIPT_NAME: /caldart-proto' ...` is not how WSGI works, so instead: `uv run backend/manage.py shell -c "from django.urls import reverse; print(reverse('portal'))"` with `URL_PREFIX=/caldart-proto` prints `/caldart-proto/portal/`.

#### url-prefix-frontend (Opus, reviewed)

- **Refs:** #334
- **Branch:** `feature/url-prefix-frontend`; database `caldart_prefixfe`
- **Owns:** `frontend/vite.config.ts#base`, `frontend/src/portal/urlPrefix.ts` (new, with test), `frontend/src/portal/api/client.ts#base`, `frontend/src/portal/App.tsx#basename`, every `frontend/src/portal/**` file with a root-relative URL literal that is not a router path (the worker lists them in the PR), `frontend/src/site/main.ts`, `frontend/src/test/{render,handlers,server}.ts#prefix`, `docs/developer/architecture.rst#url-prefix` (one paragraph on where the prefix is read), `docs/developer/theming.rst` or `local-development.rst` only if they name `base`.
- **Steps:** §5.5.
- **Verify:** `make lint test check docs audit`; `make e2e` (plain) green; with `data-url-prefix="/x"` stubbed in a vitest render, `API_BASE` is `/x/api/v1` and the router's basename `/x/portal`.

### Wave 2

#### url-prefix-e2e (Opus, reviewed)

- **Refs:** #334
- **Branch:** `feature/url-prefix-e2e`; database `caldart_prefixe2e`; e2e port 8281
- **Owns:** `Makefile#e2e-prefix`, `frontend/e2e/prefix_proxy.py` (new), `frontend/e2e/*.spec.ts#baseURL` (only where a spec hard-codes a root path), `frontend/playwright.config.ts#baseURL` if needed, `.github/workflows/ci.yml#e2e-prefix`, `docs/developer/testing.rst#e2e-prefix`, `docs/developer/setup.rst#e2e-row`, and, for fixes the prefixed run demands, the files of `url-prefix-backend` and `url-prefix-frontend`.
- **Steps:** §5.9; run `make e2e E2E_PORT=8281 E2E_DB=caldart_prefixe2e_e2e E2E_URL_PREFIX=/caldart-proto` and fix what fails, then the plain run too.
- **Verify:** both e2e runs green; `make lint test check docs audit`.

#### attach-install (Opus, reviewed)

- **Refs:** #334
- **Branch:** `feature/attach-install`; database `caldart_attach`
- **Owns:** `deploy/apache/caldart-attach.conf` (new), `deploy/nginx/caldart-attach.conf` (new), `deploy/nginx/caldart-upstream.conf` (new), `deploy/lib.sh#prefix-and-attach`, `deploy/install.sh#prefix-and-attach`, `deploy/steps/packages.sh#existing`, `deploy/steps/configure.sh#prefix`, `deploy/steps/web-server.sh` (the `existing` mode), `deploy/steps/check.sh#prefix-and-bundle`, `deploy/uninstall.sh#snippet`, `Makefile#rehearse-prefix`, `frontend/e2e/rehearsal/` (new: the stand-in vhosts), `backend/tests/test_deploy_scripts.py#existing-and-prefix`, `docs/developer/deployment.rst#prefix-and-attach`, `docs/developer/testing.rst#rehearsal-prefix`.
- **Steps:** §5.6, §5.7, §5.8. Run all four rehearsals.
- **Verify:** four rehearsals green; `make lint test check docs audit`; the dry run of the owner's one-liner prints the snippet install, the include insertion into the named file, and no `certbot`.

### Wave 3

#### closeout (Sonnet)

- **Refs:** #334 (`Closes #334.`)
- **Branch:** `chore/subpath-closeout`; database `caldart_subpath_closeout`
- **Owns:** whatever §9 below lists; header comments of the new snippets; a last read of `deployment.rst` for a sentence that still assumes the root of a host or `/srv/caldart`.
- **Verify:** `make lint test check docs audit`.

## 8. Manifest

```json
[
  {"wave": 1, "package": "install-root-port-mail", "model": "opus", "review": true, "branch": "feature/install-root-port-mail", "database": "caldart_rootport", "closes": [], "refs": [334], "after": []},
  {"wave": 1, "package": "url-prefix-backend", "model": "opus", "review": true, "branch": "feature/url-prefix-backend", "database": "caldart_prefixbe", "closes": [], "refs": [334], "after": []},
  {"wave": 1, "package": "url-prefix-frontend", "model": "opus", "review": true, "branch": "feature/url-prefix-frontend", "database": "caldart_prefixfe", "closes": [], "refs": [334], "after": []},
  {"wave": 2, "package": "url-prefix-e2e", "model": "opus", "review": true, "branch": "feature/url-prefix-e2e", "database": "caldart_prefixe2e", "e2e_port": 8281, "closes": [], "refs": [334], "after": ["url-prefix-backend", "url-prefix-frontend"]},
  {"wave": 2, "package": "attach-install", "model": "opus", "review": true, "branch": "feature/attach-install", "database": "caldart_attach", "closes": [], "refs": [334], "after": ["install-root-port-mail", "url-prefix-backend"]},
  {"wave": 3, "package": "closeout", "model": "sonnet", "review": false, "branch": "chore/subpath-closeout", "database": "caldart_subpath_closeout", "closes": [334], "refs": [], "after": ["url-prefix-e2e", "attach-install"]}
]
```
