==========
Deployment
==========

Putting CalDART on a server: Postgres in Docker, installing the locked
dependencies, building the frontend assets, migrating and collecting static
files, running gunicorn under the ``caldart-web`` systemd unit on
``127.0.0.1:8001``, fronting it with the shipped Apache (or nginx) virtual
host and certbot TLS, and enabling the renewal-reminder timer.  The configs
themselves live in ``deploy/``; this page is owned by ``feat/ops``, per PLAN
§13.
