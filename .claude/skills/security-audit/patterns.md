# Search patterns and scanners

Use these to find candidate locations quickly. A match is a lead, never a finding: read the
code around it, trace the data, and confirm the issue before reporting. Use the sections for
the stacks the inventory found; skip the rest.

## Scanners

Run each scanner that applies, in the background, writing to the scratchpad. Fetch tools
ad hoc (`uvx`, `npx -y`) or use one already installed; never add them to the project's
dependencies. No scanner may upload code or results: pass `--metrics=off` to semgrep and
never log in to a scanner's service. When a scanner is unavailable or fails, say so in the
report's Coverage section rather than silently dropping it.

| Concern | Command (from the repository root) |
| --- | --- |
| Python static analysis | `uvx bandit -r <source dirs> -f json -o <scratch>/bandit.json -q` |
| Multi-language rules | `uvx semgrep scan --metrics=off --config p/default --config p/owasp-top-ten --json -o <scratch>/semgrep.json` (add `p/django`, `p/flask`, `p/react`, `p/nodejs`, `p/secrets` as they apply) |
| Python dependencies | the project's own audit target if it has one, else `uvx pip-audit` (or `uv audit` with a `uv.lock`) |
| npm dependencies | `npm audit --json` in each directory with a `package-lock.json` (also with `--omit=dev` to separate runtime risk) |
| Other ecosystems | `osv-scanner -r .`, `govulncheck ./...`, `cargo audit`, `bundle audit` when installed |
| Secrets in the tree and history | `gitleaks git --report-path <scratch>/gitleaks.json` (`gitleaks detect` on versions before 8.19) when installed; otherwise `uvx detect-secrets scan --all-files` for the tree and the history greps below |
| GitHub Actions | `uvx zizmor .github/workflows` |
| Shell scripts | `shellcheck` over every `*.sh` when installed |
| Containers | `hadolint Dockerfile` when installed |
| Framework self-checks | e.g. Django `manage.py check --deploy` against the production settings module, with throwaway values for required secrets |

Secrets in history without a dedicated tool:

```bash
git log --all -p -G '(?i)(api[_-]?key|secret|passw(or)?d|token|private[_-]?key|BEGIN [A-Z ]*PRIVATE KEY)' --format='%H %an %ad %s' | head -400
git log --all --diff-filter=D --name-only --format='%H' | grep -Ei '\.(env|pem|key|p12|pfx|sqlite3?|db|dump)$'
```

## Every stack

```
# secrets and credentials
(?i)(secret|passw(or)?d|passwd|api[_-]?key|access[_-]?key|private[_-]?key|token|bearer|authorization)\s*[:=]
-----BEGIN [A-Z ]*PRIVATE KEY-----
AKIA[0-9A-Z]{16}|sk_live_[0-9a-zA-Z]{20,}|xox[baprs]-|ghp_[0-9A-Za-z]{36}|AIza[0-9A-Za-z_-]{35}
# disabled TLS or weak crypto
verify\s*=\s*False|rejectUnauthorized\s*:\s*false|InsecureSkipVerify|CERT_NONE
(?i)\b(md5|sha1)\b|DES|RC4|ECB
# insecure randomness for tokens
\brandom\.(random|randint|choice)|Math\.random
# markers people leave on shortcuts
(?i)(TODO|FIXME|HACK|XXX).*(auth|security|permission|csrf|password|token|bypass)
```

## Python (Django, DRF, Flask, FastAPI)

```
# authorization
permission_classes|authentication_classes|AllowAny|IsAuthenticatedOrReadOnly|@login_required|@permission_required|has_permission|has_object_permission|get_queryset|DEFAULT_PERMISSION_CLASSES
# CSRF and cookies
csrf_exempt|CSRF_COOKIE|SESSION_COOKIE|SameSite|CSRF_TRUSTED_ORIGINS|CORS_
# injection
\.raw\(|\.extra\(|cursor\.execute|RawSQL|format\(.*(SELECT|INSERT|UPDATE|DELETE)|%s.*%\s*\(|f"(SELECT|INSERT|UPDATE|DELETE)
subprocess|os\.system|os\.popen|shell=True|eval\(|exec\(|pickle\.|yaml\.load\(|marshal\.|__import__|importlib\.import_module
# XSS and templates
mark_safe|\|safe|autoescape off|format_html\(|Markup\(|render_template_string|Template\(
# redirects and SSRF
redirect\(|HttpResponseRedirect|url_has_allowed_host_and_scheme|requests\.(get|post)|httpx\.|urllib\.request|urlopen
# files
open\(|FileResponse|send_file|os\.path\.join|Path\(.*request|FileField|ImageField|upload_to|MEDIA_ROOT
# settings
DEBUG|ALLOWED_HOSTS|SECRET_KEY|SECURE_|X_FRAME_OPTIONS|PASSWORD_HASHERS|AUTH_PASSWORD_VALIDATORS|LOGGING
# serializers that expose too much
fields\s*=\s*['"]__all__['"]|exclude\s*=|depth\s*=
# logging of sensitive data
log(ger)?\.(debug|info|warning|error|exception)\(.*(request|password|token|email|user)
```

## JavaScript and TypeScript (React, Vue, Angular, Node, Express, Next)

```
# XSS sinks
dangerouslySetInnerHTML|innerHTML|outerHTML|insertAdjacentHTML|document\.write|v-html|\{@html|\[innerHTML\]|bypassSecurityTrust
# URL and navigation sinks
window\.location|location\.href\s*=|window\.open\(|href=\{|src=\{|javascript:
# storage of credentials
localStorage|sessionStorage|indexedDB|document\.cookie
# cross-window
postMessage|addEventListener\(['"]message
# code execution
eval\(|new Function\(|setTimeout\(['"`]|child_process|exec\(|execSync|spawn\(.*shell
# build-time values that become public
import\.meta\.env|process\.env|VITE_|NEXT_PUBLIC_|REACT_APP_
# server frameworks
app\.(get|post|put|patch|delete)\(|router\.|cors\(|helmet|express\.json\(\{.*limit|bodyParser|cookie-parser|jsonwebtoken|jwt\.(sign|verify|decode)
# prototype pollution and unsafe merge
__proto__|constructor\.prototype|merge\(|defaultsDeep|Object\.assign\(\{\},.*req\.
```

## Other backends (pointers)

- **Ruby on Rails:** `html_safe`, `raw(`, `find_by_sql`, `where("... #{`, `permit!`,
  `skip_before_action :verify_authenticity_token`, `protect_from_forgery`.
- **Go:** `template.HTML(`, `fmt.Sprintf` into SQL, `exec.Command`, `InsecureSkipVerify`,
  `http.ListenAndServe` without timeouts.
- **PHP:** `$_GET`/`$_POST` into `mysqli_query`, `eval`, `include $`, `unserialize`,
  `echo $_`.
- **Java/Kotlin:** `createQuery` with concatenation, `ObjectInputStream`, `Runtime.exec`,
  `@CrossOrigin("*")`, `permitAll()`.

## Configuration, deployment, and CI

```
# web servers
server_tokens|autoindex|client_max_body_size|proxy_set_header X-Forwarded|add_header|ssl_protocols|LimitRequestBody|Header set|Options Indexes
# systemd and containers
User=|NoNewPrivileges|ProtectSystem|PrivateTmp|CapabilityBoundingSet|^USER |privileged:|ports:
# install scripts
curl .*\| *(ba)?sh|wget .*\| *(ba)?sh|chmod 777|chmod -R|set -x
# GitHub Actions
pull_request_target|workflow_run|\$\{\{ *github\.event\.|permissions:|uses: [^@]+@(main|master|v?[0-9]+)$|secrets\.
```
